param(
  [string]$AssetRoot = "C:\astrofrekans\assets",
  [string]$OutputRoot = "C:\astrofrekans\reports\assets_contact_sheets"
)

Add-Type -AssemblyName System.Drawing

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

$tileWidth = 190
$tileHeight = 250
$imageHeight = 205
$padding = 10
$font = New-Object System.Drawing.Font('Arial', 9)
$brush = [System.Drawing.Brushes]::White
$background = [System.Drawing.Color]::FromArgb(255, 8, 12, 28)

foreach ($directory in Get-ChildItem -LiteralPath $AssetRoot -Directory | Sort-Object Name) {
  $files = @(Get-ChildItem -LiteralPath $directory.FullName -File | Where-Object Extension -Match '^\.(png|jpg|jpeg|webp)$' | Sort-Object Name)
  if ($files.Count -eq 0) { continue }

  $columns = [Math]::Min(6, $files.Count)
  $rowCount = [int][Math]::Ceiling($files.Count / $columns)
  $sheetWidth = [int]($columns * $tileWidth)
  $sheetHeight = [int]($rowCount * $tileHeight)
  $sheet = [System.Drawing.Bitmap]::new($sheetWidth, $sheetHeight)
  $graphics = [System.Drawing.Graphics]::FromImage($sheet)
  $graphics.Clear($background)
  $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic

  for ($index = 0; $index -lt $files.Count; $index++) {
    $column = $index % $columns
    $row = [Math]::Floor($index / $columns)
    $left = $column * $tileWidth
    $top = $row * $tileHeight

    $image = [System.Drawing.Image]::FromFile($files[$index].FullName)
    $scale = [Math]::Min(($tileWidth - 2 * $padding) / $image.Width, ($imageHeight - 2 * $padding) / $image.Height)
    $drawWidth = [Math]::Max(1, [int]($image.Width * $scale))
    $drawHeight = [Math]::Max(1, [int]($image.Height * $scale))
    $drawLeft = $left + [int](($tileWidth - $drawWidth) / 2)
    $drawTop = $top + [int](($imageHeight - $drawHeight) / 2)
    $graphics.DrawImage($image, $drawLeft, $drawTop, $drawWidth, $drawHeight)
    $image.Dispose()

    $label = $files[$index].BaseName
    if ($label.Length -gt 25) { $label = $label.Substring(0, 22) + '...' }
    $graphics.DrawString($label, $font, $brush, $left + $padding, $top + $imageHeight + 6)
  }

  $outputPath = Join-Path $OutputRoot ($directory.Name + '.jpg')
  $sheet.Save($outputPath, [System.Drawing.Imaging.ImageFormat]::Jpeg)
  $graphics.Dispose()
  $sheet.Dispose()
}

$font.Dispose()
Write-Output "Contact sheets written to $OutputRoot"
