# Run! Run! Run!

A clean, fast LAN survival game built in Python with Pygame and TCP networking.

## Features
- Minimal arcade style with clean dark UI
- Mouse-controlled movement
- Real-time multiplayer over LAN
- Live leaderboard synced across players
- Quick host/join flow
- Simple local settings and sound toggles
- No AI fluff, no clutter, no cringe

## Requirements
- Python 3.10+
- pygame

## Install
```bash
pip install -r requirements.txt
```

## Run a server
```bash
python server.py --host 0.0.0.0 --port 9000
```

## Run a client
```bash
python client.py --host 192.168.1.10 --name "Alex"
```

## Quick launcher
```bash
python game.py --server
python game.py --host 192.168.1.10 --name "Alex"
```

## Controls
- Move with the mouse
- Avoid incoming enemy circles
- Survive as long as possible
- Climb the leaderboard

## Notes
- Server is authoritative and sends world state every tick
- Leaderboard saved to `leaderboard.json`
- Works best on a local school LAN
