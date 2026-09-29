$ErrorActionPreference = 'Stop'

$oldBackground = 'C:\astrofrekans\assets\backgrounds\login_backgraud.png'
$newBackground = 'C:\astrofrekans\assets\backgrounds\login_background.png'
if (Test-Path -LiteralPath $oldBackground -PathType Leaf) {
  if (Test-Path -LiteralPath $newBackground) { throw "Target already exists: $newBackground" }
  Move-Item -LiteralPath $oldBackground -Destination $newBackground
}

$legacyAi = 'C:\astrofrekans\assets\ai'
if ((Test-Path -LiteralPath $legacyAi -PathType Container) -and
    @(Get-ChildItem -LiteralPath $legacyAi -Force).Count -eq 0) {
  Remove-Item -LiteralPath $legacyAi
}

Write-Output 'Final asset names normalized.'
