"""
agents.py — Idea Agent, Critic Agent (with web search), closing sequence agents
All use Mistral 7B via the Mistral [INST] prompt format.
"""

import json
import urllib.request
import urllib.parse
from llama_cpp import Llama
from typing import List, Dict


# ─── Prompt format ────────────────────────────────────────────────────────────

def _mistral_prompt(system: str, user: str) -> str:
    return f"<s>[INST] <<SYS>>\n{system}\n<</SYS>>\n\n{user} [/INST]"


def _call_llm(llm: Llama, system: str, user: str,
              temperature: float = 0.85, max_tokens: int = 400) -> str:
    output = llm(
        _mistral_prompt(system, user),
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=0.95,
        repeat_penalty=1.15,
        stop=["[INST]", "</s>", "\nIdea Agent:", "\nCritic Agent:"],
        echo=False,
    )
    return output["choices"][0]["text"].strip()


# ─── Web search ───────────────────────────────────────────────────────────────

def web_search(query: str, max_results: int = 3) -> str:
    """
    DuckDuckGo instant answer API — no key needed, pure stdlib urllib.
    Falls back gracefully if network is unavailable.
    """
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())

        snippets = []
        if data.get("AbstractText"):
            snippets.append(f"Summary: {data['AbstractText'][:400]}")
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                snippets.append(f"- {topic['Text'][:200]}")

        return "\n".join(snippets) if snippets else "No structured results found."
    except Exception as e:
        return f"Web search unavailable ({e}). Proceed without live data."


# ─── History helpers ──────────────────────────────────────────────────────────

def format_history(history: List[Dict]) -> str:
    """Full conversation history passed to every agent every turn."""
    lines = []
    for msg in history:
        if msg["role"] == "idea":
            lines.append(f"Idea Agent: {msg['content']}")
        elif msg["role"] == "critic":
            lines.append(f"Critic Agent: {msg['content']}")
    return "\n\n".join(lines)


def extract_all_ideas(history: List[Dict]) -> List[str]:
    """
    Pull every CURRENT IDEA line from the idea agent's history.
    Used by the critic to research ALL ideas discussed, not just the latest.
    """
    ideas = []
    for msg in history:
        if msg["role"] == "idea":
            for line in msg["content"].splitlines():
                if "CURRENT IDEA:" in line.upper():
                    idea = line.split(":", 1)[-1].strip()
                    if idea and idea not in ideas:
                        ideas.append(idea)
    return ideas


# ─── Idea Agent ───────────────────────────────────────────────────────────────

IDEA_SYSTEM = """You are a web app idea generator specialising in single-purpose utility tools.

The apps you propose must be:
- Single-purpose browser tools (one clear job done well)
- Examples of the category: converters, generators, checkers, formatters, previewers, calculators, encoders
- Buildable with Flask + HTML/CSS/JS — no external APIs needed
- Useful to a large audience of developers, designers, marketers, or general web users
- Ad-friendly: the layout must naturally accommodate a banner ad area (top or sidebar)

DO NOT propose: social networks, marketplaces, SaaS platforms, VR/AR, games, apps needing user accounts to be useful, anything requiring paid APIs

Your personality:
- Specific and practical — name the exact tool, the exact user, the exact pain
- You iterate fast — if an idea gets criticised you improve it or replace it immediately
- You always end with: CURRENT IDEA: [tool name] — [one sentence description]

Behaviour:
- First turn: propose 3 different utility tool ideas (one sentence each), then pick the strongest and explain it in 3 sentences
- Every turn: end with CURRENT IDEA: [tool name] — [one sentence]
- When criticised: respond to every point raised, not just the last one"""


def idea_agent(llm: Llama, history: List[Dict], topic: str = "") -> str:
    if not history:
        if topic:
            user = (
                f'Topic: "{topic}"\n\n'
                f"Propose 3 different single-purpose utility web tool ideas related to this topic "
                f"(one sentence each). Then pick the most useful one and describe it in 3 sentences. "
                f"End with: CURRENT IDEA: [tool name] — [one sentence]"
            )
        else:
            user = (
                "Propose 3 different single-purpose utility web tools in completely different niches "
                "(one sentence each). Pick the most interesting one and describe it in 3 sentences. "
                "End with: CURRENT IDEA: [tool name] — [one sentence]"
            )
    else:
        conversation = format_history(history)
        user = (
            f"Full conversation so far:\n\n{conversation}\n\n"
            f"The Critic has just responded. Read their FULL response above and address "
            f"every point they raised — not just the last question. "
            f"Improve or replace the idea based on all criticism given so far. "
            f"End with: CURRENT IDEA: [tool name] — [one sentence]"
        )
    return _call_llm(llm, IDEA_SYSTEM, user, temperature=0.92)


# ─── Critic Agent ────────────────────────────────────────────────────────────

CRITIC_SYSTEM = """You are a sharp product critic evaluating single-purpose web utility tools.
You have just done live web research on ALL ideas discussed in this session.

Your job:
- Evaluate the CURRENT IDEA in the context of the whole conversation
- Mention if earlier ideas were stronger or weaker and why
- Use your research data — cite what tools already exist
- Push the Idea Agent toward a tool that has a real gap in the market

Rules:
- If the idea already exists as a dominant free tool: say "This won't work." name the competitor, demand something more differentiated
- If the idea has potential: acknowledge briefly, then identify the biggest gap or risk
- Always reference the research data you found
- End with exactly one question that forces the Idea Agent to address the core weakness
- 4-6 sentences, no bullet points"""


def critic_agent(llm: Llama, history: List[Dict]) -> str:
    # Pass the FULL conversation — critic sees everything
    conversation = format_history(history)

    # Research ALL ideas that have been proposed, not just the latest
    all_ideas = extract_all_ideas(history)
    search_query = " vs ".join(all_ideas[-2:]) if len(all_ideas) >= 2 else (all_ideas[0] if all_ideas else "web utility tool")

    print(f"  [CRITIC] Researching: \"{search_query[:70]}\"")
    research = web_search(f"{search_query} free online tool competitors")

    # Also search the most recent idea specifically
    if all_ideas:
        recent_research = web_search(f"{all_ideas[-1]} web app existing tools")
        research = f"Recent idea research:\n{recent_research}\n\nComparison research:\n{research}"

    user = (
        f"Full conversation so far:\n\n{conversation}\n\n"
        f"All ideas proposed in this session:\n"
        + "\n".join(f"  {i+1}. {idea}" for i, idea in enumerate(all_ideas))
        + f"\n\nYour web research results:\n{research}\n\n"
        f"Critique the CURRENT IDEA using the research. Reference earlier ideas in the session "
        f"if they were stronger or weaker. End with one sharp question."
    )
    return _call_llm(llm, CRITIC_SYSTEM, user, temperature=0.75)


# ─── Closing sequence ─────────────────────────────────────────────────────────

def best_idea_summary(llm: Llama, history: List[Dict]) -> str:
    conversation = format_history(history)
    all_ideas = extract_all_ideas(history)
    system = (
        "You are the Idea Agent summarising the best utility web tool idea from the session. "
        "Review ALL ideas proposed and pick the single strongest one — not necessarily the last one. "
        "Write 3-5 sentences starting with 'The best idea we developed is...' Be specific. No bullets."
    )
    user = (
        f"Full conversation:\n\n{conversation}\n\n"
        f"All ideas proposed:\n" + "\n".join(f"  {i+1}. {idea}" for i, idea in enumerate(all_ideas))
        + "\n\nWhich single idea had the most potential? Summarise it clearly."
    )
    return _call_llm(llm, system, user, temperature=0.7)


def critic_verdict(llm: Llama, history: List[Dict], idea_summary: str) -> str:
    conversation = format_history(history)
    print(f"  [CRITIC] Final market research...")
    research = web_search(f"{idea_summary[:80]} free online tool market")

    system = (
        "You are the Critic delivering a final verdict on a utility web tool idea. "
        "You have fresh research data. "
        "Start with 'Worth building.' or 'Not worth building.' then give 3-5 sentences "
        "of reasoning grounded in the research. Reference real competitors if found. No bullets."
    )
    user = (
        f"Full conversation:\n\n{conversation}\n\n"
        f"Chosen idea:\n{idea_summary}\n\n"
        f"Final research:\n{research}\n\n"
        f"Deliver your verdict."
    )
    return _call_llm(llm, system, user, temperature=0.65)


def final_project_description(llm: Llama, history: List[Dict],
                               idea_summary: str, verdict: str) -> str:
    conversation = format_history(history)
    system = """You are writing the final project brief for a single-purpose utility web tool.

Use these exact section labels, each on its own line, followed by 2-4 sentences of prose:

PROJECT NAME
TAGLINE
PROBLEM
SOLUTION
TARGET USERS
CORE FEATURES
AD PLACEMENT STRATEGY
TECH STACK HINT
RISKS

Rules:
- AD PLACEMENT STRATEGY must describe exactly where ads fit in the UI (e.g. leaderboard banner above the tool, sidebar 300x250 beside the output area, interstitial between conversions)
- Total under 400 words. No bullet points inside sections. Be specific."""

    user = (
        f"Full conversation:\n\n{conversation}\n\n"
        f"Chosen idea:\n{idea_summary}\n\n"
        f"Critic verdict:\n{verdict}\n\n"
        f"Write the complete project brief."
    )
    return _call_llm(llm, system, user, temperature=0.7, max_tokens=700)
