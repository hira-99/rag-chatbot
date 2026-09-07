"""Server allowlist -- only ever launch a command that's explicitly listed
here (Step 24's item 11: never launch an arbitrary, user-supplied command).

sys.executable, not a bare "python3" -- the server needs the same
interpreter/environment as the app (packages installed there), not
whatever "python3" happens to resolve to on PATH.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

ALLOWED_SERVERS = {
    "bytemage_server": {
        "command": sys.executable,
        "args": [str(PROJECT_ROOT / "mcp_server" / "server.py")],
    },
}
