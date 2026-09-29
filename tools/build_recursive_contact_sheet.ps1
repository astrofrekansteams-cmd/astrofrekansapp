param(
  [Parameter(Mandatory = $true)][string]$InputRoot,
  [Parameter(Mandatory = $true)][string]$OutputPath,
  [string[]]$ExcludeSegments = @('source_opaque')
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$root = (Resolve-Path -LiteralPath $InputRoot).Path.TrimEnd('\')
$files = @(Get-ChildItem -LiteralPath $root -Recurse -File |
  Where-Object {
    $candidate = $_
    $excluded = @($ExcludeSegments | Where-Object {
      $segment = $_
      $segment -and $candidate.FullName -match ('\\' + [regex]::Escape($segment) + '\\')
    }).Count -gt 0
    $candidate.Extension -match '^\.(png|jpg|jpeg|webp)$' -and -not $excluded
  } |
  Sort-Object FullName)

if ($files.Count -eq 0) { throw "No images found under $root" }

$tileWidth = 210
$tileHeight = 260
$imageHeight = 210
$padding = 10
$columns = [Math]::Min(6, $files.Count)
$rows = [int][Math]::Ceiling($files.Count / $columns)
$sheet = [System.Drawing.Bitmap]::new([int]($columns * $tileWidth), [int]($rows * $tileHeight))
$graphics = [System.Drawing.Graphics]::FromImage($sheet)
$graphics.Clear([System.Drawing.Color]::FromArgb(255, 8, 12, 28))
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$font = [System.Drawing.Font]::new('Arial', 9)

try {
  for ($index = 0; $index -lt $files.Count; $index++) {
    $column = $index % $columns
    $row = [Math]::Floor($index / $columns)
    $left = $column * $tileWidth
    $top = $row * $tileHeight
    $image = [System.Drawing.Image]::FromFile($files[$index].FullName)
    try {
      $scale = [Math]::Min(($tileWidth - 2 * $padding) / $image.Width, ($imageHeight - 2 * $padding) / $image.Height)
      $drawWidth = [Math]::Max(1, [int]($image.Width * $scale))
      $drawHeight = [Math]::Max(1, [int]($image.Height * $scale))
      $drawLeft = $left + [int](($tileWidth - $drawWidth) / 2)
      $drawTop = $top + [int](($imageHeight - $drawHeight) / 2)
      $graphics.DrawImage($image, $drawLeft, $drawTop, $drawWidth, $drawHeight)
    } finally { $image.Dispose() }

    $label = $files[$index].FullName.Substring($root.Length).TrimStart('\').Replace('\', '/')
    if ($label.Length -gt 31) { $label = $label.Substring(0, 28) + '...' }
    $graphics.DrawString($label, $font, [System.Drawing.Brushes]::White, $left + $padding, $top + $imageHeight + 6)
  }

  $parent = Split-Path -Parent $OutputPath
  New-Item -ItemType Directory -Path $parent -Force | Out-Null
  $sheet.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Jpeg)
} finally {
  $font.Dispose()
  $graphics.Dispose()
  $sheet.Dispose()
}

Write-Output "Contact sheet: $OutputPath ($($files.Count) images)"
