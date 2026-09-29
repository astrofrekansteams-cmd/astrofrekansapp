$ErrorActionPreference = 'Stop'
$assetRoot = (Resolve-Path -LiteralPath 'C:\astrofrekans\assets').Path.TrimEnd('\')
if ($assetRoot -ne 'C:\astrofrekans\assets') { throw "Unexpected asset root: $assetRoot" }

$oldTransit = Join-Path $assetRoot 'dogumharitasi\transit-gostericileri'
$newTransit = Join-Path $assetRoot 'natal_chart\transit_indicators'
if (Test-Path -LiteralPath $oldTransit -PathType Container) {
  if (Test-Path -LiteralPath $newTransit) { throw "Destination exists: $newTransit" }
  Move-Item -LiteralPath $oldTransit -Destination $newTransit
}

$oldNatal = Join-Path $assetRoot 'dogumharitasi'
if (Test-Path -LiteralPath $oldNatal -PathType Container) {
  if (@(Get-ChildItem -LiteralPath $oldNatal -Force).Count -ne 0) { throw "Refusing to remove non-empty directory: $oldNatal" }
  Remove-Item -LiteralPath $oldNatal -Force
}

foreach ($mapping in @(
  @('gezegen\puluto.png', 'gezegen\pluto.png'),
  @('gezegen\saturun.png', 'gezegen\saturn.png')
)) {
  $source = Join-Path $assetRoot $mapping[0]
  $destination = Join-Path $assetRoot $mapping[1]
  if (Test-Path -LiteralPath $source -PathType Leaf) {
    if (Test-Path -LiteralPath $destination) { throw "Destination exists: $destination" }
    Move-Item -LiteralPath $source -Destination $destination
  }
}

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
  $source = Join-Path $categoryRoot $pair.Key
  $destination = Join-Path $categoryRoot $pair.Value
  if (Test-Path -LiteralPath $source -PathType Leaf) {
    if (Test-Path -LiteralPath $destination) { throw "Destination exists: $destination" }
    Move-Item -LiteralPath $source -Destination $destination
  }
}

$productionFiles = @(Get-ChildItem -LiteralPath $assetRoot -Recurse -File | Where-Object {
  -not $_.FullName.StartsWith((Join-Path $assetRoot 'masters') + '\', [StringComparison]::OrdinalIgnoreCase)
})
$masterFiles = @(Get-ChildItem -LiteralPath (Join-Path $assetRoot 'masters\original_2026_09_22') -Recurse -File)

if ($productionFiles.Count -ne 260) { throw "Production file count mismatch: $($productionFiles.Count)" }
if ($masterFiles.Count -ne 260) { throw "Master file count mismatch: $($masterFiles.Count)" }

Write-Output "Production files after rename: $($productionFiles.Count)"
Write-Output "Verified master files: $($masterFiles.Count)"
