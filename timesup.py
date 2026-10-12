import tkinter as tk
import subprocess, sys, os, base64, tempfile, ctypes, math, datetime, threading, json
import io, struct, time, wave

# ── Mode flags ────────────────────────────────────────────────────────────────
SNOOZE_MODE = "--snooze" in sys.argv
ON_TOP_MODE = "--ontop"  in sys.argv
QUIET_MODE  = "--quiet"  in sys.argv

def _arg_value(flag, default=None):
    try:
        return sys.argv[sys.argv.index(flag) + 1]
    except (ValueError, IndexError):
        return default

ALERT_NAME = _arg_value("--name", "")

# --delay N: wait N seconds before showing (used by snooze to re-launch itself)
try:
    time.sleep(max(0, float(_arg_value("--delay", 0))))
except ValueError:
    pass

# ── Activity log ───────────────────────────────────────────────────────────────
LOG_FILE = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "TimesUp", "log.jsonl")
_t_start = datetime.datetime.now()

def _log(action):
    try:
        entry = {
            "ts":      _t_start.isoformat(timespec="seconds"),
            "action":  action,
            "mode":    [m for m, f in [("snooze", SNOOZE_MODE), ("ontop", ON_TOP_MODE)] if f],
            "name":    ALERT_NAME,
            "elapsed": round((datetime.datetime.now() - _t_start).total_seconds(), 1),
        }
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

# ── Font name (loaded after root creation) ────────────────────────────────────
PF = "Pixelify Sans"

def _load_pixel_font():
    try:
        import tkinter.font as tkfont
        # PyInstaller one-file builds unpack bundled data to sys._MEIPASS
        _here = getattr(sys, "_MEIPASS", None) or os.path.dirname(
            sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
        _ns = {}
        exec(open(os.path.join(_here, "font_data.py")).read(), _ns)
        _font_bytes = base64.b64decode(_ns["FONT_B64"])
        _num = ctypes.c_uint32(0)
        _buf = ctypes.create_string_buffer(_font_bytes)
        ctypes.windll.gdi32.AddFontMemResourceEx(
            _buf, len(_font_bytes), None, ctypes.byref(_num))
        _tmp = os.path.join(tempfile.gettempdir(), "PixelifySans_tu.ttf")
        with open(_tmp, "wb") as _f:
            _f.write(_font_bytes)
        ctypes.windll.gdi32.AddFontResourceW(_tmp)
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)
        root.tk.call("font", "families")
        tkfont.Font(root=root, family=PF, size=12)
    except Exception:
        pass

# ── Palette ────────────────────────────────────────────────────────────────────
BG      = "#0a0a18"
PANEL   = "#10102a"
RED     = "#e94560"
RED2    = "#ff6680"
RED_DK  = "#b0304a"
RED_DIM = "#6a1530"
AMBER   = "#ffaa00"
AMBER2  = "#ffcc44"
CYAN    = "#00e5ff"
WHITE   = "#ffffff"
FACE    = "#16163a"
DIM     = "#2d2d55"
DIM2    = "#4a4a80"
DIM3    = "#8080c0"

# ── Dimensions ─────────────────────────────────────────────────────────────────
W, H      = 740, 600
BORDER_PX = 4     # outer frame thickness
NOTCH     = 8     # stepped pixel corner size

# ── Keyboard hook (on-top mode) ────────────────────────────────────────────────
# Blocks Win key, Alt+Tab, Alt+F4, Alt+Esc, Ctrl+Esc/Ctrl+Shift+Esc so the
# user cannot task-switch away from the alert.
_HOOK_REFS = []         # keep HOOKPROC alive; GC would break the callback
_hook_id   = [None]
_hook_tid  = [None]     # thread id of the hook message pump

def _install_keyboard_hook():
    import ctypes.wintypes as wt
    WH_KEYBOARD_LL = 13
    WM_KEYDOWN     = 0x0100
    WM_SYSKEYDOWN  = 0x0104
    LLKHF_ALTDOWN  = 0x20
    WIN_KEYS       = {0x5B, 0x5C}   # LWin, RWin

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [("vkCode",      ctypes.c_uint32),
                    ("scanCode",    ctypes.c_uint32),
                    ("flags",       ctypes.c_uint32),
                    ("time",        ctypes.c_uint32),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wt.WPARAM, wt.LPARAM)

    def _cb(nCode, wParam, lParam):
        if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            kbd  = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk   = kbd.vkCode
            alt  = bool(kbd.flags & LLKHF_ALTDOWN)
            ctrl = bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000)
            if vk in WIN_KEYS:       return 1   # Win key
            if vk == 0x09 and alt:   return 1   # Alt+Tab
            if vk == 0x73 and alt:   return 1   # Alt+F4
            if vk == 0x1B and alt:   return 1   # Alt+Esc
            if vk == 0x1B and ctrl:  return 1   # Ctrl+Esc / Ctrl+Shift+Esc
        return ctypes.windll.user32.CallNextHookEx(_hook_id[0], nCode, wParam, lParam)

    proc = HOOKPROC(_cb)
    _HOOK_REFS.append(proc)
    _hook_id[0]  = ctypes.windll.user32.SetWindowsHookExW(WH_KEYBOARD_LL, proc, None, 0)
    _hook_tid[0] = ctypes.windll.kernel32.GetCurrentThreadId()

    msg = wt.MSG()
    while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
        ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

    if _hook_id[0]:
        ctypes.windll.user32.UnhookWindowsHookEx(_hook_id[0])

def _stop_hook():
    # Post WM_QUIT to the hook thread so it exits its message loop
    if _hook_tid[0]:
        ctypes.windll.user32.PostThreadMessageW(_hook_tid[0], 0x0012, 0, 0)

SNOOZE_SECS = 5 * 60

# ── Tone ───────────────────────────────────────────────────────────────────────
def _make_tone():
    """Build a short chiptune jingle (pulse-wave arpeggio) as WAV bytes."""
    rate = 22050
    notes = [(659.25, .09), (783.99, .09), (1046.5, .09), (1318.5, .09),   # E5 G5 C6 E6
             (0, .06), (1046.5, .11), (1318.5, .38)]                       # rest, C6, E6
    frames = bytearray()
    for freq, dur in notes:
        n = int(rate * dur)
        for i in range(n):
            if freq == 0:
                v = 0.0
            else:
                phase = (i * freq / rate) % 1.0
                pulse = 1.0 if phase < 0.25 else -1.0          # 25% duty pulse
                sine  = math.sin(2 * math.pi * phase)
                env   = min(1.0, i / (rate * .004)) * math.exp(-3.2 * i / n)
                v     = (0.55 * pulse + 0.45 * sine) * env * 0.22
            frames += struct.pack("<h", int(v * 32767))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(bytes(frames))
    return buf.getvalue()

def play_tone():
    if QUIET_MODE:
        return
    def _play():
        try:
            import winsound
            winsound.PlaySound(_make_tone(), winsound.SND_MEMORY)
        except Exception:
            pass
    threading.Thread(target=_play, daemon=True).start()

# ── Actions ────────────────────────────────────────────────────────────────────
def shutdown():
    _log("shutdown")
    _stop_hook()
    try:
        subprocess.Popen([r"C:\Windows\System32\shutdown.exe",
                          "/s", "/t", "30", "/c",
                          "Shutdown initiated by Time's Up."])
        root.destroy(); sys.exit(0)
    except Exception as e:
        import tkinter.messagebox
        tkinter.messagebox.showerror("Error", f"Could not run shutdown:\n{e}")

def cancel():
    _log("snooze" if SNOOZE_MODE else "cancel")
    _stop_hook()
    if SNOOZE_MODE:
        # Re-launch self as a detached process that waits 5 minutes, preserving
        # all active flags. (Avoids schtasks /sd, whose date format is
        # locale-dependent, and works when run as a plain .py script too.)
        cmd = [sys.executable] if getattr(sys, "frozen", False)               else [sys.executable, os.path.abspath(__file__)]
        args, skip = [], False
        for a in sys.argv[1:]:          # drop any previous "--delay N"
            if skip:            skip = False
            elif a == "--delay": skip = True
            else:               args.append(a)
        cmd += args + ["--delay", str(SNOOZE_SECS)]
        subprocess.Popen(cmd, close_fds=True,
                         creationflags=0x00000008 | 0x00000200)  # DETACHED | NEW_GROUP
    root.destroy(); sys.exit(0)

# ── Root ───────────────────────────────────────────────────────────────────────
root = tk.Tk()
root.overrideredirect(True)
root.configure(bg=BG)
root.attributes("-topmost", True)
root.bind("<Escape>", lambda e: cancel())
_load_pixel_font()

sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
if ON_TOP_MODE:
    # Full-screen overlay: nothing behind is reachable; panel sits centred
    CW, CH = sw, sh
    OX, OY = (sw - W) // 2, (sh - H) // 2
    root.geometry(f"{sw}x{sh}+0+0")
else:
    CW, CH = W, H
    OX, OY = 0, 0
    root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

# Everything is drawn on one canvas so the scanlines run edge to edge
cv = tk.Canvas(root, width=CW, height=CH, bg=BG, highlightthickness=0)
cv.pack()

# ── Drawing helpers (panel-relative coordinates) ───────────────────────────────
def rect(x1, y1, x2, y2, fill, **kw):
    return cv.create_rectangle(OX + x1, OY + y1, OX + x2, OY + y2,
                               fill=fill, outline="", **kw)

def text(x, y, s, color, size, **kw):
    return cv.create_text(OX + x, OY + y, text=s, fill=color, font=(PF, size), **kw)

def shade(c, f):
    """Lighten (f > 0) or darken (f < 0) a hex colour by fraction f."""
    rgb = [int(c[i:i+2], 16) for i in (1, 3, 5)]
    rgb = [v + (255 - v) * f if f > 0 else v * (1 + f) for v in rgb]
    return "#{:02x}{:02x}{:02x}".format(*(int(max(0, min(255, v))) for v in rgb))

def notched_frame(x1, y1, x2, y2, t, n, fill, tag):
    """Pixel frame of thickness t with stepped (notched) corners of size n."""
    for r in [(x1 + n, y1, x2 - n, y1 + t), (x1 + n, y2 - t, x2 - n, y2),
              (x1, y1 + n, x1 + t, y2 - n), (x2 - t, y1 + n, x2, y2 - n),
              (x1 + t, y1 + t, x1 + n, y1 + n), (x2 - n, y1 + t, x2 - t, y1 + n),
              (x1 + t, y2 - n, x1 + n, y2 - t), (x2 - n, y2 - n, x2 - t, y2 - t)]:
        rect(*r, fill, tags=tag)

# ── Backdrop (on-top mode: dotted grid behind the panel) ───────────────────────
if ON_TOP_MODE:
    for gx in range(16, CW, 32):
        for gy in range(16, CH, 32):
            cv.create_rectangle(gx, gy, gx + 2, gy + 2, fill=DIM, outline="")

# ── Panel, scanlines, frame ────────────────────────────────────────────────────
rect(BORDER_PX, BORDER_PX, W - BORDER_PX, H - BORDER_PX, PANEL)
for sy in range(BORDER_PX, H - BORDER_PX, 4):
    cv.create_line(OX + BORDER_PX, OY + sy, OX + W - BORDER_PX, OY + sy,
                   fill="#000000", width=1, stipple="gray25")
notched_frame(0, 0, W, H, BORDER_PX, NOTCH, RED, "frame")
notched_frame(10, 10, W - 10, H - 10, 2, 6, RED_DIM, "frame2")

# ── Title bar ──────────────────────────────────────────────────────────────────
rect(16, 16, W - 16, 44, FACE)
rect(16, 44, W - 16, 46, DIM)
rect(26, 26, 34, 34, RED, tags="led")
text(44, 30, f"TIMESUP.EXE  /  {ALERT_NAME.upper()[:28]}" if ALERT_NAME else "TIMESUP.EXE",
     DIM3, 9, anchor="w")
clock_txt = text(W - 26, 30, "", DIM3, 9, anchor="e")

_badges = ([("SNOOZE", AMBER)] if SNOOZE_MODE else []) + \
          ([("LOCKED", CYAN)]  if ON_TOP_MODE else [])
_bx = W // 2 - (len(_badges) * 84 - 8) // 2
for label, col in _badges:
    rect(_bx, 22, _bx + 76, 38, shade(col, -0.7))
    rect(_bx, 22, _bx + 3, 38, col)
    text(_bx + 40, 30, label, col, 7)
    _bx += 84

# ── Pixel clock ────────────────────────────────────────────────────────────────
CELL  = 5                   # screen px per clock pixel
CN    = 37                  # clock grid size in cells
CC    = CN // 2             # centre cell
CLK_X = W // 2 - CN * CELL // 2
CLK_Y = 58

def cell(i, j, color, tag):
    x, y = CLK_X + i * CELL, CLK_Y + j * CELL
    rect(x, y, x + CELL, y + CELL, color, tags=tag)

def _init_clock_static():
    for j in range(CN):
        for i in range(CN):
            dx, dy = i - CC, j - CC
            d = math.hypot(dx, dy)
            if d <= 13.5:
                cell(i, j, FACE, "static")
            elif d <= 16.5:
                # bevelled rim: lit from the top-left
                if d > 15.5 and dx + dy < -6:   col = RED2
                elif d > 15.5 and dx + dy > 6:  col = RED_DK
                else:                           col = RED
                cell(i, j, col, "static")
            elif d <= 18 and (i + j) % 2 == 0:
                cell(i, j, RED_DIM, "static")   # dithered glow
    for h in range(12):
        a = math.radians(h * 30 - 90)
        radii, col = ((11.6, 10.6), WHITE) if h % 3 == 0 else ((11.6,), DIM3)
        for rr in radii:
            cell(CC + round(rr * math.cos(a)), CC + round(rr * math.sin(a)), col, "static")

def _line_cells(length, angle_deg):
    """Bresenham line from the clock centre, in cell coordinates."""
    a  = math.radians(angle_deg - 90)
    x1 = CC + round(length * math.cos(a))
    y1 = CC + round(length * math.sin(a))
    x0, y0 = CC, CC
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err, out = dx + dy, []
    while True:
        out.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return out
        e2 = 2 * err
        if e2 >= dy: err += dy; x0 += sx
        if e2 <= dx: err += dx; y0 += sy

_init_clock_static()

def draw_clock(angle_deg):
    cv.delete("hand")
    for i, j in _line_cells(10.5, angle_deg):
        cell(i, j, WHITE, "hand")
    for i, j in _line_cells(6.5, angle_deg / 2):
        cell(i, j, CYAN, "hand")
    for di, dj in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
        cell(CC + di, CC + dj, CYAN, "hand")

# ── Title ──────────────────────────────────────────────────────────────────────
TITLE_Y = 278
text(W // 2 + 4, TITLE_Y + 4, "TIME IS UP!", "#000000", 34)
text(W // 2 + 2, TITLE_Y + 2, "TIME IS UP!", RED_DK, 34)
text(W // 2,     TITLE_Y,     "TIME IS UP!", WHITE, 34)

# ── Divider: pixel dashes that fade toward the edges ───────────────────────────
DIV_Y, DIV_L, DIV_R = 318, 90, W - 90
for x in range(DIV_L, DIV_R, 12):
    t = abs((x + 4) - W / 2) / ((DIV_R - DIV_L) / 2)
    rect(x, DIV_Y, x + 8, DIV_Y + 4, RED if t < 0.55 else RED_DK if t < 0.8 else RED_DIM)
rect(W // 2 - 4, DIV_Y - 2, W // 2 + 4, DIV_Y + 6, WHITE)

# ── Subtitle ───────────────────────────────────────────────────────────────────
sub_txt = text(W // 2, 346, "", CYAN, 10)

# ── Buttons ────────────────────────────────────────────────────────────────────
BW, BH, BSH = 250, 62, 6
BTN_Y       = 382
_focus  = [0]
_hover  = [None]
_press  = [None]
_btns   = []   # {"x", "label", "face", "cmd", "ink"}

def _draw_btn(idx):
    b   = _btns[idx]
    tag = f"btn{idx}"
    cv.delete(tag)
    pressed = _press[0] == idx
    off     = BSH // 2 if pressed else 0
    x, y    = b["x"] + off, BTN_Y + off
    fw, fh  = BW - BSH, BH - BSH
    face    = shade(b["face"], 0.18) if _hover[0] == idx else b["face"]

    if not pressed:
        rect(x + BSH, y + BSH, x + BW, y + BH, "#000000", tags=tag)
    rect(x, y, x + fw, y + fh, face, tags=tag)
    rect(x, y, x + fw, y + 3, shade(face, 0.35), tags=tag)             # top light
    rect(x, y, x + 3, y + fh, shade(face, 0.2), tags=tag)              # left light
    rect(x, y + fh - 4, x + fw, y + fh, shade(face, -0.35), tags=tag)  # bottom dark
    rect(x + fw - 3, y, x + fw, y + fh, shade(face, -0.25), tags=tag)  # right dark
    for cx_, cy_ in ((x, y), (x + fw - 3, y), (x, y + fh - 3), (x + fw - 3, y + fh - 3)):
        rect(cx_, cy_, cx_ + 3, cy_ + 3, PANEL, tags=tag)              # rounded px corners
    text(x + fw // 2, y + fh // 2, b["label"], b["ink"], 12, tags=tag)

    if _focus[0] == idx:
        # cyan corner brackets around the focused button
        g, L, T = 7, 14, 3
        x1, y1, x2, y2 = x - g, y - g, x + fw + g, y + fh + g
        for (px_, py_, sx, sy) in ((x1, y1, 1, 1), (x2, y1, -1, 1),
                                   (x1, y2, 1, -1), (x2, y2, -1, -1)):
            rect(min(px_, px_ + sx * L), min(py_, py_ + sy * T),
                 max(px_, px_ + sx * L), max(py_, py_ + sy * T), CYAN, tags=tag)
            rect(min(px_, px_ + sx * T), min(py_, py_ + sy * L),
                 max(px_, px_ + sx * T), max(py_, py_ + sy * L), CYAN, tags=tag)

def make_btn(label, cmd, face, x, ink=WHITE):
    _btns.append({"x": x, "label": label, "face": face, "cmd": cmd, "ink": ink})

_GAP = 48
_bx0 = (W - (2 * BW + _GAP)) // 2
make_btn("SHUT DOWN", shutdown, RED, _bx0)
make_btn("SNOOZE 5 MIN" if SNOOZE_MODE else "CANCEL", cancel,
         AMBER if SNOOZE_MODE else DIM, _bx0 + BW + _GAP,
         ink=BG if SNOOZE_MODE else WHITE)

def _btn_at(e):
    for i, b in enumerate(_btns):
        if b["x"] <= e.x - OX < b["x"] + BW and BTN_Y <= e.y - OY < BTN_Y + BH:
            return i
    return None

def _redraw_btns():
    for i in range(len(_btns)):
        _draw_btn(i)

def _on_motion(e):
    i = _btn_at(e)
    if i != _hover[0]:
        _hover[0] = i
        cv.config(cursor="hand2" if i is not None else "")
        _redraw_btns()

def _on_press(e):
    _press[0] = _btn_at(e)
    if _press[0] is not None:
        _focus[0] = _press[0]
    _redraw_btns()

def _on_release(e):
    i = _press[0]
    _press[0] = None
    _redraw_btns()
    if i is not None and _btn_at(e) == i:
        _btns[i]["cmd"]()

cv.bind("<Motion>",          _on_motion)
cv.bind("<Leave>",           lambda e: (_hover.__setitem__(0, None), _redraw_btns()))
cv.bind("<ButtonPress-1>",   _on_press)
cv.bind("<ButtonRelease-1>", _on_release)

def _set_focus(idx):
    _focus[0] = idx % len(_btns)
    _redraw_btns()

def _activate():
    _btns[_focus[0]]["cmd"]()

def _on_key(e):
    k = e.keysym
    if k in ("Left", "a", "A"):
        _set_focus(_focus[0] - 1)
    elif k in ("Right", "d", "D", "Tab"):
        _set_focus(_focus[0] + 1)
    elif k == "Return":
        _activate()

for _k in ("<Left>", "<Right>", "<a>", "<A>", "<d>", "<D>", "<Tab>", "<Return>"):
    root.bind(_k, _on_key)
_set_focus(0)
root.focus_force()

# ── Warning strip with hazard stripes ──────────────────────────────────────────
WARN_Y, WARN_W, WARN_H = 476, 440, 32
_wx = (W - WARN_W) // 2
rect(_wx, WARN_Y, _wx + WARN_W, WARN_Y + WARN_H, "#1a0a1c")
HZ = 4   # hazard stripe pixel size
for side in (_wx, _wx + WARN_W - 40):
    for cy_ in range(WARN_H // HZ):
        for cx_ in range(40 // HZ):
            if ((cx_ + cy_) // 3) % 2 == 0:
                rect(side + cx_ * HZ, WARN_Y + cy_ * HZ,
                     side + (cx_ + 1) * HZ, WARN_Y + (cy_ + 1) * HZ, RED_DIM)
notched_frame(_wx, WARN_Y, _wx + WARN_W, WARN_Y + WARN_H, 2, 4, RED, "warnbox")
warn_txt = text(W // 2, WARN_Y + WARN_H // 2,
                "SNOOZE ONLY DELAYS 5 MIN  -  NO ESCAPE" if SNOOZE_MODE
                else "SHUTDOWN STARTS 30 SEC AFTER CONFIRM", RED, 9)

# ── Footer: key hints ──────────────────────────────────────────────────────────
rect(16, H - 46, W - 16, H - 44, DIM)
_hints = [("<  >", "SELECT"), ("ENTER", "CONFIRM"),
          ("ESC", "SNOOZE" if SNOOZE_MODE else "CANCEL")]
_hx = [0]
_hint_items = []
for key, desc in _hints:
    k_id = text(0, H - 28, f" {key} ", WHITE, 8, anchor="w")
    x1, y1, x2, y2 = cv.bbox(k_id)
    kw = x2 - x1
    bg = rect(0, 0, kw, 18, DIM)
    cv.tag_lower(bg, k_id)
    d_id = text(0, H - 28, desc, DIM2, 8, anchor="w")
    dw = cv.bbox(d_id)[2] - cv.bbox(d_id)[0]
    _hint_items.append((k_id, bg, d_id, kw, dw))
_total = sum(kw + 8 + dw for *_, kw, dw in _hint_items) + 28 * (len(_hint_items) - 1)
_x = W // 2 - _total // 2
for k_id, bg, d_id, kw, dw in _hint_items:
    cv.coords(k_id, OX + _x, OY + H - 28)
    cv.coords(bg, OX + _x, OY + H - 37, OX + _x + kw, OY + H - 19)
    cv.coords(d_id, OX + _x + kw + 8, OY + H - 28)
    _x += kw + 8 + dw + 28

# ── Animation ──────────────────────────────────────────────────────────────────
_angle  = [0]
_tick   = [0]
PULSE = [RED, RED2, RED, RED, RED_DIM, RED_DIM, RED_DIM, RED]
SUBTITLE = (">SNOOZE MODE - SHUT DOWN OR DELAY 5 MIN" if SNOOZE_MODE
            else ">SESSION ENDED. SHUT DOWN NOW?")

def animate():
    _tick[0] += 1
    t = _tick[0]
    _angle[0] = (_angle[0] + 3) % 360
    draw_clock(_angle[0])

    # typewriter reveal, then a blinking cursor
    n = min(len(SUBTITLE), t * 3)
    cur = "_" if (t // 2) % 2 == 0 or n < len(SUBTITLE) else " "
    cv.itemconfig(sub_txt, text=SUBTITLE[:n] + cur)

    cv.itemconfig("frame", fill=PULSE[t % len(PULSE)])
    blink = t % 2 == 0
    cv.itemconfig(warn_txt, fill=RED2 if blink else RED)
    cv.itemconfig("warnbox", fill=RED if blink else RED_DIM)
    cv.itemconfig("led", fill=RED if blink else RED_DIM)
    cv.itemconfig(clock_txt, text=datetime.datetime.now().strftime("%H:%M:%S"))

    root.after(350, animate)

def _assert_topmost():
    try:
        hwnd = ctypes.windll.user32.GetAncestor(root.winfo_id(), 2)  # GA_ROOT
        ctypes.windll.user32.SetWindowPos(
            hwnd, -1, 0, 0, 0, 0,
            0x0002 | 0x0001 | 0x0010)  # NOMOVE|NOSIZE|NOACTIVATE
    except Exception:
        pass
    root.after(1000, _assert_topmost)

if ON_TOP_MODE:
    threading.Thread(target=_install_keyboard_hook, daemon=True).start()
    root.update_idletasks()
    try:
        hwnd = ctypes.windll.user32.GetAncestor(root.winfo_id(), 2)
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0,
                                          0x0002 | 0x0001 | 0x0040)  # +SHOWWINDOW
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    _assert_topmost()

play_tone()
animate()
root.mainloop()
