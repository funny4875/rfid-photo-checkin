#!/usr/bin/env python
# coding: utf-8

from __future__ import annotations

import datetime
import json
import os
import queue
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, scrolledtext, ttk

try:
    import autoline
except Exception as exc:
    autoline = None
    AUTOLINE_IMPORT_ERROR = exc
else:
    AUTOLINE_IMPORT_ERROR = None

try:
    import holidays
except Exception as exc:
    holidays = None
    HOLIDAYS_IMPORT_ERROR = exc
else:
    HOLIDAYS_IMPORT_ERROR = None


APP_TITLE = "每日出勤 LINE 推播"
DEFAULT_SERVER_URL = os.environ.get("RFID_SERVER_URL", "http://127.0.0.1:5000")
DEFAULT_GROUP_TITLE = "家齊學生出勤推播群組"
CONFIG_FILE = Path(__file__).resolve().parent / "lineMsg_config.json"
MSG_FILE = Path(__file__).resolve().parent / "msg.txt"


def today_text() -> str:
    return datetime.datetime.now().strftime("%Y%m%d")


def display_date(date_text: str) -> str:
    try:
        return datetime.datetime.strptime(date_text, "%Y%m%d").strftime("%m/%d")
    except ValueError:
        return datetime.datetime.now().strftime("%m/%d")


def normalize_date(value: str) -> str:
    raw = (value or "").strip().replace("-", "")
    if len(raw) != 8 or not raw.isdigit():
        raise ValueError("日期格式需為 yyyymmdd，例如 20260618")
    datetime.datetime.strptime(raw, "%Y%m%d")
    return raw


def normalize_server_url(value: str) -> str:
    url = (value or "").strip().rstrip("/")
    if not url:
        raise ValueError("請輸入伺服器網址")
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url.rstrip("/")


def fetch_attendance_records(server_url: str, date_text: str) -> list[dict[str, object]]:
    api_url = f"{normalize_server_url(server_url)}/api/attendance/summary/{date_text}"
    with urllib.request.urlopen(api_url, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("records") or []


def write_msg_file(records: list[dict[str, object]]) -> None:
    with MSG_FILE.open("w", encoding="utf-8", newline="") as handle:
        handle.write("時間\t卡片UID\t學號\t班級\t座號\t姓名\t進/出\n")
        for record in records:
            handle.write(
                "\t".join(
                    [
                        str(record.get("time") or ""),
                        str(record.get("uid") or ""),
                        str(record.get("student_id") or ""),
                        str(record.get("class_name") or ""),
                        str(record.get("seat") or ""),
                        str(record.get("name") or ""),
                        str(record.get("direction") or ""),
                    ]
                )
                + "\n"
            )


def build_messages(records: list[dict[str, object]], date_text: str, max_lines: int = 72) -> list[str]:
    by_class: dict[str, list[str]] = {}
    for record in records:
        class_name = str(record.get("class_name") or "").strip()
        if len(class_name) == 3:
            class_name = class_name[0:2] + "0" + class_name[2]
        if not class_name:
            class_name = "未分班"
        row = f"{record.get('time') or ''}\t{record.get('name') or ''}"
        by_class.setdefault(class_name, []).append(row)

    if not by_class:
        return [f"\n{display_date(date_text)}遲到學生名單\n今日沒有出勤資料\n"]

    messages: list[str] = []
    index = 1
    line_count = 1
    message = f"\n{display_date(date_text)}遲到學生名單-{index}\n"

    for class_name in sorted(by_class.keys()):
        rows = by_class[class_name]
        if line_count + len(rows) + 3 > max_lines:
            messages.append(message)
            index += 1
            line_count = 1
            message = f"\n{display_date(date_text)}遲到學生名單-{index}\n"
        line_count += len(rows) + 1
        message += f"[{class_name}]\n"
        for row in rows:
            message += row + "\n"

    messages.append(message)
    return messages


def is_working_day(day: datetime.datetime) -> tuple[bool, str]:
    if day.weekday() >= 5:
        return False, "週末"
    if holidays is None:
        return True, f"無法載入 holidays，僅依星期判斷：{HOLIDAYS_IMPORT_ERROR}"
    tw_holidays = holidays.TW()
    if day.date() in tw_holidays:
        return False, "台灣例假日"
    return True, ""


def load_config() -> dict[str, str]:
    defaults = {
        "server_url": DEFAULT_SERVER_URL,
        "group_title": DEFAULT_GROUP_TITLE,
        "send_time": "12:30",
    }
    if not CONFIG_FILE.exists():
        return defaults
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    defaults.update({key: str(value) for key, value in data.items() if value is not None})
    return defaults


def save_config(server_url: str, group_title: str, send_time: str) -> None:
    payload = {
        "server_url": server_url,
        "group_title": group_title,
        "send_time": send_time,
    }
    CONFIG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def configure_fonts(root: tk.Tk) -> None:
    try:
        tkfont.nametofont("TkDefaultFont").configure(family="Microsoft JhengHei UI", size=10)
        tkfont.nametofont("TkTextFont").configure(family="Microsoft JhengHei UI", size=10)
    except tk.TclError:
        pass


class LineMsgGui:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.title_font = tkfont.Font(root=root, family="Microsoft JhengHei UI", size=18, weight="bold")
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.running = False
        self.sending = False
        self.sent_dates: set[str] = set()
        self.config = load_config()

        self.server_url = tk.StringVar(value=self.config["server_url"])
        self.group_title = tk.StringVar(value=self.config["group_title"])
        self.send_time = tk.StringVar(value=self.config["send_time"])
        self.resend_date = tk.StringVar(value=today_text())
        self.status_text = tk.StringVar(value="尚未開始排程")

        root.title(APP_TITLE)
        root.geometry("860x660")
        root.minsize(760, 560)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.build_ui()
        self.log("system", "程式啟動")
        if AUTOLINE_IMPORT_ERROR is not None:
            self.log("system", f"注意：無法載入 autoline，發送時會失敗：{AUTOLINE_IMPORT_ERROR}")
        if HOLIDAYS_IMPORT_ERROR is not None:
            self.log("system", f"注意：無法載入 holidays，工作日判斷只會排除週末：{HOLIDAYS_IMPORT_ERROR}")

        self.root.after(250, self.drain_log_queue)
        self.root.after(1000, self.scheduler_tick)

    def build_ui(self) -> None:
        shell = ttk.Frame(self.root, padding=16)
        shell.pack(fill="both", expand=True)

        title = ttk.Label(shell, text=APP_TITLE, font=self.title_font)
        title.pack(anchor="w")

        settings = ttk.LabelFrame(shell, text="日常排程設定", padding=12)
        settings.pack(fill="x", pady=(14, 10))
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=0)

        ttk.Label(settings, text="伺服器網址").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Entry(settings, textvariable=self.server_url).grid(row=0, column=1, columnspan=3, sticky="ew", pady=5)

        ttk.Label(settings, text="LINE 視窗").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Entry(settings, textvariable=self.group_title).grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(settings, text="每日發送時間").grid(row=1, column=2, sticky="e", padx=(12, 8), pady=5)
        ttk.Entry(settings, textvariable=self.send_time, width=10).grid(row=1, column=3, sticky="w", pady=5)

        actions = ttk.Frame(settings)
        actions.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        self.start_button = ttk.Button(actions, text="開始", command=self.start_schedule)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(actions, text="停止", command=self.stop_schedule, state="disabled")
        self.stop_button.pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="預覽今日訊息", command=lambda: self.preview_date(today_text())).pack(side="left", padx=(8, 0))
        ttk.Label(actions, textvariable=self.status_text).pack(side="left", padx=(16, 0))

        resend = ttk.LabelFrame(shell, text="補發某日出勤訊息", padding=12)
        resend.pack(fill="x", pady=(0, 10))
        resend.columnconfigure(1, weight=1)

        ttk.Label(resend, text="補發日期 yyyymmdd").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(resend, textvariable=self.resend_date, width=16).grid(row=0, column=1, sticky="w")
        ttk.Button(resend, text="預覽補發", command=self.preview_resend).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(resend, text="補發至 LINE", command=self.resend).grid(row=0, column=3, padx=(8, 0))

        log_panel = ttk.LabelFrame(shell, text="系統訊息 / 預定發送訊息 / 執行記錄", padding=8)
        log_panel.pack(fill="both", expand=True)
        self.log_box = scrolledtext.ScrolledText(log_panel, height=22, wrap="word", state="disabled")
        self.log_box.pack(fill="both", expand=True)

    def log(self, category: str, message: str) -> None:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_queue.put((category, f"[{stamp}] [{category}] {message}\n"))

    def drain_log_queue(self) -> None:
        while True:
            try:
                _category, line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.root.after(250, self.drain_log_queue)

    def validate_settings(self) -> tuple[str, str, str] | None:
        try:
            server_url = normalize_server_url(self.server_url.get())
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return None
        group_title = self.group_title.get().strip()
        if not group_title:
            messagebox.showerror(APP_TITLE, "請輸入 LINE 視窗名稱")
            return None
        send_time = self.send_time.get().strip()
        try:
            datetime.datetime.strptime(send_time, "%H:%M")
        except ValueError:
            messagebox.showerror(APP_TITLE, "每日發送時間需為 HH:MM，例如 12:30")
            return None
        return server_url, group_title, send_time

    def start_schedule(self) -> None:
        settings = self.validate_settings()
        if settings is None:
            return
        server_url, group_title, send_time = settings
        save_config(server_url, group_title, send_time)
        self.server_url.set(server_url)
        self.group_title.set(group_title)
        self.send_time.set(send_time)
        self.running = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_text.set(f"排程中：每天 {send_time} 發送今日出勤")
        self.log("system", f"已開始排程，每天 {send_time} 發送到 [{group_title}]")

    def stop_schedule(self) -> None:
        self.running = False
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status_text.set("排程已停止")
        self.log("system", "已停止日常排程")

    def scheduler_tick(self) -> None:
        now = datetime.datetime.now()
        if self.running and not self.sending:
            current_time = now.strftime("%H:%M")
            current_date = now.strftime("%Y%m%d")
            if current_time == self.send_time.get().strip() and current_date not in self.sent_dates:
                self.sent_dates.add(current_date)
                ok, reason = is_working_day(now)
                if not ok:
                    self.log("system", f"{current_date} 非上學日（{reason}），略過日常推播")
                else:
                    if reason:
                        self.log("system", reason)
                    self.log("system", f"排程時間到，準備發送 {current_date} 出勤訊息")
                    self.send_for_date(current_date, scheduled=True)
            if now.strftime("%H:%M") == "23:59":
                self.sent_dates.clear()
        self.root.after(1000, self.scheduler_tick)

    def preview_resend(self) -> None:
        try:
            date_text = normalize_date(self.resend_date.get())
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.preview_date(date_text)

    def resend(self) -> None:
        try:
            date_text = normalize_date(self.resend_date.get())
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.send_for_date(date_text, scheduled=False)

    def preview_date(self, date_text: str) -> None:
        settings = self.validate_settings()
        if settings is None:
            return
        server_url, group_title, send_time = settings
        save_config(server_url, group_title, send_time)
        self.server_url.set(server_url)
        self.group_title.set(group_title)
        self.send_time.set(send_time)
        self.run_background(self.preview_worker, date_text, server_url)

    def send_for_date(self, date_text: str, scheduled: bool) -> None:
        if self.sending:
            self.log("system", "目前已有發送工作執行中，略過這次請求")
            return
        settings = self.validate_settings()
        if settings is None:
            return
        server_url, group_title, send_time = settings
        save_config(server_url, group_title, send_time)
        self.server_url.set(server_url)
        self.group_title.set(group_title)
        self.send_time.set(send_time)
        self.sending = True
        self.run_background(self.send_worker, date_text, scheduled, server_url, group_title)

    def run_background(self, target, *args) -> None:
        threading.Thread(target=target, args=args, daemon=True).start()

    def prepare_messages(self, date_text: str, server_url: str) -> list[str]:
        self.log("system", f"取得 {date_text} 出勤資料：{server_url}")
        records = fetch_attendance_records(server_url, date_text)
        write_msg_file(records)
        self.log("system", f"取得 {len(records)} 筆出勤紀錄，已更新 {MSG_FILE.name}")
        return build_messages(records, date_text)

    def preview_worker(self, date_text: str, server_url: str) -> None:
        try:
            messages = self.prepare_messages(date_text, server_url)
        except Exception as exc:
            self.log("error", f"預覽失敗：{exc}")
            return
        self.log("preview", f"{date_text} 預定發送 {len(messages)} 則訊息")
        for index, message in enumerate(messages, start=1):
            self.log("preview", f"第 {index} 則：\n{message.rstrip()}")

    def send_worker(self, date_text: str, scheduled: bool, server_url: str, group_title: str) -> None:
        try:
            messages = self.prepare_messages(date_text, server_url)
            self.log("run", f"準備發送 {date_text}，共 {len(messages)} 則，目標 [{group_title}]")
            self.send_messages(group_title, messages)
            kind = "排程" if scheduled else "補發"
            self.log("run", f"{kind}發送完成：{date_text}")
        except Exception as exc:
            self.log("error", f"發送失敗：{exc}")
        finally:
            self.sending = False

    def send_messages(self, group_title: str, messages: list[str]) -> None:
        if autoline is None:
            raise RuntimeError(f"無法載入 autoline：{AUTOLINE_IMPORT_ERROR}")
        for index, message in enumerate(messages, start=1):
            result = autoline.send(group_title, message + "\n")
            if result is None:
                self.log("system", f"LINE 視窗 [{group_title}] 可能未開啟或未找到，第 {index} 則未確認送出")
            else:
                self.log("run", f"已送出第 {index} 則訊息")
            time.sleep(0.5)
        try:
            hidden = autoline.hideWindow(group_title)
        except Exception as exc:
            self.log("system", f"隱藏 LINE 視窗時發生錯誤：{exc}")
            return
        if hidden is None:
            self.log("system", f"未找到 LINE 視窗 [{group_title}]，請確認群組視窗已開啟")

    def on_close(self) -> None:
        if self.sending:
            if not messagebox.askyesno(APP_TITLE, "目前正在發送，確定要關閉？"):
                return
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    configure_fonts(root)
    LineMsgGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
