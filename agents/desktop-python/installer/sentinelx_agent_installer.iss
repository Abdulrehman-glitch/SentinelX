; SentinelX Desktop Agent — Windows installer (Sprint 7 Phase 8).
;
; Wraps the existing WinSW service scripts (..\service\install_service.ps1,
; uninstall_service.ps1, sentinelx-agent.xml) in a GUI installer: creates a
; venv, installs dependencies, prompts for backend URL + enrolment code,
; writes .env, then registers and starts the Windows service.
;
; Deliberately does NOT run the agent interactively before starting the
; service (unlike the manual README instructions) — WinSW's default service
; account is LocalSystem, which has its own Windows Credential Manager vault
; separate from the installing user's. An interactive pre-run would store
; the device token in the wrong account's vault. Instead the service
; performs its own first-run enrolment as LocalSystem, so enrolment and
; every later run happen under the same account consistently.
;
; Requires Python 3.11+ already installed and on PATH (checked before the
; wizard starts) — this is a monitoring agent for IT-managed machines, not a
; consumer app; bundling a full Python runtime was judged out of scope for
; this sprint (see docs/releases/DESKTOP_INSTALLER.md).

#define MyAppName "SentinelX Desktop Agent"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "SentinelX"

[Setup]
AppId={{B4D8F2A1-7C3E-4F5A-9D2B-8E1A6C4F3D2B}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SentinelX Agent
DefaultGroupName=SentinelX Agent
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=SentinelXAgentSetup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName={#MyAppName}
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\sentinelx_agent\*"; DestDir: "{app}\sentinelx_agent"; Excludes: "__pycache__,*.pyc"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\service\*"; DestDir: "{app}\service"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\service_allowlist.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
; The service runs as LocalSystem (WinSW's default, no <serviceaccount> override
; in sentinelx-agent.xml), whose %LOCALAPPDATA% is the built-in system profile,
; not any interactive user's — {localappdata} at install time would point
; at the wrong place, so this is hardcoded to match where the service
; actually writes.
Name: "{group}\Agent Logs"; Filename: "{win}\System32\config\systemprofile\AppData\Local\SentinelX\logs"

[Run]
Filename: "{cmd}"; Parameters: "/C py -3 -m venv "".venv"""; WorkingDir: "{app}"; StatusMsg: "Creating Python virtual environment..."; Flags: runhidden waituntilterminated
Filename: "{app}\.venv\Scripts\python.exe"; Parameters: "-m pip install --upgrade pip"; WorkingDir: "{app}"; StatusMsg: "Upgrading pip..."; Flags: runhidden waituntilterminated
Filename: "{app}\.venv\Scripts\python.exe"; Parameters: "-m pip install -r requirements.txt"; WorkingDir: "{app}"; StatusMsg: "Installing agent dependencies (this can take a minute)..."; Flags: runhidden waituntilterminated
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\service\install_service.ps1"""; WorkingDir: "{app}\service"; StatusMsg: "Registering and starting the SentinelX Agent service..."; Flags: runhidden waituntilterminated

[UninstallRun]
; Calls the bundled WinSW executable directly rather than routing through
; powershell.exe -File uninstall_service.ps1 — that invocation was found,
; during the Phase 8 install/upgrade/uninstall rehearsal, to fail silently
; specifically inside the compiled uninstaller's process (unins000.exe is a
; separate binary from Setup.exe with a different process-launch context;
; the script's own first line, a Start-Transcript call, never even fired).
; WinSW's own stop/uninstall commands are simple native calls with no
; scripting-host layer to go wrong, and already synchronously wait for the
; service to actually stop before returning.
Filename: "{app}\service\sentinelx-agent.exe"; Parameters: "stop"; WorkingDir: "{app}\service"; RunOnceId: "StopService"; Flags: runhidden waituntilterminated
Filename: "{app}\service\sentinelx-agent.exe"; Parameters: "uninstall"; WorkingDir: "{app}\service"; RunOnceId: "UninstallService"; Flags: runhidden waituntilterminated

[Code]
var
  ConfigPage: TInputQueryWizardPage;

function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // "py" (the Python Launcher, installed to %WINDIR% by every python.org
  // installer) rather than bare "python" — a user-scope Python install's
  // PATH entry isn't reliably visible to this elevated (admin) process,
  // but the launcher always is.
  if not Exec('cmd.exe', '/C py -3 --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    MsgBox(
      'Python 3.11 or later is required to run the SentinelX Desktop Agent, but it was not found (the "py" launcher is missing from PATH).' + #13#10#13#10 +
      'Install Python from https://www.python.org/downloads/ (check "Add python.exe to PATH" during install), then run this setup again.',
      mbError, MB_OK
    );
    Result := False;
  end;
end;

procedure InitializeWizard();
begin
  ConfigPage := CreateInputQueryPage(
    wpSelectDir,
    'Agent Configuration',
    'Connect this agent to your SentinelX backend',
    'Enter the backend URL and a one-time enrolment code from your organization administrator ' +
    '(Dashboard -> Devices -> Enroll Device, or POST /api/v1/devices/enrollment-codes). ' +
    'The code is single-use and is exchanged for a device token on the service''s first start.'
  );
  ConfigPage.Add('Backend API base URL:', False);
  ConfigPage.Add('Enrolment code:', False);
  ConfigPage.Values[0] := 'http://127.0.0.1:8000/api/v1';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ConfigPage.ID then
  begin
    if Trim(ConfigPage.Values[0]) = '' then
    begin
      MsgBox('Please enter the backend API base URL.', mbError, MB_OK);
      Result := False;
    end
    else if Trim(ConfigPage.Values[1]) = '' then
    begin
      MsgBox(
        'Please enter the one-time enrolment code from your organization administrator. ' +
        'The service cannot register a device without one.',
        mbError, MB_OK
      );
      Result := False;
    end;
  end;
end;

procedure WriteAgentEnvFile();
var
  Lines: TArrayOfString;
  EnvPath: string;
begin
  SetArrayLength(Lines, 8);
  Lines[0] := '# Written by the SentinelX Agent installer — see .env.example for every option.';
  Lines[1] := 'SENTINELX_API_BASE_URL=' + Trim(ConfigPage.Values[0]);
  Lines[2] := 'SENTINELX_ENROLLMENT_CODE=' + Trim(ConfigPage.Values[1]);
  Lines[3] := 'SENTINELX_DEVICE_TYPE=desktop';
  Lines[4] := 'SENTINELX_AGENT_TYPE=python_desktop_agent';
  Lines[5] := 'SENTINELX_AGENT_VERSION=3.0.0';
  Lines[6] := 'SENTINELX_COMMAND_POLLING_ENABLED=true';
  Lines[7] := 'SENTINELX_SERVICE_ALLOWLIST_PATH=service_allowlist.json';

  EnvPath := ExpandConstant('{app}\.env');
  SaveStringsToFile(EnvPath, Lines, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    WriteAgentEnvFile();
  end;
end;
