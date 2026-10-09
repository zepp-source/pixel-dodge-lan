import json
import os
import socket
import struct
from typing import Any, Dict, Optional, Tuple

PORT = 9000
HEADER_SIZE = 4
DEFAULT_HOST = "127.0.0.1"
LEADERBOARD_FILE = "leaderboard.json"


def encode_message(msg: Dict[str, Any]) -> bytes:
    payload = json.dumps(msg, separators=(",", ":")).encode("utf-8")
    return struct.pack(">I", len(payload)) + payload


def decode_message(sock: socket.socket) -> Optional[Dict[str, Any]]:
    try:
        header = sock.recv(HEADER_SIZE)
        if not header:
            return None
        if len(header) != HEADER_SIZE:
            return None
        length = struct.unpack(">I", header)[0]
        chunks = []
        remaining = length
        while remaining > 0:
            chunk = sock.recv(remaining)
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        return json.loads(raw.decode("utf-8"))
    except (socket.timeout, ConnectionError, ValueError, json.JSONDecodeError):
        return None


def send_message(sock: socket.socket, msg: Dict[str, Any]) -> None:
    try:
        sock.sendall(encode_message(msg))
    except (BrokenPipeError, OSError):
        pass


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def host_ip_from_env() -> str:
    return os.environ.get("PIXEL_DODGE_HOST", DEFAULT_HOST)


def load_leaderboard(path: str = LEADERBOARD_FILE) -> list:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, list):
                return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return []


def save_leaderboard(entries: list, path: str = LEADERBOARD_FILE) -> None:
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(entries[:10], fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def push_leaderboard_entry(name: str, score: float, path: str = LEADERBOARD_FILE) -> None:
    records = load_leaderboard(path)
    records.append({"name": name[:18], "score": round(score, 2), "timestamp": int(__import__("time").time())})
    records = sorted(records, key=lambda item: item.get("score", 0), reverse=True)[:10]
    save_leaderboard(records, path)


def player_color(player_id: str) -> Tuple[int, int, int]:
    palette = [
        (120, 230, 170),
        (130, 185, 255),
        (255, 170, 110),
        (255, 120, 170),
        (185, 210, 255),
        (170, 255, 210),
    ]
    idx = abs(hash(player_id)) % len(palette)
    return palette[idx]
