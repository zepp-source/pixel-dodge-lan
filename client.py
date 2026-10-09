import argparse
import socket
import threading
import time
from collections import defaultdict

from common import DEFAULT_HOST, PORT, clamp, decode_message, load_leaderboard, player_color, push_leaderboard_entry, save_leaderboard, send_message


class Player:
    def __init__(self, conn_id: str, name: str, x: float, y: float):
        self.conn_id = conn_id
        self.name = name[:18]
        self.x = x
        self.y = y
        self.target_x = x
        self.target_y = y
        self.r = 14
        self.score = 0.0
        self.alive = True
        self.spawn_time = time.monotonic()
        self.death_time = 0.0


class Enemy:
    def __init__(self, x: float, y: float, radius: float, speed: float):
        self.x = x
        self.y = y
        self.r = radius
        self.speed = speed


class GameServer:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.lock = threading.Lock()
        self.players = {}
        self.enemies = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen(16)
        self.running = True
        self.next_id = 1
        self.spawn_timer = 0.0
        self.leaderboard = load_leaderboard()
        self.last_broadcast = 0.0
        self.connections = {}

    def start(self):
        accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        accept_thread.start()
        self._game_loop()

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self.sock.accept()
            except OSError:
                break
            conn.settimeout(0.15)
            client_id = f"client-{self.next_id}"
            self.next_id += 1
            self.connections[client_id] = conn
            threading.Thread(target=self._handle_client, args=(client_id, conn), daemon=True).start()

    def _handle_client(self, client_id: str, conn: socket.socket):
        while self.running:
            try:
                msg = decode_message(conn)
            except socket.timeout:
                continue
            if msg is None:
                break
            msg_type = msg.get("type")
            payload = msg.get("payload", {})
            if msg_type == "hello":
                name = str(payload.get("name", "Player"))[:18]
                with self.lock:
                    player = Player(client_id, name, 320 + len(self.players) * 30, 220)
                    self.players[client_id] = player
                send_message(conn, {"type": "welcome", "payload": {"client_id": client_id}})
            elif msg_type == "input":
                with self.lock:
                    player = self.players.get(client_id)
                    if player:
                        player.target_x = float(payload.get("x", player.x))
                        player.target_y = float(payload.get("y", player.y))
            elif msg_type == "ping":
                send_message(conn, {"type": "pong", "payload": {}})
        with self.lock:
            self.players.pop(client_id, None)
            self.connections.pop(client_id, None)
        try:
            conn.close()
        except OSError:
            pass

    def _spawn_enemy(self):
        side = __import__("random").choice(["left", "right", "top", "bottom"])
        width = 960
        height = 540
        if side == "left":
            x, y = -30, __import__("random").uniform(40, height - 40)
        elif side == "right":
            x, y = width + 30, __import__("random").uniform(40, height - 40)
        elif side == "top":
            x, y = __import__("random").uniform(30, width - 30), -30
        else:
            x, y = __import__("random").uniform(30, width - 30), height + 30
        radius = __import__("random").randint(14, 22)
        speed = __import__("random").uniform(180, 260)
        self.enemies.append(Enemy(x, y, radius, speed))

    def _update_game(self, dt: float):
        with self.lock:
            if not self.players:
                self.enemies.clear()
                return

            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self._spawn_enemy()
                self.spawn_timer = max(0.6, 1.2 - (len(self.enemies) * 0.02))

            for player in self.players.values():
                if not player.alive:
                    if time.monotonic() - player.death_time > 1.5:
                        player.x = 320 + __import__("random").uniform(0, 280)
                        player.y = 220 + __import__("random").uniform(0, 180)
                        player.target_x = player.x
                        player.target_y = player.y
                        player.alive = True
                        player.spawn_time = time.monotonic()
                    continue

                dx = player.target_x - player.x
                dy = player.target_y - player.y
                dist = (dx * dx + dy * dy) ** 0.5
                if dist > 0.1:
                    move = min(520.0 * dt, dist)
                    player.x += (dx / dist) * move
                    player.y += (dy / dist) * move

                player.x = clamp(player.x, 20, 940)
                player.y = clamp(player.y, 20, 520)
                player.score = max(0.0, time.monotonic() - player.spawn_time)

            for enemy in list(self.enemies):
                nearest = None
                dist_min = 999999.0
                for player in self.players.values():
                    if not player.alive:
                        continue
                    dx = player.x - enemy.x
                    dy = player.y - enemy.y
                    dist = (dx * dx + dy * dy) ** 0.5
                    if dist < dist_min:
                        nearest = player
                        dist_min = dist
                if nearest:
                    dx = nearest.x - enemy.x
                    dy = nearest.y - enemy.y
                    dist = (dx * dx + dy * dy) ** 0.5 or 1.0
                    enemy.x += (dx / dist) * enemy.speed * dt
                    enemy.y += (dy / dist) * enemy.speed * dt

                if enemy.x < -60 or enemy.x > 1040 or enemy.y < -60 or enemy.y > 620:
                    self.enemies.remove(enemy)
                    continue

                for player in self.players.values():
                    if not player.alive:
                        continue
                    if (player.x - enemy.x) ** 2 + (player.y - enemy.y) ** 2 < (player.r + enemy.r) ** 2:
                        player.alive = False
                        player.death_time = time.monotonic()
                        player.score = max(0.0, time.monotonic() - player.spawn_time)
                        self.leaderboard = load_leaderboard()
                        self.leaderboard.append({"name": player.name, "score": round(player.score, 2), "timestamp": int(time.time())})
                        self.leaderboard = sorted(self.leaderboard, key=lambda item: item.get("score", 0), reverse=True)[:10]
                        save_leaderboard(self.leaderboard)
                        break

    def _broadcast(self):
        with self.lock:
            world = {
                "type": "world",
                "payload": {
                    "players": [{
                        "id": pid,
                        "name": p.name,
                        "x": p.x,
                        "y": p.y,
                        "r": p.r,
                        "alive": p.alive,
                        "score": round(p.score, 2),
                        "color": player_color(pid),
                    } for pid, p in self.players.items()],
                    "enemies": [{
                        "x": e.x,
                        "y": e.y,
                        "r": e.r,
                    } for e in self.enemies],
                    "leaderboard": self.leaderboard,
                    "server_time": time.time(),
                },
            }
            for conn in list(self.connections.values()):
                send_message(conn, world)

    def _game_loop(self):
        last = time.monotonic()
        while self.running:
            now = time.monotonic()
            dt = max(0.016, min(0.05, now - last))
            last = now
            self._update_game(dt)
            self._broadcast()
            time.sleep(1 / 60)

    def shutdown(self):
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pixel Dodge LAN server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    server = GameServer(args.host, args.port)
    print(f"Server listening on {args.host}:{args.port}")
    try:
        server.start()
    except KeyboardInterrupt:
        print("Shutting down server...")
        server.shutdown()
