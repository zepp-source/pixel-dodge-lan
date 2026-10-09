# Pixel Dodge LAN

A fast, clean LAN multiplayer survival game built in Python with Pygame and TCP sockets.

Features:
- Minimal circular-player arcade gameplay
- Mouse-controlled movement
- Clean dark neon UI
- Real-time LAN multiplayer via TCP
- Live leaderboard synced across clients
- Procedural music and SFX generated in code
- Server + client split into separate modules

Requirements:
- Python 3.10+
- pygame

Install:
```bash
pip install -r requirements.txt
```

Run the server (host machine):
```bash
python server.py --host 0.0.0.0 --port 9000
```

Run the client (on any machine on the same LAN):
```bash
python client.py --host 192.168.1.10 --name You
```

Optional: if you're on the same machine, use `127.0.0.1`.

Controls:
- Move mouse to steer your circle
- Survive as long as possible
- Avoid incoming enemy circles

Notes:
- The server keeps the authoritative game state.
- The leaderboard is saved on the server machine in `leaderboard.json`.
- If you want a clean local-only quick test, run the server and client on the same PC.
