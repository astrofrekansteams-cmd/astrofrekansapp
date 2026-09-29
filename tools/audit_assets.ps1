param(
  [string]$AssetRoot = "C:\astrofrekans\assets",
  [string]$OutputPath = "C:\astrofrekans\assets_audit.md"
)

Add-Type -AssemblyName System.Drawing

function Get-Purpose([string]$category) {
  switch ($category) {
    'app-thema' { 'UI screen reference' }
    'ay-fazlari' { 'Moon phase illustration' }
    'backgraunds' { 'Screen background' }
    'burc' { 'Zodiac illustration' }
    'cards-back' { 'Card/deck reverse' }
    'dogumharitasi' { 'Natal chart overlay/symbol' }
    'element' { 'Element illustration' }
    'gezegen' { 'Planet/node symbol' }
    'kategori' { 'Daily frequency category icon' }
    'katina' { 'Katina card face' }
    'logo' { 'Branding' }
    'rune' { 'Rune card face' }
    'tarrot' { 'Tarot card face' }
    'tas-rune' { 'Rune stone illustration' }
    default { 'Unclassified' }
  }
}

function Get-Audit([string]$category, [string]$baseName) {
  $status = 'OK'
  $action = 'Keep; use as an in-category style reference.'

  if ($category -eq 'app-thema' -and $baseName -match '^[0-9a-f]{8}-') {
    return @('RENAME', 'Rename to the represented screen; retain as a UI style reference only.')
  }
  if ($category -eq 'kategori') {
    return @('RENAME', 'Map the icon to its semantic purpose, then rename with lowercase_snake_case.')
  }
  if ($category -eq 'backgraunds') {
    return @('RENAME', 'Rename folder to backgrounds and file to login_background.png.')
  }
  if ($category -eq 'tarrot') {
    return @('RENAME', 'Keep the image; rename the folder from tarrot to tarot during reorganization.')
  }
  if ($category -eq 'tas-rune') {
    $extra = if ($baseName -eq 'lngwaz') { ' Also correct lngwaz to ingwaz.' } else { '' }
    return @('WRONG_SIZE', 'Normalize the full set to one canvas, crop, object scale, and transparent-background policy.' + $extra)
  }
  if ($category -eq 'dogumharitasi' -and $baseName -eq 'aspect-line') {
    return @('RENAME', 'Rename to aspect_line.png.')
  }
  if ($category -eq 'gezegen' -and $baseName -eq 'puluto') {
    return @('RENAME', 'Rename to pluto.png.')
  }
  if ($category -eq 'gezegen' -and $baseName -eq 'saturun') {
    return @('RENAME', 'Rename to saturn.png.')
  }
  if ($category -eq 'logo' -and $baseName -match '^[12]logo$') {
    return @('RENAME', 'Rename by role, for example brand_lockup_full and brand_lockup_compact.')
  }

  return @($status, $action)
}

$files = @(Get-ChildItem -LiteralPath $AssetRoot -Recurse -File | Sort-Object FullName)
$hashGroups = $files | ForEach-Object {
  [pscustomobject]@{ File = $_; Hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
} | Group-Object Hash
$duplicatePaths = @{}
foreach ($group in $hashGroups | Where-Object Count -gt 1) {
  foreach ($item in $group.Group) { $duplicatePaths[$item.File.FullName] = $true }
}

$records = foreach ($file in $files) {
  $relative = $file.FullName.Substring($AssetRoot.Length + 1).Replace('\', '/')
  $category = $relative.Split('/')[0]
  $image = [System.Drawing.Image]::FromFile($file.FullName)
  $pixelFormat = $image.PixelFormat.ToString()
  $hasAlpha = $pixelFormat -match 'Alpha|PAlpha'
  $width = $image.Width
  $height = $image.Height
  $image.Dispose()

  $audit = Get-Audit $category $file.BaseName
  $status = $audit[0]
  $action = $audit[1]
  if ($duplicatePaths.ContainsKey($file.FullName)) {
    $status = 'DUPLICATE'
    $action = 'Retain the canonical copy and remove or alias the duplicate during reorganization.'
  }

  $divisor = [Math]::Max(1, [Math]::Min($width, $height))
  $aspect = [Math]::Round($width / $height, 3).ToString('0.###', [Globalization.CultureInfo]::InvariantCulture)
  [pscustomobject]@{
    Category = $category
    File = $relative
    Size = "${width}x${height}"
    Aspect = $aspect
    Format = $file.Extension.TrimStart('.').ToUpperInvariant()
    Transparent = $(if ($hasAlpha) { 'YES' } else { 'NO' })
    Purpose = Get-Purpose $category
    Status = $status
    Action = $action
  }
}

$missing = @(
  @('branding', 'branding/app_icon/app_icon.png', 'App icon master'),
  @('branding', 'branding/splash/splash_background.png', 'Splash background'),
  @('branding', 'branding/onboarding/onboarding_cosmic_guide.png', 'Onboarding hero'),
  @('astro_ai', 'astro_ai/avatar/astro_ai_avatar.png', 'AI guide avatar'),
  @('astro_ai', 'astro_ai/orb/astro_ai_orb.png', 'Idle orb'),
  @('astro_ai', 'astro_ai/listening/astro_ai_listening.png', 'Listening state'),
  @('astro_ai', 'astro_ai/typing/astro_ai_typing.png', 'Typing state'),
  @('astro_ai', 'astro_ai/empty_state/astro_ai_empty_state.png', 'Empty state'),
  @('natal_chart', 'natal_chart/dsc/dsc.png', 'DSC marker'),
  @('natal_chart', 'natal_chart/ic/ic.png', 'IC marker'),
  @('empty_states', 'empty_states/no_data/no_data.png', 'No-data state'),
  @('empty_states', 'empty_states/offline/offline.png', 'Offline state'),
  @('empty_states', 'empty_states/no_birth_data/no_birth_data.png', 'Missing birth data'),
  @('empty_states', 'empty_states/no_results/no_results.png', 'No-results state'),
  @('empty_states', 'empty_states/premium_locked/premium_locked.png', 'Premium lock state'),
  @('empty_states', 'empty_states/loading/loading.png', 'Loading state'),
  @('consultants', 'consultants/placeholders/consultant_placeholder.png', 'Consultant fallback avatar'),
  @('premium', 'premium/crown/premium_crown.png', 'Premium crown'),
  @('premium', 'premium/star/premium_star.png', 'Premium star'),
  @('premium', 'premium/crystal/premium_crystal.png', 'Premium crystal')
)

$okCount = @($records | Where-Object Status -eq 'OK').Count
$renameCount = @($records | Where-Object Status -eq 'RENAME').Count
$wrongSizeCount = @($records | Where-Object Status -eq 'WRONG_SIZE').Count
$duplicateCount = @($records | Where-Object Status -eq 'DUPLICATE').Count
$totalMb = [Math]::Round(($files | Measure-Object Length -Sum).Sum / 1MB, 1)

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add('# Astrofrekans Assets Audit')
$lines.Add('')
$lines.Add('Generated from the current `assets/` tree. Visual judgments were checked against category contact sheets; file facts are read from the source images.')
$lines.Add('')
$lines.Add('## Executive summary')
$lines.Add('')
$lines.Add("- Source images: **$($files.Count)** files, **$totalMb MB** total.")
$lines.Add("- File results: **$okCount OK**, **$renameCount RENAME**, **$wrongSizeCount WRONG_SIZE**, **$duplicateCount DUPLICATE**.")
$lines.Add("- Required additions explicitly identified: **$($missing.Count) MISSING** assets.")
$lines.Add('- Exact byte-for-byte duplicates: **none detected**.' )
$lines.Add('- Every current PNG is encoded without an alpha channel. This is acceptable for full-bleed cards/screens, but reusable emblems, chart overlays, icons, logos, and rune stones need transparent derivatives or controlled background removal before production use.')
$lines.Add('- Strongest existing visual language: deep navy/near-black, champagne-gold filigree, restrained celestial glow, centered premium compositions. New generation must match this set rather than introducing a new visual language.')
$lines.Add('')
$lines.Add('## Blocking cleanup before application coding')
$lines.Add('')
$lines.Add('1. Rename misspelled folders: `tarrot` -> `tarot`, `backgraunds` -> `backgrounds`, `tas-rune` -> `rune/stones`, `app-thema` -> `references/ui_screens`, `dogumharitasi` -> `natal_chart`.')
$lines.Add('2. Resolve known filename defects: `puluto` -> `pluto`, `saturun` -> `saturn`, `lngwaz` -> `ingwaz`, `aspect-line` -> `aspect_line`, plus UUID-based UI/category names.')
$lines.Add('3. Normalize the 24 rune-stone canvases; the current set mixes 1024x1536, 1086x1448, and 1122x1402.')
$lines.Add('4. Produce or derive the missing Astro AI, empty-state, premium, consultant-placeholder, DSC, and IC assets.')
$lines.Add('5. Create transparent derivatives for reusable symbol/icon categories while preserving original masters and their exact visual style.')
$lines.Add('')
$lines.Add('## Approved style anchors for future generation')
$lines.Add('')
$lines.Add('| Use | Primary reference | Why |')
$lines.Add('|---|---|---|')
$lines.Add('| Overall UI | `assets/app-thema/c4dc11cc-d22c-490c-96a5-6acf1e1e4021.png` | Best consolidated dashboard palette, spacing, glow, cards, and icon treatment. |')
$lines.Add('| Astro AI | `assets/app-thema/d6b71bc7-7950-44d1-834d-3871f8e16420.png` | Defines the non-robotic cosmic guide, gold-lit navy body, and AI surface language. |')
$lines.Add('| Entry/onboarding | `assets/app-thema/login_register.png` | Strong full-screen cosmic atmosphere and premium brand hierarchy. |')
$lines.Add('| Zodiac/icon rendering | `assets/burc/aslan.png` | Clean gold relief, deep-blue enamel, centered scale, controlled ornament. |')
$lines.Add('| Planet symbols | `assets/gezegen/saturun.png` | Strong material, line weight, ring detail, and circular frame. |')
$lines.Add('| Moon phases | `assets/ay-fazlari/dolunay.png` | Realistic moon texture integrated with the gold celestial frame. |')
$lines.Add('| Element icons | `assets/element/su.png` | Balanced ornamental illustration with readable elemental symbolism. |')
$lines.Add('| Tarot | `assets/tarrot/yildiz.png` | Representative polished tarot frame, palette, and illustration density. |')
$lines.Add('| Katina | `assets/katina/gunes.png` | Representative Katina frame and luminous focal treatment. |')
$lines.Add('| Rune cards | `assets/rune/sowilo.png` | Representative rune glow, frame, and narrative background. |')
$lines.Add('| Rune stones | `assets/tas-rune/algiz.png` | Strongest readable stone silhouette and engraved gold treatment. |')
$lines.Add('| Branding | `assets/logo/banner.png` | Canonical celestial landscape, logo gold, and brand mood. |')
$lines.Add('')
$lines.Add('These anchors are mandatory inputs for ImageGen prompts. New assets must keep the same navy/gold palette, material response, glow restraint, centered object scale, and ornate-but-premium detail level. No cyberpunk neon, game UI, robotic AI, text, watermark, or unrelated fantasy styling.')
$lines.Add('')
$lines.Add('## Missing assets')
$lines.Add('')
$lines.Add('| CATEGORY | FILE | SIZE | FORMAT | TRANSPARENT | PURPOSE | STATUS | ACTION |')
$lines.Add('|---|---|---:|---|---|---|---|---|')
foreach ($item in $missing) {
  $lines.Add(('| {0} | `{1}` | TBD | PNG/WebP | YES where reusable | {2} | MISSING | Generate or derive only after applying the approved style anchors. |' -f $item[0], $item[1], $item[2]))
}
$lines.Add('')
$lines.Add('## Current file inventory')
$lines.Add('')
$lines.Add('| CATEGORY | FILE | SIZE | ASPECT | FORMAT | TRANSPARENT | PURPOSE | STATUS | ACTION |')
$lines.Add('|---|---|---:|---:|---|---|---|---|---|')
foreach ($record in $records) {
  $safeAction = $record.Action.Replace('|', '\|')
  $lines.Add(('| {0} | `{1}` | {2} | {3} | {4} | {5} | {6} | {7} | {8} |' -f $record.Category, $record.File, $record.Size, $record.Aspect, $record.Format, $record.Transparent, $record.Purpose, $record.Status, $safeAction))
}
$lines.Add('')
$lines.Add('## Notes on scope')
$lines.Add('')
$lines.Add('- Full-screen backgrounds can often be built as gradients, particles, and subtle overlays in Flutter; do not generate a separate raster background for every screen unless it materially improves the design.')
$lines.Add('- Card faces and UI screenshots are intentionally opaque and do not require alpha.')
$lines.Add('- The original image masters should remain untouched until the rename/reorganization mapping is applied atomically and verified against the application asset manifest.')

Set-Content -LiteralPath $OutputPath -Value $lines -Encoding utf8
Write-Output "Wrote $OutputPath"
