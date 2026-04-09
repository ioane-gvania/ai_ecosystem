"""
model.py — Model loaders

Two separate model instances:
  - load_chat_model()  → Mistral 7B  — used by Idea Agent and Critic Agent
  - load_code_model()  → DeepSeek Coder 6.7B Instruct — used by Developer and Tester
"""

from llama_cpp import Llama

CHAT_MODEL_PATH = "/home/azureuser/ai_ecosystem/models/mistral-7b-instruct.Q4_K_M.gguf"
CODE_MODEL_PATH = "/home/azureuser/ai_ecosystem/models/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"


def load_chat_model(model_path: str = CHAT_MODEL_PATH) -> Llama:
    """
    Mistral 7B Instruct — for brainstorming agents.
    Loaded first, stays in memory the whole session.
    """
    print(f"[CHAT MODEL] Loading: {model_path}")
    llm = Llama(
        model_path=model_path,
        n_ctx=4096,
        n_threads=4,
        n_gpu_layers=0,
        verbose=False,
    )
    print("[CHAT MODEL] Ready.\n")
    return llm


def load_code_model(model_path: str = CODE_MODEL_PATH) -> Llama:
    """
    DeepSeek Coder 6.7B Instruct — for Developer and Tester agents.
    Loaded after brainstorm phase completes to avoid competing for RAM.
    """
    print(f"[CODE MODEL] Loading: {model_path}")
    llm = Llama(
        model_path=model_path,
        n_ctx=8192,      # code generation needs more context window
        n_threads=4,
        n_gpu_layers=0,
        verbose=False,
    )
    print("[CODE MODEL] Ready.\n")
    return llm
