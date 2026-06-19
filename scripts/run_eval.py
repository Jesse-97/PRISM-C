"""CLI shortcut for eval mode without going through the UI.

Usage: python -m scripts.run_eval --profile baseline
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.services.eval_runner import run_eval  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    aggregate = run_eval(args.profile, args.limit)
    print(aggregate, flush=True)


if __name__ == "__main__":
    main()
