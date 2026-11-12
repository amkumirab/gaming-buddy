const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{57C1EB82-EEAD-4E5F-8F24-49C61A578D08}_is1';

var
  InstalledVersion: String;
  InstalledPacked: Int64;
  HasInstalledVersion: Boolean;

function ParseInstalledVersion(Value: String; var Packed: Int64): Boolean;
var
  I, Dots: Integer;
begin
  Result := False;
  if (Length(Value) = 0) or (Length(Value) > 64) then Exit;
  Dots := 0;
  for I := 1 to Length(Value) do
    if Value[I] = '.' then Dots := Dots + 1
    else if (Value[I] < '0') or (Value[I] > '9') then Exit;
  if (Dots <> 2) and (Dots <> 3) then Exit;
  Result := StrToVersion(Value, Packed);
end;

function RememberVersion(Value: String): String;
var
  Packed: Int64;
begin
  Result := '';
  if not ParseInstalledVersion(Value, Packed) then
  begin
    Result := 'The installed Gaming Buddy version could not be verified. ' +
      'Uninstall it while keeping your data, then run this installer again.';
    Exit;
  end;
  if (not HasInstalledVersion) or (ComparePackedVersion(Packed, InstalledPacked) > 0) then
  begin
    InstalledVersion := Value;
    InstalledPacked := Packed;
    HasInstalledVersion := True;
  end;
end;

function InspectExecutable(Directory: String): String;
var
  FileName, Value: String;
begin
  Result := '';
  FileName := AddBackslash(Directory) + '{#MyAppExeName}';
  if not FileExists(FileName) then Exit;
  if not GetVersionNumbersString(FileName, Value) then
    Result := 'The existing Gaming Buddy executable has no readable version. ' +
      'Uninstall the existing copy while keeping your data before reinstalling.'
  else Result := RememberVersion(Value);
end;

function InspectRegistration(Root: Integer): String;
var
  Value, Directory: String;
begin
  Result := '';
  if not RegKeyExists(Root, UninstallKey) then Exit;
  if not RegQueryStringValue(Root, UninstallKey, 'DisplayVersion', Value) then
    Result := RememberVersion('')
  else Result := RememberVersion(Value);
  if Result <> '' then Exit;
  if RegQueryStringValue(Root, UninstallKey, 'InstallLocation', Directory) then
    if Directory <> '' then Result := InspectExecutable(Directory);
end;

function CheckInstalledVersion(TargetDirectory: String): String;
var
  Target: Int64;
begin
  HasInstalledVersion := False;
  InstalledVersion := '';
  Result := InspectRegistration(HKCU32);
  if (Result = '') and IsWin64 then Result := InspectRegistration(HKCU64);
  if (Result = '') and (TargetDirectory <> '') then
    Result := InspectExecutable(TargetDirectory);
  if Result <> '' then Exit;
  if not ParseInstalledVersion('{#MyAppVersion}', Target) then
  begin
    Result := 'This installer contains an invalid version.';
    Exit;
  end;
  if HasInstalledVersion and (ComparePackedVersion(InstalledPacked, Target) > 0) then
    Result := 'A newer Gaming Buddy version (' + InstalledVersion + ') is already installed. ' +
      'This installer (' + '{#MyAppVersion}' + ') cannot replace it. Your files have not been changed.';
end;

function InitializeSetup: Boolean;
var
  Error: String;
begin
  Error := CheckInstalledVersion('');
  Result := Error = '';
  if not Result then
  begin
    Log(Error);
    SuppressibleMsgBox(Error, mbError, MB_OK, IDOK);
  end;
end;

function MaintenanceOperation: String;
var
  Target: Int64;
begin
  Result := 'Install';
  if not HasInstalledVersion then Exit;
  StrToVersion('{#MyAppVersion}', Target);
  if ComparePackedVersion(InstalledPacked, Target) = 0 then Result := 'Reinstall'
  else Result := 'Upgrade';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := CheckInstalledVersion(ExpandConstant('{app}'));
  if Result <> '' then Exit;
  Log('Maintenance operation: ' + MaintenanceOperation + '; installed=' + InstalledVersion +
    '; installer={#MyAppVersion}');
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo,
  MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
var
  Error, Operation: String;
begin
  Error := CheckInstalledVersion(ExpandConstant('{app}'));
  Operation := MaintenanceOperation;
  Result := Operation + ' Gaming Buddy' + NewLine;
  if HasInstalledVersion then Result := Result + 'Installed version: ' + InstalledVersion + NewLine;
  Result := Result + 'Installer version: {#MyAppVersion}' + NewLine +
    'Your saved cards, screenshots and settings will be kept.' + NewLine + NewLine +
    MemoDirInfo + NewLine + MemoTasksInfo;
  if Error <> '' then Result := Error;
  WizardForm.NextButton.Caption := Operation;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpReady then WizardForm.NextButton.Caption := MaintenanceOperation;
end;
