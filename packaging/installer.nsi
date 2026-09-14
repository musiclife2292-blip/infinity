Unicode True
!include "MUI2.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
!define APP_NAME "Infinity audio"
!define APP_VERSION "0.1.0-alpha.2"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\InfinityAudio"
Name "${APP_NAME} ${APP_VERSION}"
OutFile "..\dist\Infinity-audio-0.1.0-alpha.2-win64-setup.exe"
InstallDir "$LOCALAPPDATA\Programs\InfinityAudio"
InstallDirRegKey HKCU "Software\InfinityAudio" "InstallDir"
RequestExecutionLevel user
SetCompressor zlib
ShowInstDetails show
ShowUninstDetails show
VIProductVersion "0.1.0.2"
VIAddVersionKey "ProductName" "Infinity audio"
VIAddVersionKey "FileDescription" "Infinity audio alpha installer — chưa nghiệm thu đầy đủ"
VIAddVersionKey "FileVersion" "0.1.0.2"
VIAddVersionKey "LegalCopyright" "Infinity audio contributors — GPL-3.0-only"
!define MUI_ICON "..\assets\infinity.ico"
!define MUI_UNICON "..\assets\infinity.ico"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\InfinityAudio.exe"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Vietnamese"
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Infinity audio cần Windows x64."
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "Infinity audio cần Windows 10/11 x64. Mục tiêu thử nghiệm: Windows 10 22H2 và Windows 11 23H2/24H2."
    Abort
  ${EndIf}
  SetRegView 64
FunctionEnd

Section "Infinity audio" Main
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "..\dist\InfinityAudio\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\InfinityAudio" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "Infinity audio (alpha)"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "Infinity audio contributors"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\InfinityAudio.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '$\"$INSTDIR\Uninstall.exe$\" /S'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
  CreateDirectory "$SMPROGRAMS\Infinity audio"
  CreateShortcut "$SMPROGRAMS\Infinity audio\Infinity audio.lnk" "$INSTDIR\InfinityAudio.exe"
  CreateShortcut "$SMPROGRAMS\Infinity audio\Gỡ cài đặt.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  SetRegView 64
  ; Only installed application files are removed. User projects/recovery data remain.
  Delete "$INSTDIR\InfinityAudio.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR\_internal"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\Infinity audio\Infinity audio.lnk"
  Delete "$SMPROGRAMS\Infinity audio\Gỡ cài đặt.lnk"
  RMDir "$SMPROGRAMS\Infinity audio"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  DeleteRegKey HKCU "Software\InfinityAudio"
SectionEnd
