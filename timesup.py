import tkinter as tk
import subprocess, sys, os, base64, tempfile, ctypes, math, datetime, threading

# ── Mode flags ────────────────────────────────────────────────────────────────
SNOOZE_MODE = "--snooze" in sys.argv
ON_TOP_MODE = "--ontop"  in sys.argv

# ── Font name (loaded after root creation) ────────────────────────────────────
PF = "Pixelify Sans"

def _load_pixel_font():
    try:
        import tkinter.font as tkfont
        _here = os.path.dirname(sys.executable if getattr(sys, 'frozen', False)
                                else os.path.abspath(__file__))
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
RED_DIM = "#6a1530"
AMBER   = "#ffaa00"
AMBER2  = "#ffcc44"
CYAN    = "#00e5ff"
WHITE   = "#ffffff"
DIM     = "#2d2d55"
DIM2    = "#4a4a80"

# ── Dimensions ─────────────────────────────────────────────────────────────────
W, H      = 740, 600
BORDER_PX = 6
PAD       = BORDER_PX

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

# ── Actions ────────────────────────────────────────────────────────────────────
def shutdown():
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
    _stop_hook()
    if SNOOZE_MODE:
        # Re-schedule self in 5 minutes, preserving all active flags
        t    = datetime.datetime.now() + datetime.timedelta(minutes=5)
        exe  = sys.executable
        args = "--snooze" + (" --ontop" if ON_TOP_MODE else "")
        subprocess.Popen([
            r"C:\Windows\System32\schtasks.exe",
            "/create", "/tn", "TimesUp_Snooze",
            "/tr", f'"{exe}" {args}',
            "/sc", "once",
            "/st", t.strftime("%H:%M"),
            "/sd", t.strftime("%m/%d/%Y"),
            "/f"
        ])
    root.destroy(); sys.exit(0)

# ── Root ───────────────────────────────────────────────────────────────────────
root = tk.Tk()
root.overrideredirect(True)
root.configure(bg=BG)
root.attributes("-topmost", True)
root.bind("<Escape>", lambda e: cancel())
_load_pixel_font()

# ── Border canvas ──────────────────────────────────────────────────────────────
border_cv = tk.Canvas(root, width=W, height=H, bg=BG, highlightthickness=0)
border_cv.pack()

# Panel origin within border_cv — (0,0) normally; centered offset in on-top mode
_OX = [0]
_OY = [0]

def draw_border(color):
    border_cv.delete("border")
    ox, oy = _OX[0], _OY[0]
    for i in range(BORDER_PX):
        border_cv.create_rectangle(ox + i,       oy + i,
                                   ox + W - 1 - i, oy + H - 1 - i,
                                   outline=color if i % 2 == 0 else BG,
                                   tags="border")

# ── Inner panel ────────────────────────────────────────────────────────────────
panel = tk.Frame(border_cv, bg=PANEL)
panel.place(x=PAD, y=PAD, width=W - PAD*2, height=H - PAD*2)

# ── Scanlines ──────────────────────────────────────────────────────────────────
scan_cv = tk.Canvas(panel, bg=PANEL, highlightthickness=0)
scan_cv.place(x=0, y=0, relwidth=1, relheight=1)
for sy in range(0, H, 4):
    scan_cv.create_line(0, sy, W, sy, fill="#000000", width=1, stipple="gray25")

# ── Content frame ──────────────────────────────────────────────────────────────
content = tk.Frame(panel, bg=PANEL)
content.place(relx=0.5, rely=0.5, anchor="center")

# ── Pixel clock ────────────────────────────────────────────────────────────────
CS = 160
clock_cv = tk.Canvas(content, width=CS, height=CS, bg=PANEL, highlightthickness=0)
clock_cv.pack(pady=(0, 28))

def draw_clock(angle_deg):
    clock_cv.delete("all")
    cx = cy = CS // 2
    r = CS // 2 - 6
    THICK = 12
    for dy in range(-r, r + 1):
        dx = int((r**2 - dy**2) ** 0.5)
        clock_cv.create_rectangle(cx - dx, cy + dy, cx + dx, cy + dy + 1,
                                  fill="#16163a", outline="")
    for dy in range(-r, r + 1):
        dx_out = int((r**2 - dy**2) ** 0.5)
        ri = r - THICK
        dx_in = int((ri**2 - dy**2) ** 0.5) if abs(dy) <= ri else 0
        clock_cv.create_rectangle(cx - dx_out, cy + dy, cx - dx_in, cy + dy + 1,
                                  fill=RED, outline="")
        clock_cv.create_rectangle(cx + dx_in, cy + dy, cx + dx_out, cy + dy + 1,
                                  fill=RED, outline="")
    for i in range(12):
        a  = math.radians(i * 30 - 90)
        tr = r - THICK - 4
        x1 = cx + int(tr * math.cos(a))
        y1 = cy + int(tr * math.sin(a))
        sz = 4 if i % 3 == 0 else 2
        clock_cv.create_rectangle(x1 - sz, y1 - sz, x1 + sz, y1 + sz,
                                  fill=WHITE, outline="")
    a_min = math.radians(angle_deg - 90)
    mlen  = r - THICK - 14
    clock_cv.create_line(cx, cy,
                         cx + int(mlen * math.cos(a_min)),
                         cy + int(mlen * math.sin(a_min)),
                         fill=WHITE, width=5, capstyle="round")
    a_hr = math.radians(angle_deg / 2 - 90)
    hlen = r - THICK - 30
    clock_cv.create_line(cx, cy,
                         cx + int(hlen * math.cos(a_hr)),
                         cy + int(hlen * math.sin(a_hr)),
                         fill=CYAN, width=5, capstyle="round")
    clock_cv.create_rectangle(cx - 5, cy - 5, cx + 5, cy + 5,
                              fill=CYAN, outline="")

# ── Title ──────────────────────────────────────────────────────────────────────
tk.Label(content, text="TIME IS UP!", font=(PF, 22),
         bg=PANEL, fg=WHITE).pack(pady=(0, 18))

# ── Divider ────────────────────────────────────────────────────────────────────
tk.Frame(content, bg=RED, height=4, width=620).pack(pady=(0, 20))

# ── Subtitle ───────────────────────────────────────────────────────────────────
sub_var = tk.StringVar()
tk.Label(content, textvariable=sub_var, font=(PF, 9),
         bg=PANEL, fg=CYAN).pack(pady=(0, 28))

# ── Buttons ────────────────────────────────────────────────────────────────────
def make_btn(parent, label, cmd, face, hover):
    BW, BH, SH = 240, 60, 6
    cv = tk.Canvas(parent, width=BW, height=BH, bg=PANEL, highlightthickness=0)

    def draw(fill):
        cv.delete("all")
        cv.create_rectangle(SH, SH, BW, BH, fill="#000000", outline="")
        cv.create_rectangle(0, 0, BW - SH, BH - SH, fill=fill, outline="")
        cv.create_rectangle(0, 0, 4, 4, fill=PANEL, outline="")
        cv.create_rectangle(BW-SH-4, BH-SH-4, BW-SH, BH-SH, fill=PANEL, outline="")
        cv.create_text((BW - SH) // 2, (BH - SH) // 2,
                       text=label, fill=WHITE, font=(PF, 10))

    draw(face)
    cv.bind("<Enter>",           lambda e: draw(hover))
    cv.bind("<Leave>",           lambda e: draw(face))
    cv.bind("<ButtonPress-1>",   lambda e: cv.move("all", SH // 2, SH // 2))
    cv.bind("<ButtonRelease-1>", lambda e: (cv.move("all", -(SH//2), -(SH//2)), cmd()))
    return cv

btn_row = tk.Frame(content, bg=PANEL)
btn_row.pack(pady=(0, 28))

make_btn(btn_row, "SHUT DOWN",
         shutdown, RED, RED2).pack(side="left", padx=22)
make_btn(btn_row,
         "SNOOZE (5 MIN)" if SNOOZE_MODE else "CANCEL",
         cancel,
         AMBER if SNOOZE_MODE else DIM,
         AMBER2 if SNOOZE_MODE else DIM2).pack(side="left", padx=22)

# ── Warning label ──────────────────────────────────────────────────────────────
warn_var = tk.StringVar(
    value="!! SNOOZE = 5 MIN DELAY ONLY — NO ESCAPE !!" if SNOOZE_MODE
    else  "!! SHUTDOWN IN 30 SECONDS !!")
warn_lbl = tk.Label(content, textvariable=warn_var,
                    font=(PF, 8), bg=PANEL, fg=RED)
warn_lbl.pack()

# ── Window geometry ────────────────────────────────────────────────────────────
root.update_idletasks()
sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()

if ON_TOP_MODE:
    # Full-screen overlay: nothing behind is reachable
    root.geometry(f"{sw}x{sh}+0+0")
    border_cv.config(width=sw, height=sh)
    _OX[0] = (sw - W) // 2
    _OY[0] = (sh - H) // 2
    panel.place(x=_OX[0] + PAD, y=_OY[0] + PAD, width=W - PAD*2, height=H - PAD*2)
else:
    root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

# ── Animation ──────────────────────────────────────────────────────────────────
_angle   = [0]
_cursor  = [True]
_bphase  = [0]
_warn_on = [True]
PULSE = [RED, RED2, RED, RED, RED_DIM, RED_DIM, RED_DIM, RED]

def animate():
    _angle[0] = (_angle[0] + 3) % 360
    draw_clock(_angle[0])

    _cursor[0] = not _cursor[0]
    _c = '_' if _cursor[0] else ' '
    if SNOOZE_MODE:
        sub_var.set(f">SNOOZE MODE — SHUTDOWN OR DELAY 5 MIN{_c}")
    else:
        sub_var.set(f">SESSION ENDED. SHUTDOWN?{_c}")

    _bphase[0] = (_bphase[0] + 1) % len(PULSE)
    draw_border(PULSE[_bphase[0]])

    _warn_on[0] = not _warn_on[0]
    warn_lbl.config(fg=RED if _warn_on[0] else RED_DIM)

    root.after(350, animate)

if ON_TOP_MODE:
    threading.Thread(target=_install_keyboard_hook, daemon=True).start()

animate()
root.mainloop()
