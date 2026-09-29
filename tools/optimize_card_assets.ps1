$ErrorActionPreference = 'Stop'

$assetRoot = 'C:\astrofrekans\assets'
$ffmpeg = 'C:\Users\nicat\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'
if (-not (Test-Path -LiteralPath $ffmpeg -PathType Leaf)) { throw "ffmpeg not found: $ffmpeg" }

$sets = @(
  @{ Name='tarot'; Source='tarot'; Destination='tarot\cards' },
  @{ Name='katina'; Source='katina'; Destination='katina\cards' },
  @{ Name='rune'; Source='rune'; Destination='rune\cards' },
  @{ Name='cards-back'; Source='cards-back'; Destination='cards-back\webp' }
)

$rows = [System.Collections.Generic.List[object]]::new()
foreach ($set in $sets) {
  $sourceRoot = Join-Path $assetRoot $set.Source
  $destinationRoot = Join-Path $assetRoot $set.Destination
  New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null

  foreach ($file in Get-ChildItem -LiteralPath $sourceRoot -File -Filter *.png | Sort-Object Name) {
    $destination = Join-Path $destinationRoot ($file.BaseName + '.webp')
    if (-not (Test-Path -LiteralPath $destination)) {
      & $ffmpeg -hide_banner -loglevel error -y -i $file.FullName -c:v libwebp -quality 88 -compression_level 6 -preset picture $destination
      if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed for $($file.FullName)" }
    }
    $optimized = Get-Item -LiteralPath $destination
    if ($optimized.Length -ge $file.Length) {
      Remove-Item -LiteralPath $destination -Force
      $rows.Add([pscustomobject]@{Set=$set.Name; File=$file.Name; SourceBytes=$file.Length; ProductionBytes=$file.Length; Format='PNG'; SavedBytes=0})
    } else {
      $rows.Add([pscustomobject]@{Set=$set.Name; File=$file.Name; SourceBytes=$file.Length; ProductionBytes=$optimized.Length; Format='WebP'; SavedBytes=($file.Length-$optimized.Length)})
    }
  }
}

$report = 'C:\astrofrekans\reports\card_optimization.csv'
$rows | Export-Csv -LiteralPath $report -NoTypeInformation -Encoding UTF8
Write-Output "Optimized $($rows.Count) card assets. Report: $report"
