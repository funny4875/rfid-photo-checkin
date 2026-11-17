from __future__ import annotations

import datetime
import csv
import json
import os
import queue
import re
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


CONFIG_FILE = Path(os.environ.get("APPDATA") or Path.home()) / "CCSH" / "AttendanceQuery" / "config.json"
RELEASES_API = "https://api.github.com/repos/funny4875/rfid-photo-checkin/releases/latest"


def application_version() -> str:
    root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    return (root / "VERSION").read_text(encoding="utf-8").strip()


def check_for_update(current: str) -> tuple[str, str] | None:
    def version_tuple(value: str) -> tuple[int, int, int]:
        if not re.fullmatch(r"\d+\.\d+\.\d+", value):
            raise ValueError("版本格式錯誤")
        return tuple(int(part) for part in value.split("."))

    request = Request(RELEASES_API, headers={"User-Agent": "CCSH-AttendanceQuery", "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=8) as response:
        release = json.loads(response.read().decode("utf-8"))
    tag = release.get("tag_name", "")
    version = tag[1:] if tag.startswith("v") else tag
    if version_tuple(version) <= version_tuple(current):
        return None
    asset_name = f"AttendanceQuery-{version}.msi"
    if not any(asset.get("name") == asset_name and asset.get("state") == "uploaded" for asset in release.get("assets", [])):
        return None
    return version, f"https://github.com/funny4875/rfid-photo-checkin/releases/download/{tag}/{asset_name}"


def normalize_server(server: str) -> str:
    if not isinstance(server, str):
        raise ValueError("伺服器網址格式錯誤")
    server = server.strip().rstrip("/")
    if not server:
        raise ValueError("請輸入伺服器網址")
    if not server.startswith(("http://", "https://")):
        server = "http://" + server
    parts = urlsplit(server)
    if not parts.netloc or parts.path or parts.query or parts.fragment:
        raise ValueError("伺服器網址格式錯誤，請輸入網址及埠號")
    if not parts.hostname or parts.username or parts.password:
        raise ValueError("伺服器網址格式錯誤，請輸入網址及埠號")
    try:
        parts.port
    except ValueError as exc:
        raise ValueError("伺服器埠號錯誤") from exc
    return server


def read_server() -> str:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return normalize_server(data["server_url"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def save_server(server: str) -> str:
    server = normalize_server(server)
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"server_url": server}, ensure_ascii=False, indent=2), encoding="utf-8")
    return server


def fetch_records(server: str, date: str) -> list:
    server = normalize_server(server)
    if not re.fullmatch(r"[0-9]{8}", date):
        raise ValueError("日期格式需為 YYYYMMDD")
    try:
        datetime.datetime.strptime(date, "%Y%m%d")
    except ValueError as exc:
        raise ValueError("日期不存在") from exc
    with urlopen(server + "/api/attendance/summary/" + date, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise ValueError("伺服器回傳的資料格式錯誤")
    return data["records"]


def parse_date(value: str) -> datetime.date:
    if not re.fullmatch(r"[0-9]{8}", value):
        raise ValueError("日期格式需為 YYYYMMDD")
    try:
        return datetime.datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError("日期不存在") from exc


def fetch_date_range(server: str, start: str, end: str) -> list:
    first, last = parse_date(start), parse_date(end)
    if first > last:
        raise ValueError("起始日期不可晚於結束日期")
    records = []
    current = first
    while True:
        date = current.strftime("%Y%m%d")
        try:
            daily = fetch_records(server, date)
            if not all(isinstance(record, dict) for record in daily):
                raise ValueError("紀錄格式錯誤")
            records.extend({**record, "date": date} for record in daily)
        except Exception as exc:
            raise RuntimeError(f"{date} 查詢失敗：{exc}") from exc
        if current == last:
            break
        current += datetime.timedelta(days=1)
    return records


def write_records(path: str, records: list) -> None:
    columns = ("date", "time", "student_id", "class_name", "seat", "name", "direction", "machine_label")
    with open(path, "w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerow(("日期", "時間", "學號", "班級", "座號", "姓名", "進出", "場域"))
        for record in records:
            writer.writerow([record.get(key, "") for key in columns])


class AttendanceQuery:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.results: queue.Queue = queue.Queue()
        self.updates: queue.Queue = queue.Queue()
        self.server = tk.StringVar(value=read_server())
        self.start_date = tk.StringVar(value=datetime.date.today().strftime("%Y%m%d"))
        self.end_date = tk.StringVar(value=datetime.date.today().strftime("%Y%m%d"))
        self.records: list | None = None
        self.result_dates = ("", "")
        self.status = tk.StringVar(value="請輸入起訖日期並查詢")
        root.title("出勤紀錄查詢")
        icon = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets" / "attendance_query.ico"
        if icon.exists():
            root.iconbitmap(str(icon))
        root.geometry("900x560")
        root.minsize(680, 400)

        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)
        form = ttk.Frame(frame)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="伺服器網址").grid(row=0, column=0, padx=(0, 8), pady=4, sticky="w")
        server_entry = ttk.Entry(form, textvariable=self.server)
        server_entry.grid(row=0, column=1, columnspan=3, sticky="ew", pady=4)
        server_entry.bind("<FocusOut>", self.save_server_on_focus_out)
        ttk.Label(form, text="日期 YYYYMMDD").grid(row=1, column=0, padx=(0, 8), pady=4, sticky="w")
        dates = ttk.Frame(form)
        dates.grid(row=1, column=1, sticky="w", pady=4)
        start_entry = ttk.Entry(dates, textvariable=self.start_date, width=12)
        start_entry.pack(side="left")
        ttk.Label(dates, text="至").pack(side="left", padx=6)
        end_entry = ttk.Entry(dates, textvariable=self.end_date, width=12)
        end_entry.pack(side="left")
        for entry in (start_entry, end_entry):
            entry.bind("<Return>", lambda event: self.search())
        self.button = ttk.Button(form, text="查詢", command=self.search)
        self.button.grid(row=1, column=2, padx=8, pady=4)
        self.save_button = ttk.Button(form, text="儲存文字檔", command=self.save_results, state="disabled")
        self.save_button.grid(row=1, column=3, pady=4)
        ttk.Label(frame, textvariable=self.status).pack(anchor="w", pady=(10, 6))

        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True)
        columns = ("date", "time", "student_id", "class_name", "seat", "name", "direction", "machine_label")
        self.tree = ttk.Treeview(table, columns=columns, show="headings")
        for key, label, width in zip(columns, ("日期", "時間", "學號", "班級", "座號", "姓名", "進出", "場域"), (95, 95, 110, 100, 70, 110, 70, 120)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=55, stretch=True)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        root.after(100, self.poll)
        if not self.server.get():
            root.after(100, self.ask_server)
        threading.Thread(target=self._check_update, daemon=True).start()

    def _check_update(self) -> None:
        try:
            update = check_for_update(application_version())
            if update:
                self.updates.put(update)
        except Exception:
            pass

    def ask_server(self) -> None:
        value = simpledialog.askstring("伺服器設定", "請輸入出勤系統的伺服器網址：", parent=self.root)
        if value is not None:
            self.server.set(value.strip())
            self.persist_server(show_errors=True)

    def persist_server(self, show_errors: bool = False) -> bool:
        try:
            server = save_server(self.server.get())
        except (OSError, ValueError) as exc:
            self.status.set("無法儲存伺服器網址：" + str(exc))
            if show_errors:
                messagebox.showerror("伺服器設定", str(exc), parent=self.root)
            return False
        self.server.set(server)
        return True

    def save_server_on_focus_out(self, _event) -> None:
        if self.server.get().strip():
            self.persist_server()

    def search(self) -> None:
        if self.button.instate(["disabled"]):
            return
        if not self.persist_server():
            return
        server, start, end = self.server.get(), self.start_date.get().strip(), self.end_date.get().strip()
        self.button.configure(state="disabled")
        self.save_button.configure(state="disabled")
        self.records = None
        self.status.set("查詢中…")
        self.tree.delete(*self.tree.get_children())
        threading.Thread(target=self._fetch, args=(server, start, end), daemon=True).start()

    def _fetch(self, server: str, start: str, end: str) -> None:
        try:
            self.results.put((start, end, fetch_date_range(server, start, end), None))
        except Exception as exc:
            self.results.put((start, end, None, str(exc)))

    def save_results(self) -> None:
        if self.records is None:
            return
        start, end = self.result_dates
        path = filedialog.asksaveasfilename(parent=self.root, title="儲存出勤紀錄", defaultextension=".txt", filetypes=[("文字檔", "*.txt")], initialfile=f"出勤紀錄_{start}_{end}.txt")
        if not path:
            return
        try:
            write_records(path, self.records)
        except (OSError, csv.Error) as exc:
            messagebox.showerror("儲存失敗", str(exc), parent=self.root)
            return
        self.status.set(f"已儲存 {len(self.records)} 筆紀錄：{path}")

    def poll(self) -> None:
        try:
            version, url = self.updates.get_nowait()
        except queue.Empty:
            pass
        else:
            if messagebox.askyesno("程式更新", f"發現新版本 {version}，是否下載更新？", parent=self.root):
                if not webbrowser.open(url):
                    messagebox.showerror("程式更新", "無法開啟下載連結，請到 GitHub Release 下載。", parent=self.root)
        try:
            start, end, records, error = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.button.configure(state="normal")
            if error:
                self.status.set("查詢失敗：" + error)
            else:
                self.records = records
                self.result_dates = (start, end)
                for record in records:
                    self.tree.insert("", "end", values=tuple(record.get(key, "") for key in self.tree["columns"]))
                self.save_button.configure(state="normal")
                self.status.set(f"{start} 至 {end}：共 {len(records)} 筆紀錄" if records else f"{start} 至 {end}：沒有出勤紀錄")
        self.root.after(100, self.poll)


if __name__ == "__main__":
    root = tk.Tk()
    AttendanceQuery(root)
    root.mainloop()
