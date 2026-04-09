# AI Ecosystem — Two-Agent Conversation System

## File Structure

```
ai-ecosystem/
├── model.py          ← loads the GGUF model once
├── agents.py         ← Idea Agent + Critic Agent logic
├── orchestrator.py   ← conversation loop controller
├── run.py            ← entry point (run this)
├── models/
│   └── your-model.gguf
└── logs/             ← auto-created, conversation logs saved here
```

## Setup

```bash
# Make sure your venv is active
source venv/bin/activate

# Install dependency (if not already installed)
pip install llama-cpp-python

# Place your model in the models/ folder
mkdir -p models
# (your mistral.gguf should already be here)
```

## Configuration

Edit `run.py` to change:

```python
INITIAL_TOPIC = "Build a productivity app for people with ADHD"
NUM_ROUNDS    = 5
MODEL_PATH    = "./models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
```

## Run

```bash
python run.py
```

## Expected Output

```
────────────────────────────────────────────────────────────
  TOPIC: Build a productivity app for people with ADHD
  ROUNDS: 5
────────────────────────────────────────────────────────────

  [ Round 1 / 5 ]

┌─ [IDEA AGENT] ────────────────────────────────────────────
│  We should build a time-boxing app designed specifically
│  for ADHD brains — short sprints, visual timers, no
│  overwhelming lists.
└───────────────────────────────────────────────────────────

┌─ [CRITIC AGENT] ──────────────────────────────────────────
│  Time-boxing apps already exist. What makes yours
│  different for ADHD users specifically — is it the
│  UX, the science, or something else?
└───────────────────────────────────────────────────────────
```

## How It Works

1. `run.py` calls `load_model()` — model loads **once**
2. `run_conversation()` starts the loop
3. Each round:
   - `idea_agent()` generates/refines an idea
   - Response added to shared `history`
   - `critic_agent()` reads full history, challenges the idea
   - Response added to shared `history`
4. Loop repeats for N rounds
5. Conversation saved to `./logs/`

## Tuning

- **Slower/more thoughtful responses**: lower `temperature` (e.g. `0.5`)
- **More creative responses**: raise `temperature` (e.g. `1.0`)
- **Longer responses**: raise `max_tokens` in `agents.py` (currently `256`)
- **More CPU threads**: raise `n_threads` in `model.py` to match your VM

## Next Steps (Future Agents)

Once this works, expand to:
- `planner_agent` — designs the app architecture
- `builder_agent` — writes the actual code
- `tester_agent` — critiques the code
- SQLite memory — agents remember past sessions
