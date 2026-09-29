$ErrorActionPreference = 'Stop'

$assetRoot = (Resolve-Path -LiteralPath 'C:\astrofrekans\assets').Path.TrimEnd('\')
$stoneRoot = Join-Path $assetRoot 'rune\stones'
$sourceRoot = Join-Path $stoneRoot 'source_opaque'
$expected = @(
  'fehu','uruz','thurisaz','ansuz','raidho','kenaz','gebo','wunjo',
  'hagalaz','nauthiz','isa','jera','eihwaz','perthro','algiz','sowilo',
  'tiwaz','berkano','ehwaz','mannaz','laguz','ingwaz','dagaz','othala'
)

if (-not $stoneRoot.StartsWith($assetRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
  throw "Stone root escaped asset root: $stoneRoot"
}

if (-not (Test-Path -LiteralPath $sourceRoot)) {
  New-Item -ItemType Directory -Path $sourceRoot -Force | Out-Null
  foreach ($name in $expected) {
    $source = Join-Path $stoneRoot ($name + '.png')
    $destination = Join-Path $sourceRoot ($name + '.png')
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing rune stone source: $source" }
    if (Test-Path -LiteralPath $destination) { throw "Source archive destination exists: $destination" }
    Move-Item -LiteralPath $source -Destination $destination
  }
}

$sourceFiles = @(Get-ChildItem -LiteralPath $sourceRoot -File -Filter '*.png')
if ($sourceFiles.Count -ne 24) { throw "Expected 24 archived rune stones; found $($sourceFiles.Count)." }

Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public static class RuneStoneProcessor
{
    private static bool IsBackgroundCandidate(byte b, byte g, byte r)
    {
        int max = Math.Max(r, Math.Max(g, b));
        int min = Math.Min(r, Math.Min(g, b));
        return max <= 42 && (max - min) <= 26;
    }

    public static void Process(string inputPath, string outputPath)
    {
        using (var original = new Bitmap(inputPath))
        using (var source = new Bitmap(original.Width, original.Height, PixelFormat.Format32bppArgb))
        {
            using (var g = Graphics.FromImage(source))
            {
                g.CompositingMode = CompositingMode.SourceCopy;
                g.DrawImageUnscaled(original, 0, 0);
            }

            int width = source.Width;
            int height = source.Height;
            var rect = new Rectangle(0, 0, width, height);
            var data = source.LockBits(rect, ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
            int stride = Math.Abs(data.Stride);
            byte[] pixels = new byte[stride * height];
            Marshal.Copy(data.Scan0, pixels, 0, pixels.Length);

            bool[] background = new bool[width * height];
            var queue = new Queue<int>(width * 2 + height * 2);

            Action<int, int> enqueue = (x, y) =>
            {
                int id = y * width + x;
                if (background[id]) return;
                int p = y * stride + x * 4;
                if (!IsBackgroundCandidate(pixels[p], pixels[p + 1], pixels[p + 2])) return;
                background[id] = true;
                queue.Enqueue(id);
            };

            for (int x = 0; x < width; x++) { enqueue(x, 0); enqueue(x, height - 1); }
            for (int y = 0; y < height; y++) { enqueue(0, y); enqueue(width - 1, y); }

            while (queue.Count > 0)
            {
                int id = queue.Dequeue();
                int x = id % width;
                int y = id / width;
                if (x > 0) enqueue(x - 1, y);
                if (x + 1 < width) enqueue(x + 1, y);
                if (y > 0) enqueue(x, y - 1);
                if (y + 1 < height) enqueue(x, y + 1);
            }

            bool[] fringe = new bool[width * height];
            for (int y = 1; y < height - 1; y++)
            {
                for (int x = 1; x < width - 1; x++)
                {
                    int id = y * width + x;
                    if (background[id]) continue;
                    for (int dy = -2; dy <= 2 && !fringe[id]; dy++)
                    {
                        for (int dx = -2; dx <= 2; dx++)
                        {
                            int nx = x + dx, ny = y + dy;
                            if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
                            if (background[ny * width + nx]) { fringe[id] = true; break; }
                        }
                    }
                }
            }

            int minX = width, minY = height, maxX = -1, maxY = -1;
            for (int y = 0; y < height; y++)
            {
                for (int x = 0; x < width; x++)
                {
                    int id = y * width + x;
                    int p = y * stride + x * 4;
                    byte alpha = 255;
                    if (background[id])
                    {
                        alpha = 0;
                        pixels[p] = pixels[p + 1] = pixels[p + 2] = 0;
                    }
                    else if (fringe[id])
                    {
                        int max = Math.Max(pixels[p + 2], Math.Max(pixels[p + 1], pixels[p]));
                        alpha = (byte)Math.Max(0, Math.Min(255, (max - 3) * 255 / 52));
                        if (alpha > 0 && alpha < 255)
                        {
                            pixels[p] = (byte)Math.Min(255, pixels[p] * 255 / alpha);
                            pixels[p + 1] = (byte)Math.Min(255, pixels[p + 1] * 255 / alpha);
                            pixels[p + 2] = (byte)Math.Min(255, pixels[p + 2] * 255 / alpha);
                        }
                    }
                    pixels[p + 3] = alpha;
                    if (alpha > 16)
                    {
                        if (x < minX) minX = x;
                        if (x > maxX) maxX = x;
                        if (y < minY) minY = y;
                        if (y > maxY) maxY = y;
                    }
                }
            }

            Marshal.Copy(pixels, 0, data.Scan0, pixels.Length);
            source.UnlockBits(data);
            if (maxX < minX || maxY < minY) throw new InvalidOperationException("No foreground detected: " + inputPath);

            var bounds = Rectangle.FromLTRB(minX, minY, maxX + 1, maxY + 1);
            const int canvasWidth = 1024;
            const int canvasHeight = 1536;
            const int maxObjectWidth = 850;
            const int maxObjectHeight = 1300;
            double scale = Math.Min((double)maxObjectWidth / bounds.Width, (double)maxObjectHeight / bounds.Height);
            int drawWidth = Math.Max(1, (int)Math.Round(bounds.Width * scale));
            int drawHeight = Math.Max(1, (int)Math.Round(bounds.Height * scale));
            int drawX = (canvasWidth - drawWidth) / 2;
            int drawY = (canvasHeight - drawHeight) / 2;

            using (var output = new Bitmap(canvasWidth, canvasHeight, PixelFormat.Format32bppArgb))
            using (var g = Graphics.FromImage(output))
            {
                g.Clear(Color.Transparent);
                g.CompositingMode = CompositingMode.SourceCopy;
                g.CompositingQuality = CompositingQuality.HighQuality;
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                g.SmoothingMode = SmoothingMode.HighQuality;
                g.DrawImage(source, new Rectangle(drawX, drawY, drawWidth, drawHeight), bounds, GraphicsUnit.Pixel);
                output.Save(outputPath, ImageFormat.Png);
            }
        }
    }
}
'@

foreach ($name in $expected) {
  $input = Join-Path $sourceRoot ($name + '.png')
  $output = Join-Path $stoneRoot ($name + '.png')
  if (Test-Path -LiteralPath $output) { throw "Refusing to overwrite existing production file: $output" }
  [RuneStoneProcessor]::Process($input, $output)
}

$outputs = @(Get-ChildItem -LiteralPath $stoneRoot -File -Filter '*.png')
if ($outputs.Count -ne 24) { throw "Expected 24 standardized outputs; found $($outputs.Count)." }

Write-Output "Standardized rune stones: $($outputs.Count)"
Write-Output "Canvas: 1024x1536 PNG with alpha"
Write-Output "Opaque sources preserved: $sourceRoot"
