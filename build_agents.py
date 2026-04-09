"""
build_agents.py — Developer Agent and Tester Agent

Developer Agent: reads the Planner's technical spec, writes a real Flask web app
                 with proper file structure, installs pip packages, creates all files.
Tester Agent:    starts the Flask server as a subprocess, hits it with real HTTP
                 requests, checks responses, reports PASS/FAIL.

Uses DeepSeek Coder 6.7B Instruct (### System / ### Instruction / ### Response format).
"""

import os
import re
import json
import time
import signal
import subprocess
import sys
import urllib.request
import urllib.error
from typing import Dict, List, Tuple

from llama_cpp import Llama


# ─── Prompt helpers ───────────────────────────────────────────────────────────

def _deepseek_prompt(system: str, user: str) -> str:
    return f"### System:\n{system}\n\n### Instruction:\n{user}\n\n### Response:\n"


def _call_llm(llm: Llama, system: str, user: str,
              temperature: float = 0.15, max_tokens: int = 2048) -> str:
    output = llm(
        _deepseek_prompt(system, user),
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=0.95,
        repeat_penalty=1.1,
        stop=["### Instruction:", "### System:", "<|EOT|>"],
        echo=False,
    )
    return output["choices"][0]["text"].strip()


def _strip_fences(raw: str) -> str:
    """Remove markdown code fences from model output."""
    raw = re.sub(r"```(?:python|html|css|javascript|js)?\s*", "", raw)
    raw = re.sub(r"```", "", raw)
    return raw.strip()


# ─── Package installer ────────────────────────────────────────────────────────

def install_packages(packages: List[str], project_dir: str) -> Tuple[bool, str]:
    """
    Install pip packages into the project virtualenv.
    Returns (success, output_log).
    """
    if not packages:
        return True, "No packages to install."

    log_lines = []
    for pkg in packages:
        print(f"  [INSTALL] pip install {pkg}")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            log_lines.append(f"✓ {pkg}")
        else:
            log_lines.append(f"✗ {pkg}: {result.stderr[:200]}")

    all_ok = all(l.startswith("✓") for l in log_lines)
    return all_ok, "\n".join(log_lines)


# ─── Developer Agent ──────────────────────────────────────────────────────────

DEVELOPER_SYSTEM = """You are an expert web developer. You write complete, working Flask web applications.

You will receive a technical plan (JSON) and you must write ALL the files specified in that plan.

Output format — you must output EACH file using this exact delimiter pattern:
=== FILE: path/to/filename.ext ===
<full file contents here>
=== END FILE ===

Rules you NEVER break:
- Output ALL files listed in the plan's file_structure
- Flask app must start on port 5000 with debug=False
- Use app.run(host='0.0.0.0', port=5000, debug=False) — NOT debug=True
- Include demo data so the app looks populated on first run
- Backend: Python/Flask only, use only the pip packages listed in the plan
- Frontend: plain HTML with inline or linked CSS/JS — no npm, no bundlers
- HTML templates go in templates/ folder, static files in static/
- SQLite database file goes in the project root if needed
- Every route must return something valid (no 500 errors)
- Handle missing data gracefully with try/except
- No hardcoded absolute paths — use os.path.join and relative paths
- Every HTML template MUST include ad slot placeholders:
    * <div class="ad-slot ad-leaderboard" data-ad-size="728x90"><!-- AD LEADERBOARD --></div> above the tool
    * <div class="ad-slot ad-rectangle" data-ad-size="300x250"><!-- AD RECTANGLE --></div> in sidebar or below output
  Style ad slots with a light grey background (#f0f0f0) and dashed border so they are visible during development
- Output ONLY the file blocks — no explanation before or after
- Do NOT wrap file contents in ``` backticks or markdown fences
- The content between === FILE === and === END FILE === must be raw code, not markdown"""

DEVELOPER_FIX_SYSTEM = """You are an expert web developer fixing a broken Flask application.

You will receive the original plan, all current files, and the error output.

Output format — output ALL files (fixed ones AND unchanged ones) using:
=== FILE: path/to/filename.ext ===
<full file contents>
=== END FILE ===

Rules:
- Fix every error shown
- Keep all working functionality
- Use app.run(host='0.0.0.0', port=5000, debug=False)
- Output ALL files, not just the changed ones
- No explanation before or after the file blocks
- Do NOT wrap file contents in ``` backticks or markdown fences
- Raw code only between the === FILE === delimiters"""


def _parse_file_blocks(raw: str) -> Dict[str, str]:
    """
    Parse the === FILE: path === ... === END FILE === blocks from model output.
    Returns dict of {relative_path: file_contents}.
    """
    files = {}
    pattern = re.compile(
        r'===\s*FILE:\s*(.+?)\s*===\s*\n(.*?)===\s*END FILE\s*===',
        re.DOTALL
    )
    for match in pattern.finditer(raw):
        path = match.group(1).strip()
        content = match.group(2)
        # Strip markdown fences the model wraps individual file contents in
        content = re.sub(r"^```[a-zA-Z]*\s*\n?", "", content.strip())
        content = re.sub(r"\n?```\s*$", "", content)
        files[path] = content.strip() + "\n"
    return files


def _write_project_files(files: Dict[str, str], project_dir: str):
    """Write all files to disk, creating subdirectories as needed."""
    for rel_path, content in files.items():
        full_path = os.path.join(project_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)


def developer_agent(
    llm: Llama,
    plan: dict,
    project_dir: str,
    previous_files: Dict[str, str] = None,
    error_output: str = "",
    tester_feedback: str = "",
) -> Dict[str, str]:
    """
    Write or fix all project files based on the plan.
    Returns dict of {relative_path: content}.
    """
    plan_str = json.dumps(plan, indent=2)

    if not previous_files:
        user = (
            f"Technical plan:\n{plan_str}\n\n"
            f"Write ALL files listed in file_structure. "
            f"Include demo data as described in the plan. "
            f"The app must work at http://localhost:5000 immediately after: python3 app.py\n\n"
        f"CRITICAL: Do NOT wrap file contents in backticks or markdown fences. Output raw code only inside the === FILE === delimiters."
        )
        system = DEVELOPER_SYSTEM
    else:
        existing = "\n\n".join(
            f"=== FILE: {p} ===\n{c}\n=== END FILE ==="
            for p, c in previous_files.items()
        )
        user = (
            f"Technical plan:\n{plan_str}\n\n"
            f"Current files:\n{existing}\n\n"
            f"Error output:\n{error_output}\n\n"
            f"Tester feedback:\n{tester_feedback}\n\n"
            f"Fix all errors. Output ALL files."
        )
        system = DEVELOPER_FIX_SYSTEM

    raw = _call_llm(llm, system, user, temperature=0.1, max_tokens=3000)
    files = _parse_file_blocks(raw)

    if not files:
        # Fallback: model didn't use delimiters — try to salvage a single app.py
        stripped = _strip_fences(raw)
        if "from flask" in stripped or "import flask" in stripped:
            # Extract just the Python portion if there's surrounding text
            match = re.search(r'((?:from flask|import flask).*)', stripped, re.DOTALL)
            if match:
                stripped = match.group(1).strip()
            files = {"app.py": stripped + "\n"}

    return files


# ─── Tester Agent — HTTP-based ────────────────────────────────────────────────

def _start_server(project_dir: str) -> subprocess.Popen:
    """Start Flask app as background subprocess."""
    app_path = os.path.join(project_dir, "app.py")
    proc = subprocess.Popen(
        [sys.executable, app_path],
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc


def _wait_for_server(url: str, timeout: int = 15) -> bool:
    """Poll until server responds or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def _http_get(url: str) -> Tuple[int, str]:
    """Simple HTTP GET. Returns (status_code, body)."""
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return 0, str(e)


def run_web_app(plan: dict, project_dir: str) -> Tuple[str, str, int, dict]:
    """
    Start the Flask app, hit all routes, collect results.
    Returns (stdout_log, stderr_log, exit_code, http_results).
    http_results = {url: (status, body_snippet)}
    """
    base_url = plan.get("test_url", "http://localhost:5000")
    routes = plan.get("routes", [{"method": "GET", "path": "/"}])

    proc = _start_server(project_dir)

    # Wait for server to come up
    started = _wait_for_server(base_url, timeout=15)

    http_results = {}
    if started:
        for route in routes:
            if route.get("method", "GET").upper() == "GET":
                url = base_url + route["path"]
                status, body = _http_get(url)
                http_results[url] = (status, body[:300])
    else:
        # Server never came up — collect stderr
        time.sleep(1)

    # Stop the server
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

    stdout = proc.stdout.read() if proc.stdout else ""
    stderr = proc.stderr.read() if proc.stderr else ""
    exit_code = 0 if started else 1

    return stdout, stderr, exit_code, http_results


TESTER_SYSTEM = """You are a QA engineer testing a Flask web application.

You receive:
- The technical plan (what the app should do)
- The HTTP results from hitting real routes
- Server stdout/stderr
- Exit code

PASS criteria: server started AND at least the homepage (/) returned HTTP 200
FAIL criteria: server didn't start, homepage returned non-200, or server crashed

Respond in EXACTLY this format:
RESULT: PASS or FAIL
REASON: one sentence
ISSUES: (only if FAIL) one issue per line
SUGGESTIONS: (only if FAIL) one concrete fix per line"""


def tester_agent(
    llm: Llama,
    plan: dict,
    stdout: str,
    stderr: str,
    exit_code: int,
    http_results: dict,
) -> Tuple[bool, str]:
    """
    Analyse HTTP test results. Returns (passed, report).
    """
    http_summary = "\n".join(
        f"  {url} → HTTP {status} | {body[:150]}"
        for url, (status, body) in http_results.items()
    ) or "  No HTTP requests succeeded (server never started)"

    user = (
        f"Technical plan:\n{json.dumps(plan, indent=2)}\n\n"
        f"HTTP results:\n{http_summary}\n\n"
        f"Server stdout:\n{stdout[:500] if stdout else '(empty)'}\n\n"
        f"Server stderr:\n{stderr[:500] if stderr else '(none)'}\n\n"
        f"Exit code: {exit_code}\n\n"
        f"Did the app start and serve pages correctly?"
    )

    report = _call_llm(llm, TESTER_SYSTEM, user, temperature=0.05, max_tokens=400)

    # Also do a hard check — if / returned 200 it's a pass regardless of LLM
    hard_pass = any(
        status == 200
        for url, (status, _) in http_results.items()
        if url.endswith(":5000") or url.endswith(":5000/")
    )

    passed = hard_pass or "RESULT: PASS" in report.upper()
    return passed, report
