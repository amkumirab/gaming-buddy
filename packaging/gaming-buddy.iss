#define MyAppName "Gaming Buddy"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Amir Ali Mirab Zadeh Ardekani"
#define MyAppURL "https://github.com/amkumirab/gaming-buddy"
#define MyAppExeName "GamingBuddy.exe"

[Setup]
AppId={{57C1EB82-EEAD-4E5F-8F24-49C61A578D08}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
UninstallDisplayName={#MyAppName}
DefaultDirName={localappdata}\Programs\Gaming Buddy
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=Gaming-Buddy-Setup-{#MyAppVersion}-x64
SetupIconFile=..\src\gaming_buddy\assets\app-icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Uninstallable=yes
CreateUninstallRegKey=yes
LicenseFile=..\LICENSE
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
CloseApplicationsFilter={#MyAppExeName}
UsePreviousAppDir=yes
UsePreviousTasks=yes
VersionInfoVersion=0.1.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCopyright=Copyright © 2026 {#MyAppPublisher}. All rights reserved.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\GamingBuddy\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "GamingBuddy"; Flags: uninsdeletevalue dontcreatekey noerror

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent unchecked

[Code]
function HasCommandLineParameter(const Parameter: String): Boolean;
var
  Index: Integer;
begin
  Result := False;
  for Index := 1 to ParamCount do
  begin
    if CompareText(ParamStr(Index), Parameter) = 0 then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  RemoveData: Boolean;
begin
  if CurUninstallStep <> usUninstall then
    Exit;

  RemoveData := HasCommandLineParameter('/PURGEUSERDATA');
  if (not RemoveData) and (not UninstallSilent) then
    RemoveData := MsgBox(
      'Do you also want to permanently delete your saved cards, screenshots, layouts, and settings?' + #13#10 + #13#10 +
      'Choose No to keep them for a future installation.',
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2
    ) = IDYES;

  if RemoveData then
  begin
    DelTree(ExpandConstant('{localappdata}\GamingBuddy'), True, True, True);
    RegDeleteKeyIncludingSubkeys(HKCU, 'Software\GamingBuddy');
  end;
end;
