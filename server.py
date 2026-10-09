#!/usr/bin/env python3
import argparse
import json
import random
import socket
import threading
import time
from pathlib import Path

from common import (
    HOST,
    PORT,
    PLAYER_RADIUS,
    PLAYER_SPEED,
    RESPAWN_DELAY,
    WORLD_HEIGHT,
    WORLD_WIDTH,
    clamp,
    decode_message,
    dist,
    load_json,
    player_color,
    save_json,
    send_message,
)

LEADERBOARD_FILE = Path("leaderboard.json")


class Player:
    def __init__(self, client_id: str, name: str):
        self.client_id = client_id
        self.name = name[:18]
        self.x = WORLD_WIDTH * 0.5 + random.uniform(-80, 80)
        self.y = WORLD_HEIGHT * 0.5 + random.uniform(-60, 60)
        self.target_x = self.x
        self.target_y = self.y
        self.r = PLAYER_RADIUS
        self.score = 0.0
        self.alive = True
        self.spawn_time = time.monotonic()
        self.death_time = 0.0
        self.color = player_color(client_id)


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
        self.running = True
        self.lock = threading.RLock()
        self.players = {}
        self.connections = {}
        self.enemies = []
        self.leaderboard = self.load_leaderboard()
        self.spawn_timer = 0.5
        self.next_client_id = 1

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.bind((host, port))
        self.sock.listen(32)

    def load_leaderboard(self):
        data = load_json(str(LEADERBOARD_FILE), [])
        if not isinstance(data, list):
            return []
        return data

    def save_leaderboard(self):
        save_json(str(LEADERBOARD_FILE), self.leaderboard[:10])

    def start(self):
        accept_thread = threading.Thread(target=self.accept_loop, daemon=True)
        accept_thread.start()
        try:
            self.game_loop()
        except KeyboardInterrupt:
            self.shutdown()

    def accept_loop(self):
        while self.running:
            try:
                conn, addr = self.sock.accept()
            except OSError:
                break
            conn.settimeout(0.2)
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            client_id = f"p{self.next_client_id}"
            self.next_client_id += 1
            self.connections[client_id] = conn
            threading.Thread(target=self.handle_client, args=(client_id, conn), daemon=True).start()

    def handle_client(self, client_id: str, conn: socket.socket):
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
                name = str(payload.get("name", "Player")).strip()[:18] or "Player"
                with self.lock:
                    self.players[client_id] = Player(client_id, name)
                send_message(conn, {"type": "welcome", "payload": {"id": client_id}})
                print(f"player joined: {name} ({client_id})")

            elif msg_type == "input":
                with self.lock:
                    player = self.players.get(client_id)
                    if not player:
                        continue
                    player.target_x = clamp(float(payload.get("x", player.x)), 0, WORLD_WIDTH)
                    player.target_y = clamp(float(payload.get("y", player.y)), 0, WORLD_HEIGHT)

            elif msg_type == "ping":
                send_message(conn, {"type": "pong", "payload": {}})

        with self.lock:
            self.players.pop(client_id, None)
            self.connections.pop(client_id, None)
        try:
            conn.close()
        except OSError:
            pass

    def spawn_enemy(self):
        side = random.choice(["left", "right", "top", "bottom"])
        if side == "left":
            x, y = -50, random.uniform(40, WORLD_HEIGHT - 40)
        elif side == "right":
            x, y = WORLD_WIDTH + 50, random.uniform(40, WORLD_HEIGHT - 40)
        elif side == "top":
            x, y = random.uniform(30, WORLD_WIDTH - 30), -50
        else:
            x, y = random.uniform(30, WORLD_WIDTH - 30), WORLD_HEIGHT + 50

        radius = random.randint(14, 22)
        speed = random.uniform(180, 260)
        self.enemies.append(Enemy(x, y, radius, speed))

    def update_game(self, dt: float):
        with self.lock:
            if not self.players:
                self.enemies.clear()
                return

            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self.spawn_enemy()
                self.spawn_timer = max(0.5, 1.1 - len(self.enemies) * 0.025)

            for player in self.players.values():
                if not player.alive:
                    if time.monotonic() - player.death_time > RESPAWN_DELAY:
                        player.x = WORLD_WIDTH * 0.5 + random.uniform(-100, 100)
                        player.y = WORLD_HEIGHT * 0.5 + random.uniform(-100, 100)
                        player.target_x = player.x
                        player.target_y = player.y
                        player.alive = True
                        player.spawn_time = time.monotonic()
                    continue

                dx = player.target_x - player.x
                dy = player.target_y - player.y
                step = dist(player.x, player.y, player.target_x, player.target_y)
                if step > 0.1:
                    move = min(PLAYER_SPEED * dt, step)
                    player.x += (dx / step) * move
                    player.y += (dy / step) * move

                player.x = clamp(player.x, player.r, WORLD_WIDTH - player.r)
                player.y = clamp(player.y, player.r, WORLD_HEIGHT - player.r)
                player.score = max(0.0, time.monotonic() - player.spawn_time)

            # enemy AI: each enemy chases nearest alive player
            for enemy in list(self.enemies):
                target = None
                nearest_dist = 1e9
                for player in self.players.values():
                    if not player.alive:
                        continue
                    d = dist(player.x, player.y, enemy.x, enemy.y)
                    if d < nearest_dist:
                        nearest_dist = d
                        target = player

                if target is not None:
                    dx = target.x - enemy.x
                    dy = target.y - enemy.y
                    d = dist(enemy.x, enemy.y, target.x, target.y) or 1.0
                    enemy.x += (dx / d) * enemy.speed * dt
                    enemy.y += (dy / d) * enemy.speed * dt

                if enemy.x < -80 or enemy.x > WORLD_WIDTH + 80 or enemy.y < -80 or enemy.y > WORLD_HEIGHT + 80:
                    self.enemies.remove(enemy)
                    continue

                for player in self.players.values():
                    if not player.alive:
                        continue
                    if dist(player.x, player.y, enemy.x, enemy.y) < (player.r + enemy.r):
                        player.alive = False
                        player.death_time = time.monotonic()
                        player.score = max(0.0, time.monotonic() - player.spawn_time)
                        score_entry = {"name": player.name, "score": round(player.score, 2), "timestamp": int(time.time())}
                        self.leaderboard.append(score_entry)
                        self.leaderboard = sorted(self.leaderboard, key=lambda x: x.get("score", 0), reverse=True)[:10]
                        self.save_leaderboard()
                        break

    def broadcast_state(self):
        with self.lock:
            state = {
                "type": "state",
                "payload": {
                    "players": [
                        {
                            "id": pid,
                            "name": p.name,
                            "x": round(p.x, 2),
                            "y": round(p.y, 2),
                            "r": p.r,
                            "alive": p.alive,
                            "score": round(p.score, 2),
                            "color": p.color,
                        }
                        for pid, p in self.players.items()
                    ],
                    "enemies": [{"x": round(e.x, 2), "y": round(e.y, 2), "r": e.r} for e in self.enemies],
                    "leaderboard": self.leaderboard,
                },
            }
            for conn in list(self.connections.values()):
                send_message(conn, state)

    def game_loop(self):
        last = time.monotonic()
        while self.running:
            now = time.monotonic()
            dt = max(0.016, min(0.05, now - last))
            last = now
            self.update_game(dt)
            self.broadcast_state()
            time.sleep(1 / 60)

    def shutdown(self):
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass
        for conn in self.connections.values():
            try:
                conn.close()
            except OSError:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run! Run! Run! server")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    server = GameServer(args.host, args.port)
    print(f"server listening on {args.host}:{args.port}")
    server.start()
