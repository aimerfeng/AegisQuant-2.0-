; ============================================================================
; Titan-Quant NSIS Installer Custom Script
; ============================================================================

!macro customHeader
  ; Custom header code
!macroend

!macro preInit
  ; Pre-initialization code
!macroend

!macro customInit
  ; Custom initialization code
!macroend

!macro customInstall
  ; Create additional directories
  CreateDirectory "$INSTDIR\logs"
  CreateDirectory "$INSTDIR\database"
  CreateDirectory "$INSTDIR\reports"
  CreateDirectory "$INSTDIR\strategies"
!macroend

!macro customUnInstall
  ; Clean up additional directories
  RMDir /r "$INSTDIR\logs"
  RMDir /r "$INSTDIR\database"
  RMDir /r "$INSTDIR\reports"
  RMDir /r "$INSTDIR\strategies"
!macroend

!macro customInstallMode
  ; Set installation mode
!macroend
