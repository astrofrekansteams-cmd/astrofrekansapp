$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath 'C:\astrofrekans').Path.TrimEnd('\')
$target = (Resolve-Path -LiteralPath 'C:\astrofrekans\work\rune_transparent_raw').Path.TrimEnd('\')
if ($target -ne 'C:\astrofrekans\work\rune_transparent_raw') { throw "Unexpected target: $target" }
if (-not $target.StartsWith($workspace + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Target escaped workspace: $target" }
Remove-Item -LiteralPath $target -Recurse -Force
Write-Output "Removed discarded rune generations: $target"
