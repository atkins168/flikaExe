# -*- coding: utf-8 -*-
"""
Flika 通用启动器 (Python 原生 tkinter 启动界面 + pywebview 内嵌浏览器显示 Flika)。
逻辑：
  1) 端口 1420 已有服务 -> 直接用 pywebview 显示 Flika；
  2) 否则定位项目目录：配置文件(flikaExe.json) -> exe 当前目录 -> tkinter 目录选择框；
  3) tkinter 启动器显示进度条，30 秒未就绪报错（可重选目录 / 退出）；
  4) 就绪后切到 pywebview 显示 Flika，关窗时停掉本次启动的服务，并回写 flikaExe.json。
"""
import os
import sys
import time
import socket
import subprocess
import threading
import json
import ctypes
import webview
import tkinter as tk
from tkinter import ttk, filedialog

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

PORT = 1420
URL = "http://localhost:%d/" % PORT
TIMEOUT_SEC = 30

# Windows 下隐藏子进程(如 taskkill/netstat)弹出的命令行窗口
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

if getattr(sys, "frozen", False):
    # 冻结(exe)模式：onefile 下 sys.executable 可能在解压临时目录，
    # 这里尝试取真实 exe 目录，避免配置/日志写到临时目录被系统清理。
    BASE = os.path.dirname(os.path.abspath(sys.executable))
    try:
        if sys.argv and os.path.isfile(sys.argv[0]):
            alt = os.path.dirname(os.path.abspath(sys.argv[0]))
            if os.path.normcase(alt) != os.path.normcase(BASE):
                BASE = alt
    except Exception:
        pass
else:
    BASE = os.path.dirname(os.path.abspath(__file__))

# 配置/日志用相对路径，落在"进程工作目录"(用户双击 exe 时 = exe 所在目录)。
# 关键：不要 os.chdir(BASE) —— onefile 下 BASE 是临时解压目录，
# 一旦 chdir 过去，配置/日志就会写进临时目录被系统清理、永远读不到。
CONFIG_FILE = "flikaExe.json"
LOG_FILE = "flika_gui.log"

SYS_NODE_DIR = r"C:\Program Files\nodejs"
if os.name == "nt" and os.path.isdir(SYS_NODE_DIR):
    os.environ["PATH"] = SYS_NODE_DIR + os.pathsep + os.environ.get("PATH", "")


def log(m):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%H:%M:%S"), m))
    except Exception:
        pass


def center_xy(w, h):
    try:
        u = ctypes.windll.user32
        sw = u.GetSystemMetrics(0)
        sh = u.GetSystemMetrics(1)
        return max(0, (sw - w) // 2), max(0, (sh - h) // 2)
    except Exception:
        return None, None


def port_listening():
    for host in ("::1", "127.0.0.1"):
        try:
            fam = socket.AF_INET6 if ":" in host else socket.AF_INET
            s = socket.socket(fam, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((host, PORT))
            s.close()
            return True
        except Exception:
            try:
                s.close()
            except Exception:
                pass
    return False


def is_flika_env(d):
    return (os.path.isfile(os.path.join(d, "package.json"))
            and os.path.isdir(os.path.join(d, "node_modules")))


def load_config():
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            p = d.get("flika_dir") or d.get("project_dir")
            if p and is_flika_env(p):
                return p
    except Exception:
        pass
    return None


def save_config(proj):
    """回写配置：文件不存在则创建，存在则读取后更新 flika_dir（保留其他字段）。"""
    try:
        d = os.path.dirname(CONFIG_FILE)
        if d:
            os.makedirs(d, exist_ok=True)
        data = {}
        if os.path.isfile(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
            except Exception:
                data = {}
        data["flika_dir"] = proj
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log("config saved -> %s (flika_dir=%s)" % (CONFIG_FILE, proj))
        return True
    except Exception as e:
        log("save_config error: %s" % e)
        return False


def stop_port_service():
    pids = set()
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True,
                             text=True, encoding="utf-8",
                             creationflags=CREATE_NO_WINDOW).stdout
        for line in out.splitlines():
            if ":1420" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    pid = parts[-1]
                    if pid.isdigit():
                        pids.add(int(pid))
        for pid in pids:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True, creationflags=CREATE_NO_WINDOW)
    except Exception:
        pass
    return pids


class Launcher:
    """tkinter 启动器：进度条 + 状态 + 选目录/重试/退出。"""

    def __init__(self, proj):
        self.proj = proj
        self.proc = None
        self.started = False
        self.state = "starting" if proj else "need_dir"
        self.progress = 0
        self.error = ""

        self.root = tk.Tk()
        self.root.title("Flika 启动器")
        self.root.configure(bg="#f2f3f5")
        xy = center_xy(440, 260)
        self.root.geometry("440x260+%s+%s" % (xy[0] or 0, xy[1] or 0))
        self.root.resizable(False, False)

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Horizontal.TProgressbar", troughcolor="#e8eaed",
                        background="#40A3F2", thickness=12, borderwidth=0)
        style.configure("Blue.TButton", font=("Microsoft YaHei", 11), padding=8,
                        background="#40A3F2", foreground="white")
        style.map("Blue.TButton", background=[("active", "#358ed6"),
                                              ("pressed", "#2f85c9")])
        style.configure("Gray.TButton", font=("Microsoft YaHei", 11), padding=8,
                        background="#eef0f4", foreground="#333333")
        style.map("Gray.TButton", background=[("active", "#e2e5ec")])

        title = tk.Label(self.root, text="Flika 启动器",
                         font=("Microsoft YaHei", 18, "bold"),
                         bg="#f2f3f5", fg="#1a1a1a")
        title.pack(pady=(22, 4))

        self.status = tk.Label(self.root, text="",
                               font=("Microsoft YaHei", 11), bg="#f2f3f5", fg="#666666")
        self.status.pack(pady=4)

        self.bar = ttk.Progressbar(self.root, maximum=100)
        self.bar.pack(fill=tk.X, padx=40, pady=8)
        self.pct = tk.Label(self.root, text="0%", font=("Microsoft YaHei", 10),
                            bg="#f2f3f5", fg="#888888")
        self.pct.pack()

        self.err = tk.Label(self.root, text="", fg="#d33", font=("Microsoft YaHei", 10),
                            wraplength=380, bg="#f2f3f5")
        self.err.pack(pady=2)

        self.btn_frame = tk.Frame(self.root, bg="#f2f3f5")
        self.btn_frame.pack(pady=10)
        self.choose_btn = ttk.Button(self.btn_frame, text="选择项目目录", style="Blue.TButton",
                                     width=16, command=self.choose)
        self.retry_btn = ttk.Button(self.btn_frame, text="重新选择目录", style="Blue.TButton",
                                    width=16, command=self.choose)
        self.quit_btn = ttk.Button(self.btn_frame, text="退出", style="Gray.TButton",
                                   width=8, command=self.root.destroy)

        if proj:
            self.start(proj)
        self.poll_ui()
        self.root.mainloop()

    def start(self, proj):
        log("start npm run dev in %s" % proj)
        self.state = "starting"
        self.progress = 0
        self.proc = subprocess.Popen(
            "npm run dev", cwd=proj, shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW)
        self.started = True
        threading.Thread(target=self._wait, daemon=True).start()

    def _wait(self):
        steps = TIMEOUT_SEC * 2
        for i in range(steps):
            self.progress = min(int(i / steps * 100), 99)
            if port_listening():
                self.progress = 100
                self.state = "ready"
                log("port ready after ~%ds" % (i / 2))
                return
            if self.proc is not None and self.proc.poll() is not None:
                self.state = "error"
                self.error = "npm run dev 启动失败（退出码 %s）" % self.proc.returncode
                log(self.error)
                return
            time.sleep(0.5)
        self.state = "error"
        self.error = "30 秒内服务未启动，请检查项目目录是否正确"
        log(self.error)

    def poll_ui(self):
        self.bar["value"] = self.progress
        self.pct["text"] = "%d%%" % self.progress
        if self.state == "ready":
            self.status["text"] = "服务已就绪，正在打开 Flika..."
            self.root.after(300, self._done)
            return
        if self.state == "error":
            self.status["text"] = "启动失败"
            self.err["text"] = self.error
            self.choose_btn.pack_forget()
            self.retry_btn.pack(side=tk.LEFT, padx=4)
            self.quit_btn.pack(side=tk.LEFT, padx=4)
            return
        if self.state == "need_dir":
            self.status["text"] = "未找到 Flika 项目，请选择项目目录"
            self.choose_btn.pack(side=tk.LEFT, padx=4)
            self.quit_btn.pack(side=tk.LEFT, padx=4)
            return
        # starting
        self.status["text"] = "正在启动服务，请稍候..."
        self.root.after(300, self.poll_ui)

    def _done(self):
        self.root.destroy()

    def choose(self):
        d = filedialog.askdirectory(title="请选择 Flika 项目目录（含 package.json）")
        if d and is_flika_env(d):
            self.proj = d
            save_config(d)
            self.err["text"] = ""
            self.start(d)
            self.root.after(300, self.poll_ui)
        else:
            self.err["text"] = "所选目录无效或未选择"
            self.root.after(300, self.poll_ui)


def show_flika():
    xy = center_xy(1280, 800)
    kw = dict(width=1280, height=800, min_size=(960, 640))
    if xy[0] is not None:
        kw.update(x=xy[0], y=xy[1])
    # on_top: 窗口保持置顶，避免启动后被其他窗口遮挡，需点任务栏切回
    webview.create_window("Flika", URL, on_top=True, **kw)
    webview.start()


def main():
    log("=== Flika GUI start, base=%s ===" % BASE)

    # 1) 定位项目目录：配置文件 -> exe 当前目录
    proj = load_config()
    if proj:
        log("found env from config: %s" % proj)
    elif is_flika_env(os.getcwd()):
        proj = os.getcwd()
        log("found env in cwd: %s" % os.getcwd())
    else:
        log("no project dir, waiting for user choice")

    launcher = None
    # 2) 端口已有服务 -> 直接复用显示；否则走 tkinter 启动器（选目录/启动服务）
    if port_listening():
        log("service already listening on %d -> reuse" % PORT)
        show_flika()
    else:
        launcher = Launcher(proj)
        if port_listening():
            show_flika()

    # 3) 关闭窗口后统一回写配置：不存在则创建，存在则更新（记录定位/选择的目录）
    chosen = launcher.proj if launcher else proj
    if chosen:
        save_config(chosen)
        log("config re-written on close: %s" % chosen)
    else:
        log("no project dir, config not written on close")

    # 4) 停掉本次启动的服务，并释放 1420 端口
    if launcher is not None and launcher.started and launcher.proc is not None \
            and launcher.proc.poll() is None:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(launcher.proc.pid)],
                       capture_output=True, creationflags=CREATE_NO_WINDOW)
    stop_port_service()
    log("=== Flika GUI exit ===")


if __name__ == "__main__":
    main()
