import tkinter as tk
from tkinter import ttk
import json, os, sys, datetime, ctypes, base64, tempfile

LOG_FILE = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "TimesUp", "log.jsonl")

# ── Palette (matches timesup.py) ───────────────────────────────────────────────
BG      = "#0a0a18"
PANEL   = "#10102a"
RED     = "#e94560"
RED2    = "#ff6680"
RED_DIM = "#6a1530"
AMBER   = "#ffaa00"
GREEN   = "#00e676"
CYAN    = "#00e5ff"
CYAN_DIM= "#0a6a7a"
WHITE   = "#ffffff"
FACE    = "#16163a"
DIM     = "#2d2d55"
DIM2    = "#4a4a80"
DIM3    = "#8080c0"
PF      = "Pixelify Sans"

SW, SH    = 860, 640
BORDER_PX = 4     # outer frame thickness
NOTCH     = 8     # stepped pixel corner size

ACTION_LABEL = {"shutdown": "SHUTDOWN", "snooze": "SNOOZE", "cancel": "CANCEL"}

# ── Data helpers ───────────────────────────────────────────────────────────────
def load_entries():
    if not os.path.exists(LOG_FILE):
        return []
    out = []
    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return sorted(out, key=lambda e: e.get("ts", ""))

def compute_stats(entries):
    n         = len(entries)
    shutdowns = sum(1 for e in entries if e.get("action") == "shutdown")
    snoozes   = sum(1 for e in entries if e.get("action") == "snooze")
    cancels   = sum(1 for e in entries if e.get("action") == "cancel")
    elapsed   = [e["elapsed"] for e in entries if "elapsed" in e]
    avg_e     = sum(elapsed) / len(elapsed) if elapsed else 0
    return dict(total=n, shutdowns=shutdowns, snoozes=snoozes,
                cancels=cancels, rate=shutdowns / n if n else 0, avg_elapsed=avg_e,
                streak=compute_streak(entries))

def compute_streak(entries):
    """Consecutive days (ending today or yesterday) whose alerts all ended in shutdown."""
    by_day = {}
    for e in entries:
        d = e.get("ts", "")[:10]
        if d:
            by_day.setdefault(d, []).append(e.get("action"))
    day = datetime.date.today()
    if day.isoformat() not in by_day:
        day -= datetime.timedelta(days=1)
    streak = 0
    while all(a == "shutdown" for a in by_day.get(day.isoformat(), [None])):
        streak += 1
        day -= datetime.timedelta(days=1)
    return streak

def get_daily(entries, days=21):
    today = datetime.date.today()
    out   = []
    for i in range(days):
        d   = today - datetime.timedelta(days=days - 1 - i)
        ds  = d.isoformat()
        day = [e for e in entries if e.get("ts", "")[:10] == ds]
        out.append((d,
                    sum(1 for e in day if e.get("action") == "shutdown"),
                    sum(1 for e in day if e.get("action") == "snooze"),
                    sum(1 for e in day if e.get("action") == "cancel")))
    return out

def fmt_elapsed(secs):
    if secs < 60:
        return f"{secs:.0f}s"
    return f"{secs / 60:.1f}m"

# ── Root ───────────────────────────────────────────────────────────────────────
root = tk.Tk()
root.overrideredirect(True)
root.configure(bg=BG)
root.attributes("-topmost", True)
root.bind("<Escape>", lambda e: root.destroy())

# ── Font ───────────────────────────────────────────────────────────────────────
def _load_font():
    try:
        import tkinter.font as tkfont
        # PyInstaller one-file builds unpack bundled data to sys._MEIPASS
        _here = getattr(sys, "_MEIPASS", None) or os.path.dirname(
            sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
        _ns = {}
        exec(open(os.path.join(_here, "font_data.py")).read(), _ns)
        _b = base64.b64decode(_ns["FONT_B64"])
        _n = ctypes.c_uint32(0)
        _buf = ctypes.create_string_buffer(_b)
        ctypes.windll.gdi32.AddFontMemResourceEx(_buf, len(_b), None, ctypes.byref(_n))
        _tmp = os.path.join(tempfile.gettempdir(), "PixelifySans_tu.ttf")
        with open(_tmp, "wb") as _f:
            _f.write(_b)
        ctypes.windll.gdi32.AddFontResourceW(_tmp)
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)
        root.tk.call("font", "families")
        tkfont.Font(root=root, family=PF, size=12)
    except Exception:
        pass

_load_font()

# ── Load data ──────────────────────────────────────────────────────────────────
entries = load_entries()
stats   = compute_stats(entries)
daily   = get_daily(entries, 21)

# ── Window + canvas ────────────────────────────────────────────────────────────
scr_w, scr_h = root.winfo_screenwidth(), root.winfo_screenheight()
root.geometry(f"{SW}x{SH}+{(scr_w - SW)//2}+{(scr_h - SH)//2}")

cv = tk.Canvas(root, width=SW, height=SH, bg=BG, highlightthickness=0)
cv.pack()

def rect(x1, y1, x2, y2, fill, **kw):
    return cv.create_rectangle(x1, y1, x2, y2, fill=fill, outline="", **kw)

def text(x, y, s, color, size, **kw):
    return cv.create_text(x, y, text=s, fill=color, font=(PF, size), **kw)

def shade(c, f):
    """Lighten (f > 0) or darken (f < 0) a hex colour by fraction f."""
    rgb = [int(c[i:i+2], 16) for i in (1, 3, 5)]
    rgb = [v + (255 - v) * f if f > 0 else v * (1 + f) for v in rgb]
    return "#{:02x}{:02x}{:02x}".format(*(int(max(0, min(255, v))) for v in rgb))

def notched_frame(x1, y1, x2, y2, t, n, fill, tag=""):
    """Pixel frame of thickness t with stepped (notched) corners of size n."""
    for r in [(x1 + n, y1, x2 - n, y1 + t), (x1 + n, y2 - t, x2 - n, y2),
              (x1, y1 + n, x1 + t, y2 - n), (x2 - t, y1 + n, x2, y2 - n),
              (x1 + t, y1 + t, x1 + n, y1 + n), (x2 - n, y1 + t, x2 - t, y1 + n),
              (x1 + t, y2 - n, x1 + n, y2 - t), (x2 - n, y2 - n, x2 - t, y2 - t)]:
        rect(*r, fill, tags=tag)

def notched_box(x1, y1, x2, y2, n, fill):
    """Solid box with stepped corners."""
    rect(x1 + n, y1, x2 - n, y2, fill)
    rect(x1, y1 + n, x2, y2 - n, fill)
    rect(x1 + n // 2, y1 + n // 2, x2 - n // 2, y2 - n // 2, fill)

# ── Panel, scanlines, frame ────────────────────────────────────────────────────
rect(BORDER_PX, BORDER_PX, SW - BORDER_PX, SH - BORDER_PX, PANEL)
for sy in range(BORDER_PX, SH - BORDER_PX, 4):
    cv.create_line(BORDER_PX, sy, SW - BORDER_PX, sy,
                   fill="#000000", width=1, stipple="gray25")
notched_frame(0, 0, SW, SH, BORDER_PX, NOTCH, CYAN)
notched_frame(10, 10, SW - 10, SH - 10, 2, 6, CYAN_DIM)

# ── Buttons (canvas-drawn, hit-tested) ─────────────────────────────────────────
_btns  = []    # {"x","y","w","h","label","face","cmd","size"}
_hover = [None]
_press = [None]

def _draw_btn(idx):
    b   = _btns[idx]
    tag = f"btn{idx}"
    cv.delete(tag)
    sh_ = 4
    pressed = _press[0] == idx
    off     = sh_ // 2 if pressed else 0
    x, y    = b["x"] + off, b["y"] + off
    fw, fh  = b["w"] - sh_, b["h"] - sh_
    face    = b["hover"] if _hover[0] == idx else b["face"]
    if not pressed:
        rect(x + sh_, y + sh_, x + b["w"], y + b["h"], "#000000", tags=tag)
    rect(x, y, x + fw, y + fh, face, tags=tag)
    rect(x, y, x + fw, y + 2, shade(face, 0.3), tags=tag)
    rect(x, y + fh - 3, x + fw, y + fh, shade(face, -0.35), tags=tag)
    for cx_, cy_ in ((x, y), (x + fw - 2, y), (x, y + fh - 2), (x + fw - 2, y + fh - 2)):
        rect(cx_, cy_, cx_ + 2, cy_ + 2, b["bg"], tags=tag)
    text(x + fw // 2, y + fh // 2, b["label"], WHITE, b["size"], tags=tag)

def add_btn(x, y, w, h, label, face, hover, cmd, size=8, bg=PANEL):
    _btns.append(dict(x=x, y=y, w=w, h=h, label=label, face=face,
                      hover=hover, cmd=cmd, size=size, bg=bg))
    _draw_btn(len(_btns) - 1)
    return len(_btns) - 1

def _btn_at(e):
    for i, b in enumerate(_btns):
        if b["x"] <= e.x < b["x"] + b["w"] and b["y"] <= e.y < b["y"] + b["h"]:
            return i
    return None

# ── Title bar (draggable) ──────────────────────────────────────────────────────
TB_Y1, TB_Y2 = 16, 44
rect(16, TB_Y1, SW - 16, TB_Y2, FACE)
rect(16, TB_Y2, SW - 16, TB_Y2 + 2, DIM)
rect(26, 26, 34, 34, CYAN)
text(44, 30, "TIMESUP.EXE  /  STATS", DIM3, 9, anchor="w")
add_btn(SW - 60, 20, 38, 22, "X", DIM, RED, root.destroy, size=8, bg=FACE)

_drag = [None]

def _on_press(e):
    _press[0] = _btn_at(e)
    if _press[0] is not None:
        _draw_btn(_press[0])
    elif TB_Y1 <= e.y <= TB_Y2:
        _drag[0] = (e.x_root - root.winfo_x(), e.y_root - root.winfo_y())

def _on_drag(e):
    if _drag[0]:
        root.geometry(f"+{e.x_root - _drag[0][0]}+{e.y_root - _drag[0][1]}")

def _on_release(e):
    _drag[0] = None
    i = _press[0]
    _press[0] = None
    if i is not None:
        _draw_btn(i)
        if _btn_at(e) == i:
            _btns[i]["cmd"]()

def _on_motion(e):
    i = _btn_at(e)
    if i != _hover[0]:
        old, _hover[0] = _hover[0], i
        for j in (old, i):
            if j is not None and j < len(_btns):
                _draw_btn(j)
        cv.config(cursor="hand2" if i is not None
                  else "fleur" if TB_Y1 <= e.y <= TB_Y2 else "")
    elif i is None:
        cv.config(cursor="fleur" if TB_Y1 <= e.y <= TB_Y2 else "")

cv.bind("<ButtonPress-1>",   _on_press)
cv.bind("<B1-Motion>",       _on_drag)
cv.bind("<ButtonRelease-1>", _on_release)
cv.bind("<Motion>",          _on_motion)

# ── Heading ────────────────────────────────────────────────────────────────────
text(28, 76, "STATS & LOG", "#000000", 20, anchor="w")
text(26, 74, "STATS & LOG", CYAN_DIM, 20, anchor="w")
text(24, 72, "STATS & LOG", WHITE, 20, anchor="w")
if entries:
    last = entries[-1]
    text(SW - 26, 74,
         f"LAST ALERT  {last.get('ts', '?')[:16].replace('T', '  ')}  "
         f"-  {last.get('action', '?').upper()}",
         DIM3, 8, anchor="e")

# ── Stat cards ─────────────────────────────────────────────────────────────────
STAT_CELLS = [
    ("TOTAL",      str(stats["total"]),               CYAN),
    ("SHUTDOWNS",  str(stats["shutdowns"]),           RED),
    ("SNOOZES",    str(stats["snoozes"]),             AMBER),
    ("CANCELS",    str(stats["cancels"]),             DIM3),
    ("SHUTDOWN %", f"{stats['rate']*100:.0f}%",       GREEN),
    ("STREAK",     f"{stats['streak']}d",             AMBER),
    ("AVG RESP",   fmt_elapsed(stats["avg_elapsed"]), CYAN),
]
CARD_Y, CARD_H, CARD_GAP = 100, 78, 8
_cx0, _cx1 = 24, SW - 24
card_w = (_cx1 - _cx0 - CARD_GAP * (len(STAT_CELLS) - 1)) // len(STAT_CELLS)
for k, (lbl, val, col) in enumerate(STAT_CELLS):
    x = _cx0 + k * (card_w + CARD_GAP)
    notched_box(x, CARD_Y, x + card_w, CARD_Y + CARD_H, 4, DIM)
    notched_box(x + 2, CARD_Y + 2, x + card_w - 2, CARD_Y + CARD_H - 2, 4, FACE)
    rect(x + 6, CARD_Y + 2, x + card_w - 6, CARD_Y + 6, col)
    text(x + card_w // 2, CARD_Y + 36, val, col, 18)
    text(x + card_w // 2, CARD_Y + 62, lbl, DIM3, 7)

# ── Activity chart ─────────────────────────────────────────────────────────────
SEC_Y = 204
text(24, SEC_Y, f"ACTIVITY  -  LAST {len(daily)} DAYS", DIM3, 8, anchor="w")
_lx = SW - 24
for txt, col in reversed([("SHUTDOWN", RED), ("SNOOZE", AMBER), ("CANCEL", DIM3)]):
    t_id = text(_lx, SEC_Y, txt, col, 8, anchor="e")
    _lx = cv.bbox(t_id)[0] - 6
    rect(_lx - 8, SEC_Y - 4, _lx, SEC_Y + 4, col)
    _lx -= 24

CH_X1, CH_Y1, CH_X2, CH_Y2 = 24, 218, SW - 24, 330
notched_box(CH_X1, CH_Y1, CH_X2, CH_Y2, 4, BG)
PLOT_T, PLOT_B = CH_Y1 + 12, CH_Y2 - 22       # bar area top / baseline
max_day = max((sd + sn + ca for _, sd, sn, ca in daily), default=0) or 1

for frac in (0.25, 0.5, 0.75, 1.0):            # dotted grid
    gy = PLOT_B - int((PLOT_B - PLOT_T) * frac)
    for gx in range(CH_X1 + 8, CH_X2 - 8, 8):
        rect(gx, gy, gx + 2, gy + 1, DIM)
rect(CH_X1 + 8, PLOT_B, CH_X2 - 8, PLOT_B + 2, DIM)
text(CH_X1 + 10, PLOT_T - 2, str(max_day), DIM2, 7, anchor="nw")

col_w = (CH_X2 - CH_X1 - 16) / len(daily)
for i, (d, sd, sn, ca) in enumerate(daily):
    total = sd + sn + ca
    x1 = int(CH_X1 + 8 + i * col_w) + 4
    x2 = int(CH_X1 + 8 + (i + 1) * col_w) - 4
    if total:
        bar_h = max(6, int((total / max_day) * (PLOT_B - PLOT_T)))
        y = PLOT_B
        for count, color in [(ca, DIM3), (sn, AMBER), (sd, RED)]:
            if count:
                seg = max(3, round(bar_h * count / total))
                rect(x1, y - seg, x2, y, color)
                rect(x1, y - seg, x2, y - seg + 2, shade(color, 0.35))  # lit top edge
                y -= seg
        text((x1 + x2) // 2, y - 7, str(total), DIM3, 6)
    is_today = i == len(daily) - 1
    if i % 7 == 0 or is_today:
        text((x1 + x2) // 2, CH_Y2 - 10,
             "TODAY" if is_today else d.strftime("%m/%d"),
             CYAN if is_today else DIM2, 7)

if not any(sd + sn + ca for _, sd, sn, ca in daily):
    text((CH_X1 + CH_X2) // 2, (PLOT_T + PLOT_B) // 2,
         "NO ACTIVITY YET", DIM2, 10)

# ── Log header ─────────────────────────────────────────────────────────────────
LOG_Y = 354
text(24, LOG_Y, "RECENT LOG", DIM3, 8, anchor="w")
text(118, LOG_Y, f"({min(len(entries), 500)} of {len(entries)})" if entries else "",
     DIM2, 7, anchor="w")

_clear_armed = [False]

def _clear_log():
    # First click arms, second click within 3 s clears
    b = _btns[clear_idx]
    if not _clear_armed[0]:
        _clear_armed[0] = True
        b.update(label="SURE? CLICK AGAIN", face=RED_DIM, hover=RED)
        _draw_btn(clear_idx)
        def _disarm():
            _clear_armed[0] = False
            b.update(label="CLEAR LOG", face=DIM, hover=RED_DIM)
            _draw_btn(clear_idx)
        root.after(3000, _disarm)
        return
    try:
        open(LOG_FILE, "w").close()
    except Exception:
        pass
    root.destroy()

clear_idx = add_btn(SW - 24 - 150, LOG_Y - 12, 150, 26, "CLEAR LOG", DIM, RED_DIM, _clear_log)

# column headings (match the Text widget's tab stops below)
COLS = [("DATE", 0), ("TIME", 130), ("ACTION", 210), ("RESPONSE", 340), ("MODE", 460)]
for lbl, cx_ in COLS:
    text(24 + 10 + cx_, LOG_Y + 26, lbl, DIM2, 7, anchor="w")
rect(24, LOG_Y + 36, SW - 24, LOG_Y + 38, DIM)

# ── Log text area ──────────────────────────────────────────────────────────────
style = ttk.Style(root)
style.theme_use("clam")
style.configure("Px.Vertical.TScrollbar",
                background=DIM, troughcolor=BG, bordercolor=BG,
                lightcolor=DIM, darkcolor=DIM, arrowcolor=DIM3,
                gripcount=0, arrowsize=12)
style.map("Px.Vertical.TScrollbar",
          background=[("active", DIM2), ("pressed", CYAN_DIM)])

log_frame = tk.Frame(cv, bg=BG)
cv.create_window(24, LOG_Y + 42, anchor="nw", window=log_frame,
                 width=SW - 48, height=SH - 48 - (LOG_Y + 42))

sb = ttk.Scrollbar(log_frame, orient="vertical", style="Px.Vertical.TScrollbar")
sb.pack(side="right", fill="y")

log_txt = tk.Text(
    log_frame,
    bg=BG, fg=WHITE, font=(PF, 9),
    insertbackground=WHITE, selectbackground=DIM2,
    relief="flat", borderwidth=0, padx=10, pady=6,
    spacing1=3, spacing3=3,
    state="disabled", yscrollcommand=sb.set, cursor="arrow",
    tabs=tuple(c for _, c in COLS[1:]),
)
log_txt.pack(side="left", fill="both", expand=True)
sb.config(command=log_txt.yview)

log_txt.tag_config("shutdown", foreground=RED)
log_txt.tag_config("snooze",   foreground=AMBER)
log_txt.tag_config("cancel",   foreground=DIM3)
log_txt.tag_config("dim",      foreground=DIM2)
log_txt.tag_config("mode",     foreground=CYAN)
log_txt.tag_config("time",     foreground=WHITE)
log_txt.tag_config("odd",      background="#0d0d20")
log_txt.tag_config("empty",    foreground=DIM2, justify="center", spacing1=60)

def _wheel(e):
    log_txt.yview_scroll(int(-e.delta / 40), "units")
    return "break"
cv.bind("<MouseWheel>", _wheel)
log_txt.bind("<MouseWheel>", _wheel)

log_txt.config(state="normal")
if not entries:
    log_txt.insert("end",
        "No entries yet - run an alert and take an action to start logging.\n",
        "empty")
else:
    # newest first, cap at 500
    for n, e in enumerate(reversed(entries[-500:])):
        ts      = e.get("ts", "?")
        action  = e.get("action", "?")
        modes   = e.get("mode", [])
        row     = ("odd",) if n % 2 else ()
        log_txt.insert("end", f"{ts[:10]}\t", ("dim",) + row)
        log_txt.insert("end", f"{ts[11:16]}\t", ("time",) + row)
        log_txt.insert("end", f"{ACTION_LABEL.get(action, action.upper())}\t", (action,) + row)
        log_txt.insert("end", f"{fmt_elapsed(e.get('elapsed', 0))}\t", ("time",) + row)
        log_txt.insert("end", " + ".join(m.upper() for m in modes) or "-",
                       ("mode" if modes else "dim",) + row)
        log_txt.insert("end", "\n", row)
log_txt.config(state="disabled")

# ── Footer ─────────────────────────────────────────────────────────────────────
_path = LOG_FILE if len(LOG_FILE) <= 70 else LOG_FILE[:30] + " ... " + LOG_FILE[-36:]
text(24, SH - 30, _path, DIM2, 7, anchor="w")
text(SW - 24, SH - 30, "ESC  CLOSE", DIM2, 7, anchor="e")

root.focus_force()
root.mainloop()
