[Setup]
AppName=FileFlow
AppVersion=1.0.1
AppPublisher=FileFlow
AppPublisherURL=https://example.com
AppSupportURL=https://example.com
AppUpdatesURL=https://example.com
AppCopyright=Copyright (C) 2026
DefaultDirName={localappdata}\Programs\FileFlow
DefaultGroupName=FileFlow
OutputBaseFilename=FileFlow-Installer
SetupIconFile=.\fileflow_icon.ico
WizardImageFile=.\fileflow_wizard.bmp
WizardSmallImageFile=.\fileflow_small.bmp
Compression=lzma2
SolidCompression=yes
CreateAppDir=yes
CreateUninstallRegKey=yes
UninstallDisplayIcon={app}\FileFlow.exe
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: ".\dist\FileFlow.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: ".\fileflow_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: ".\fileflow_wizard.bmp"; DestDir: "{tmp}"; Flags: ignoreversion
Source: ".\fileflow_small.bmp"; DestDir: "{tmp}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\FileFlow"; Filename: "{app}\FileFlow.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\FileFlow"; Filename: "{app}\FileFlow.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\FileFlow.exe"; Description: "Run FileFlow"; Flags: nowait postinstall skipifsilent
