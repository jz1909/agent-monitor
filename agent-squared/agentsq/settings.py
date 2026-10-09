from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"

# stream chunks of raw chain of thought per monitor block (one chunk ~ one token)
TOKENS_SPENT = 200


def run_dir(run_id: str) -> Path:
    path = RUNS_DIR / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path
