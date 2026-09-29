param(
  [string]$WorkspaceRoot = "C:\astrofrekans"
)

$ErrorActionPreference = 'Stop'

$workspace = (Resolve-Path -LiteralPath $WorkspaceRoot).Path.TrimEnd('\')
$assetRoot = (Resolve-Path -LiteralPath (Join-Path $workspace 'assets')).Path.TrimEnd('\')
if ($assetRoot -ne (Join-Path $workspace 'assets')) {
  throw "Unexpected asset root: $assetRoot"
}

$masterRoot = Join-Path $assetRoot 'masters\original_2026_09_22'
if (-not $masterRoot.StartsWith($assetRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
  throw "Master target escaped asset root: $masterRoot"
}

$sourceFiles = @(Get-ChildItem -LiteralPath $assetRoot -Recurse -File | Where-Object {
  -not $_.FullName.StartsWith((Join-Path $assetRoot 'masters') + '\', [StringComparison]::OrdinalIgnoreCase)
})
if ($sourceFiles.Count -ne 260) {
  throw "Expected 260 original source files before cleanup; found $($sourceFiles.Count)."
}

$sourceManifest = foreach ($file in $sourceFiles) {
  [pscustomobject]@{
    RelativePath = $file.FullName.Substring($assetRoot.Length + 1)
    Bytes = $file.Length
    Sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
  }
}

if (Test-Path -LiteralPath $masterRoot) {
  throw "Master directory already exists; refusing to overwrite: $masterRoot"
}
New-Item -ItemType Directory -Path $masterRoot -Force | Out-Null

foreach ($topLevel in Get-ChildItem -LiteralPath $assetRoot -Force | Where-Object Name -ne 'masters') {
  Copy-Item -LiteralPath $topLevel.FullName -Destination $masterRoot -Recurse
}

$manifestPath = Join-Path $assetRoot 'masters\original_2026_09_22_manifest.csv'
$sourceManifest | Export-Csv -LiteralPath $manifestPath -NoTypeInformation -Encoding utf8

$copyFiles = @(Get-ChildItem -LiteralPath $masterRoot -Recurse -File)
if ($copyFiles.Count -ne $sourceFiles.Count) {
  throw "Master copy count mismatch: source=$($sourceFiles.Count), copy=$($copyFiles.Count)."
}
foreach ($record in $sourceManifest) {
  $copyPath = Join-Path $masterRoot $record.RelativePath
  if (-not (Test-Path -LiteralPath $copyPath -PathType Leaf)) {
    throw "Master copy missing: $copyPath"
  }
  $copyHash = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash
  if ($copyHash -ne $record.Sha256) {
    throw "Master copy hash mismatch: $copyPath"
  }
}

function Assert-DestinationAbsent([string]$path) {
  if (Test-Path -LiteralPath $path) { throw "Destination already exists: $path" }
}

function Move-ExactFile([string]$sourceRelative, [string]$destinationRelative) {
  $source = Join-Path $assetRoot $sourceRelative
  $destination = Join-Path $assetRoot $destinationRelative
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Source file missing: $source" }
  Assert-DestinationAbsent $destination
  $parent = Split-Path -Parent $destination
  New-Item -ItemType Directory -Path $parent -Force | Out-Null
  Move-Item -LiteralPath $source -Destination $destination
}

# Simple whole-folder corrections.
foreach ($mapping in @(
  @('tarrot', 'tarot'),
  @('backgraunds', 'backgrounds')
)) {
  $source = Join-Path $assetRoot $mapping[0]
  $destination = Join-Path $assetRoot $mapping[1]
  if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw "Source folder missing: $source" }
  Assert-DestinationAbsent $destination
  Move-Item -LiteralPath $source -Destination $destination
}

# Rune stones move into the existing rune domain.
$stoneSource = Join-Path $assetRoot 'tas-rune'
$stoneDestination = Join-Path $assetRoot 'rune\stones'
if (-not (Test-Path -LiteralPath $stoneSource -PathType Container)) { throw "Source folder missing: $stoneSource" }
Assert-DestinationAbsent $stoneDestination
New-Item -ItemType Directory -Path $stoneDestination -Force | Out-Null
foreach ($file in Get-ChildItem -LiteralPath $stoneSource -File) {
  $destinationName = if ($file.Name -eq 'lngwaz.png') { 'ingwaz.png' } else { $file.Name }
  Move-Item -LiteralPath $file.FullName -Destination (Join-Path $stoneDestination $destinationName)
}
Remove-Item -LiteralPath $stoneSource

# UI references move with semantic names.
$uiMap = [ordered]@{
  '04bdc8c6-3497-4bcd-9f8b-f5e5a877ac56.png' = 'cosmic_calendar.png'
  '07cc11d7-18f7-4203-988e-8f99c81c4849.png' = 'natal_chart.png'
  '16e6a90e-b355-4ef5-ab8e-3dc2dbdb8fbf.png' = 'profile.png'
  '755e9d0f-3c5f-45b0-b952-a1599cdb620a.png' = 'transits.png'
  '81da2f94-6e26-47fa-b96e-5eeedd5de16a.png' = 'compatibility.png'
  '9bf23e5d-713e-4f06-8b0c-52e64225856e.png' = 'consultants.png'
  'c4dc11cc-d22c-490c-96a5-6acf1e1e4021.png' = 'home.png'
  'd6b71bc7-7950-44d1-834d-3871f8e16420.png' = 'astro_ai.png'
  'e57798f5-1714-438e-a611-9b7643db35cc.png' = 'tarot.png'
  'login_register.png' = 'login_register.png'
}
$uiSource = Join-Path $assetRoot 'app-thema'
$uiDestination = Join-Path $assetRoot 'references\ui_screens'
Assert-DestinationAbsent $uiDestination
New-Item -ItemType Directory -Path $uiDestination -Force | Out-Null
foreach ($pair in $uiMap.GetEnumerator()) {
  Move-Item -LiteralPath (Join-Path $uiSource $pair.Key) -Destination (Join-Path $uiDestination $pair.Value)
}
Remove-Item -LiteralPath $uiSource

# Natal chart move and filename normalization.
$natalSource = Join-Path $assetRoot 'dogumharitasi'
$natalDestination = Join-Path $assetRoot 'natal_chart'
Assert-DestinationAbsent $natalDestination
New-Item -ItemType Directory -Path $natalDestination -Force | Out-Null
foreach ($file in Get-ChildItem -LiteralPath $natalSource -File) {
  $destinationName = if ($file.Name -eq 'aspect-line.png') { 'aspect_line.png' } else { $file.Name }
  Move-Item -LiteralPath $file.FullName -Destination (Join-Path $natalDestination $destinationName)
}
$oldTransitIndicators = Join-Path $natalSource 'transit-gostericileri'
if (Test-Path -LiteralPath $oldTransitIndicators -PathType Container) {
  Move-Item -LiteralPath $oldTransitIndicators -Destination (Join-Path $natalDestination 'transit_indicators')
}
Remove-Item -LiteralPath $natalSource

# Planet filename corrections.
Move-ExactFile 'gezegen\puluto.png' 'gezegen\pluto.png'
Move-ExactFile 'gezegen\saturun.png' 'gezegen\saturn.png'

# Daily-frequency icons receive semantic names.
$categoryMap = [ordered]@{
  '116b61bb-4123-45d2-b6b8-66467896db0f.png' = 'love.png'
  '3e34eb61-b400-46f6-a41c-0425808dfe66.png' = 'health_balance.png'
  '46e809ba-d6cc-45f5-a830-c10f7a5902eb.png' = 'general_energy.png'
  '93ee8630-2111-4ba8-8a6f-a725d013a633.png' = 'career.png'
  'f06eaffc-0a89-4fad-b0ba-bffa643fa17c.png' = 'important_hours.png'
  'f171b089-7f1f-4b2f-95d4-c535a1555a72.png' = 'money.png'
  'f6e8d555-a5c3-4bb9-b74b-3a6c1568333e.png' = 'luck.png'
}
$categoryRoot = Join-Path $assetRoot 'kategori'
foreach ($pair in $categoryMap.GetEnumerator()) {
  Move-Item -LiteralPath (Join-Path $categoryRoot $pair.Key) -Destination (Join-Path $categoryRoot $pair.Value)
}

$productionFiles = @(Get-ChildItem -LiteralPath $assetRoot -Recurse -File | Where-Object {
  -not $_.FullName.StartsWith((Join-Path $assetRoot 'masters') + '\', [StringComparison]::OrdinalIgnoreCase)
})
if ($productionFiles.Count -ne 260) {
  throw "Post-move production count mismatch: expected 260, found $($productionFiles.Count)."
}

Write-Output "Master copy verified: $($copyFiles.Count) files"
Write-Output "Production files after rename: $($productionFiles.Count)"
Write-Output "Original manifest: $manifestPath"
