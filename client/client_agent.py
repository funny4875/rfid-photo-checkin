from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from acr122_reader import ACR122Reader


HOST = "127.0.0.1"
PORT = 5055


class LocalThreadingHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        """Bind locally without Windows hostname reverse lookup."""
        TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port
BACKEND_BASE_URL = ""

reader: ACR122Reader | None = None
startup_error = ""
_last_readers_text = ""
_last_error = ""
_last_sequence = 0


def start_reader() -> None:
    global reader, startup_error
    if reader:
        startup_error = ""
        return
    try:
        reader = ACR122Reader()
        reader.start()
        startup_error = ""
    except Exception as exc:
        reader = None
        startup_error = str(exc)


def status_payload() -> dict[str, object]:
    if not reader:
        return {
            "enabled": False,
            "readers": [],
            "last_card": None,
            "sequence": 0,
            "error": startup_error or "RFID 讀卡程式尚未啟動",
        }
    return {"enabled": True, **reader.snapshot()}


def monitor_reader() -> None:
    global _last_error, _last_readers_text, _last_sequence

    while True:
        payload = status_payload()
        readers = payload.get("readers") or []
        readers_text = ", ".join(readers) if readers else "(no reader detected)"
        error = str(payload.get("error") or "")
        sequence = int(payload.get("sequence") or 0)

        if readers_text != _last_readers_text:
            _last_readers_text = readers_text
            print(f"[RFID] Readers: {readers_text}", flush=True)

        if error != _last_error:
            _last_error = error
            if error:
                print(f"[RFID] Error: {error}", flush=True)
            else:
                print("[RFID] Reader status OK", flush=True)

        if sequence > _last_sequence:
            _last_sequence = sequence
            card = payload.get("last_card") or {}
            print(
                "[RFID] Card read: "
                f"reader={card.get('reader')} "
                f"uid_decimal={card.get('uid_decimal')} "
                f"uid_hex={card.get('uid_hex')} "
                f"at={card.get('at')}",
                flush=True,
            )

        time.sleep(1)


class ClientAgentHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] not in ("/api/rfid/status", "/health"):
            self.proxy_to_backend("GET")
            return
        self.send_json(status_payload())

    def do_POST(self) -> None:
        self.proxy_to_backend("POST")

    def do_DELETE(self) -> None:
        self.proxy_to_backend("DELETE")

    def send_json(self, payload: dict[str, object], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")

    def log_message(self, format: str, *args: object) -> None:
        return

    def proxy_to_backend(self, method: str) -> None:
        if not BACKEND_BASE_URL:
            self.send_json({"error": "Backend server URL is not configured"}, status=500)
            return

        body = None
        content_length = self.headers.get("Content-Length")
        if content_length:
            body = self.rfile.read(int(content_length))

        target_url = urljoin(BACKEND_BASE_URL.rstrip("/") + "/", self.path.lstrip("/"))
        headers = {}
        content_type = self.headers.get("Content-Type")
        if content_type:
            headers["Content-Type"] = content_type

        request = Request(target_url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=15) as response:
                response_body = response.read()
                self.send_response(response.status)
                self.copy_backend_headers(response.headers)
                self.send_header("Content-Length", str(len(response_body)))
                self.end_headers()
                self.wfile.write(response_body)
        except HTTPError as exc:
            response_body = exc.read()
            self.send_response(exc.code)
            self.copy_backend_headers(exc.headers)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
        except URLError as exc:
            self.send_json({"error": f"Cannot connect backend server: {exc.reason}"}, status=502)

    def copy_backend_headers(self, headers) -> None:
        blocked = {
            "connection",
            "content-length",
            "transfer-encoding",
            "content-encoding",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "upgrade",
        }
        for name, value in headers.items():
            if name.lower() not in blocked:
                self.send_header(name, value)


def parse_backend_url() -> str:
    for index, arg in enumerate(sys.argv):
        if arg == "--server" and index + 1 < len(sys.argv):
            return normalize_backend_url(sys.argv[index + 1])
        if arg.startswith("--server="):
            return normalize_backend_url(arg.split("=", 1)[1])
    return ""


def normalize_backend_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        value = "http://" + value
    return value.rstrip("/")


if __name__ == "__main__":
    BACKEND_BASE_URL = parse_backend_url()
    start_reader()
    print("RFID client agent is starting...", flush=True)
    if BACKEND_BASE_URL:
        print(f"Backend proxy: {BACKEND_BASE_URL}", flush=True)
        print(f"Open browser: http://{HOST}:{PORT}/", flush=True)
    else:
        print("Backend proxy is not configured. Start with --server http://SERVER_IP:5000", flush=True)
    print(f"Status URL: http://{HOST}:{PORT}/api/rfid/status", flush=True)
    print(f"Health URL: http://{HOST}:{PORT}/health", flush=True)
    if startup_error:
        print(f"RFID reader startup error: {startup_error}", flush=True)
    threading.Thread(target=monitor_reader, daemon=True).start()
    try:
        LocalThreadingHTTPServer((HOST, PORT), ClientAgentHandler).serve_forever()
    except OSError as exc:
        print(f"HTTP server startup error: {exc}", flush=True)
        print("If port 5055 is already in use, close the old client.bat window and run client.bat again.", flush=True)
        raise
