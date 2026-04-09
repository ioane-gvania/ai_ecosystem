"""
orchestrator.py — Full pipeline

Phase 1: Brainstorm     — Idea Agent <-> Critic Agent (N rounds, critic does web research)
Phase 2: Closing        — best idea, verdict with research, project description
Phase 3: Plan           — Planner Agent validates and creates technical spec
Phase 4: Build & Test   — Developer writes full web app, Tester hits it with HTTP
"""

import os
import re
from datetime import datetime
from llama_cpp import Llama
from typing import List, Dict, Tuple

from agents import (
    idea_agent, critic_agent,
    best_idea_summary, critic_verdict, final_project_description,
)
from planner_agent import planner_agent, format_plan_for_display
from build_agents import (
    install_packages, developer_agent,
    run_web_app, tester_agent, _write_project_files,
)

SEP  = "─" * 60
SEP2 = "═" * 60
MAX_FIX_ATTEMPTS = 3

ROLE_HEADERS = {
    "idea":      "─ [IDEA AGENT] "                  + "─" * 44,
    "critic":    "─ [CRITIC AGENT] "                + "─" * 42,
    "summary":   "─ [IDEA AGENT — BEST IDEA] "      + "─" * 32,
    "verdict":   "─ [CRITIC AGENT — VERDICT] "      + "─" * 32,
    "final":     "─ [IDEA AGENT — PROJECT DESC] "   + "─" * 29,
    "planner":   "─ [PLANNER AGENT] "               + "─" * 41,
    "developer": "─ [DEVELOPER AGENT] "             + "─" * 39,
    "tester":    "─ [TESTER AGENT] "                + "─" * 42,
}


# ─── Display helpers ──────────────────────────────────────────────────────────

def _print_box(role: str, content: str):
    header = ROLE_HEADERS.get(role, "─" * 59)
    words = content.split()
    lines, line = [], []
    for word in words:
        if sum(len(w) for w in line) + len(line) + len(word) > 56:
            lines.append(" ".join(line))
            line = []
        line.append(word)
    if line:
        lines.append(" ".join(line))
    print("┌" + header)
    for ln in lines:
        print(f"│  {ln}")
    print("└" + "─" * 59)
    print()


def _print_files(files: Dict[str, str]):
    for path, content in files.items():
        print(f"┌─ [FILE: {path}] " + "─" * max(0, 42 - len(path)))
        for i, line in enumerate(content.splitlines()[:30], 1):
            print(f"│ {i:3}  {line}")
        if content.count("\n") > 30:
            print(f"│  ... ({content.count(chr(10))} lines total)")
        print("└" + "─" * 59)
    print()


def _print_http_results(http_results: dict):
    print("┌─ [TESTER — HTTP RESULTS] " + "─" * 33)
    if not http_results:
        print("│  No HTTP responses (server didn't start)")
    for url, (status, body) in http_results.items():
        icon = "✓" if status == 200 else "✗"
        print(f"│  {icon} {url}  →  HTTP {status}")
        if body:
            preview = body[:120].replace("\n", " ")
            print(f"│    {preview}")
    print("└" + "─" * 59)
    print()


def _print_phase(title: str):
    print()
    print(SEP2)
    print(f"  {title}")
    print(SEP2)
    print()


def _make_project_dir(project_slug: str) -> str:
    """Create a named, dated project folder."""
    base = os.path.dirname(os.path.abspath(__file__))
    date = datetime.now().strftime("%Y%m%d_%H%M%S")
    # sanitise slug
    slug = re.sub(r'[^a-z0-9\-]', '-', project_slug.lower())[:40]
    folder = f"{slug}_{date}"
    path = os.path.join(base, "projects", folder)
    os.makedirs(path, exist_ok=True)
    return path


# ─── Phase 1 + 2: Brainstorm ─────────────────────────────────────────────────

def run_brainstorm(llm_chat: Llama, topic: str,
                   num_rounds: int, history: List[Dict]) -> str:
    _print_phase("PHASE 1 — BRAINSTORM")

    for round_num in range(1, num_rounds + 1):
        print(f"  [ Round {round_num} / {num_rounds} ]")
        print()
        idea = idea_agent(llm=llm_chat, history=history, topic=topic)
        history.append({"role": "idea", "content": idea})
        _print_box("idea", idea)

        critic = critic_agent(llm=llm_chat, history=history)
        history.append({"role": "critic", "content": critic})
        _print_box("critic", critic)

    _print_phase("PHASE 2 — CLOSING SEQUENCE")

    print("  Step 1 — Idea Agent picks the best idea")
    print()
    summary = best_idea_summary(llm=llm_chat, history=history)
    history.append({"role": "summary", "content": summary})
    _print_box("summary", summary)

    print("  Step 2 — Critic delivers verdict (with research)")
    print()
    verdict = critic_verdict(llm=llm_chat, history=history, idea_summary=summary)
    history.append({"role": "verdict", "content": verdict})
    _print_box("verdict", verdict)

    print("  Step 3 — Idea Agent writes project description")
    print()
    description = final_project_description(
        llm=llm_chat, history=history,
        idea_summary=summary, verdict=verdict,
    )
    history.append({"role": "final", "content": description})
    _print_box("final", description)

    return description


# ─── Phase 3: Plan ───────────────────────────────────────────────────────────

def run_planning(llm_code: Llama, project_description: str,
                 history: List[Dict]) -> dict:
    _print_phase("PHASE 3 — PLANNING")
    print("  [ Planner Agent creating technical spec... ]")
    print()

    plan = planner_agent(llm=llm_code, project_description=project_description)

    display = format_plan_for_display(plan)
    history.append({"role": "planner", "content": display})
    _print_box("planner", display)

    return plan


# ─── Phase 4: Build & Test ───────────────────────────────────────────────────

def run_build(llm_code: Llama, plan: dict,
              project_dir: str, history: List[Dict]) -> Tuple:
    _print_phase("PHASE 4 — BUILD & TEST")

    # Install packages first
    packages = plan.get("pip_packages", [])
    if packages:
        print(f"  [ Installing: {', '.join(packages)} ]")
        print()
        ok, install_log = install_packages(packages, project_dir)
        print(f"  {install_log}")
        print()

    files = {}
    passed = False
    error_output = ""
    feedback = ""

    for attempt in range(1, MAX_FIX_ATTEMPTS + 2):
        label = "Writing initial app..." if attempt == 1 else f"Fix attempt {attempt-1}/{MAX_FIX_ATTEMPTS}"
        print(f"  [ Developer Agent: {label} ]")
        print()

        files = developer_agent(
            llm=llm_code,
            plan=plan,
            project_dir=project_dir,
            previous_files=files if attempt > 1 else None,
            error_output=error_output,
            tester_feedback=feedback,
        )

        if not files:
            print("  ✗ Developer produced no files. Retrying...")
            error_output = "No files were generated. Please output all files using the === FILE: === delimiters."
            continue

        _write_project_files(files, project_dir)
        _print_files(files)

        print("  [ Tester Agent: starting server and running HTTP tests... ]")
        print()

        stdout, stderr, exit_code, http_results = run_web_app(plan, project_dir)
        _print_http_results(http_results)

        passed, report = tester_agent(
            llm=llm_code,
            plan=plan,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            http_results=http_results,
        )

        history.append({"role": "developer", "content": f"[Attempt {attempt}]\n" +
                        "\n".join(f"--- {p} ---\n{c}" for p, c in files.items())})
        history.append({"role": "tester", "content": report})
        _print_box("tester", report)

        if passed:
            print(SEP)
            print("  ✓ TESTER PASSED — web app is running correctly")
            print(SEP)
            print()
            break

        error_output = stderr or stdout or "Server did not start."
        feedback = report

        if attempt == MAX_FIX_ATTEMPTS + 1:
            print(SEP)
            print(f"  ✗ Could not fix after {MAX_FIX_ATTEMPTS} attempts.")
            print(SEP)
            print()

    return files, passed


# ─── Main entry point ─────────────────────────────────────────────────────────

def run_conversation(
    llm_chat: Llama,
    llm_code: Llama,
    topic: str = "",
    num_rounds: int = 5,
) -> List[Dict]:
    history: List[Dict] = []

    print()
    print(SEP2)
    print("  AI WEB APP FACTORY")
    print(f"  Topic:  {topic if topic else '(agents choose)'}")
    print(f"  Rounds: {num_rounds}")
    print(SEP2)

    # Phase 1 + 2
    project_description = run_brainstorm(llm_chat, topic, num_rounds, history)

    # Phase 3: Plan
    try:
        plan = run_planning(llm_code, project_description, history)
    except ValueError as e:
        print(f"\n  ✗ Planner rejected this project: {e}")
        print("  Restart and choose a different idea.")
        return history

    # Create named project directory
    project_dir = _make_project_dir(plan.get("project_slug", "project"))
    print(f"  Project directory: {project_dir}")
    print()

    # Save description
    with open(os.path.join(project_dir, "description.txt"), "w") as f:
        f.write(project_description)
    with open(os.path.join(project_dir, "plan.json"), "w") as f:
        import json
        json.dump(plan, f, indent=2)

    # Phase 4: Build + Test
    files, passed = run_build(llm_code, plan, project_dir, history)

    print(SEP2)
    print("  SESSION COMPLETE")
    print(f"  Project: {project_dir}")
    print(f"  Start:   cd {project_dir} && python3 app.py")
    print(f"  Open:    http://localhost:5000")
    print(f"  Status:  {'✓ PASSING' if passed else '✗ NEEDS REVIEW'}")
    print(SEP2)

    return history
