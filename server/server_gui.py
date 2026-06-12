from __future__ import annotations

import subprocess
import socket
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
VERSION_FILE = ROOT_DIR / "VERSION"
CONFIG_FILE = BASE_DIR / "config.txt"


def app_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0"


def available_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM):
            address = item[4][0]
            if address and not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            address = probe.getsockname()[0]
            if address and not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass

    return sorted(addresses, key=lambda value: tuple(int(part) for part in value.split("."))) or ["127.0.0.1"]


def read_saved_bind_ip() -> str:
    if not CONFIG_FILE.exists():
        return ""
    return CONFIG_FILE.read_text(encoding="utf-8-sig").strip()


def save_bind_ip(bind_ip: str) -> None:
    CONFIG_FILE.write_text(bind_ip.strip() + "\n", encoding="utf-8")


def preferred_bind_ip(addresses: list[str]) -> str:
    saved_bind_ip = read_saved_bind_ip()
    return saved_bind_ip if saved_bind_ip in addresses else addresses[0]


class ServerGui:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.process: subprocess.Popen[str] | None = None
        self.pending_bind_ip = ""
        self.status_var = tk.StringVar(value="已停止")
        self.web_url = tk.StringVar(value="尚未啟動")
        self.bind_ip = tk.StringVar()
        self.bind_addresses = available_ipv4_addresses()
        self.bind_ip.set(preferred_bind_ip(self.bind_addresses))

        root.title("門禁網頁伺服器")
        root.geometry("520x340")
        root.minsize(460, 310)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        frame = tk.Frame(root, padx=22, pady=18)
        frame.pack(fill="both", expand=True)

        title = tk.Label(frame, text="門禁網頁伺服器", font=("Microsoft JhengHei UI", 18, "bold"))
        title.pack(anchor="w")

        version = tk.Label(frame, text=f"版本 v{app_version()}", fg="#526575")
        version.pack(anchor="w", pady=(2, 14))

        status_row = tk.Frame(frame)
        status_row.pack(fill="x", pady=(0, 8))
        tk.Label(status_row, text="狀態", width=10, anchor="w").pack(side="left")
        tk.Label(status_row, textvariable=self.status_var, anchor="w").pack(side="left", fill="x", expand=True)

        bind_row = tk.Frame(frame)
        bind_row.pack(fill="x", pady=(4, 8))
        tk.Label(bind_row, text="綁定 IP", width=10, anchor="w").pack(side="left")
        self.bind_select = ttk.Combobox(
            bind_row,
            textvariable=self.bind_ip,
            values=self.bind_addresses,
            state="readonly",
            width=24,
        )
        self.bind_select.pack(side="left", fill="x", expand=True)

        url_row = tk.Frame(frame)
        url_row.pack(fill="x", pady=(4, 8))
        tk.Label(url_row, text="網頁網址", width=10, anchor="w").pack(side="left")
        self.url_entry = ttk.Entry(url_row, textvariable=self.web_url, state="readonly")
        self.url_entry.pack(side="left", fill="x", expand=True)

        buttons = tk.Frame(frame)
        buttons.pack(fill="x", pady=(10, 12))
        self.start_button = tk.Button(buttons, text="啟動", width=12, command=self.start_server)
        self.start_button.pack(side="left", padx=(0, 10))
        self.stop_button = tk.Button(buttons, text="停止", width=12, command=self.stop_server, state="disabled")
        self.stop_button.pack(side="left")

        self.log = tk.Text(frame, height=5, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, pady=(12, 0))

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start_server(self) -> None:
        if self.process and self.process.poll() is None:
            return
        bind_ip = self.bind_ip.get().strip()
        if bind_ip not in self.bind_addresses:
            messagebox.showerror("綁定 IP 錯誤", "請選擇可用的本機 IP")
            return
        self.process = subprocess.Popen(
            [sys.executable, "app.py", "--host", bind_ip],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0,
        )
        self.pending_bind_ip = bind_ip
        url = f"http://{bind_ip}:5000"
        self.status_var.set("執行中")
        self.web_url.set(url)
        self.bind_select.configure(state="disabled")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.append_log(f"伺服器已啟動，可由以下網址連入：{url}")
        threading.Thread(target=self.read_output, daemon=True).start()
        self.root.after(1000, self.watch_process)

    def stop_server(self) -> None:
        if not self.process or self.process.poll() is not None:
            self.set_stopped("已停止")
            return
        self.append_log("正在停止伺服器...")
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.set_stopped("已停止")

    def read_output(self) -> None:
        if not self.process or not self.process.stdout:
            return
        for line in self.process.stdout:
            self.root.after(0, self.append_log, line)

    def watch_process(self) -> None:
        if not self.process:
            return
        if self.process.poll() is None:
            if self.pending_bind_ip:
                save_bind_ip(self.pending_bind_ip)
                self.pending_bind_ip = ""
            self.root.after(1000, self.watch_process)
            return
        self.pending_bind_ip = ""
        self.set_stopped("已停止")

    def set_stopped(self, text: str) -> None:
        self.status_var.set(text)
        self.web_url.set("尚未啟動")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.bind_select.configure(state="readonly")

    def on_close(self) -> None:
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("門禁網頁伺服器", "伺服器仍在執行，是否停止並關閉？"):
                return
            self.stop_server()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    ServerGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
