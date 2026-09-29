$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$assetRoot = 'C:\astrofrekans\assets'
$rawRoot = Join-Path $assetRoot 'masters\generated_missing_raw'

$relativeFiles = @(
  'branding\app_icon\app_icon.png',
  'branding\splash\splash_background.png',
  'branding\onboarding\onboarding_cosmic_guide.png',
  'astro_ai\avatar\astro_ai_avatar.png',
  'astro_ai\orb\astro_ai_orb.png',
  'astro_ai\listening\astro_ai_listening.png',
  'astro_ai\typing\astro_ai_typing.png',
  'astro_ai\empty_state\astro_ai_empty_state.png',
  'natal_chart\dsc\dsc.png',
  'natal_chart\ic\ic.png',
  'empty_states\no_data\no_data.png',
  'empty_states\offline\offline.png',
  'empty_states\no_birth_data\no_birth_data.png',
  'empty_states\no_results\no_results.png',
  'empty_states\premium_locked\premium_locked.png',
  'empty_states\loading\loading.png',
  'consultants\placeholders\consultant_placeholder.png',
  'premium\crown\premium_crown.png',
  'premium\star\premium_star.png',
  'premium\crystal\premium_crystal.png'
)

foreach ($relative in $relativeFiles) {
  $source = Join-Path $assetRoot $relative
  $backup = Join-Path $rawRoot $relative
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing generated asset: $source" }
  if (-not (Test-Path -LiteralPath $backup)) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $backup) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $backup
  }
}

Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;

public static class GeneratedAssetNormalizer
{
    public static void Resize(string inputPath, string outputPath, int width, int height, bool transparent, bool fit)
    {
        using (var source = new Bitmap(inputPath))
        using (var output = new Bitmap(width, height, PixelFormat.Format32bppArgb))
        using (var g = Graphics.FromImage(output))
        {
            g.CompositingMode = CompositingMode.SourceCopy;
            g.CompositingQuality = CompositingQuality.HighQuality;
            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
            g.PixelOffsetMode = PixelOffsetMode.HighQuality;
            g.SmoothingMode = SmoothingMode.HighQuality;
            g.Clear(transparent ? Color.Transparent : Color.Black);

            Rectangle destination;
            if (fit)
            {
                double scale = Math.Min((double)width / source.Width, (double)height / source.Height);
                int drawWidth = Math.Max(1, (int)Math.Round(source.Width * scale));
                int drawHeight = Math.Max(1, (int)Math.Round(source.Height * scale));
                destination = new Rectangle((width-drawWidth)/2, (height-drawHeight)/2, drawWidth, drawHeight);
            }
            else destination = new Rectangle(0, 0, width, height);

            g.DrawImage(source, destination, new Rectangle(0,0,source.Width,source.Height), GraphicsUnit.Pixel);
            output.Save(outputPath + ".tmp.png", ImageFormat.Png);
        }
        System.IO.File.Copy(outputPath + ".tmp.png", outputPath, true);
        System.IO.File.Delete(outputPath + ".tmp.png");
    }
}
'@

[GeneratedAssetNormalizer]::Resize(
  (Join-Path $rawRoot 'branding\app_icon\app_icon.png'),
  (Join-Path $assetRoot 'branding\app_icon\app_icon.png'), 1024, 1024, $false, $false)
[GeneratedAssetNormalizer]::Resize(
  (Join-Path $rawRoot 'branding\splash\splash_background.png'),
  (Join-Path $assetRoot 'branding\splash\splash_background.png'), 1080, 1920, $false, $false)

foreach ($relative in $relativeFiles | Where-Object {
  $_ -notmatch '^branding\\(app_icon|splash|onboarding)\\'
}) {
  [GeneratedAssetNormalizer]::Resize(
    (Join-Path $rawRoot $relative),
    (Join-Path $assetRoot $relative), 1024, 1024, $true, $true)
}

Write-Output "Generated assets normalized; raw copies preserved at $rawRoot"
