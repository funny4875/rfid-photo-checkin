from __future__ import annotations

import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
VERSION_FILE = ROOT_DIR / "VERSION"
PHOTO_DIR_FILE = BASE_DIR / "照片資料夾.txt"


def app_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0"


def ensure_photo_dir_file() -> None:
    if not PHOTO_DIR_FILE.exists():
        PHOTO_DIR_FILE.write_text("ccsh_data\n", encoding="utf-8")


def photo_dir_text() -> str:
    ensure_photo_dir_file()
    value = PHOTO_DIR_FILE.read_text(encoding="utf-8-sig").strip()
    return value or "ccsh_data"


class ServerGui:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.process: subprocess.Popen[str] | None = None
        self.status_var = tk.StringVar(value="已停止")
        self.photo_dir_var = tk.StringVar(value=photo_dir_text())

        root.title("門禁網頁伺服器")
        root.geometry("520x300")
        root.minsize(460, 260)
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

        photo_row = tk.Frame(frame)
        photo_row.pack(fill="x", pady=(0, 16))
        tk.Label(photo_row, text="照片資料夾", width=10, anchor="w").pack(side="left")
        tk.Label(photo_row, textvariable=self.photo_dir_var, anchor="w", fg="#0d5f59").pack(
            side="left", fill="x", expand=True
        )

        buttons = tk.Frame(frame)
        buttons.pack(fill="x", pady=(4, 12))
        self.start_button = tk.Button(buttons, text="啟動", width=12, command=self.start_server)
        self.start_button.pack(side="left", padx=(0, 10))
        self.stop_button = tk.Button(buttons, text="停止", width=12, command=self.stop_server, state="disabled")
        self.stop_button.pack(side="left")

        hint = tk.Label(
            frame,
            text="照片資料夾可在 server\\照片資料夾.txt 設定，修改後請停止再啟動伺服器。",
            fg="#60717e",
            anchor="w",
            justify="left",
            wraplength=460,
        )
        hint.pack(fill="x", pady=(6, 0))

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
        ensure_photo_dir_file()
        self.photo_dir_var.set(photo_dir_text())
        self.process = subprocess.Popen(
            [sys.executable, "app.py"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0,
        )
        self.status_var.set("執行中：http://0.0.0.0:5000")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.append_log("伺服器已啟動")
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
            self.root.after(1000, self.watch_process)
            return
        self.set_stopped("已停止")

    def set_stopped(self, text: str) -> None:
        self.status_var.set(text)
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

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
