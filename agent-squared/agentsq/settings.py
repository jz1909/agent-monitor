from pathlib import Path

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()

MONITOR_MODEL = "gpt-4o-mini"
AGENT_MODEL = "gpt-5.5"

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"

monitor_model = init_chat_model(MONITOR_MODEL)


def run_dir(run_id: str) -> Path:
    path = RUNS_DIR / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path
