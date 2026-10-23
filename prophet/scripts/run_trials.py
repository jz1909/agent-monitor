import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

ALL_TRIALS = [
    "MiniMax-M2.5__claude-code__anuraghazra__githubreadmestats148",
    "claude-haiku-4-5-20251001__claude-code__anuraghazra__githubreadmestats1608",
    "claude-opus-4-6__claude-code__anuraghazra__githubreadmestats1608",
    "claude-sonnet-4-6__claude-code__astropy__astropy-12907",
    "deepseek-chat__claude-code__anuraghazra__githubreadmestats105",
    "deepseek-reasoner__terminus-2__astropy__astropy-12907",
    "gemini-3-flash-preview__terminus-2__anuraghazra__githubreadmestats117",
    "gemini-3.1-pro-preview__terminus-2__anuraghazra__githubreadmestats117",
    "glm-5__terminus-2__anuraghazra__githubreadmestats117",
    "gpt-5-mini__terminus-2__anuraghazra__githubreadmestats117",
    "gpt-5-nano__terminus-2__anuraghazra__githubreadmestats117",
    "gpt-5.4__terminus-2__anuraghazra__githubreadmestats117",
    "kimi-k2.5__claude-code__astropy__astropy-12907",
    "mimo-v2-pro__claude-code__astropy__astropy-12907",
    "qwen3-max__qwen-coder__astropy__astropy-12907",
]

TRIALS = [
    "MiniMax-M2.5__claude-code__anuraghazra__githubreadmestats148",
    "claude-haiku-4-5-20251001__claude-code__anuraghazra__githubreadmestats1608",
    "claude-opus-4-6__claude-code__anuraghazra__githubreadmestats1608",
    "claude-sonnet-4-6__claude-code__astropy__astropy-12907",
    "deepseek-chat__claude-code__anuraghazra__githubreadmestats105",
    "deepseek-reasoner__terminus-2__astropy__astropy-12907",
    "gemini-3-flash-preview__terminus-2__anuraghazra__githubreadmestats117",
    "gemini-3.1-pro-preview__terminus-2__anuraghazra__githubreadmestats117",
    "glm-5__terminus-2__anuraghazra__githubreadmestats117",
    "gpt-5-mini__terminus-2__anuraghazra__githubreadmestats117",
    "gpt-5-nano__terminus-2__anuraghazra__githubreadmestats117",
    "gpt-5.4__terminus-2__anuraghazra__githubreadmestats117",
    "kimi-k2.5__claude-code__astropy__astropy-12907",
    "mimo-v2-pro__claude-code__astropy__astropy-12907",
    "qwen3-max__qwen-coder__astropy__astropy-12907",
]



PARAMS = {
    "backend": "alcf",          # jev or alcf
    "model": "openai/gpt-oss-20b",             # required for alcf; jev defaults to jev-latest
    "cluster": None,
    "bag": "sliding",       # single, cumulative or sliding
    "k": 5,                 
    "batch_size": 15,
    "align": "event",
    "policy": "choice",        # choice or threshold
    "threshold": None,         
    "out_dir": None,
}


def to_args(params: dict) -> list[str]:
    args = []
    for key, value in params.items():
        if value is not None:
            args += [f"--{key.replace('_', '-')}", str(value)]
    return args


def main():
    failed = []
    for i, trial in enumerate(TRIALS, 1):
        print(f"=== [{i}/{len(TRIALS)}] {trial}", flush=True)
        cmd = [sys.executable, "-m", "prophet.run_experiment", "--trials", trial, *to_args(PARAMS)]
        if subprocess.run(cmd, cwd=REPO_ROOT).returncode != 0:
            failed.append(trial)

    print(f"\nDone: {len(TRIALS) - len(failed)}/{len(TRIALS)} trials succeeded")
    for trial in failed:
        print(f"  FAILED: {trial}")


if __name__ == "__main__":
    main()
