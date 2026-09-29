$ErrorActionPreference = 'Stop'
$projectRoot = 'C:\astrofrekans'
$assetRoot = Join-Path $projectRoot 'assets'

function Relative-Path([string]$path) {
  return $path.Substring($projectRoot.Length + 1).Replace('\','/')
}
function Files-In([string]$relative, [string]$filter = '*') {
  $directory = Join-Path $assetRoot $relative
  return @((Get-ChildItem -LiteralPath $directory -Recurse -File -Filter $filter | Sort-Object FullName) |
    ForEach-Object { Relative-Path $_.FullName })
}

$manifest = [ordered]@{
  schema_version = 1
  project = 'Astrofrekans'
  generated_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
  policy = [ordered]@{
    source_masters = 'assets/masters'
    transparent_format = 'PNG'
    card_production_format = 'WebP'
    source_pngs_preserved = $true
  }
  branding = [ordered]@{
    app_icon = 'assets/branding/app_icon/app_icon.png'
    splash_background = 'assets/branding/splash/splash_background.png'
    onboarding = 'assets/branding/onboarding/onboarding_cosmic_guide.png'
    logo = Files-In 'branding\logo' '*.png'
  }
  backgrounds = Files-In 'backgrounds' '*.png'
  zodiac = Files-In 'zodiac' '*.png'
  planets = Files-In 'planets' '*.png'
  moon_phases = Files-In 'moon_phases' '*.png'
  elements = Files-In 'elements' '*.png'
  daily_frequency = Files-In 'daily_frequency' '*.png'
  astro_ai = Files-In 'astro_ai' '*.png'
  tarot = [ordered]@{
    cards = Files-In 'tarot\cards' '*.webp'
    back = 'assets/cards-back/webp/tarot_back.webp'
  }
  katina = [ordered]@{
    cards = Files-In 'katina\cards' '*.webp'
    back = 'assets/cards-back/webp/katina_back.webp'
  }
  rune = [ordered]@{
    cards = Files-In 'rune\cards' '*.webp'
    stones = @((Get-ChildItem -LiteralPath (Join-Path $assetRoot 'rune\stones') -File -Filter '*.png' | Sort-Object Name) |
      ForEach-Object { Relative-Path $_.FullName })
    card_back = 'assets/cards-back/webp/rune_back.webp'
    stone_back = 'assets/cards-back/webp/runetas_back.webp'
  }
  natal_chart = [ordered]@{
    asc = 'assets/natal_chart/asc/asc.png'
    dsc = 'assets/natal_chart/dsc/dsc.png'
    mc = 'assets/natal_chart/mc/mc.png'
    ic = 'assets/natal_chart/ic/ic.png'
    retrograde = 'assets/natal_chart/retrograde/retrograde.png'
    zodiac_wheel = 'assets/natal_chart/zodiac_wheel/zodiac_wheel.png'
    overlays = Files-In 'natal_chart\overlays' '*.png'
  }
  empty_states = Files-In 'empty_states' '*.png'
  consultants = Files-In 'consultants' '*.png'
  premium = Files-In 'premium' '*.png'
  ui_references = Files-In 'references\ui_screens' '*.png'
}

$manifestPath = Join-Path $projectRoot 'assets_manifest.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Output "Manifest written: $manifestPath"
