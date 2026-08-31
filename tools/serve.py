#!/usr/bin/env python3
"""Serve the WebUI locally with the project's default port."""

import argparse
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DEFAULT_PORT = 17342
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Live2D motion WebUI")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    os.chdir(PROJECT_ROOT)
    server = ThreadingHTTPServer(("", args.port), SimpleHTTPRequestHandler)
    print(f"Live2D WebUI: http://localhost:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
