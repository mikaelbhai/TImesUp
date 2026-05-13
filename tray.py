"""TimesUp Tray Manager — system tray icon with alert scheduling and option management."""

import pystray
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import messagebox
import subprocess, os, sys, json, threading, math, winreg, re, datetime

# ── Paths ──────────────────────────────────────────────────────────────────────
INSTALL_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "TimesUp")
ALERT_EXE   = os.path.join(INSTALL_DIR, "TimesUp.exe")
STATS_EXE   = os.path.join(INSTALL_DIR, "TimesUpStats.exe")
ALERTS_FILE = os.path.join(INSTALL_DIR, "alerts.json")

REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "TimesUpTray"

# ── Palette ────────────────────────────────────────────────────────────────────
BG      = "#0a0a18"
PANEL   = "#10102a"
RED     = "#e94560"
RED_DIM = "#6a1530"
RED2    = "#ff6680"
AMBER   = "#ffaa00"
CYAN    = "#00e5ff"
WHITE   = "#ffffff"
DIM     = "#2d2d55"
DIM2    = "#4a4a80"
GREEN   = "#00e676"
PF      = "Pixelify Sans"

# ── Alert store ────────────────────────────────────────────────────────────────
def load_alerts():
    try:
        with open(ALERTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_alerts(alerts):
    os.makedirs(INSTALL_DIR, exist_ok=True)
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2)

# ── Task Scheduler ─────────────────────────────────────────────────────────────
def schtask_create(a):
    flags  = ("--snooze " if a.get("snooze") else "") + ("--ontop" if a.get("ontop") else "")
    flags  = flags.strip()
    tr_val = f'"{ALERT_EXE}"' + (f" {flags}" if flags else "")
    sc_args = ["/sc", "daily"]
    if a.get("schedule") == "weekly":
        sc_args = ["/sc", "weekly", "/d", a.get("day", "MON")]
    elif a.get("schedule") == "once":
        sc_args = ["/sc", "once"]
    subprocess.run(
        ["schtasks", "/create", "/tn", a["name"],
         "/tr", tr_val, *sc_args, "/st", a["time"], "/f"],
        capture_output=True)

def schtask_delete(name):
    subprocess.run(["schtasks", "/delete", "/tn", name, "/f"], capture_output=True)

# ── Startup registry ───────────────────────────────────────────────────────────
def _tray_exe_path():
    return sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)

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
        winreg.SetValueEx(k, REG_NAME, 0, winreg.REG_SZ, f'"{_tray_exe_path()}"')
    else:
        try:
            winreg.DeleteValue(k, REG_NAME)
        except OSError:
            pass
    winreg.CloseKey(k)

# ── Tray icon image (pixel art clock, drawn with Pillow) ───────────────────────
def _make_icon(size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    cx = cy = size // 2
    r  = size // 2 - 2
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(10, 10, 24))
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(233, 69, 96), width=7)
    for a_deg, length, color, w in [
        (300, r-14, (0, 229, 255), 3),   # hour hand  ~10 o'clock
        (0,   r-7,  (255,255,255), 2),   # minute hand ~12 o'clock
    ]:
        a = math.radians(a_deg - 90)
        d.line([cx, cy, cx + int(length*math.cos(a)), cy + int(length*math.sin(a))],
               fill=color, width=w)
    d.ellipse([cx-3, cy-3, cx+3, cy+3], fill=(0, 229, 255))
    return img

# ── Shared UI helpers ──────────────────────────────────────────────────────────
def _px_btn(parent, text, cmd, face, w=150, h=38, sh=4):
    """Pixel-art push button. Returns the Canvas widget."""
    cv = tk.Canvas(parent, width=w, height=h, bg=PANEL, highlightthickness=0)
    def _r(c, dx=0, dy=0):
        r2, g2, b2 = int(c[1:3],16)+dx, int(c[3:5],16)+dy, int(c[5:7],16)+dx
        return "#{:02x}{:02x}{:02x}".format(
            min(max(r2,0),255), min(max(g2,0),255), min(max(b2,0),255))
    hover = _r(face, 36, 36)
    def draw(fill):
        cv.delete("all")
        cv.create_rectangle(sh, sh, w, h,    fill="#000000", outline="")
        cv.create_rectangle(0,  0,  w-sh, h-sh, fill=fill,  outline="")
        cv.create_rectangle(0, 0, 4, 4, fill=PANEL, outline="")
        cv.create_rectangle(w-sh-4, h-sh-4, w-sh, h-sh, fill=PANEL, outline="")
        cv.create_text((w-sh)//2, (h-sh)//2, text=text, fill=WHITE, font=(PF, 8))
    draw(face)
    cv.bind("<Enter>",           lambda e: draw(hover))
    cv.bind("<Leave>",           lambda e: draw(face))
    cv.bind("<ButtonPress-1>",   lambda e: cv.move("all", sh//2, sh//2))
    cv.bind("<ButtonRelease-1>", lambda e: (cv.move("all", -(sh//2), -(sh//2)), cmd()))
    return cv

def _add_drag(win, *widgets):
    drag = [0, 0]
    def start(e): drag[0]=e.x_root-win.winfo_x(); drag[1]=e.y_root-win.winfo_y()
    def move(e):  win.geometry(f"+{e.x_root-drag[0]}+{e.y_root-drag[1]}")
    for w in widgets:
        w.bind("<ButtonPress-1>", start)
        w.bind("<B1-Motion>",     move)

def _bordered_win(title_text, w, h):
    """Creates a themed overrideredirect Toplevel. Returns (win, inner_frame)."""
    win = tk.Toplevel(root)
    win.configure(bg=BG)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    cv = tk.Canvas(win, width=w, height=h, bg=BG, highlightthickness=0)
    cv.pack()
    for i in range(5):
        cv.create_rectangle(i, i, w-1-i, h-1-i, outline=CYAN if i%2==0 else BG)

    panel = tk.Frame(cv, bg=PANEL)
    panel.place(x=5, y=5, width=w-10, height=h-10)

    hdr = tk.Frame(panel, bg=PANEL)
    hdr.pack(fill="x", padx=14, pady=(12, 0))
    tk.Label(hdr, text=title_text, font=(PF, 13), bg=PANEL, fg=WHITE).pack(side="left")
    _px_btn(hdr, "✕ CLOSE", win.destroy, DIM, w=80, h=26, sh=3).pack(side="right")
    tk.Frame(panel, bg=RED, height=2).pack(fill="x", padx=14, pady=(6, 10))

    inner = tk.Frame(panel, bg=PANEL)
    inner.pack(fill="both", expand=True, padx=14, pady=(0, 12))

    _add_drag(win, cv, panel, hdr)
    return win, inner

# ── Add / Edit Alert dialog ────────────────────────────────────────────────────
def show_add_dialog(prefill=None, edit_idx=None):
    win, inner = _bordered_win(
        "ADD ALERT" if edit_idx is None else "EDIT ALERT", 490, 460)

    entry_kw = dict(bg=BG, fg=WHITE, insertbackground=WHITE, relief="flat",
                    font=(PF, 9), highlightthickness=1,
                    highlightcolor=CYAN, highlightbackground=DIM)

    def field(label, var, widget_fn):
        f = tk.Frame(inner, bg=PANEL); f.pack(fill="x", pady=3)
        tk.Label(f, text=label, font=(PF, 8), bg=PANEL, fg=DIM2,
                 width=16, anchor="w").pack(side="left")
        widget_fn(f, var).pack(side="left", fill="x", expand=True)

    pre = prefill or {}
    name_v  = tk.StringVar(value=pre.get("name", ""))
    time_v  = tk.StringVar(value=pre.get("time", "22:00"))
    sched_v = tk.StringVar(value=pre.get("schedule", "daily"))
    day_v   = tk.StringVar(value=pre.get("day", "MON"))
    snooze_v = tk.BooleanVar(value=pre.get("snooze", False))
    ontop_v  = tk.BooleanVar(value=pre.get("ontop",  False))

    field("Alert name",    name_v,  lambda f,v: tk.Entry(f, textvariable=v, **entry_kw))
    field("Time (HH:MM)",  time_v,  lambda f,v: tk.Entry(f, textvariable=v, **entry_kw))

    # schedule row
    sf = tk.Frame(inner, bg=PANEL); sf.pack(fill="x", pady=3)
    tk.Label(sf, text="Schedule", font=(PF, 8), bg=PANEL, fg=DIM2,
             width=16, anchor="w").pack(side="left")
    for val, lbl in [("daily","Daily"),("weekly","Weekly"),("once","Once")]:
        tk.Radiobutton(sf, text=lbl, variable=sched_v, value=val,
                       font=(PF, 8), bg=PANEL, fg=WHITE,
                       selectcolor=DIM, activebackground=PANEL,
                       activeforeground=WHITE).pack(side="left", padx=4)

    # day of week (weekly only)
    df = tk.Frame(inner, bg=PANEL); df.pack(fill="x", pady=3)
    tk.Label(df, text="Day of week", font=(PF, 8), bg=PANEL, fg=DIM2,
             width=16, anchor="w").pack(side="left")
    day_om = tk.OptionMenu(df, day_v, "MON","TUE","WED","THU","FRI","SAT","SUN")
    day_om.config(bg=DIM, fg=WHITE, font=(PF, 8), highlightthickness=0, relief="flat",
                  activebackground=DIM2)
    day_om["menu"].config(bg=DIM, fg=WHITE, font=(PF, 8))
    day_om.pack(side="left")

    def _toggle_day(*_):
        if sched_v.get() == "weekly": day_om.pack(side="left")
        else:                         day_om.pack_forget()
    sched_v.trace_add("write", _toggle_day); _toggle_day()

    # mode checkboxes
    tk.Frame(inner, bg=DIM, height=1).pack(fill="x", pady=(8, 6))
    ck = tk.Frame(inner, bg=PANEL); ck.pack(fill="x")
    chk_kw = dict(bg=PANEL, activebackground=PANEL, selectcolor=DIM,
                  font=(PF, 8), anchor="w")
    tk.Checkbutton(ck, text="  Forever Snooze  — re-alerts every 5 min on cancel",
                   variable=snooze_v, fg=AMBER, activeforeground=AMBER,
                   **chk_kw).pack(fill="x")
    tk.Checkbutton(ck, text="  On Top Mode     — fullscreen lock, blocks task-switch",
                   variable=ontop_v,  fg=CYAN,  activeforeground=CYAN,
                   **chk_kw).pack(fill="x")

    err_v = tk.StringVar()
    tk.Label(inner, textvariable=err_v, font=(PF, 7), bg=PANEL, fg=RED).pack(pady=(6,0))

    def on_save():
        name = name_v.get().strip()
        time = time_v.get().strip()
        if not name:
            err_v.set("Alert name cannot be empty."); return
        if not re.match(r"^[0-2]\d:[0-5]\d$", time):
            err_v.set("Time must be HH:MM  (e.g. 22:30)"); return

        alert = dict(name=name, time=time, schedule=sched_v.get(),
                     day=day_v.get() if sched_v.get()=="weekly" else "",
                     snooze=snooze_v.get(), ontop=ontop_v.get())
        alerts = load_alerts()
        if edit_idx is not None:
            schtask_delete(alerts[edit_idx]["name"])
            alerts[edit_idx] = alert
        else:
            alerts.append(alert)
        save_alerts(alerts)
        schtask_create(alert)
        _refresh_menu()
        win.destroy()

    btn_row = tk.Frame(inner, bg=PANEL); btn_row.pack(pady=(12,0))
    lbl = "SAVE CHANGES" if edit_idx is not None else "CREATE ALERT"
    _px_btn(btn_row, lbl,      on_save,      RED,  w=160).pack(side="left", padx=6)
    _px_btn(btn_row, "CANCEL", win.destroy,  DIM,  w=110).pack(side="left", padx=6)

# ── Manage Alerts dialog ───────────────────────────────────────────────────────
def show_manage_dialog():
    win, inner = _bordered_win("MANAGE ALERTS", 620, 440)

    add_btn = _px_btn(inner, "+ ADD ALERT", lambda: (win.destroy(), root.after(50, show_add_dialog)),
                      GREEN, w=120, h=28, sh=3)
    add_btn.pack(anchor="e", pady=(0, 8))

    list_frame = tk.Frame(inner, bg=BG)
    list_frame.pack(fill="both", expand=True)

    sb = tk.Scrollbar(list_frame, bg=DIM, troughcolor=BG, width=10, relief="flat")
    sb.pack(side="right", fill="y")
    canvas = tk.Canvas(list_frame, bg=BG, highlightthickness=0, yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.config(command=canvas.yview)
    rows = tk.Frame(canvas, bg=BG)
    canvas.create_window((0,0), window=rows, anchor="nw")
    rows.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    def render():
        for w in rows.winfo_children(): w.destroy()
        alerts = load_alerts()
        if not alerts:
            tk.Label(rows, text="  No alerts yet — click + ADD ALERT above.",
                     font=(PF, 8), bg=BG, fg=DIM2, pady=20).pack()
            return
        tk.Label(rows,
                 text=f"  {'TIME':<7}{'NAME':<22}{'SCHED':<14}{'MODES'}",
                 font=(PF, 7), bg=BG, fg=DIM2).pack(fill="x")
        tk.Frame(rows, bg=DIM, height=1).pack(fill="x")
        for i, a in enumerate(alerts):
            modes = "+".join(m.upper() for m in
                             (["SNOOZE"]*a.get("snooze",False) +
                              ["ONTOP"]*a.get("ontop",False)))
            sched = a.get("schedule","daily").upper()
            if a.get("schedule")=="weekly" and a.get("day"):
                sched += f" {a['day']}"
            row = tk.Frame(rows, bg=PANEL if i%2==0 else BG)
            row.pack(fill="x", pady=1)
            tk.Label(row,
                     text=f"  {a['time']:<7}{a['name'][:20]:<22}{sched:<14}{modes}",
                     font=(PF, 8), bg=row["bg"], fg=WHITE, anchor="w"
                     ).pack(side="left", fill="x", expand=True)

            def _del(idx=i):
                al = load_alerts()
                if idx < len(al):
                    schtask_delete(al[idx]["name"]); al.pop(idx)
                    save_alerts(al); _refresh_menu(); render()

            def _edit(idx=i):
                al = load_alerts()
                if idx < len(al):
                    win.destroy()
                    root.after(50, lambda a=al[idx], j=idx: show_add_dialog(a, j))

            _px_btn(row, "EDIT",   lambda idx=i: _edit(idx), DIM2,  w=56, h=24, sh=3).pack(side="right", padx=2, pady=2)
            _px_btn(row, "DELETE", lambda idx=i: _del(idx),  RED_DIM, w=66, h=24, sh=3).pack(side="right", padx=2, pady=2)

    render()

# ── Tray actions ───────────────────────────────────────────────────────────────
_icon_ref = [None]

def _refresh_menu():
    if _icon_ref[0]:
        _icon_ref[0].menu = _build_menu()
        _icon_ref[0].update_menu()

def _open_stats(_=None, __=None):
    if os.path.exists(STATS_EXE): subprocess.Popen([STATS_EXE])
    else: messagebox.showwarning("TimesUp", f"Stats EXE not found:\n{STATS_EXE}")

def _test_alert(_=None, __=None):
    if os.path.exists(ALERT_EXE): subprocess.Popen([ALERT_EXE])
    else: messagebox.showwarning("TimesUp", f"Alert EXE not found:\n{ALERT_EXE}")

def _toggle_startup(icon, item):
    set_startup(not is_startup_enabled()); _refresh_menu()

def _exit(icon, item):
    icon.stop(); root.destroy()

def _build_menu():
    alerts = load_alerts()
    items  = []
    for i, a in enumerate(alerts):
        modes = "+".join(m.upper() for m in
                         (["SNOOZE"]*a.get("snooze",False) +
                          ["ONTOP"]*a.get("ontop",False)))
        sfx  = f"  [{modes}]" if modes else ""
        sched = a.get("schedule","daily").upper()
        if a.get("schedule")=="weekly" and a.get("day"): sched += f" {a['day']}"
        label = f"{a['time']}  {a['name']}  ({sched}){sfx}"

        def _edit_cb(ic, it, idx=i):
            al = load_alerts()
            if idx < len(al):
                root.after(0, lambda a=al[idx], j=idx: show_add_dialog(a, j))

        def _del_cb(ic, it, idx=i):
            al = load_alerts()
            if idx < len(al):
                schtask_delete(al[idx]["name"]); al.pop(idx)
                save_alerts(al); _refresh_menu()

        items.append(pystray.MenuItem(label, pystray.Menu(
            pystray.MenuItem("Edit...",  _edit_cb),
            pystray.MenuItem("Delete",   _del_cb),
        )))

    if not items:
        items = [pystray.MenuItem("(no alerts — click Add Alert)", None, enabled=False)]

    return pystray.Menu(
        pystray.MenuItem("TimesUp!", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Add Alert...",     lambda ic,it: root.after(0, show_add_dialog)),
        pystray.MenuItem("Manage Alerts...", lambda ic,it: root.after(0, show_manage_dialog)),
        pystray.MenuItem("Scheduled Alerts", pystray.Menu(*items)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Stats & Log",      lambda ic,it: root.after(0, _open_stats)),
        pystray.MenuItem("Test Alert Now",   lambda ic,it: root.after(0, _test_alert)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start with Windows", _toggle_startup,
                         checked=lambda item: is_startup_enabled()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", _exit),
    )

# ── Main ───────────────────────────────────────────────────────────────────────
root = None

def main():
    global root
    root = tk.Tk()
    root.withdraw()

    icon = pystray.Icon("TimesUp", _make_icon(64), "TimesUp!", _build_menu())
    _icon_ref[0] = icon

    threading.Thread(target=icon.run, daemon=True).start()
    root.mainloop()
    icon.stop()

if __name__ == "__main__":
    main()
