#!/usr/bin/env python3
import argparse

from client import run_client
from server import GameServer
from common import HOST, PORT


def main():
    parser = argparse.ArgumentParser(description="Run! Run! Run! launcher")
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--name", default="Player")
    args = parser.parse_args()

    if args.server:
        GameServer(args.host, args.port).start()
    else:
        run_client(args.host, args.name)


if __name__ == "__main__":
    main()
