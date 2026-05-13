import tkinter as tk
import subprocess, sys, os, base64, tempfile, ctypes, math

# ── Font name (loaded after root creation) ────────────────────────────────────
PF = "Pixelify Sans"

def _load_pixel_font():
    """Load Pixelify Sans into GDI after Tk is running."""
    try:
        import tkinter.font as tkfont
        _here = os.path.dirname(sys.executable if getattr(sys, 'frozen', False)
                                else os.path.abspath(__file__))
        _ns = {}
        exec(open(os.path.join(_here, "font_data.py")).read(), _ns)
        _font_bytes = base64.b64decode(_ns["FONT_B64"])
        # Load from memory (process-wide, no file needed)
        _num = ctypes.c_uint32(0)
        _buf = ctypes.create_string_buffer(_font_bytes)
        ctypes.windll.gdi32.AddFontMemResourceEx(
            _buf, len(_font_bytes), None, ctypes.byref(_num))
        # Also write to temp and register via path for Tk's GDI lookup
        _tmp = os.path.join(tempfile.gettempdir(), "PixelifySans_tu.ttf")
        with open(_tmp, "wb") as _f:
            _f.write(_font_bytes)
        ctypes.windll.gdi32.AddFontResourceW(_tmp)
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)
        # Force Tk to re-query GDI font list
        root.tk.call("font", "families")
        # Pre-create the font object so Tk caches it
        tkfont.Font(root=root, family=PF, size=12)
    except Exception as e:
        pass

# ── Palette ────────────────────────────────────────────────────────────────────
BG      = "#0a0a18"
PANEL   = "#10102a"
RED     = "#e94560"
RED2    = "#ff6680"
RED_DIM = "#6a1530"
CYAN    = "#00e5ff"
WHITE   = "#ffffff"
DIM     = "#2d2d55"
DIM2    = "#4a4a80"

# ── Dimensions ─────────────────────────────────────────────────────────────────
W, H      = 740, 600
BORDER_PX = 6
PAD       = BORDER_PX

# ── Actions ────────────────────────────────────────────────────────────────────
def shutdown():
    try:
        subprocess.Popen([r"C:\Windows\System32\shutdown.exe",
                          "/s", "/t", "30", "/c",
                          "Shutdown initiated by Time's Up."])
        root.destroy(); sys.exit(0)
    except Exception as e:
        import tkinter.messagebox
        tkinter.messagebox.showerror("Error", f"Could not run shutdown:\n{e}")

def cancel():
    root.destroy(); sys.exit(0)

# ── Root ───────────────────────────────────────────────────────────────────────
root = tk.Tk()
root.overrideredirect(True)
root.configure(bg=BG)
root.attributes("-topmost", True)
root.bind("<Escape>", lambda e: cancel())
_load_pixel_font()   # must be after Tk init

# ── Border canvas ──────────────────────────────────────────────────────────────
border_cv = tk.Canvas(root, width=W, height=H, bg=BG, highlightthickness=0)
border_cv.pack()

def draw_border(color):
    border_cv.delete("border")
    for i in range(BORDER_PX):
        border_cv.create_rectangle(i, i, W-1-i, H-1-i,
                                   outline=color if i % 2 == 0 else BG,
                                   tags="border")

# ── Inner panel (fills border canvas) ─────────────────────────────────────────
panel = tk.Frame(border_cv, bg=PANEL)
panel.place(x=PAD, y=PAD, width=W - PAD*2, height=H - PAD*2)

# ── Scanlines (stipple) ────────────────────────────────────────────────────────
scan_cv = tk.Canvas(panel, bg=PANEL, highlightthickness=0)
scan_cv.place(x=0, y=0, relwidth=1, relheight=1)
for sy in range(0, H, 4):
    scan_cv.create_line(0, sy, W, sy, fill="#000000", width=1, stipple="gray25")

# ── Layout: use a centred content frame so we control spacing exactly ──────────
content = tk.Frame(panel, bg=PANEL)
content.place(relx=0.5, rely=0.5, anchor="center")

# ── Pixel clock (canvas, larger) ───────────────────────────────────────────────
CS = 160   # clock canvas size
clock_cv = tk.Canvas(content, width=CS, height=CS, bg=PANEL, highlightthickness=0)
clock_cv.pack(pady=(0, 28))

def draw_clock(angle_deg):
    clock_cv.delete("all")
    cx = cy = CS // 2
    r = CS // 2 - 6
    THICK = 12

    # filled face
    for dy in range(-r, r + 1):
        dx = int((r**2 - dy**2) ** 0.5)
        clock_cv.create_rectangle(cx - dx, cy + dy, cx + dx, cy + dy + 1,
                                  fill="#16163a", outline="")
    # chunky ring
    for dy in range(-r, r + 1):
        dx_out = int((r**2 - dy**2) ** 0.5)
        ri = r - THICK
        dx_in = int((ri**2 - dy**2) ** 0.5) if abs(dy) <= ri else 0
        clock_cv.create_rectangle(cx - dx_out, cy + dy, cx - dx_in, cy + dy + 1,
                                  fill=RED, outline="")
        clock_cv.create_rectangle(cx + dx_in, cy + dy, cx + dx_out, cy + dy + 1,
                                  fill=RED, outline="")
    # tick marks
    for i in range(12):
        a = math.radians(i * 30 - 90)
        tr = r - THICK - 4
        x1 = cx + int(tr * math.cos(a))
        y1 = cy + int(tr * math.sin(a))
        sz = 4 if i % 3 == 0 else 2
        clock_cv.create_rectangle(x1 - sz, y1 - sz, x1 + sz, y1 + sz,
                                  fill=WHITE, outline="")
    # hands
    a_min = math.radians(angle_deg - 90)
    mlen = r - THICK - 14
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
    # centre pip
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
        # shadow block
        cv.create_rectangle(SH, SH, BW, BH, fill="#000000", outline="")
        # face
        cv.create_rectangle(0, 0, BW - SH, BH - SH, fill=fill, outline="")
        # pixel corner notches (top-left + bottom-right) for extra retro feel
        cv.create_rectangle(0, 0, 4, 4, fill=PANEL, outline="")        # TL notch
        cv.create_rectangle(BW-SH-4, BH-SH-4, BW-SH, BH-SH,
                            fill=PANEL, outline="")                      # BR notch
        # label
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

make_btn(btn_row, "SHUT DOWN", shutdown, RED,  RED2).pack(side="left", padx=22)
make_btn(btn_row, "CANCEL",    cancel,   DIM,  DIM2).pack(side="left", padx=22)

# ── Warning flash label ────────────────────────────────────────────────────────
warn_var = tk.StringVar(value="!! SHUTDOWN IN 30 SECONDS !!")
warn_lbl = tk.Label(content, textvariable=warn_var,
                    font=(PF, 8), bg=PANEL, fg=RED)
warn_lbl.pack()

# ── Center on screen ───────────────────────────────────────────────────────────
root.update_idletasks()
sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

# ── Animation ──────────────────────────────────────────────────────────────────
_angle      = [0]
_cursor     = [True]
_bphase     = [0]
_warn_on    = [True]
PULSE = [RED, RED2, RED, RED, RED_DIM, RED_DIM, RED_DIM, RED]

def animate():
    _angle[0] = (_angle[0] + 3) % 360
    draw_clock(_angle[0])

    _cursor[0] = not _cursor[0]
    sub_var.set(f">SESSION ENDED. SHUTDOWN?{'_' if _cursor[0] else ' '}")

    _bphase[0] = (_bphase[0] + 1) % len(PULSE)
    draw_border(PULSE[_bphase[0]])

    _warn_on[0] = not _warn_on[0]
    warn_lbl.config(fg=RED if _warn_on[0] else RED_DIM)

    root.after(350, animate)

animate()
root.mainloop()
