; 漫剧制作助手 — 个人通道 Inno Setup 6 安装脚本（REL-04B）
; 由 scripts/installer_build.py 传入 /DAppVersion=<contract.app_metadata.VERSION> 与 /DSourceDir=<分发副本目录>
; 升级只覆盖程序文件，绝不覆盖或删除用户配置、私有数据、运行数据与用户项目。

[Setup]
AppId={{8B4E2C1D-9F3A-4E6B-A7C2-5D1F8E3B9A40}
AppName=漫剧制作助手
AppVersion={#AppVersion}
AppPublisher=漫剧制作助手
DefaultDirName={localappdata}\漫剧制作助手
DefaultGroupName=漫剧制作助手
PrivilegesRequired=lowest
WizardStyle=modern dark
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
SetupIconFile={#SourceDir}\漫剧制作助手.ico
UninstallDisplayIcon={app}\漫剧制作助手.ico
OutputBaseFilename=漫剧助手-{#AppVersion}
#ifdef Signed
SignTool=SignedCode $f
SignedUninstaller=yes
#endif

[Languages]
Name: "default"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"

[Files]
; 整目录递归安装程序文件，显式排除开发缓存、用户配置、运行数据、私有数据与日志
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: ".git\*,__pycache__\*,*.pyc,config.json,desktop_settings.json,projects.json,private\*,data\*,配置\*,app.log*,tasks_round\evidence\*"; Flags: ignoreversion recursesubdirs createallsubdirs
; 规格 §2.3：内置术语表是程序文件，排除 data\* 后单独放回并随包覆盖
Source: "{#SourceDir}\程序\data\skill_note_terms_zh.json"; DestDir: "{app}\程序\data"; Flags: ignoreversion
; 分发清单保留的默认配置种子：仅在目标不存在时写入，升级绝不覆盖用户配置
Source: "{#SourceDir}\程序\配置\客户端档案.json"; DestDir: "{app}\程序\配置"; Flags: onlyifdoesntexist
Source: "{#SourceDir}\程序\配置\SKILL\预设.json"; DestDir: "{app}\程序\配置\SKILL"; Flags: onlyifdoesntexist

[Icons]
Name: "{autoprograms}\漫剧制作助手"; Filename: "{app}\运行环境\Python\pythonw.exe"; Parameters: "-I ""{app}\启动漫剧制作助手.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\漫剧制作助手.ico"
Name: "{autodesktop}\漫剧制作助手"; Filename: "{app}\运行环境\Python\pythonw.exe"; Parameters: "-I ""{app}\启动漫剧制作助手.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\漫剧制作助手.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\运行环境\Python\pythonw.exe"; Parameters: "-I ""{app}\启动漫剧制作助手.pyw"""; WorkingDir: "{app}"; Description: "启动漫剧制作助手"; Flags: nowait postinstall skipifsilent

[Code]
function CopyDirRecursive(const SrcDir, DstDir: String): Boolean;
var
  FindRec: TFindRec;
  SrcPath, DstPath: String;
begin
  Result := True;
  if not DirExists(SrcDir) then
    Exit;
  if not ForceDirectories(DstDir) then
  begin
    Result := False;
    Exit;
  end;
  if FindFirst(AddBackslash(SrcDir) + '*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          SrcPath := AddBackslash(SrcDir) + FindRec.Name;
          DstPath := AddBackslash(DstDir) + FindRec.Name;
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          begin
            if not CopyDirRecursive(SrcPath, DstPath) then
              Result := False;
          end
          else
          begin
            if not FileCopy(SrcPath, DstPath, False) then
              Result := False;
          end;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure BackupUserDataBeforeUpgrade;
var
  AppDir, ProgDir, BackupRoot, BackupProg, Stamp: String;
  NeedBackup, AllOk: Boolean;
begin
  AppDir := ExpandConstant('{app}');
  ProgDir := AddBackslash(AppDir) + '程序';
  NeedBackup :=
    FileExists(AddBackslash(ProgDir) + 'config.json') or
    FileExists(AddBackslash(ProgDir) + 'desktop_settings.json') or
    FileExists(AddBackslash(ProgDir) + 'projects.json') or
    DirExists(AddBackslash(ProgDir) + 'private') or
    DirExists(AddBackslash(ProgDir) + 'data') or
    DirExists(AddBackslash(ProgDir) + '配置');
  if not NeedBackup then
    Exit;

  Stamp := GetDateTimeString('yyyymmdd_hhnnss', #0, #0);
  BackupRoot := AddBackslash(AppDir) + '_upgrade_backup\' + Stamp;
  BackupProg := AddBackslash(BackupRoot) + '程序';
  AllOk := ForceDirectories(BackupProg);

  if AllOk and FileExists(AddBackslash(ProgDir) + 'config.json') then
    if not FileCopy(AddBackslash(ProgDir) + 'config.json', AddBackslash(BackupProg) + 'config.json', False) then
      AllOk := False;
  if AllOk and FileExists(AddBackslash(ProgDir) + 'desktop_settings.json') then
    if not FileCopy(AddBackslash(ProgDir) + 'desktop_settings.json', AddBackslash(BackupProg) + 'desktop_settings.json', False) then
      AllOk := False;
  if AllOk and FileExists(AddBackslash(ProgDir) + 'projects.json') then
    if not FileCopy(AddBackslash(ProgDir) + 'projects.json', AddBackslash(BackupProg) + 'projects.json', False) then
      AllOk := False;
  if AllOk and DirExists(AddBackslash(ProgDir) + 'private') then
    if not CopyDirRecursive(AddBackslash(ProgDir) + 'private', AddBackslash(BackupProg) + 'private') then
      AllOk := False;
  if AllOk and DirExists(AddBackslash(ProgDir) + 'data') then
    if not CopyDirRecursive(AddBackslash(ProgDir) + 'data', AddBackslash(BackupProg) + 'data') then
      AllOk := False;
  if AllOk and DirExists(AddBackslash(ProgDir) + '配置') then
    if not CopyDirRecursive(AddBackslash(ProgDir) + '配置', AddBackslash(BackupProg) + '配置') then
      AllOk := False;

  if (not AllOk) and (not WizardSilent) then
    MsgBox(
      '升级前备份用户数据未完全成功（备份目录：' + BackupRoot + '）。' + #13#10 +
      '现有用户数据不会被移动或删除，安装将继续进行。',
      mbInformation, MB_OK
    );
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    BackupUserDataBeforeUpgrade;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDir: String;
  Choice: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if not UninstallSilent then
    begin
      AppDir := ExpandConstant('{app}');
      Choice := MsgBox(
        '是否保留用户配置与运行数据（config.json、desktop_settings.json、projects.json、data、private、配置）？' + #13#10 +
        '建议选择「是」保留（默认）；卸载程序不会自动删除任何用户数据或项目文件。',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON1
      );
      if Choice = IDNO then
        MsgBox(
          '为保护用户数据，卸载程序不会自动删除 config.json、desktop_settings.json、projects.json、data、private 与 配置 目录。' + #13#10 +
          '如需彻底清理，请手动检查并删除：' + AddBackslash(AppDir) + '程序',
          mbInformation, MB_OK
        );
    end;
  end;
end;
