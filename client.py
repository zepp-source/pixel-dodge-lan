#!/usr/bin/env python3
import argparse
import json
import socket
import threading
import time

import pygame

from common import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_MUTED,
    COLOR_PANEL,
    COLOR_PRIMARY,
    COLOR_TEXT,
    HOST,
    PORT,
    WORLD_HEIGHT,
    WORLD_WIDTH,
    clamp,
    decode_message,
    load_json,
    player_color,
    save_json,
    send_message,
)

SETTINGS_FILE = "settings.json"


def load_settings():
    data = load_json(SETTINGS_FILE, {})
    if not isinstance(data, dict):
        data = {}
    return {
        "sound": bool(data.get("sound", True)),
        "fullscreen": bool(data.get("fullscreen", False)),
        "name": str(data.get("name", "Player"))[:18],
        "host": str(data.get("host", HOST)),
    }


def save_settings(settings):
    save_json(SETTINGS_FILE, settings)


class Client:
    def __init__(self, host: str, name: str, fullscreen: bool = False, sound: bool = True):
        self.host = host
        self.name = name
        self.fullscreen = fullscreen
        self.sound = sound
        self.running = True
        self.connected = False
        self.sock = None
        self.player_id = None
        self.state = {"players": [], "enemies": [], "leaderboard": []}
        self.mode = "menu"
        self.last_input_sent = 0.0

        self.clock = pygame.time.Clock()
        self.font_title = pygame.font.SysFont("Arial", 28, bold=True)
        self.font_big = pygame.font.SysFont("Arial", 22)
        self.font_med = pygame.font.SysFont("Arial", 18)
        self.font_small = pygame.font.SysFont("Arial", 14)

        # UI elements
        self.name_input = pygame.Rect(180, 180, 360, 46)
        self.host_input = pygame.Rect(180, 240, 360, 46)
        self.start_btn = pygame.Rect(180, 330, 170, 52)
        self.settings_btn = pygame.Rect(370, 330, 170, 52)
        self.play_again_btn = pygame.Rect(180, 360, 170, 52)
        self.back_btn = pygame.Rect(370, 360, 170, 52)
        self.leaderboard_btn = pygame.Rect(180, 430, 170, 52)

        self.focus_name = False
        self.focus_host = False
        self.settings = load_settings()
        self.settings["name"] = self.name
        self.settings["host"] = self.host

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.settimeout(0.2)
            self.sock.connect((self.host, PORT))
            self.connected = True
            send_message(self.sock, {"type": "hello", "payload": {"name": self.name}})
            threading.Thread(target=self.receive_loop, daemon=True).start()
            self.mode = "playing"
            return True
        except (OSError, ConnectionError):
            self.mode = "menu"
            return False

    def receive_loop(self):
        while self.connected and self.running:
            try:
                msg = decode_message(self.sock)
            except socket.timeout:
                continue
            if msg is None:
                break
            if msg.get("type") == "welcome":
                self.player_id = msg["payload"].get("id")
            elif msg.get("type") == "state":
                self.state = msg.get("payload", {})
            elif msg.get("type") == "pong":
                pass
        self.connected = False

    def send_input(self):
        if not self.connected or self.sock is None:
            return
        x, y = pygame.mouse.get_pos()
        x = clamp(x, 0, WORLD_WIDTH)
        y = clamp(y, 0, WORLD_HEIGHT)
        send_message(self.sock, {"type": "input", "payload": {"x": x, "y": y}})

    def render_background(self, screen):
        screen.fill(COLOR_BG)
        for i in range(0, WORLD_WIDTH, 120):
            pygame.draw.line(screen, (25, 36, 52), (i, 0), (i, WORLD_HEIGHT), 1)
        for i in range(0, WORLD_HEIGHT, 120):
            pygame.draw.line(screen, (25, 36, 52), (0, i), (WORLD_WIDTH, i), 1)

    def render_game(self, screen):
        self.render_background(screen)

        # enemies
        for enemy in self.state.get("enemies", []):
            x = int(enemy["x"])
            y = int(enemy["y"])
            r = int(enemy["r"])
            pygame.draw.circle(screen, COLOR_ACCENT, (x, y), r)
            pygame.draw.circle(screen, (255, 160, 130), (x, y), r, 2)

        # players
        for player in self.state.get("players", []):
            x = int(player["x"])
            y = int(player["y"])
            r = int(player["r"])
            color = tuple(player.get("color", (110, 220, 180)))
            alive = player.get("alive", True)
            if alive:
                pygame.draw.circle(screen, color, (x, y), r)
                pygame.draw.circle(screen, (255, 255, 255), (x, y), r, 2)
            else:
                s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (*color, 120), (r, r), r)
                screen.blit(s, (x - r, y - r))

        # HUD
        my_name = self.name
        my_score = 0.0
        players_count = len(self.state.get("players", []))
        for p in self.state.get("players", []):
            if p.get("id") == self.player_id:
                my_score = p.get("score", 0.0)
                my_name = p.get("name", self.name)
                break

        title = self.font_big.render(my_name, True, COLOR_PRIMARY)
        screen.blit(title, (20, 18))

        score = self.font_med.render(f"Time: {my_score:.1f}s", True, COLOR_TEXT)
        screen.blit(score, (20, 52))

        count = self.font_med.render(f"Players: {players_count}", True, COLOR_MUTED)
        screen.blit(count, (20, 82))

    def render_menu(self, screen):
        screen.fill(COLOR_BG)
        title = self.font_title.render("Run! Run! Run!", True, COLOR_PRIMARY)
        screen.blit(title, (180, 80))

        subtitle = self.font_med.render("Survive. Dodge. Compete.", True, COLOR_MUTED)
        screen.blit(subtitle, (180, 122))

        pygame.draw.rect(screen, COLOR_PANEL, self.name_input, border_radius=8)
        pygame.draw.rect(screen, COLOR_PANEL, self.host_input, border_radius=8)
        pygame.draw.rect(screen, screen.get_at((0, 0))[:3], self.start_btn, border_radius=8)
        pygame.draw.rect(screen, COLOR_PANEL, self.settings_btn, border_radius=8)

        # border / buttons
        pygame.draw.rect(screen, COLOR_PRIMARY if self.focus_name else COLOR_MUTED, self.name_input, 2, border_radius=8)
        pygame.draw.rect(screen, COLOR_PRIMARY if self.focus_host else COLOR_MUTED, self.host_input, 2, border_radius=8)
        pygame.draw.rect(screen, COLOR_PRIMARY, self.start_btn, 2, border_radius=8)
        pygame.draw.rect(screen, COLOR_MUTED, self.settings_btn, 2, border_radius=8)

        name_text = self.font_med.render(self.name, True, COLOR_TEXT)
        host_text = self.font_med.render(self.host, True, COLOR_TEXT)
        screen.blit(name_text, (self.name_input.x + 12, self.name_input.y + 12))
        screen.blit(host_text, (self.host_input.x + 12, self.host_input.y + 12))

        start_label = self.font_med.render("Join", True, COLOR_TEXT)
        settings_label = self.font_med.render("Settings", True, COLOR_TEXT)
        screen.blit(start_label, (self.start_btn.centerx - 18, self.start_btn.centery - 10))
        screen.blit(settings_label, (self.settings_btn.centerx - 38, self.settings_btn.centery - 10))

    def render_settings(self, screen):
        screen.fill(COLOR_BG)
        title = self.font_title.render("Settings", True, COLOR_PRIMARY)
        screen.blit(title, (180, 80))

        # toggles
        sound_box = pygame.Rect(180, 180, 220, 48)
        fullscreen_box = pygame.Rect(180, 250, 220, 48)
        back_box = pygame.Rect(180, 420, 160, 50)

        pygame.draw.rect(screen, COLOR_PANEL, sound_box, border_radius=8)
        pygame.draw.rect(screen, COLOR_PANEL, fullscreen_box, border_radius=8)
        pygame.draw.rect(screen, COLOR_PANEL, back_box, border_radius=8)

        sound_label = self.font_med.render(f"Sound: {'ON' if self.sound else 'OFF'}", True, COLOR_TEXT)
        fullscreen_label = self.font_med.render(f"Fullscreen: {'ON' if self.fullscreen else 'OFF'}", True, COLOR_TEXT)
        back_label = self.font_med.render("Back", True, COLOR_TEXT)
        screen.blit(sound_label, (sound_box.x + 16, sound_box.y + 14))
        screen.blit(fullscreen_label, (fullscreen_box.x + 16, fullscreen_box.y + 14))
        screen.blit(back_label, (back_box.x + 58, back_box.y + 15))

    def render_gameover(self, screen):
        screen.fill(COLOR_BG)
        title = self.font_title.render("Game Over", True, COLOR_ACCENT)
        screen.blit(title, (180, 120))

        score = self.font_big.render(f"Final: {self.get_player_score():.1f}s", True, COLOR_TEXT)
        screen.blit(score, (180, 180))

        pygame.draw.rect(screen, COLOR_PANEL, self.play_again_btn, border_radius=8)
        pygame.draw.rect(screen, COLOR_PANEL, self.leaderboard_btn, border_radius=8)
        pygame.draw.rect(screen, COLOR_PANEL, self.back_btn, border_radius=8)

        play_text = self.font_med.render("Play Again", True, COLOR_TEXT)
        leader_text = self.font_med.render("Leaderboard", True, COLOR_TEXT)
        back_text = self.font_med.render("Menu", True, COLOR_TEXT)

        screen.blit(play_text, (self.play_again_btn.x + 30, self.play_again_btn.y + 15))
        screen.blit(leader_text, (self.leaderboard_btn.x + 18, self.leaderboard_btn.y + 15))
        screen.blit(back_text, (self.back_btn.x + 58, self.back_btn.y + 15))

    def render_leaderboard(self, screen):
        screen.fill(COLOR_BG)
        title = self.font_title.render("Leaderboard", True, COLOR_PRIMARY)
        screen.blit(title, (180, 70))

        entries = self.state.get("leaderboard", [])
        if not entries:
            empty = self.font_med.render("No scores yet", True, COLOR_MUTED)
            screen.blit(empty, (180, 130))
        else:
            for idx, entry in enumerate(entries[:10], 1):
                row = f"{idx}. {entry.get('name', 'Player'):<16} {entry.get('score', 0):.2f}s"
                text = self.font_med.render(row, True, COLOR_TEXT)
                screen.blit(text, (180, 120 + idx * 28))

        pygame.draw.rect(screen, COLOR_PANEL, self.back_btn, border_radius=8)
        back_text = self.font_med.render("Back", True, COLOR_TEXT)
        screen.blit(back_text, (self.back_btn.x + 58, self.back_btn.y + 15))

    def get_player_score(self):
        for player in self.state.get("players", []):
            if player.get("id") == self.player_id:
                return float(player.get("score", 0.0))
        return 0.0

    def handle_events(self, events):
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
                return

            if self.mode == "menu":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.pos[0] >= self.name_input.x and event.pos[0] <= self.name_input.right and event.pos[1] >= self.name_input.y and event.pos[1] <= self.name_input.bottom:
                        self.focus_name = True
                        self.focus_host = False
                    elif event.pos[0] >= self.host_input.x and event.pos[0] <= self.host_input.right and event.pos[1] >= self.host_input.y and event.pos[1] <= self.host_input.bottom:
                        self.focus_host = True
                        self.focus_name = False
                    elif self.start_btn.collidepoint(event.pos):
                        self.name = self.name.strip() or "Player"
                        self.host = self.host.strip() or HOST
                        self.settings["name"] = self.name
                        self.settings["host"] = self.host
                        save_settings(self.settings)
                        if self.connect():
                            self.mode = "playing"
                    elif self.settings_btn.collidepoint(event.pos):
                        self.mode = "settings"
                elif event.type == pygame.KEYDOWN:
                    if self.focus_name:
                        if event.key == pygame.K_BACKSPACE:
                            self.name = self.name[:-1]
                        elif event.unicode and len(self.name) < 18 and event.unicode.isprintable():
                            self.name += event.unicode
                    if self.focus_host:
                        if event.key == pygame.K_BACKSPACE:
                            self.host = self.host[:-1]
                        elif event.unicode and len(self.host) < 32 and event.unicode.isprintable():
                            self.host += event.unicode

            elif self.mode == "settings":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    sound_rect = pygame.Rect(180, 180, 220, 48)
                    fullscreen_rect = pygame.Rect(180, 250, 220, 48)
                    if sound_rect.collidepoint(event.pos):
                        self.sound = not self.sound
                    elif fullscreen_rect.collidepoint(event.pos):
                        self.fullscreen = not self.fullscreen
                    elif pygame.Rect(180, 420, 160, 50).collidepoint(event.pos):
                        self.mode = "menu"
                        self.settings["sound"] = self.sound
                        self.settings["fullscreen"] = self.fullscreen
                        save_settings(self.settings)

            elif self.mode == "playing":
                if event.type == pygame.MOUSEMOTION:
                    self.send_input()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.send_input()

            elif self.mode == "gameover":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.play_again_btn.collidepoint(event.pos):
                        self.mode = "playing"
                        self.connect()
                    elif self.leaderboard_btn.collidepoint(event.pos):
                        self.mode = "leaderboard"
                    elif self.back_btn.collidepoint(event.pos):
                        self.mode = "menu"
	self.render(screen)

    def render(self, screen):
        if self.mode == "menu":
            self.render_menu(screen)
        elif self.mode == "settings":
            self.render_settings(screen)
        elif self.mode == "playing":
            self.render_game(screen)
        elif self.mode == "gameover":
            self.render_gameover(screen)
        elif self.mode == "leaderboard":
            self.render_leaderboard(screen)

    def run(self):
        self.settings = load_settings()
        self.name = self.settings.get("name", "Player")
        self.host = self.settings.get("host", HOST)

        screen = pygame.display.set_mode((960, 540), pygame.FULLSCREEN if self.settings.get("fullscreen", False) else 0)
        pygame.display.set_caption("Run! Run! Run!")

        while self.running:
            self.handle_events(pygame.event.get())
            dt = self.clock.tick(60) / 1000.0
            if self.mode == "playing":
                self.send_input()
            self.render(screen)
            pygame.display.flip()

        if self.sock:
            self.sock.close()
        pygame.quit()


def run_client(host: str = HOST, name: str = "Player"):
    settings = load_settings()
    client = Client(host, name, settings.get("fullscreen", False), settings.get("sound", True))
    client.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run! Run! Run! client")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--name", default="Player")
    args = parser.parse_args()

    pygame.init()
    run_client(args.host, args.name)
