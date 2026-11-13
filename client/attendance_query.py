from __future__ import annotations

import datetime
import json
import queue
import re
import threading
import tkinter as tk
from tkinter import ttk
from urllib.parse import urlsplit
from urllib.request import urlopen


def fetch_records(server: str, date: str) -> list:
    server = server.strip().rstrip("/")
    if not server:
        raise ValueError("請輸入伺服器網址")
    if not server.startswith(("http://", "https://")):
        server = "http://" + server
    parts = urlsplit(server)
    if not parts.netloc or parts.path or parts.query or parts.fragment:
        raise ValueError("伺服器網址格式錯誤，請輸入網址及埠號")
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


class AttendanceQuery:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.results: queue.Queue = queue.Queue()
        self.server = tk.StringVar(value="http://127.0.0.1:5000")
        self.date = tk.StringVar(value=datetime.date.today().strftime("%Y%m%d"))
        self.status = tk.StringVar(value="請輸入日期並查詢")
        root.title("出勤紀錄查詢")
        root.geometry("900x560")
        root.minsize(680, 400)

        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)
        form = ttk.Frame(frame)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="伺服器網址").grid(row=0, column=0, padx=(0, 8), pady=4, sticky="w")
        ttk.Entry(form, textvariable=self.server).grid(row=0, column=1, columnspan=3, sticky="ew", pady=4)
        ttk.Label(form, text="日期 YYYYMMDD").grid(row=1, column=0, padx=(0, 8), pady=4, sticky="w")
        date_entry = ttk.Entry(form, textvariable=self.date, width=16)
        date_entry.grid(row=1, column=1, sticky="w", pady=4)
        date_entry.bind("<Return>", lambda event: self.search())
        self.button = ttk.Button(form, text="查詢", command=self.search)
        self.button.grid(row=1, column=2, padx=8, pady=4)
        ttk.Label(frame, textvariable=self.status).pack(anchor="w", pady=(10, 6))

        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True)
        columns = ("time", "student_id", "class_name", "seat", "name", "direction", "machine_label")
        self.tree = ttk.Treeview(table, columns=columns, show="headings")
        for key, label, width in zip(columns, ("時間", "學號", "班級", "座號", "姓名", "進出", "場域"), (95, 110, 100, 70, 110, 70, 120)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=55, stretch=True)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        root.after(100, self.poll)

    def search(self) -> None:
        if self.button.instate(["disabled"]):
            return
        server, date = self.server.get(), self.date.get().strip()
        self.button.configure(state="disabled")
        self.status.set("查詢中…")
        self.tree.delete(*self.tree.get_children())
        threading.Thread(target=self._fetch, args=(server, date), daemon=True).start()

    def _fetch(self, server: str, date: str) -> None:
        try:
            self.results.put((date, fetch_records(server, date), None))
        except Exception as exc:
            self.results.put((date, None, str(exc)))

    def poll(self) -> None:
        try:
            date, records, error = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.button.configure(state="normal")
            if error:
                self.status.set("查詢失敗：" + error)
            else:
                for record in records:
                    self.tree.insert("", "end", values=tuple(record.get(key, "") for key in self.tree["columns"]))
                self.status.set(f"{date}：共 {len(records)} 筆紀錄" if records else f"{date}：沒有出勤紀錄")
        self.root.after(100, self.poll)


if __name__ == "__main__":
    root = tk.Tk()
    AttendanceQuery(root)
    root.mainloop()
