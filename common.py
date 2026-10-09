import json
import socket
import struct
from typing import Any, Dict, Optional, Tuple

PORT = 9000
HOST = "127.0.0.1"
HEADER_SIZE = 4
WORLD_WIDTH = 960
WORLD_HEIGHT = 540
PLAYER_RADIUS = 15
ENEMY_MIN_RADIUS = 14
ENEMY_MAX_RADIUS = 22
PLAYER_SPEED = 520.0
RESPAWN_DELAY = 1.5
MAX_MESSAGE_SIZE = 1024 * 100

COLOR_BG = (9, 14, 22)
COLOR_PANEL = (18, 30, 44)
COLOR_SURFACE = (22, 36, 52)
COLOR_TEXT = (235, 240, 245)
COLOR_MUTED = (136, 154, 170)
COLOR_PRIMARY = (94, 215, 165)
COLOR_ACCENT = (255, 110, 96)
COLOR_DANGER = (255, 86, 86)
COLOR_SUCCESS = (112, 214, 123)


def send_message(sock: socket.socket, msg: Dict[str, Any]) -> bool:
    try:
        payload = json.dumps(msg, separators=(",", ":")).encode("utf-8")
        header = struct.pack(">I", len(payload))
        sock.sendall(header + payload)
        return True
    except (BrokenPipeError, OSError, TypeError):
        return False


def recv_exact(sock: socket.socket, n: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < n:
        chunk = sock.recv(n - len(chunks))
        if not chunk:
            return b""
        chunks.extend(chunk)
    return bytes(chunks)


def decode_message(sock: socket.socket) -> Optional[Dict[str, Any]]:
    try:
        header = recv_exact(sock, HEADER_SIZE)
        if not header:
            return None
        length = struct.unpack(">I", header)[0]
        if length <= 0 or length > MAX_MESSAGE_SIZE:
            return None
        payload = recv_exact(sock, length)
        if not payload:
            return None
        return json.loads(payload.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, OSError, TypeError):
        return None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def dist(x1: float, y1: float, x2: float, y2: float) -> float:
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


def player_color(player_id: str) -> Tuple[int, int, int]:
    palette = [
        (110, 220, 180),
        (155, 170, 255),
        (255, 170, 110),
        (255, 120, 140),
        (150, 200, 255),
        (185, 255, 150),
        (255, 200, 110),
    ]
    idx = abs(hash(player_id)) % len(palette)
    return palette[idx]


def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def save_json(path: str, data) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
