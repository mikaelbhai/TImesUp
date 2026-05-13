# Time's Up!

A retro pixel-art shutdown alert for Windows. When the timer fires, a full-screen overlay appears giving you 30 seconds to either cancel or confirm a system shutdown — great for enforcing screen-time limits or end-of-day reminders.

![Time's Up screenshot — red pixel clock overlay with SHUT DOWN / CANCEL buttons]

---

## Quick Start

### Option A — Run the setup wizard (recommended)

```
setup.bat
```

The wizard will:
1. Build `TimesUp.exe` from source using PyInstaller
2. Install it to `%LOCALAPPDATA%\TimesUp\`
3. Add it to **Windows Task Scheduler** at whatever time you choose

### Option B — Manual steps

**1. Build**

```bat
build.bat
```

This produces `dist\TimesUp.exe`.

**2. Run immediately**

```bat
dist\TimesUp.exe
```

**3. Add to Task Scheduler manually**

Open **Task Scheduler** → *Create Basic Task* and point the action at `TimesUp.exe`, or use the command below (replace `22:00` with your preferred time):

```bat
schtasks /create /tn "TimesUp Alert" /tr "\"%LOCALAPPDATA%\TimesUp\TimesUp.exe\"" /sc daily /st 22:00 /f
```

---

## Setup Wizard — Menu Reference

| Option | What it does |
|--------|-------------|
| **1** Full install | Build EXE → install → create scheduled task |
| **2** Add/update alert | Add a new Task Scheduler entry (builds if needed) |
| **3** List alerts | Show all existing TimesUp scheduled tasks |
| **4** Remove alert | Delete a scheduled task by name |
| **5** Build EXE only | Compile without scheduling |

---

## Requirements

| Requirement | Version |
|-------------|---------|
| Windows | 10 / 11 |
| Python | 3.9 + (add to PATH) |
| pip | any recent version |

PyInstaller is installed automatically by `setup.bat` / `build.bat`.

---

## What happens when it fires

- A borderless fullscreen-style window appears on top of everything (always-on-top)
- An animated pixel clock spins with a pulsing red border
- **SHUT DOWN** — initiates `shutdown /s /t 30` (30-second grace period, cancellable with `shutdown /a`)
- **CANCEL** — dismisses the alert with no action
- **Escape key** — same as Cancel

---

## Files

```
timesup.py          Main application source
font_data.py        Pixelify Sans font embedded as base64
build.bat           Build-only script (no scheduling)
setup.bat           Full setup wizard (build + Task Scheduler)
TimesUp.spec        PyInstaller spec
dist/TimesUp.exe    Compiled executable (after build)
```

---

## Customising the shutdown delay

Edit `timesup.py` line 54 — change `/t`, `"30"` to however many seconds you want:

```python
subprocess.Popen([r"C:\Windows\System32\shutdown.exe",
                  "/s", "/t", "60",   # <-- change this
                  "/c", "Shutdown initiated by Time's Up."])
```

Then rebuild with `build.bat` or `setup.bat → option 5`.

---

## License

Font: **Pixelify Sans** — SIL Open Font License 1.1 (see `OFL.txt`)  
App: MIT — do whatever you want with it.
