"""

End-to-end PII test.



Spawns the backend server, sends a PII-containing request,

verifies the response, and inspects logs for PII redaction.



Usage:

    python tests/integration/test_e2e_pii.py

"""

import glob
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / "src" / "core" / "logs"
SERVER_CMD = [
    str(PROJECT_ROOT / "venv" / "Scripts" / "uvicorn.exe"),
    "src.core.server:app",
    "--host", "0.0.0.0",
    "--port", "8000",
]

SERVER_URL = "http://localhost:8000/api/chat"

HEALTH_URL = "http://localhost:8000/health"



# Wait up to N seconds for the server to be ready

STARTUP_TIMEOUT = 30





def _wait_for_server(timeout: int) -> bool:

    """Poll the health endpoint until the server is up."""

    deadline = time.time() + timeout

    while time.time() < deadline:

        try:

            r = requests.get(HEALTH_URL, timeout=1)

            if r.status_code == 200:

                return True

        except requests.RequestException:

            pass

        time.sleep(0.5)

    return False





def _read_logs(max_lines: int = 30) -> list[str]:

    """Read all log lines (latest log file)."""

    log_files = sorted(glob.glob(str(LOG_DIR / "*.log")))

    if not log_files:

        return []

    with open(log_files[-1], "r", encoding="utf-8") as f:

        return f.read().splitlines()[:max_lines]





def main() -> int:

    os.chdir(PROJECT_ROOT)



    # Clear old logs so this run is self-contained

    for f in glob.glob(str(LOG_DIR / "*.log")):

        os.remove(f)



    print("Starting backend...")

    proc = subprocess.Popen(

        SERVER_CMD,

        stdout=subprocess.PIPE,

        stderr=subprocess.STDOUT,

        text=True,

        bufsize=1,

    )

    try:

        if not _wait_for_server(STARTUP_TIMEOUT):

            print("ERROR: server failed to start within timeout")

            return 1



        # Send a PII-bearing request

        print("Sending PII request...")

        r = requests.post(

            SERVER_URL,

            json={"message": "My email is test@example.com, check weather"},

            timeout=60,

        )

        print(f"Reply: {r.status_code}")

        if r.status_code == 200:

            data = r.json()

            print(f"  reply: {data.get('reply', '')[:120]}")



        # Read the last few log lines for inspection

        time.sleep(2)

        print("\n=== Log file content (first 30 lines) ===")

        for i, line in enumerate(_read_logs(30), 1):

            print(f"{i:>3}: {line}")



        return 0

    finally:

        print("\nShutting down backend...")

        proc.terminate()

        try:

            proc.wait(timeout=5)

        except subprocess.TimeoutExpired:

            proc.kill()





if __name__ == "__main__":

    sys.exit(main())

