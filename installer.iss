; Inno Setup script - Sarchahan Smart School Management
#define MyAppName "Sarchahan Smart School"
#define MyAppFa "مدیریت هوشمند مدرسه سرچهان"
#define MyAppExe "SarchahanSchool.exe"

[Setup]
AppId={{B7C1E0A4-5D2F-4F6B-9A3E-7C2D8E1F0A55}
AppName={#MyAppName}
AppVersion=1.1
AppPublisher=Sarchahan School
DefaultDirName={autopf}\SarchahanSchool
DefaultGroupName={#MyAppFa}
OutputDir=installer_output
OutputBaseFilename=SarchahanSchool_Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExe}
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "resetshortcut"; Description: "Add a 'reset admin password' shortcut to the Start menu"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Dirs]
; پوشه‌ی داده‌ها (دیتابیس): برای همه‌ی کاربران ویندوز قابل نوشتن است و با حذف برنامه پاک نمی‌شود
Name: "{commonappdata}\SarchahanSchool"; Permissions: users-modify

[Files]
Source: "dist\SarchahanSchool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppFa}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\بازنشانی رمز مدیر"; Filename: "{app}\{#MyAppExe}"; Parameters: "--reset-admin"; Tasks: resetshortcut
Name: "{autodesktop}\{#MyAppFa}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Launch the program"; Flags: nowait postinstall skipifsilent
