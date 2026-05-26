; ── Time's Up! — Inno Setup installer script ─────────────────────────────────
; Requires Inno Setup 6.x: https://jrsoftware.org/isdl.php
; Build: iscc installer.iss   →   Output\TimesUpInstaller.exe

#define MyAppName    "Time's Up!"
#define MyAppVersion "1.1"
#define MyAppSlug    "TimesUp"
#define MyAppPublisher "mikaelbhai"
#define MyAppURL     "https://github.com/mikaelbhai/TImesUp"

[Setup]
AppId={{3F8A2C1D-B47E-4F90-9E2A-6C5D8F3A1B72}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

; Install per-user — no admin needed
PrivilegesRequired=lowest
DefaultDirName={localappdata}\{#MyAppSlug}
DisableDirPage=yes
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=no

OutputDir=Output
OutputBaseFilename=TimesUpInstaller-v{#MyAppVersion}
WizardStyle=modern
DisableWelcomePage=no
LicenseFile=OFL.txt

Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible

UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\TimesUp.exe
CreateUninstallRegKey=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ── Files ─────────────────────────────────────────────────────────────────────
[Files]
Source: "dist\TimesUp.exe";      DestDir: "{app}"; Flags: ignoreversion
Source: "dist\TimesUpStats.exe"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\dist\TimesUpStats.exe'))
Source: "dist\TimesUpTray.exe";  DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\dist\TimesUpTray.exe'))

; ── Start Menu shortcuts ──────────────────────────────────────────────────────
[Icons]
Name: "{group}\{#MyAppName} — Tray Manager"; Filename: "{app}\TimesUpTray.exe"
Name: "{group}\{#MyAppName} — Stats Viewer"; Filename: "{app}\TimesUpStats.exe"
Name: "{group}\Uninstall {#MyAppName}";      Filename: "{uninstallexe}"

; ── Run after install ─────────────────────────────────────────────────────────
[Run]
Filename: "{app}\TimesUpTray.exe"; Description: "Launch the Tray Manager now (recommended)"; Flags: nowait postinstall skipifsilent

; ── Uninstall cleanup ─────────────────────────────────────────────────────────
[UninstallRun]
; Kill running processes gracefully
Filename: "taskkill"; Parameters: "/f /im TimesUpTray.exe";  Flags: runhidden; RunOnceId: "KillTray"
Filename: "taskkill"; Parameters: "/f /im TimesUp.exe";      Flags: runhidden; RunOnceId: "KillAlert"
Filename: "taskkill"; Parameters: "/f /im TimesUpStats.exe"; Flags: runhidden; RunOnceId: "KillStats"
; Remove any scheduled tasks created by the app
Filename: "schtasks"; Parameters: "/delete /tn ""TimesUp Alert"" /f"; Flags: runhidden; RunOnceId: "DelTaskAlert"
Filename: "schtasks"; Parameters: "/delete /tn ""TimesUp Snooze"" /f"; Flags: runhidden; RunOnceId: "DelTaskSnooze"

[UninstallDelete]
; Remove log + config left in AppData\Local\TimesUp
Type: filesandordirs; Name: "{localappdata}\TimesUp"

; ── Custom wizard pages & messages ───────────────────────────────────────────
[Messages]
WelcomeLabel1=Welcome to the [name] Setup Wizard
WelcomeLabel2=This will install [name/ver] on your computer.%n%nTime's Up! shows a full-screen shutdown alert at a scheduled time — impossible to miss.%n%nClick Next to continue.
FinishedLabel=Time's Up! has been installed.%n%nThe Tray Manager lets you schedule alerts, toggle Snooze and On Top modes, and view your activity log.

[Code]
// ── At uninstall: also remove any schtasks whose name starts with "TimesUp" ──
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Exec('schtasks', '/delete /tn "TimesUp Alert" /f',  '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('schtasks', '/delete /tn "TimesUp Snooze" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
