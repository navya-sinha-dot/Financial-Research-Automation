"""Start the FRA API and dashboard in local browser-demo mode."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the FRA API and Streamlit dashboard.")
    parser.add_argument("--headless", action="store_true", help="Hide Chromium during ticker scraping")
    args = parser.parse_args()

    environment = os.environ.copy()
    environment.update(
        {
            "CELERY_TASK_ALWAYS_EAGER": "true",
            "SCRAPER_HEADLESS": "true" if args.headless else "false",
            "SCRAPER_SLOW_MO": "0" if args.headless else "500",
        }
    )

    commands = [
        [sys.executable, "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"],
        [sys.executable, "-m", "streamlit", "run", "src/dashboard/app.py", "--server.port", "8501"],
    ]
    processes = []
    try:
        for command in commands:
            processes.append(subprocess.Popen(command, cwd=ROOT_DIR, env=environment))
        print("FRA API: http://localhost:8000/docs")
        print("FRA dashboard: http://localhost:8501")
        print("Enter a ticker in the dashboard to launch the SEC browser scrape.")
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        return next(process.returncode or 1 for process in processes if process.poll() is not None)
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            process.wait()


if __name__ == "__main__":
    raise SystemExit(main())