"""
run.py — Entry point
Usage: python3 run.py
"""

import os
from model import load_chat_model, load_code_model
from orchestrator import run_conversation

NUM_ROUNDS = 5


def get_topic() -> str:
    print()
    print("═" * 60)
    print("  AI WEB APP FACTORY")
    print("  Brainstorm → Research → Plan → Build → Test")
    print("  Chat model: Mistral 7B  (ideas + critique)")
    print("  Code model: DeepSeek Coder 6.7B  (plan + build + test)")
    print("═" * 60)
    print()
    print("  How do you want to start?")
    print()
    print("  [1] I provide a topic  (agents build a web app around it)")
    print("  [2] Agents choose freely")
    print()

    while True:
        choice = input("  Enter 1 or 2: ").strip()
        if choice == "1":
            topic = input("\n  Enter your topic: ").strip()
            if topic:
                return topic
            print("  (topic cannot be empty, try again)")
        elif choice == "2":
            return ""
        else:
            print("  Please enter 1 or 2.")


def save_log(history, topic: str):
    os.makedirs("./logs", exist_ok=True)
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"./logs/session_{timestamp}.txt"

    role_labels = {
        "idea":      "IDEA AGENT",
        "critic":    "CRITIC AGENT",
        "summary":   "IDEA AGENT — BEST IDEA",
        "verdict":   "CRITIC AGENT — VERDICT (with research)",
        "final":     "PROJECT DESCRIPTION",
        "planner":   "PLANNER AGENT — TECHNICAL SPEC",
        "developer": "DEVELOPER AGENT",
        "tester":    "TESTER AGENT",
    }

    with open(filepath, "w") as f:
        f.write(f"TOPIC: {topic if topic else '(free choice)'}\n")
        f.write("=" * 60 + "\n\n")
        for msg in history:
            label = role_labels.get(msg["role"], msg["role"].upper())
            f.write(f"[{label}]\n{msg['content']}\n\n")

    print(f"  Session log: {filepath}")


def main():
    topic = get_topic()
    print()
    print("  Loading models (this takes ~30s)...")
    llm_chat = load_chat_model()
    llm_code = load_code_model()

    history = run_conversation(
        llm_chat=llm_chat,
        llm_code=llm_code,
        topic=topic,
        num_rounds=NUM_ROUNDS,
    )
    save_log(history, topic)


if __name__ == "__main__":
    main()
