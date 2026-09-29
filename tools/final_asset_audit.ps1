$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$projectRoot = 'C:\astrofrekans'
$assetRoot = Join-Path $projectRoot 'assets'
$manifestPath = Join-Path $projectRoot 'assets_manifest.json'
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json

function Get-AssetPaths($value) {
  if ($value -is [string] -and $value -match '^assets/.+\.(png|webp|jpg|jpeg)$') { return $value }
  if ($value -is [System.Collections.IEnumerable] -and $value -isnot [string]) {
    foreach ($item in $value) { Get-AssetPaths $item }
  } elseif ($value -is [pscustomobject]) {
    foreach ($property in $value.PSObject.Properties) { Get-AssetPaths $property.Value }
  }
}

$productionPaths = @(Get-AssetPaths $manifest | Sort-Object -Unique)
$broken = @($productionPaths | Where-Object {
  -not (Test-Path -LiteralPath (Join-Path $projectRoot $_) -PathType Leaf)
})

$expectedCounts = [ordered]@{
  zodiac = 12; planets = 12; moon_phases = 8; elements = 4;
  daily_frequency = 7; tarot_cards = 78; katina_cards = 65;
  rune_cards = 25; rune_stones = 24; astro_ai = 5;
  empty_states = 6; consultants = 1; premium = 3
}
$actualCounts = [ordered]@{
  zodiac = @($manifest.zodiac).Count
  planets = @($manifest.planets).Count
  moon_phases = @($manifest.moon_phases).Count
  elements = @($manifest.elements).Count
  daily_frequency = @($manifest.daily_frequency).Count
  tarot_cards = @($manifest.tarot.cards).Count
  katina_cards = @($manifest.katina.cards).Count
  rune_cards = @($manifest.rune.cards).Count
  rune_stones = @($manifest.rune.stones).Count
  astro_ai = @($manifest.astro_ai).Count
  empty_states = @($manifest.empty_states).Count
  consultants = @($manifest.consultants).Count
  premium = @($manifest.premium).Count
}
$countErrors = @($expectedCounts.Keys | Where-Object { $actualCounts[$_] -ne $expectedCounts[$_] })

$sizeRules = [System.Collections.Generic.List[object]]::new()
function Add-SizeRule([string[]]$paths, [int]$width, [int]$height) {
  foreach ($path in $paths) { $sizeRules.Add([pscustomobject]@{Path=$path; Width=$width; Height=$height}) }
}
Add-SizeRule @($manifest.zodiac) 1024 1024
Add-SizeRule @($manifest.planets) 1024 1024
Add-SizeRule @($manifest.moon_phases) 1024 1024
Add-SizeRule @($manifest.elements) 1024 1024
Add-SizeRule @($manifest.daily_frequency) 1024 1024
Add-SizeRule @($manifest.astro_ai) 1024 1024
Add-SizeRule @($manifest.empty_states) 1024 1024
Add-SizeRule @($manifest.consultants) 1024 1024
Add-SizeRule @($manifest.premium) 1024 1024
Add-SizeRule @($manifest.rune.stones) 1024 1536
Add-SizeRule @($manifest.natal_chart.overlays) 1024 1024
Add-SizeRule @($manifest.natal_chart.asc,$manifest.natal_chart.dsc,$manifest.natal_chart.mc,$manifest.natal_chart.ic,$manifest.natal_chart.retrograde,$manifest.natal_chart.zodiac_wheel) 1024 1024
Add-SizeRule @($manifest.branding.app_icon) 1024 1024
Add-SizeRule @($manifest.branding.splash_background) 1080 1920
Add-SizeRule @($manifest.branding.onboarding) 1024 1536
Add-SizeRule @('assets/branding/logo/brand_mark.png','assets/branding/logo/brand_lockup_compact.png') 1024 1024
Add-SizeRule @('assets/branding/logo/brand_lockup_full.png') 1536 1536

$wrongSize = [System.Collections.Generic.List[object]]::new()
foreach ($rule in $sizeRules) {
  $fullPath = Join-Path $projectRoot $rule.Path
  if (-not (Test-Path -LiteralPath $fullPath)) { continue }
  $image = [System.Drawing.Bitmap]::new($fullPath)
  try {
    if ($image.Width -ne $rule.Width -or $image.Height -ne $rule.Height) {
      $wrongSize.Add([pscustomobject]@{Path=$rule.Path; Actual="$($image.Width)x$($image.Height)"; Expected="$($rule.Width)x$($rule.Height)"})
    }
  } finally { $image.Dispose() }
}

$opaquePaths = @(
  $manifest.branding.app_icon,
  $manifest.branding.splash_background
) + @($manifest.backgrounds) + @($manifest.ui_references)
$transparentPngs = @($productionPaths | Where-Object {
  $_ -like '*.png' -and $_ -notin $opaquePaths
})
$alphaErrors = [System.Collections.Generic.List[object]]::new()
foreach ($path in $transparentPngs) {
  $fullPath = Join-Path $projectRoot $path
  $image = [System.Drawing.Bitmap]::new($fullPath)
  try {
    $cornerAlphas = @(
      $image.GetPixel(0,0).A,
      $image.GetPixel($image.Width-1,0).A,
      $image.GetPixel(0,$image.Height-1).A,
      $image.GetPixel($image.Width-1,$image.Height-1).A
    )
    if (($cornerAlphas | Measure-Object -Maximum).Maximum -gt 8) {
      $alphaErrors.Add([pscustomobject]@{Path=$path; CornerAlpha=($cornerAlphas -join ',')})
    }
  } finally { $image.Dispose() }
}

$badNamePattern = '(?i)(tarrot|backgraunds|backgraud|tas-rune|dogumharitasi|puluto|saturun|lngwaz|aspect-line|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
$unresolvedNames = @($productionPaths | Where-Object { $_ -match $badNamePattern })

$hashRows = foreach ($path in $productionPaths) {
  $fullPath = Join-Path $projectRoot $path
  if (Test-Path -LiteralPath $fullPath) {
    [pscustomobject]@{Path=$path; Hash=(Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash}
  }
}
$duplicateGroups = @($hashRows | Group-Object Hash | Where-Object Count -gt 1)

$dartPath = Join-Path $projectRoot 'lib\core\assets\app_assets.dart'
$dartText = Get-Content -Raw -LiteralPath $dartPath
$dartPaths = @([regex]::Matches($dartText, 'assets/[A-Za-z0-9_./-]+\.(?:png|webp)') | ForEach-Object Value | Sort-Object -Unique)
$dartBroken = @($dartPaths | Where-Object { -not (Test-Path -LiteralPath (Join-Path $projectRoot $_)) })

$masterFiles = @(Get-ChildItem -LiteralPath (Join-Path $assetRoot 'masters\original_2026_09_22') -Recurse -File)
$rawGenerated = @(Get-ChildItem -LiteralPath (Join-Path $assetRoot 'masters\generated_missing_raw') -Recurse -File)
$productionBytes = ($productionPaths | ForEach-Object { (Get-Item -LiteralPath (Join-Path $projectRoot $_)).Length } | Measure-Object -Sum).Sum
$masterBytes = ($masterFiles | Measure-Object Length -Sum).Sum
$generatedRawBytes = ($rawGenerated | Measure-Object Length -Sum).Sum

$cardCsv = Import-Csv -LiteralPath (Join-Path $projectRoot 'reports\card_optimization.csv')
$cardSourceBytes = ($cardCsv | Measure-Object SourceBytes -Sum).Sum
$cardProductionBytes = ($cardCsv | Measure-Object ProductionBytes -Sum).Sum
$cardSavedPercent = [math]::Round((1-$cardProductionBytes/$cardSourceBytes)*100,1)

$gate = [ordered]@{
  MISSING = $countErrors.Count
  WRONG_SIZE = $wrongSize.Count
  BROKEN_PATH = $broken.Count + $dartBroken.Count
  UNRESOLVED_RENAME = $unresolvedNames.Count
  ALPHA_ERROR = $alphaErrors.Count
  DUPLICATE_GROUP = $duplicateGroups.Count
}
$ready = @($gate.Values | Where-Object { $_ -ne 0 }).Count -eq 0

$sizeLines = [System.Collections.Generic.List[string]]::new()
$sizeLines.Add('# Assets Size Report')
$sizeLines.Add('')
$sizeLines.Add('| Scope | Files | Size |')
$sizeLines.Add('|---|---:|---:|')
$sizeLines.Add("| Original master snapshot | $($masterFiles.Count) | $([math]::Round($masterBytes/1MB,2)) MiB |")
$sizeLines.Add("| Raw generated missing assets | $($rawGenerated.Count) | $([math]::Round($generatedRawBytes/1MB,2)) MiB |")
$sizeLines.Add("| Runtime manifest | $($productionPaths.Count) | $([math]::Round($productionBytes/1MB,2)) MiB |")
$sizeLines.Add('')
$sizeLines.Add('## Card optimization')
$sizeLines.Add('')
$sizeLines.Add("- Source PNG total: $([math]::Round($cardSourceBytes/1MB,2)) MiB")
$sizeLines.Add("- Production WebP total: $([math]::Round($cardProductionBytes/1MB,2)) MiB")
$sizeLines.Add("- Savings: $cardSavedPercent%")
$sizeLines.Add('- Quality setting: WebP quality 88, picture preset, compression level 6')
$sizeLines.Add('- Source PNG files remain untouched.')
$sizeLines | Set-Content -LiteralPath (Join-Path $projectRoot 'assets_size_report.md') -Encoding UTF8

$audit = [System.Collections.Generic.List[string]]::new()
$audit.Add('# Astrofrekans Final Asset Audit')
$audit.Add('')
$audit.Add("Status: **$(if($ready){'ASSETS READY'}else{'ASSETS NOT READY'})**")
$audit.Add('')
$audit.Add('| Gate | Result |')
$audit.Add('|---|---:|')
foreach ($item in $gate.GetEnumerator()) { $audit.Add("| $($item.Key) | $($item.Value) |") }
$audit.Add('')
$audit.Add('## Delivery summary')
$audit.Add('')
$audit.Add("- Total source assets: $($masterFiles.Count)")
$audit.Add("- Production assets: $($productionPaths.Count)")
$audit.Add('- Generated: 20')
$audit.Add('- Renamed: 21 files plus 5 folder moves')
$audit.Add('- Standardized: 24 rune stones; 20 generated assets normalized to production canvases')
$audit.Add('- Transparent derivatives: 76 existing-art derivatives (52 symbol/logo assets plus 24 rune stones)')
$audit.Add("- Optimized: $($cardCsv.Count) opaque card assets converted to WebP")
$audit.Add("- Missing: $($gate.MISSING)")
$audit.Add("- Wrong size: $($gate.WRONG_SIZE)")
$audit.Add("- Broken paths: $($gate.BROKEN_PATH)")
$audit.Add('')
$audit.Add('## Verified inventory')
$audit.Add('')
$audit.Add("- Runtime manifest paths: $($productionPaths.Count)")
$audit.Add("- Dart literal paths: $($dartPaths.Count)")
$audit.Add("- Original master files preserved: $($masterFiles.Count)")
$audit.Add("- Raw generated missing assets preserved: $($rawGenerated.Count)")
foreach ($key in $expectedCounts.Keys) { $audit.Add("- ${key}: $($actualCounts[$key]) / $($expectedCounts[$key])") }
$audit.Add('')
$audit.Add('## Processing policy')
$audit.Add('')
$audit.Add('- Existing artwork was not regenerated. Transparency, canvas normalization, and WebP conversion are deterministic derivatives of existing pixels.')
$audit.Add('- Only genuinely missing branding, Astro AI, natal-axis, empty-state, consultant, and premium assets were generated.')
$audit.Add('- Original files are retained under `assets/masters`; optimized runtime files are selected by `assets_manifest.json`.')
$audit.Add('- Contact sheets were visually reviewed for set consistency, centered scale, symbols, unwanted text, watermark, and obvious edge artifacts.')
if ($wrongSize.Count) { $audit.Add(''); $audit.Add('## Wrong sizes'); foreach($x in $wrongSize){$audit.Add("- $($x.Path): $($x.Actual), expected $($x.Expected)")} }
if ($alphaErrors.Count) { $audit.Add(''); $audit.Add('## Alpha errors'); foreach($x in $alphaErrors){$audit.Add("- $($x.Path): corner alpha $($x.CornerAlpha)")} }
if ($broken.Count -or $dartBroken.Count) { $audit.Add(''); $audit.Add('## Broken paths'); foreach($x in @($broken+$dartBroken)){$audit.Add("- $x")} }
if ($unresolvedNames.Count) { $audit.Add(''); $audit.Add('## Unresolved names'); foreach($x in $unresolvedNames){$audit.Add("- $x")} }
if ($duplicateGroups.Count) { $audit.Add(''); $audit.Add('## Exact duplicate groups'); foreach($g in $duplicateGroups){$audit.Add("- $((@($g.Group.Path)) -join ', ')")} }
$audit | Set-Content -LiteralPath (Join-Path $projectRoot 'assets_final_audit.md') -Encoding UTF8

Write-Output ($gate | ConvertTo-Json -Compress)
Write-Output "Status: $(if($ready){'ASSETS READY'}else{'ASSETS NOT READY'})"
if (-not $ready) { exit 2 }
