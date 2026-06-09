from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from tkinter import END, Entry, Label, PhotoImage, StringVar, Tk
from tkinter import messagebox, ttk
from urllib.error import URLError
from urllib.request import urlopen

import client_agent


CONFIG_FILE = Path(__file__).resolve().parent / "config.txt"
ICON_FILE = Path(__file__).resolve().parent / "assets" / "rfid_client_icon.ico"
ICON_PNG = Path(__file__).resolve().parent / "assets" / "rfid_client_icon.png"
LOCAL_URL = f"http://{client_agent.HOST}:{client_agent.PORT}/"

server_thread: threading.Thread | None = None
server_instance: ThreadingHTTPServer | None = None


def normalize_server_ip(value: str) -> str:
    value = value.strip()
    if value.startswith("http://"):
        value = value[7:]
    elif value.startswith("https://"):
        value = value[8:]
    return value.split("/", 1)[0].split(":", 1)[0].strip()


def read_config() -> dict[str, str]:
    if not CONFIG_FILE.exists():
        return {"server_ip": "", "machine_id": "0"}

    text = CONFIG_FILE.read_text(encoding="utf-8").strip()
    if not text:
        return {"server_ip": "", "machine_id": "0"}

    try:
        data = json.loads(text)
        return {
            "server_ip": normalize_server_ip(str(data.get("server_ip") or "")),
            "machine_id": str(data.get("machine_id") or "0"),
        }
    except json.JSONDecodeError:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return {"server_ip": normalize_server_ip(lines[0]) if lines else "", "machine_id": "0"}


def write_config(server_ip: str, machine_id: str) -> None:
    CONFIG_FILE.write_text(
        json.dumps({"server_ip": server_ip, "machine_id": machine_id}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fetch_locations(server_ip: str) -> list[dict[str, str]]:
    server_ip = normalize_server_ip(server_ip)
    if not server_ip:
        return []
    with urlopen(f"http://{server_ip}:5000/api/locations", timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data.get("locations") or []


class ClientWindow:
    def __init__(self) -> None:
        config = read_config()
        self.root = Tk()
        self.root.title("RFID 前端連線")
        self.root.geometry("560x430")
        self.root.resizable(False, False)
        self.root.configure(bg="#eef3f5")
        if ICON_FILE.exists():
            self.root.iconbitmap(str(ICON_FILE))

        self.server_ip = StringVar(value=config["server_ip"])
        self.machine_label = StringVar(value="")
        self.status = StringVar(value="尚未連線")
        self.locations: list[dict[str, str]] = []
        self.config_machine_id = config["machine_id"]
        self.icon_image = PhotoImage(file=str(ICON_PNG)) if ICON_PNG.exists() else None
        client_agent.start_reader()

        self.configure_styles()

        shell = ttk.Frame(self.root, style="Shell.TFrame", padding=18)
        shell.pack(fill="both", expand=True)

        header = ttk.Frame(shell, style="Card.TFrame", padding=(16, 14))
        header.pack(fill="x")
        if self.icon_image:
            Label(header, image=self.icon_image, bg="#ffffff").grid(row=0, column=0, rowspan=2, padx=(0, 14), sticky="w")
        ttk.Label(header, text="RFID 前端連線", style="Title.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(header, text="選擇場域並連線到後端伺服器", style="Subtitle.TLabel").grid(row=1, column=1, sticky="w")
        header.columnconfigure(1, weight=1)

        form = ttk.Frame(shell, style="Card.TFrame", padding=(18, 16))
        form.pack(fill="x", pady=(14, 0))

        ttk.Label(form, text="場域", style="Field.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.machine_select = ttk.Combobox(
            form,
            textvariable=self.machine_label,
            values=(),
            state="readonly",
            style="Field.TCombobox",
        )
        self.machine_select.grid(row=0, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(form, text="伺服器 IP", style="Field.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 12))
        self.server_entry = Entry(form, textvariable=self.server_ip, relief="solid", bd=1, font=("Microsoft JhengHei UI", 12))
        self.server_entry.grid(row=1, column=1, sticky="ew", pady=(0, 12), ipady=6)
        self.server_entry.bind("<FocusOut>", lambda _event: self.load_locations())
        self.server_entry.bind("<Return>", lambda _event: self.load_locations())

        self.connect_button = ttk.Button(form, text="網頁連線", command=self.connect, style="Primary.TButton")
        self.connect_button.grid(row=2, column=1, sticky="e", ipadx=16, ipady=4)
        form.columnconfigure(1, weight=1)

        status_card = ttk.Frame(shell, style="Status.TFrame", padding=(14, 10))
        status_card.pack(fill="x", pady=(14, 0))
        ttk.Label(status_card, text="狀態", style="StatusName.TLabel").pack(side="left")
        ttk.Label(status_card, textvariable=self.status, style="StatusValue.TLabel").pack(side="left", padx=(14, 0))

        log_card = ttk.Frame(shell, style="Card.TFrame", padding=(14, 12))
        log_card.pack(fill="both", expand=True, pady=(14, 0))
        ttk.Label(log_card, text="讀卡狀態", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        self.log_box = ttk.Treeview(log_card, columns=("message",), show="headings", height=5, style="Log.Treeview")
        self.log_box.heading("message", text="讀卡狀態")
        self.log_box.column("message", width=490, anchor="w")
        self.log_box.pack(fill="both", expand=True)

        self.root.after(1000, self.refresh_status)
        self.root.after(300, self.load_locations)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Shell.TFrame", background="#eef3f5")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("Status.TFrame", background="#e8f5f1")
        style.configure("Title.TLabel", background="#ffffff", foreground="#17323b", font=("Microsoft JhengHei UI", 18, "bold"))
        style.configure("Subtitle.TLabel", background="#ffffff", foreground="#60717e", font=("Microsoft JhengHei UI", 10))
        style.configure("Section.TLabel", background="#ffffff", foreground="#17323b", font=("Microsoft JhengHei UI", 11, "bold"))
        style.configure("Field.TLabel", background="#ffffff", foreground="#526575", font=("Microsoft JhengHei UI", 11, "bold"))
        style.configure("StatusName.TLabel", background="#e8f5f1", foreground="#0f6d62", font=("Microsoft JhengHei UI", 11, "bold"))
        style.configure("StatusValue.TLabel", background="#e8f5f1", foreground="#17323b", font=("Microsoft JhengHei UI", 10))
        style.configure("Field.TCombobox", fieldbackground="#ffffff", background="#ffffff", foreground="#17323b", padding=6)
        style.configure("Primary.TButton", background="#12736b", foreground="#ffffff", borderwidth=0, font=("Microsoft JhengHei UI", 11, "bold"))
        style.map("Primary.TButton", background=[("active", "#0f625b"), ("pressed", "#0b524c")])
        style.configure("Log.Treeview", background="#fbfcfd", fieldbackground="#fbfcfd", foreground="#26343c", rowheight=26, borderwidth=0)
        style.configure("Log.Treeview.Heading", font=("Microsoft JhengHei UI", 10, "bold"))

    def log(self, message: str) -> None:
        self.log_box.insert("", END, values=(message,))
        children = self.log_box.get_children()
        if len(children) > 20:
            self.log_box.delete(children[0])
        self.log_box.see(self.log_box.get_children()[-1])

    def connect(self) -> None:
        server_ip = normalize_server_ip(self.server_ip.get())
        if not server_ip:
            messagebox.showerror("缺少伺服器IP", "請輸入伺服器IP")
            return
        if not self.locations:
            self.load_locations()
        machine_id = self.selected_machine_id()
        if not machine_id:
            messagebox.showerror("缺少場域", "請先選擇場域")
            return

        write_config(server_ip, machine_id)
        self.server_ip.set(server_ip)
        client_agent.BACKEND_BASE_URL = f"http://{server_ip}:5000"
        if not self.start_agent():
            return

        target = f"{LOCAL_URL}?machine_id={machine_id}"
        open_browser(target)
        self.status.set(f"已連線：{client_agent.BACKEND_BASE_URL}")
        self.log(f"開啟網頁：{target}")

    def load_locations(self) -> None:
        server_ip = normalize_server_ip(self.server_ip.get())
        if not server_ip:
            self.set_location_options([])
            return
        try:
            locations = fetch_locations(server_ip)
        except (OSError, URLError, TimeoutError) as exc:
            self.status.set(f"無法讀取場域：{exc}")
            return
        self.locations = locations
        self.set_location_options(locations)

    def set_location_options(self, locations: list[dict[str, str]]) -> None:
        labels = [location["label"] for location in locations]
        self.machine_select.configure(values=labels)
        if not labels:
            self.machine_label.set("")
            return
        selected = next(
            (location for location in locations if location["machine_id"] == self.config_machine_id),
            locations[0],
        )
        if self.machine_label.get() not in labels:
            self.machine_label.set(selected["label"])

    def selected_machine_id(self) -> str:
        label = self.machine_label.get()
        for location in self.locations:
            if location["label"] == label:
                return location["machine_id"]
        return self.locations[0]["machine_id"] if self.locations else ""

    def start_agent(self) -> bool:
        global server_instance, server_thread

        if server_thread and server_thread.is_alive():
            return True

        client_agent.start_reader()
        try:
            server_instance = ThreadingHTTPServer((client_agent.HOST, client_agent.PORT), client_agent.ClientAgentHandler)
        except OSError as exc:
            messagebox.showerror("本機代理啟動失敗", f"無法啟動 127.0.0.1:5055\n{exc}\n\n請關閉舊的 client.bat 或 client_ui.py 後再試。")
            return False
        server_thread = threading.Thread(target=server_instance.serve_forever, daemon=True)
        server_thread.start()
        self.log(f"本機代理啟動：{LOCAL_URL}")
        return True

    def refresh_status(self) -> None:
        payload = client_agent.status_payload()
        readers = payload.get("readers") or []
        error = str(payload.get("error") or "")
        card = payload.get("last_card") or {}

        if error:
            self.status.set(f"RFID 錯誤：{error}")
        elif readers:
            self.status.set(f"讀卡機：{'、'.join(readers)}")
        else:
            self.status.set("尚未偵測到讀卡機")

        sequence = card.get("sequence")
        if sequence and getattr(self, "_last_sequence", 0) != sequence:
            self._last_sequence = sequence
            self.log(f"讀到 UID：{card.get('uid_decimal')} / HEX：{card.get('uid_hex')}")

        self.root.after(1000, self.refresh_status)

    def close(self) -> None:
        if server_instance:
            threading.Thread(target=server_instance.shutdown, daemon=True).start()
        time.sleep(0.1)
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def open_browser(url: str) -> None:
    candidates = [
        Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    for chrome in candidates:
        if chrome.exists():
            subprocess.Popen([str(chrome), url])
            return
    os.startfile(url)


if __name__ == "__main__":
    ClientWindow().run()
