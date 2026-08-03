#!/usr/bin/env python3
"""Tiny CORS-enabled static server for QA file injection into the browser."""
import http.server
import os
import sys

os.chdir(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8899


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
