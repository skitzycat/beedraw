!define py2exeOutputDirectory 'dist'
!include "Sections.nsh"

; Comment out the "SetCompress Off" line and uncomment
; the next line to enable compression. Startup times
; will be a little slower but the executable will be
; quite a bit smaller
SetCompress Off
;SetCompressor lzma

Name 'Bee Draw'
OutFile "install-beedraw.exe"

page license
page components
page instfiles

LicenseData license.txt

InstallDir "$PROGRAMFILES"
InstallDirRegKey HKLM "SOFTWARE\Bee Draw" "$INSTDIR"
DirText "Select the directory to install Bee Draw in:"

;SilentInstall silent
;Icon 'icon.ico'

Section "Base Files"
    SectionIn RO
    writeRegStr HKLM "SOFTWARE\Bee Draw" "" "$INSTDIR"
    SetOutPath '$INSTDIR\beedraw\config'
    File 'config\default.pal'
    SetOutPath '$INSTDIR\beedraw'
    File '${py2exeOutputDirectory}\*.*'
SectionEnd

Section "Put short cut in start menu" SEC_START
    sectionIn 1
    CreateDirectory "$SMPROGRAMS\Bee Draw"
    createShortCut "$SMPROGRAMS\Bee Draw\beedraw.lnk" "$INSTDIR\beedraw\beedraw.exe"
    createShortCut "$SMPROGRAMS\Bee Draw\hive.lnk" "$INSTDIR\beedraw\hive.exe"
SectionEnd

Section "Create desktop shortcuts" SEC_DESK
    sectionIn 2
    createShortCut "$DESKTOP\beedraw.lnk" "$INSTDIR\beedraw\beedraw.exe"
    createShortCut "$DESKTOP\hive.lnk" "$INSTDIR\beedraw\hive.exe"
SectionEnd

Function .onInit
  StrCpy $1 ${SEC_DESK}
Functionend

;Function .onSelChange
;  !insertmacro StartRadioButtons $1
;    !insertmacro RadioButton ${SEC_START}
;    !insertmacro RadioButton ${SEC_DESK}
;  !insertMacro EndRadioButtons
;Functionend