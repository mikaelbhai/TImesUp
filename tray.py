"""TimesUp Tray Manager — system tray icon with alert scheduling and option management."""

import pystray
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import messagebox, ttk
import subprocess, os, sys, json, threading, math, winreg, re, datetime

# ── Paths ──────────────────────────────────────────────────────────────────────
INSTALL_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "TimesUp")
ALERTS_FILE = os.path.join(INSTALL_DIR, "alerts.json")

REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "TimesUpTray"

def _here():
    return os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                           else os.path.abspath(__file__))

def _find_exe(name):
    """Installed copy first, then next to the tray, then the local dist\\ build."""
    for d in (INSTALL_DIR, _here(), os.path.join(_here(), "dist")):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return os.path.join(INSTALL_DIR, name)

ALERT_EXE = _find_exe("TimesUp.exe")
STATS_EXE = _find_exe("TimesUpStats.exe")

# ── Palette ────────────────────────────────────────────────────────────────────
BG      = "#0a0a18"
PANEL   = "#10102a"
FACE    = "#16163a"
RED     = "#e94560"
RED_DIM = "#6a1530"
RED2    = "#ff6680"
AMBER   = "#ffaa00"
CYAN    = "#00e5ff"
CYAN_DIM= "#0a6a7a"
WHITE   = "#ffffff"
DIM     = "#2d2d55"
DIM2    = "#4a4a80"
DIM3    = "#8080c0"
GREEN   = "#00e676"
PF      = "Pixelify Sans"

DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

# ── Alert store ────────────────────────────────────────────────────────────────
def load_alerts():
    try:
        with open(ALERTS_FILE, encoding="utf-8") as f:
            alerts = json.load(f)
    except Exception:
        return []
    for a in alerts:                     # defaults for alerts saved by older versions
        a.setdefault("enabled", True)
        a.setdefault("sound", True)
    return alerts

def save_alerts(alerts):
    os.makedirs(INSTALL_DIR, exist_ok=True)
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2)

def mode_tags(a):
    return (["SNOOZE"] * bool(a.get("snooze")) + ["ONTOP"] * bool(a.get("ontop")) +
            ["MUTE"] * (not a.get("sound", True)))

def sched_label(a):
    s = a.get("schedule", "daily").upper()
    if a.get("schedule") == "weekly" and a.get("day"):
        s += f" {a['day']}"
    return s

# ── Task Scheduler ─────────────────────────────────────────────────────────────
# Tray-created tasks live in a \TimesUp\ folder so the uninstaller can remove
# them all; tasks made by older versions sit at the root under the bare name.
TASK_FOLDER = "\\TimesUp\\"

def _schtasks(*args):
    return subprocess.run(["schtasks", *args], capture_output=True, text=True,
                          creationflags=0x08000000)    # no console flash

def schtask_create(a):
    """Create/replace the scheduled task. Returns an error string, or None."""
    flags = (["--snooze"] * bool(a.get("snooze")) + ["--ontop"] * bool(a.get("ontop")) +
             ["--quiet"] * (not a.get("sound", True)))
    name_arg = a["name"].replace('"', "")
    tr_val = f'"{ALERT_EXE}" ' + " ".join(flags + [f'--name "{name_arg}"'])
    sc_args = ["/sc", "daily"]
    if a.get("schedule") == "weekly":
        sc_args = ["/sc", "weekly", "/d", a.get("day", "MON")]
    elif a.get("schedule") == "once":
        sc_args = ["/sc", "once"]
    r = _schtasks("/create", "/tn", TASK_FOLDER + a["name"],
                  "/tr", tr_val, *sc_args, "/st", a["time"], "/f")
    if r.returncode != 0:
        return (r.stderr or r.stdout).strip() or "schtasks failed"
    if not a.get("enabled", True):
        schtask_set_enabled(a["name"], False)
    return None

def schtask_delete(name):
    for tn in (TASK_FOLDER + name, name):
        _schtasks("/delete", "/tn", tn, "/f")

def schtask_set_enabled(name, enabled):
    for tn in (TASK_FOLDER + name, name):
        if _schtasks("/change", "/tn", tn,
                     "/enable" if enabled else "/disable").returncode == 0:
            return

# ── Next-alert calculation ─────────────────────────────────────────────────────
def next_fire(a, now=None):
    """Next datetime this alert fires, or None (disabled / once-alert already past)."""
    if not a.get("enabled", True):
        return None
    now = now or datetime.datetime.now()
    try:
        hh, mm = map(int, a["time"].split(":"))
    except Exception:
        return None
    t = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    sched = a.get("schedule", "daily")
    if sched == "once":
        return t if t > now else None
    if sched == "weekly":
        target = DAYS.index(a.get("day", "MON")) if a.get("day") in DAYS else 0
        t += datetime.timedelta(days=(target - now.weekday()) % 7)
        return t if t > now else t + datetime.timedelta(days=7)
    return t if t > now else t + datetime.timedelta(days=1)

def next_alert():
    best = None
    for a in load_alerts():
        t = next_fire(a)
        if t and (best is None or t < best[0]):
            best = (t, a)
    return best

def fmt_until(t):
    mins = max(0, int((t - datetime.datetime.now()).total_seconds() // 60))
    if mins < 60:
        return f"{mins}m"
    if mins < 24 * 60:
        return f"{mins // 60}h {mins % 60:02d}m"
    return f"{mins // (24 * 60)}d {mins // 60 % 24}h"

def status_line():
    n = next_alert()
    if not n:
        return "No upcoming alerts"
    t, a = n
    day = "" if t.date() == datetime.date.today() else t.strftime("%a ")
    return f"Next: {a['name']} at {day}{t:%H:%M} (in {fmt_until(t)})"

# ── Startup registry ───────────────────────────────────────────────────────────
def _startup_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pyw if os.path.exists(pyw) else sys.executable}" "{os.path.abspath(__file__)}"'

def is_startup_enabled():
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(k, REG_NAME)
        winreg.CloseKey(k)
        return True
    except OSError:
        return False

def set_startup(enable):
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_WRITE)
    if enable:
        winreg.SetValueEx(k, REG_NAME, 0, winreg.REG_SZ, _startup_command())
    else:
        try:
            winreg.DeleteValue(k, REG_NAME)
        except OSError:
            pass
    winreg.CloseKey(k)

# ── Tray icon image (pixel-art clock on a 16x16 grid, scaled up crisp) ─────────
def _make_icon(size=64):
    g   = 16
    img = Image.new("RGBA", (g, g), (0, 0, 0, 0))
    px  = img.load()
    c   = (g - 1) / 2
    for y in range(g):
        for x in range(g):
            d = math.hypot(x - c, y - c)
            if d <= 5.3:
                px[x, y] = (22, 22, 58, 255)
            elif d <= 7.3:
                lit = (x - c) + (y - c) < -4
                px[x, y] = (255, 102, 128, 255) if lit else (233, 69, 96, 255)
    for x, y in [(7, 3), (7, 4), (7, 5), (7, 6), (7, 7), (8, 7)]:     # minute hand
        px[x, y] = (255, 255, 255, 255)
    for x, y in [(8, 8), (9, 9), (10, 10)]:                           # hour hand
        px[x, y] = (0, 229, 255, 255)
    px[7, 8] = px[8, 7] = (0, 229, 255, 255)
    return img.resize((size, size), Image.NEAREST)

# ── Shared UI helpers ──────────────────────────────────────────────────────────
def shade(c, f):
    """Lighten (f > 0) or darken (f < 0) a hex colour by fraction f."""
    rgb = [int(c[i:i+2], 16) for i in (1, 3, 5)]
    rgb = [v + (255 - v) * f if f > 0 else v * (1 + f) for v in rgb]
    return "#{:02x}{:02x}{:02x}".format(*(int(max(0, min(255, v))) for v in rgb))

def _px_btn(parent, text, cmd, face, w=150, h=38, sh=4, bg=PANEL, ink=WHITE, size=8):
    """Pixel-art push button with a bevel. Returns the Canvas widget."""
    cv = tk.Canvas(parent, width=w, height=h, bg=bg, highlightthickness=0, cursor="hand2")
    st = {"face": face, "text": text, "ink": ink, "hover": False, "down": False}
    def draw():
        cv.delete("all")
        f   = shade(st["face"], 0.18) if st["hover"] else st["face"]
        off = sh // 2 if st["down"] else 0
        fw, fh = w - sh, h - sh
        if not st["down"]:
            cv.create_rectangle(sh, sh, w, h, fill="#000000", outline="")
        cv.create_rectangle(off, off, off + fw, off + fh, fill=f, outline="")
        cv.create_rectangle(off, off, off + fw, off + 2, fill=shade(f, 0.3), outline="")
        cv.create_rectangle(off, off + fh - 3, off + fw, off + fh,
                            fill=shade(f, -0.35), outline="")
        for x, y in ((0, 0), (fw - 2, 0), (0, fh - 2), (fw - 2, fh - 2)):
            cv.create_rectangle(off + x, off + y, off + x + 2, off + y + 2,
                                fill=bg, outline="")
        cv.create_text(off + fw // 2, off + fh // 2, text=st["text"],
                       fill=st["ink"], font=(PF, size))
    def release(e):
        st["down"] = False; draw()
        if 0 <= e.x < w and 0 <= e.y < h:
            cmd()
    cv.bind("<Enter>",           lambda e: (st.update(hover=True),  draw()))
    cv.bind("<Leave>",           lambda e: (st.update(hover=False), draw()))
    cv.bind("<ButtonPress-1>",   lambda e: (st.update(down=True),   draw()))
    cv.bind("<ButtonRelease-1>", release)
    def config(**kw):
        st.update(kw); draw()
    cv.set = config
    draw()
    return cv

def _px_check(parent, text, var, color, sub="", bg=PANEL):
    """Pixel checkbox bound to a BooleanVar, with an optional dim sub-label."""
    f  = tk.Frame(parent, bg=bg, cursor="hand2")
    cv = tk.Canvas(f, width=18, height=18, bg=bg, highlightthickness=0)
    cv.pack(side="left", padx=(0, 10))
    lab = tk.Label(f, text=text, font=(PF, 9), bg=bg, fg=color)
    lab.pack(side="left")
    sl = tk.Label(f, text=sub, font=(PF, 7), bg=bg, fg=DIM2)
    sl.pack(side="left", padx=(10, 0))
    def draw(*_):
        cv.delete("all")
        cv.create_rectangle(0, 0, 18, 18, fill=DIM, outline="")
        cv.create_rectangle(2, 2, 16, 16, fill=BG, outline="")
        if var.get():
            cv.create_rectangle(5, 5, 13, 13, fill=color, outline="")
    for w in (f, cv, lab, sl):
        w.bind("<Button-1>", lambda e: var.set(not var.get()))
    var.trace_add("write", draw)
    draw()
    return f

def _px_segmented(parent, var, options, color=CYAN, w=70, bg=PANEL):
    """Row of pixel toggle buttons acting as a radio group over a StringVar."""
    f = tk.Frame(parent, bg=bg)
    btns = {}
    def refresh(*_):
        for val, b in btns.items():
            on = var.get() == val
            b.set(face=color if on else DIM, ink=BG if on and color == CYAN else WHITE)
    for val, label in options:
        b = _px_btn(f, label, lambda v=val: var.set(v), DIM, w=w, h=28, sh=3, bg=bg,
                    ink=WHITE, size=8)
        b.pack(side="left", padx=(0, 4))
        btns[val] = b
    var.trace_add("write", refresh)
    refresh()
    return f

def _notched(cv, x1, y1, x2, y2, t, n, fill):
    for r in [(x1 + n, y1, x2 - n, y1 + t), (x1 + n, y2 - t, x2 - n, y2),
              (x1, y1 + n, x1 + t, y2 - n), (x2 - t, y1 + n, x2, y2 - n),
              (x1 + t, y1 + t, x1 + n, y1 + n), (x2 - n, y1 + t, x2 - t, y1 + n),
              (x1 + t, y2 - n, x1 + n, y2 - t), (x2 - n, y2 - n, x2 - t, y2 - t)]:
        cv.create_rectangle(*r, fill=fill, outline="")

def _style_scrollbar(widget):
    style = ttk.Style(widget)
    style.theme_use("clam")
    style.configure("Px.Vertical.TScrollbar",
                    background=DIM, troughcolor=BG, bordercolor=BG,
                    lightcolor=DIM, darkcolor=DIM, arrowcolor=DIM3,
                    gripcount=0, arrowsize=12)
    style.map("Px.Vertical.TScrollbar",
              background=[("active", DIM2), ("pressed", CYAN_DIM)])

_open_wins = {}

def _bordered_win(key, title_text, w, h):
    """Creates a themed overrideredirect Toplevel. Returns (win, inner_frame).
    Only one window per key is open at a time; reopening focuses/replaces it."""
    old = _open_wins.get(key)
    if old is not None and old.winfo_exists():
        old.destroy()

    win = tk.Toplevel(root)
    _open_wins[key] = win
    win.configure(bg=BG)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
    win.bind("<Escape>", lambda e: win.destroy())

    cv = tk.Canvas(win, width=w, height=h, bg=BG, highlightthickness=0)
    cv.pack()
    cv.create_rectangle(4, 4, w - 4, h - 4, fill=PANEL, outline="")
    _notched(cv, 0, 0, w, h, 4, 8, CYAN)
    _notched(cv, 10, 10, w - 10, h - 10, 2, 6, CYAN_DIM)

    # title bar
    tb = tk.Frame(cv, bg=FACE, cursor="fleur")
    cv.create_window(16, 16, anchor="nw", window=tb, width=w - 32, height=30)
    led = tk.Canvas(tb, width=8, height=8, bg=CYAN, highlightthickness=0)
    led.pack(side="left", padx=(10, 10))
    ttl = tk.Label(tb, text=f"TIMESUP.EXE  /  {title_text}", font=(PF, 9),
                   bg=FACE, fg=DIM3)
    ttl.pack(side="left")
    _px_btn(tb, "X", win.destroy, DIM, w=36, h=22, sh=3, bg=FACE).pack(side="right", padx=4)
    cv.create_rectangle(16, 46, w - 16, 48, fill=DIM, outline="")

    inner = tk.Frame(cv, bg=PANEL)
    cv.create_window(26, 60, anchor="nw", window=inner, width=w - 52, height=h - 82)

    drag = [0, 0]
    def start(e): drag[0] = e.x_root - win.winfo_x(); drag[1] = e.y_root - win.winfo_y()
    def move(e):  win.geometry(f"+{e.x_root - drag[0]}+{e.y_root - drag[1]}")
    for wd in (tb, ttl, led):
        wd.bind("<ButtonPress-1>", start)
        wd.bind("<B1-Motion>",     move)

    win.after(10, win.focus_force)
    return win, inner

def _heading(parent, text, color=WHITE):
    tk.Label(parent, text=text, font=(PF, 16), bg=PANEL, fg=color).pack(anchor="w")

def _label(parent, text):
    return tk.Label(parent, text=text, font=(PF, 8), bg=PANEL, fg=DIM3,
                    width=14, anchor="w")

# ── Add / Edit Alert dialog ────────────────────────────────────────────────────
def show_add_dialog(prefill=None, edit_idx=None):
    win, inner = _bordered_win(
        "alert", "ADD ALERT" if edit_idx is None else "EDIT ALERT", 560, 520)
    _heading(inner, "NEW ALERT" if edit_idx is None else "EDIT ALERT")
    tk.Frame(inner, bg=RED, height=3).pack(fill="x", pady=(6, 14))

    entry_kw = dict(bg=BG, fg=WHITE, insertbackground=CYAN, relief="flat",
                    font=(PF, 11), highlightthickness=2,
                    highlightcolor=CYAN, highlightbackground=DIM)

    pre = prefill or {}
    name_v   = tk.StringVar(value=pre.get("name", ""))
    time_v   = tk.StringVar(value=pre.get("time", "22:00"))
    sched_v  = tk.StringVar(value=pre.get("schedule", "daily"))
    day_v    = tk.StringVar(value=pre.get("day") or "MON")
    snooze_v = tk.BooleanVar(value=pre.get("snooze", False))
    ontop_v  = tk.BooleanVar(value=pre.get("ontop",  False))
    sound_v  = tk.BooleanVar(value=pre.get("sound",  True))

    def row():
        f = tk.Frame(inner, bg=PANEL); f.pack(fill="x", pady=5); return f

    f = row(); _label(f, "ALERT NAME").pack(side="left")
    name_e = tk.Entry(f, textvariable=name_v, **entry_kw)
    name_e.pack(side="left", fill="x", expand=True, ipady=4)

    # time: entry with +/- nudge buttons (arrow keys / mouse wheel also work)
    f = row(); _label(f, "TIME (24H)").pack(side="left")
    time_e = tk.Entry(f, textvariable=time_v, width=6, justify="center", **entry_kw)
    time_e.pack(side="left", ipady=4)
    def nudge(mins):
        try:
            hh, mm = map(int, time_v.get().split(":"))
        except ValueError:
            hh, mm = 22, 0
        t = (hh * 60 + mm + mins) % (24 * 60)
        time_v.set(f"{t // 60:02d}:{t % 60:02d}")
    for lbl, m in (("-15", -15), ("+15", 15), ("-1H", -60), ("+1H", 60)):
        _px_btn(f, lbl, lambda m=m: nudge(m), DIM, w=46, h=28, sh=3).pack(side="left", padx=(8 if lbl == "-15" else 3, 0))
    time_e.bind("<Up>",   lambda e: nudge(1))
    time_e.bind("<Down>", lambda e: nudge(-1))
    time_e.bind("<MouseWheel>", lambda e: nudge(5 if e.delta > 0 else -5))

    sched_row = row(); _label(sched_row, "REPEAT").pack(side="left")
    _px_segmented(sched_row, sched_v, [("daily", "DAILY"), ("weekly", "WEEKLY"), ("once", "ONCE")],
                  w=80).pack(side="left")

    day_row = row(); _label(day_row, "DAY").pack(side="left")
    _px_segmented(day_row, day_v, [(d, d) for d in DAYS], color=CYAN_DIM, w=44).pack(side="left")

    def _toggle_day(*_):
        if sched_v.get() == "weekly":
            day_row.pack(fill="x", pady=5, after=sched_row)
        else:
            day_row.pack_forget()
    sched_v.trace_add("write", _toggle_day); _toggle_day()

    tk.Frame(inner, bg=DIM, height=2).pack(fill="x", pady=(12, 10))
    _px_check(inner, "FOREVER SNOOZE", snooze_v, AMBER,
              "cancel re-alerts every 5 min").pack(fill="x", pady=3)
    _px_check(inner, "ON TOP MODE", ontop_v, CYAN,
              "fullscreen lock, blocks task-switch").pack(fill="x", pady=3)
    _px_check(inner, "PLAY TONE", sound_v, GREEN,
              "chiptune jingle when the alert opens").pack(fill="x", pady=3)

    err_v = tk.StringVar()
    tk.Label(inner, textvariable=err_v, font=(PF, 8), bg=PANEL, fg=RED,
             wraplength=480, justify="left").pack(pady=(10, 0), anchor="w")

    def on_save():
        name = name_v.get().strip()
        time = time_v.get().strip()
        if not name:
            err_v.set("Alert name cannot be empty."); return
        if re.search(r'[\\/:*?"<>|]', name):
            err_v.set('Name cannot contain  \\ / : * ? " < > |'); return
        m = re.match(r"^(\d{1,2}):(\d{2})$", time)
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            err_v.set("Time must be HH:MM in 24h format  (e.g. 22:30)"); return
        time = f"{int(m.group(1)):02d}:{m.group(2)}"

        alerts = load_alerts()
        if any(a["name"].lower() == name.lower()
               for i, a in enumerate(alerts) if i != edit_idx):
            err_v.set(f'An alert named "{name}" already exists.'); return

        alert = dict(name=name, time=time, schedule=sched_v.get(),
                     day=day_v.get() if sched_v.get() == "weekly" else "",
                     snooze=snooze_v.get(), ontop=ontop_v.get(), sound=sound_v.get(),
                     enabled=pre.get("enabled", True))
        if alert["schedule"] == "once" and next_fire(alert) is None:
            err_v.set("That time has already passed today - a ONCE alert would never fire.")
            return
        if edit_idx is not None and edit_idx < len(alerts):
            schtask_delete(alerts[edit_idx]["name"])
        err = schtask_create(alert)
        if err:
            err_v.set(f"Task Scheduler error: {err}"); return
        if edit_idx is not None and edit_idx < len(alerts):
            alerts[edit_idx] = alert
        else:
            alerts.append(alert)
        save_alerts(alerts)
        _refresh_menu()
        win.destroy()

    btn_row = tk.Frame(inner, bg=PANEL); btn_row.pack(side="bottom", anchor="e")
    lbl = "SAVE CHANGES" if edit_idx is not None else "CREATE ALERT"
    _px_btn(btn_row, "CANCEL", win.destroy, DIM, w=110).pack(side="left", padx=(0, 10))
    _px_btn(btn_row, lbl,      on_save,     RED, w=170).pack(side="left")
    win.bind("<Return>", lambda e: on_save())
    name_e.focus_set()

# ── Manage Alerts dialog ───────────────────────────────────────────────────────
def show_manage_dialog():
    win, inner = _bordered_win("manage", "MANAGE ALERTS", 680, 480)

    top = tk.Frame(inner, bg=PANEL); top.pack(fill="x")
    tk.Label(top, text="ALERTS", font=(PF, 16), bg=PANEL, fg=WHITE).pack(side="left")
    status_v = tk.StringVar(value=status_line().upper())
    tk.Label(top, textvariable=status_v, font=(PF, 8), bg=PANEL, fg=CYAN).pack(
        side="left", padx=14, pady=(6, 0))
    _px_btn(top, "+ ADD ALERT",
            lambda: (win.destroy(), root.after(50, show_add_dialog)),
            GREEN, w=130, h=32, ink=BG).pack(side="right")
    tk.Frame(inner, bg=RED, height=3).pack(fill="x", pady=(8, 10))

    _style_scrollbar(win)
    list_frame = tk.Frame(inner, bg=BG)
    list_frame.pack(fill="both", expand=True)
    sb = ttk.Scrollbar(list_frame, orient="vertical", style="Px.Vertical.TScrollbar")
    sb.pack(side="right", fill="y")
    canvas = tk.Canvas(list_frame, bg=BG, highlightthickness=0, yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.config(command=canvas.yview)
    rows = tk.Frame(canvas, bg=BG)
    rows_id = canvas.create_window((0, 0), window=rows, anchor="nw")
    rows.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(rows_id, width=e.width))
    win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 40), "units"))

    def render():
        for w in rows.winfo_children(): w.destroy()
        status_v.set(status_line().upper())
        alerts = load_alerts()
        if not alerts:
            tk.Label(rows, text="NO ALERTS YET", font=(PF, 12), bg=BG, fg=DIM2
                     ).pack(pady=(60, 4))
            tk.Label(rows, text="click  + ADD ALERT  to schedule your first one",
                     font=(PF, 8), bg=BG, fg=DIM2).pack()
            return
        for i, a in enumerate(alerts):
            on   = a.get("enabled", True)
            bg   = PANEL if i % 2 == 0 else FACE
            row  = tk.Frame(rows, bg=bg); row.pack(fill="x", pady=(0, 2))
            tk.Frame(row, bg=(RED if on else DIM), width=4).pack(side="left", fill="y")
            tk.Label(row, text=a["time"], font=(PF, 16), bg=bg,
                     fg=CYAN if on else DIM2, width=5).pack(side="left", padx=(8, 6), pady=6)
            info = tk.Frame(row, bg=bg); info.pack(side="left", fill="x", expand=True)
            tk.Label(info, text=a["name"][:30], font=(PF, 10), bg=bg,
                     fg=WHITE if on else DIM2, anchor="w").pack(fill="x")
            meta = tk.Frame(info, bg=bg); meta.pack(fill="x")
            tk.Label(meta, text=sched_label(a), font=(PF, 7), bg=bg, fg=DIM3
                     ).pack(side="left")
            for tag in mode_tags(a):
                col = {"SNOOZE": AMBER, "ONTOP": CYAN}.get(tag, DIM3)
                tk.Label(meta, text=f" {tag} ", font=(PF, 6), bg=shade(col, -0.7),
                         fg=col).pack(side="left", padx=(6, 0))
            nf = next_fire(a)
            tk.Label(meta, text=(f"in {fmt_until(nf)}" if nf else
                                 "disabled" if not on else "done"),
                     font=(PF, 7), bg=bg, fg=GREEN if nf else DIM2
                     ).pack(side="left", padx=(10, 0))

            def _del(idx=i, btn=None):
                # two-click confirm
                if not btn.armed:
                    btn.armed = True
                    btn.set(text="SURE?", face=RED)
                    root.after(2500, lambda: btn.winfo_exists() and
                               (setattr(btn, "armed", False),
                                btn.set(text="DELETE", face=RED_DIM)))
                    return
                al = load_alerts()
                if idx < len(al):
                    schtask_delete(al[idx]["name"]); al.pop(idx)
                    save_alerts(al); _refresh_menu(); render()

            def _edit(idx=i):
                al = load_alerts()
                if idx < len(al):
                    win.destroy()
                    root.after(50, lambda a=al[idx], j=idx: show_add_dialog(a, j))

            def _toggle(idx=i):
                al = load_alerts()
                if idx < len(al):
                    al[idx]["enabled"] = not al[idx].get("enabled", True)
                    schtask_set_enabled(al[idx]["name"], al[idx]["enabled"])
                    save_alerts(al); _refresh_menu(); render()

            holder = []
            d = _px_btn(row, "DELETE", lambda idx=i, h=holder: _del(idx, h[0]),
                        RED_DIM, w=70, h=28, sh=3, bg=bg)
            d.armed = False
            holder.append(d)
            d.pack(side="right", padx=(2, 8))
            _px_btn(row, "EDIT", _edit, DIM2, w=56, h=28, sh=3, bg=bg).pack(side="right", padx=2)
            _px_btn(row, "ON" if on else "OFF", _toggle, GREEN if on else DIM,
                    w=48, h=28, sh=3, bg=bg, ink=BG if on else DIM3).pack(side="right", padx=2)

    render()

# ── Tray actions ───────────────────────────────────────────────────────────────
_icon_ref = [None]

def _refresh_menu():
    ic = _icon_ref[0]
    if ic:
        ic.menu  = _build_menu()
        ic.title = f"TimesUp!  -  {status_line()}"
        ic.update_menu()

def _tick():
    _refresh_menu()                      # keep the "in Xm" countdown fresh
    root.after(30_000, _tick)

def _launch(path, *args):
    if os.path.exists(path):
        # fresh PyInstaller environment so the child doesn't touch our _MEI dir
        subprocess.Popen([path, *args],
                         env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"))
    else:
        messagebox.showwarning("TimesUp", f"Not found:\n{path}\n\nRun setup.bat to build/install.")

def _open_stats(_=None, __=None):
    _launch(STATS_EXE)

def _test_alert(*args):
    _launch(ALERT_EXE, "--name", "Test", *args)

def _toggle_startup(icon, item):
    set_startup(not is_startup_enabled()); _refresh_menu()

def _exit(icon, item):
    icon.stop(); root.after(0, root.destroy)

def _build_menu():
    alerts = load_alerts()
    items  = []
    for i, a in enumerate(alerts):
        tags  = mode_tags(a)
        sfx   = f"  [{'+'.join(tags)}]" if tags else ""
        label = f"{a['time']}  {a['name']}  ({sched_label(a)}){sfx}"

        def _make_edit(idx):
            def cb(ic, it):
                al = load_alerts()
                if idx < len(al):
                    root.after(0, lambda a=al[idx], j=idx: show_add_dialog(a, j))
            return cb

        def _make_toggle(idx):
            def cb(ic, it):
                al = load_alerts()
                if idx < len(al):
                    al[idx]["enabled"] = not al[idx].get("enabled", True)
                    schtask_set_enabled(al[idx]["name"], al[idx]["enabled"])
                    save_alerts(al); _refresh_menu()
            return cb

        def _make_del(idx):
            def cb(ic, it):
                al = load_alerts()
                if idx < len(al):
                    schtask_delete(al[idx]["name"]); al.pop(idx)
                    save_alerts(al); _refresh_menu()
            return cb

        items.append(pystray.MenuItem(label, pystray.Menu(
            pystray.MenuItem("Enabled",  _make_toggle(i),
                             checked=lambda item, en=a.get("enabled", True): en),
            pystray.MenuItem("Edit...",  _make_edit(i)),
            pystray.MenuItem("Delete",   _make_del(i)),
        )))

    if not items:
        items = [pystray.MenuItem("(no alerts — click Add Alert)", None, enabled=False)]

    return pystray.Menu(
        pystray.MenuItem("TimesUp!", None, enabled=False),
        pystray.MenuItem(status_line(), None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Add Alert...",     lambda ic, it: root.after(0, show_add_dialog),
                         default=True),
        pystray.MenuItem("Manage Alerts...", lambda ic, it: root.after(0, show_manage_dialog)),
        pystray.MenuItem("Scheduled Alerts", pystray.Menu(*items)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Stats & Log",      lambda ic, it: root.after(0, _open_stats)),
        pystray.MenuItem("Test Alert", pystray.Menu(
            pystray.MenuItem("Standard",       lambda ic, it: root.after(0, _test_alert)),
            pystray.MenuItem("On Top (lock)",  lambda ic, it: root.after(0, _test_alert, "--ontop")),
            pystray.MenuItem("Silent",         lambda ic, it: root.after(0, _test_alert, "--quiet")),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start with Windows", _toggle_startup,
                         checked=lambda item: is_startup_enabled()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", _exit),
    )

# ── Font ───────────────────────────────────────────────────────────────────────
def _load_font():
    try:
        import base64, ctypes, tempfile
        _ns = {}
        exec(open(os.path.join(getattr(sys, "_MEIPASS", None) or _here(),
                               "font_data.py")).read(), _ns)
        _b = base64.b64decode(_ns["FONT_B64"])
        _tmp = os.path.join(tempfile.gettempdir(), "PixelifySans_tu.ttf")
        with open(_tmp, "wb") as _f:
            _f.write(_b)
        ctypes.windll.gdi32.AddFontResourceW(_tmp)
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)
        root.tk.call("font", "families")
    except Exception:
        pass

# ── Main ───────────────────────────────────────────────────────────────────────
root = None

def main():
    global root
    root = tk.Tk()
    root.withdraw()
    _load_font()

    icon = pystray.Icon("TimesUp", _make_icon(64),
                        f"TimesUp!  -  {status_line()}", _build_menu())
    _icon_ref[0] = icon

    threading.Thread(target=icon.run, daemon=True).start()
    root.after(30_000, _tick)
    root.mainloop()
    icon.stop()

if __name__ == "__main__":
    main()
