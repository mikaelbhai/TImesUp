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
| **7** Forever Snooze setup | Quick-create a snooze-mode alert (see below) |
| **8** On Top Mode setup | Quick-create a fullscreen lock alert (see below) |
| **9** View stats & log | Launch the stats viewer |

---

## Forever Snooze Mode

Enable this to make the alert **inescapable** — the user cannot dismiss it, only delay it.

- The **CANCEL** button is replaced with **SNOOZE (5 MIN)**
- Clicking Snooze schedules the alert to fire again exactly 5 minutes later via Task Scheduler
- This repeats until the user clicks **SHUT DOWN**
- Escape key is still bound to Snooze (not dismiss) in this mode

**To enable:** choose option **[7]** in the setup wizard, or answer **Y** to the snooze prompt when creating any alert via options 1 or 2.

**To enable manually** (command line):

```bat
schtasks /create /tn "TimesUp Snooze" /tr "\"%LOCALAPPDATA%\TimesUp\TimesUp.exe\" --snooze" /sc daily /st 22:00 /f
```

The `--snooze` flag is what activates the mode.

---

## On Top Mode

Enable this to make the alert **impossible to task-switch away from**.

- The window expands to cover the **entire screen** (including taskbar)
- A low-level keyboard hook blocks: **Win key**, **Alt+Tab**, **Alt+F4**, **Alt+Esc**, **Ctrl+Esc**, **Ctrl+Shift+Esc**
- The user can only interact with the two buttons (or Escape = Cancel/Snooze)
- Ctrl+Alt+Del cannot be blocked (Windows kernel-level security key)

**To enable:** choose option **[8]** in the setup wizard, or answer **Y** to the On Top Mode prompt when creating any alert via options 1, 2, or 7.

**To enable manually:**

```bat
schtasks /create /tn "TimesUp OnTop" /tr "\"%LOCALAPPDATA%\TimesUp\TimesUp.exe\" --ontop" /sc daily /st 22:00 /f
```

**Combined (nuclear option) — fullscreen + no dismiss:**

```bat
schtasks /create /tn "TimesUp Nuclear" /tr "\"%LOCALAPPDATA%\TimesUp\TimesUp.exe\" --snooze --ontop" /sc daily /st 22:00 /f
```

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

## Stats & Log

Every time an alert fires and the user takes action, a record is written to:

```
%LOCALAPPDATA%\TimesUp\log.jsonl
```

Each line is a JSON object:

```json
{"ts": "2026-05-13T22:00:00", "action": "shutdown", "mode": ["snooze","ontop"], "elapsed": 12.3}
```

| Field | Values |
|-------|--------|
| `action` | `shutdown` / `snooze` / `cancel` |
| `mode` | list of active flags (`snooze`, `ontop`) |
| `elapsed` | seconds between alert appearing and action |

**To view stats:** run `setup.bat → [9]` or launch `TimesUpStats.exe` directly.

The stats window shows:
- Summary boxes: total, shutdowns, snoozes, cancels, shutdown %, avg response time
- 21-day stacked bar chart (red = shutdown, amber = snooze, grey = cancel)
- Scrollable recent log with timestamps, actions, and modes
- **Clear Log** button (irreversible)

---

## Files

```
timesup.py           Main alert source
stats.py             Stats & log viewer source
font_data.py         Pixelify Sans font embedded as base64
build.bat            Build both EXEs
setup.bat            Full setup wizard (build + Task Scheduler)
TimesUp.spec         PyInstaller spec for alert EXE
TimesUpStats.spec    PyInstaller spec for stats EXE
dist/TimesUp.exe     Alert executable (after build)
dist/TimesUpStats.exe  Stats viewer executable (after build)
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
