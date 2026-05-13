import tkinter as tk
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
WHITE   = "#ffffff"
DIM     = "#2d2d55"
DIM2    = "#4a4a80"
PF      = "Pixelify Sans"

SW, SH    = 860, 640
BORDER_PX = 6
PAD       = BORDER_PX

ACTION_COLOR = {"shutdown": RED, "snooze": AMBER, "cancel": DIM2}
ACTION_LABEL = {"shutdown": "SHUTDOWN", "snooze": "SNOOZE ", "cancel": "CANCEL  "}

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
                cancels=cancels, rate=shutdowns / n if n else 0, avg_elapsed=avg_e)

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
        _here = os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                                else os.path.abspath(__file__))
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

# ── Outer border ───────────────────────────────────────────────────────────────
border_cv = tk.Canvas(root, width=SW, height=SH, bg=BG, highlightthickness=0)
border_cv.pack()
for i in range(BORDER_PX):
    c = CYAN if i % 2 == 0 else BG
    border_cv.create_rectangle(i, i, SW - 1 - i, SH - 1 - i, outline=c)

# ── Panel ──────────────────────────────────────────────────────────────────────
panel = tk.Frame(border_cv, bg=PANEL)
panel.place(x=PAD, y=PAD, width=SW - PAD*2, height=SH - PAD*2)

scan = tk.Canvas(panel, bg=PANEL, highlightthickness=0)
scan.place(x=0, y=0, relwidth=1, relheight=1)
for sy in range(0, SH, 4):
    scan.create_line(0, sy, SW, sy, fill="#000000", width=1, stipple="gray25")

# ── Main content (packed inside panel) ────────────────────────────────────────
main = tk.Frame(panel, bg=PANEL)
main.place(x=14, y=14, width=SW - PAD*2 - 28, height=SH - PAD*2 - 28)

# ── Header row ─────────────────────────────────────────────────────────────────
hdr = tk.Frame(main, bg=PANEL)
hdr.pack(fill="x")

tk.Label(hdr, text="STATS & LOG", font=(PF, 18), bg=PANEL, fg=WHITE).pack(side="left")
tk.Label(hdr, text=LOG_FILE, font=(PF, 7), bg=PANEL, fg=DIM2).pack(
    side="left", padx=10, anchor="s", pady=4)

# pixel close button
def _close():
    root.destroy()

def _mk_btn_cv(parent, w, h, text, normal_fill, hover_fill, cmd):
    cv = tk.Canvas(parent, width=w, height=h, bg=PANEL, highlightthickness=0)
    SH2 = 4
    def _draw(fill):
        cv.delete("all")
        cv.create_rectangle(SH2, SH2, w, h,      fill="#000000", outline="")
        cv.create_rectangle(0,   0,   w-SH2, h-SH2, fill=fill, outline="")
        cv.create_text((w-SH2)//2, (h-SH2)//2, text=text, fill=WHITE, font=(PF, 7))
    _draw(normal_fill)
    cv.bind("<Enter>",           lambda e: _draw(hover_fill))
    cv.bind("<Leave>",           lambda e: _draw(normal_fill))
    cv.bind("<ButtonRelease-1>", lambda e: cmd())
    return cv

_mk_btn_cv(hdr, 80, 30, "CLOSE", DIM, RED, _close).pack(side="right")

# ── Divider ────────────────────────────────────────────────────────────────────
tk.Frame(main, bg=RED, height=3).pack(fill="x", pady=(6, 10))

# ── Stat boxes ─────────────────────────────────────────────────────────────────
STAT_CELLS = [
    ("TOTAL",      str(stats["total"]),                    CYAN),
    ("SHUTDOWNS",  str(stats["shutdowns"]),                RED),
    ("SNOOZES",    str(stats["snoozes"]),                  AMBER),
    ("CANCELS",    str(stats["cancels"]),                  DIM2),
    ("SHUTDOWN %", f"{stats['rate']*100:.0f}%",            GREEN),
    ("AVG RESP",   fmt_elapsed(stats["avg_elapsed"]),      CYAN),
]

stat_row = tk.Frame(main, bg=PANEL)
stat_row.pack(fill="x", pady=(0, 8))

CONTENT_W = SW - PAD*2 - 28
box_w = CONTENT_W // len(STAT_CELLS)
for lbl, val, col in STAT_CELLS:
    outer = tk.Frame(stat_row, bg=DIM2, width=box_w - 4, height=76)
    outer.pack(side="left", padx=2)
    outer.pack_propagate(False)
    inner = tk.Frame(outer, bg=PANEL)
    inner.place(x=2, y=2, width=box_w - 8, height=72)
    tk.Label(inner, text=val, font=(PF, 17), bg=PANEL, fg=col).pack(expand=True)
    tk.Label(inner, text=lbl, font=(PF, 7),  bg=PANEL, fg=DIM2).pack(pady=(0, 4))

tk.Frame(main, bg=DIM, height=2).pack(fill="x", pady=(0, 6))

# ── Activity bar chart ─────────────────────────────────────────────────────────
tk.Label(main, text="ACTIVITY — LAST 21 DAYS",
         font=(PF, 7), bg=PANEL, fg=DIM2).pack(anchor="w")

CHART_H  = 86
chart_cv = tk.Canvas(main, width=CONTENT_W, height=CHART_H, bg=BG, highlightthickness=0)
chart_cv.pack(fill="x", pady=(3, 0))

max_day = max((sd + sn + ca for _, sd, sn, ca in daily), default=1) or 1
col_w   = CONTENT_W // len(daily)
GAP     = 2

for i, (d, sd, sn, ca) in enumerate(daily):
    total = sd + sn + ca
    if total == 0:
        continue
    bar_h = max(4, int((total / max_day) * (CHART_H - 18)))
    x1 = i * col_w + GAP
    x2 = (i + 1) * col_w - GAP
    y  = CHART_H - 6
    for count, color in [(ca, DIM2), (sn, AMBER), (sd, RED)]:
        if count == 0:
            continue
        seg = max(2, int(bar_h * count / total))
        chart_cv.create_rectangle(x1, y - seg, x2, y, fill=color, outline="")
        y -= seg

for i, (d, *_) in enumerate(daily):
    if i % 7 == 0 or i == len(daily) - 1:
        chart_cv.create_text(i * col_w + col_w // 2, CHART_H - 1,
                             text=d.strftime("%m/%d"), fill=DIM2,
                             font=(PF, 6), anchor="s")

# legend
leg = tk.Frame(main, bg=PANEL)
leg.pack(anchor="w", pady=(2, 4))
for txt, col in [("■ SHUTDOWN", RED), ("■ SNOOZE", AMBER), ("■ CANCEL", DIM2)]:
    tk.Label(leg, text=txt, font=(PF, 7), bg=PANEL, fg=col).pack(side="left", padx=8)

tk.Frame(main, bg=DIM, height=2).pack(fill="x", pady=(0, 6))

# ── Log header + clear button ──────────────────────────────────────────────────
log_hdr = tk.Frame(main, bg=PANEL)
log_hdr.pack(fill="x", pady=(0, 4))
tk.Label(log_hdr, text="RECENT LOG", font=(PF, 7), bg=PANEL, fg=DIM2).pack(side="left")

def _clear_log():
    try:
        open(LOG_FILE, "w").close()
    except Exception:
        pass
    root.destroy()

_mk_btn_cv(log_hdr, 90, 22, "CLEAR LOG", DIM, RED_DIM, _clear_log).pack(side="right")

# ── Log text area ──────────────────────────────────────────────────────────────
log_frame = tk.Frame(main, bg=BG)
log_frame.pack(fill="both", expand=True)

sb = tk.Scrollbar(log_frame, bg=DIM, troughcolor=BG, width=10, relief="flat")
sb.pack(side="right", fill="y")

log_txt = tk.Text(
    log_frame,
    bg=BG, fg=WHITE, font=(PF, 8),
    insertbackground=WHITE,
    selectbackground=DIM2,
    relief="flat", state="disabled",
    yscrollcommand=sb.set, cursor="arrow",
)
log_txt.pack(side="left", fill="both", expand=True)
sb.config(command=log_txt.yview)

log_txt.tag_config("shutdown", foreground=RED)
log_txt.tag_config("snooze",   foreground=AMBER)
log_txt.tag_config("cancel",   foreground=DIM2)
log_txt.tag_config("dim",      foreground=DIM2)
log_txt.tag_config("mode",     foreground=CYAN)
log_txt.tag_config("time",     foreground=WHITE)

log_txt.config(state="normal")

if not entries:
    log_txt.insert("end",
        "  No entries yet — run an alert and take an action to start logging.\n", "dim")
else:
    # newest first, cap at 500
    for e in reversed(entries[-500:]):
        ts      = e.get("ts", "?")[:16].replace("T", "  ")
        action  = e.get("action", "?")
        elapsed = e.get("elapsed", 0)
        modes   = e.get("mode", [])
        mode_str = "  [" + "+".join(m.upper() for m in modes) + "]" if modes else ""

        log_txt.insert("end", f"  {ts}  ", "dim")
        log_txt.insert("end", f"{ACTION_LABEL.get(action, action):<10}", action)
        log_txt.insert("end", f"  {fmt_elapsed(elapsed):<7}", "time")
        if mode_str:
            log_txt.insert("end", mode_str, "mode")
        log_txt.insert("end", "\n")

log_txt.config(state="disabled")

# ── Centre window ──────────────────────────────────────────────────────────────
root.update_idletasks()
scr_w = root.winfo_screenwidth()
scr_h = root.winfo_screenheight()
root.geometry(f"{SW}x{SH}+{(scr_w - SW)//2}+{(scr_h - SH)//2}")

root.mainloop()
