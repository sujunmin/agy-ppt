#!/usr/bin/env python3
"""Serve a built site under its real GitHub project-site prefix locally."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


PREFIX = "/agy-ppt"


class ProjectSiteHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        request_path = unquote(urlsplit(path).path)
        if request_path == PREFIX:
            request_path = "/"
        elif request_path.startswith(PREFIX + "/"):
            request_path = request_path[len(PREFIX) :]
        else:
            request_path = "/__outside_project_site__"
        return super().translate_path(request_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not (directory / "index.html").is_file():
        raise SystemExit(f"No built index.html found in {directory}; run website/build.py first")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(ProjectSiteHandler, directory=directory))
    print(f"Preview: http://127.0.0.1:{args.port}{PREFIX}/  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
