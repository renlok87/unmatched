"""GD-053: the client <-> server protocol number is one number in two places."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _number(path: Path, pattern: str) -> int:
    match = re.search(pattern, path.read_text(encoding="utf-8"))
    assert match, f"{path} has no protocol constant"
    return int(match.group(1))


def test_client_and_server_protocol_match():
    server = _number(ROOT / "backend/src/health/protocol.ts", r"SERVER_PROTOCOL\s*=\s*(\d+)")
    client = _number(ROOT / "unreal/Unmatched/Source/Unmatched/S08/S08Protocol.h", r"S08ClientProtocol\s*=\s*(\d+)")
    assert client == server
