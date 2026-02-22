"""Development runner with hot reload.

Watches all .py files in the project directory and automatically restarts
the bot when any change is detected.

Usage:
    python dev.py
"""
from watchfiles import run_process


def _run_bot():
    from main import main
    main()


if __name__ == "__main__":
    print("Dev mode: watching for .py changes, bot will restart automatically.")
    run_process(
        ".",
        target=_run_bot,
        watch_filter=lambda change, path: path.endswith(".py"),
    )
