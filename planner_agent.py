"""
planner_agent.py — Planner Agent

Sits between Phase 2 (brainstorm) and Phase 3 (build).
Reads the project description, produces a concrete technical plan:
  - Validates the idea is actually buildable as a web app
  - Chooses a minimal, sensible stack (Flask + vanilla JS or similar)
  - Defines exact file structure
  - Lists pip packages to install
  - Writes function signatures for backend routes
  - Describes what each page/component does

Output is a structured JSON-like plan the Developer Agent reads directly.
"""

import json
import re
from llama_cpp import Llama


PLANNER_SYSTEM = """You are a senior software architect specialising in small web applications.

You receive a project description and you output a concrete, buildable technical plan.

CONSTRAINTS — the plan must follow these rules:
- Backend: Python + Flask only
- Frontend: plain HTML + CSS + vanilla JavaScript (no React, no Vue, no bundlers)
- Database: SQLite via Python sqlite3 (if data persistence needed) or JSON files
- All pip packages must be installable with: pip install <package>
- The app must start with: python3 app.py
- The app must be fully working at http://localhost:5000
- No external APIs that require keys
- No packages that need compilation (no numpy, scipy, etc.)
- Allowed pip packages: flask, flask-cors, requests (for internal use only)
- The app is a single-purpose utility tool (converter, generator, checker, formatter, etc.)
- The HTML layout MUST include clearly marked ad placement zones:
    * A leaderboard banner slot (728x90) above the main tool area
    * A rectangle ad slot (300x250) in the sidebar or below the output
  These should be <div> placeholders with class="ad-slot" and data-ad-size attributes
  so Google AdSense or any ad network can be dropped in later

You must output ONLY valid JSON — no explanation, no markdown, no backticks.

The JSON must have exactly these fields:
{
  "project_slug": "short-lowercase-hyphenated-name",
  "description": "one sentence what the app does",
  "pip_packages": ["flask"],
  "file_structure": {
    "app.py": "description of what this file contains",
    "templates/index.html": "description",
    "templates/dashboard.html": "description (if needed)",
    "static/style.css": "description",
    "static/app.js": "description"
  },
  "routes": [
    {"method": "GET",  "path": "/",        "returns": "renders index.html"},
    {"method": "GET",  "path": "/api/data","returns": "JSON list of items"},
    {"method": "POST", "path": "/api/add", "returns": "JSON success/error"}
  ],
  "demo_data": "describe what hardcoded demo data to include so the app looks populated on first run",
  "start_command": "python3 app.py",
  "test_url": "http://localhost:5000",
  "ad_slots": ["leaderboard above tool (728x90)", "rectangle beside output (300x250)"],
  "feasibility": "BUILDABLE"
}

If the project is impossible to build as a simple web app, set feasibility to "IMPOSSIBLE" and add an "issue" field explaining why."""


def planner_agent(llm: Llama, project_description: str) -> dict:
    """
    Takes the project description, returns a validated plan dict.
    If the plan is IMPOSSIBLE, raises ValueError with the reason.
    """
    prompt = (
        f"### System:\n{PLANNER_SYSTEM}\n\n"
        f"### Instruction:\nProject description:\n{project_description}\n\n"
        f"Output the technical plan as valid JSON only.\n\n"
        f"### Response:\n"
    )

    output = llm(
        prompt,
        max_tokens=1024,
        temperature=0.1,       # very deterministic — we need valid JSON
        top_p=0.95,
        repeat_penalty=1.05,
        stop=["### Instruction:", "### System:", "<|EOT|>"],
        echo=False,
    )

    raw = output["choices"][0]["text"].strip()

    # Strip accidental markdown fences
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = re.sub(r"```", "", raw).strip()

    # Find the JSON object (model sometimes adds text before/after)
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise ValueError(f"Planner did not return valid JSON.\nRaw output:\n{raw[:300]}")

    plan = json.loads(match.group())

    if plan.get("feasibility") == "IMPOSSIBLE":
        raise ValueError(
            f"Planner rejected this project as unbuildable: {plan.get('issue', 'no reason given')}"
        )

    return plan


def format_plan_for_display(plan: dict) -> str:
    """Human-readable version of the plan for terminal output."""
    lines = [
        f"Project:     {plan.get('project_slug', '?')}",
        f"Description: {plan.get('description', '?')}",
        f"Packages:    {', '.join(plan.get('pip_packages', []))}",
        f"Start:       {plan.get('start_command', '?')}",
        f"Test at:     {plan.get('test_url', '?')}",
        "",
        "Files:",
    ]
    for fname, fdesc in plan.get("file_structure", {}).items():
        lines.append(f"  {fname:35s} — {fdesc}")
    lines.append("")
    lines.append("Routes:")
    for route in plan.get("routes", []):
        lines.append(f"  {route['method']:6s} {route['path']:25s} → {route['returns']}")
    return "\n".join(lines)
