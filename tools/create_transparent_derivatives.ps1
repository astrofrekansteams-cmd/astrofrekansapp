$ErrorActionPreference = 'Stop'

$assetRoot = (Resolve-Path -LiteralPath 'C:\astrofrekans\assets').Path.TrimEnd('\')

$jobs = [System.Collections.Generic.List[object]]::new()
function Add-Derivative([string]$sourceRelative, [string]$destinationRelative, [int]$canvas = 1024, [int]$maxObject = 860) {
  $jobs.Add([pscustomobject]@{
    Source = Join-Path $assetRoot $sourceRelative
    Destination = Join-Path $assetRoot $destinationRelative
    Canvas = $canvas
    MaxObject = $maxObject
  })
}

$zodiac = [ordered]@{
  'koc'='aries'; 'boga'='taurus'; 'ikizler'='gemini'; 'yengec'='cancer';
  'aslan'='leo'; 'basak'='virgo'; 'terazi'='libra'; 'akrep'='scorpio';
  'yay'='sagittarius'; 'oglak'='capricorn'; 'kova'='aquarius'; 'balik'='pisces'
}
foreach ($pair in $zodiac.GetEnumerator()) {
  Add-Derivative "burc\$($pair.Key).png" "zodiac\$($pair.Value)\$($pair.Value).png"
}

$planets = [ordered]@{
  'gunes'='sun'; 'ay'='moon'; 'merkur'='mercury'; 'venus'='venus'; 'mars'='mars';
  'jupiter'='jupiter'; 'saturn'='saturn'; 'uranus'='uranus'; 'neptun'='neptune';
  'pluto'='pluto'; 'kuzey_ay_dugumu'='north_node'; 'guney_ay_dugumu'='south_node'
}
foreach ($pair in $planets.GetEnumerator()) {
  Add-Derivative "gezegen\$($pair.Key).png" "planets\$($pair.Value)\$($pair.Value).png"
}

$moonPhases = [ordered]@{
  'yeni_ay'='new_moon'; 'buyuyen_hilal'='waxing_crescent'; 'ilk_dordun'='first_quarter';
  'buyuyen_siskin_ay'='waxing_gibbous'; 'dolunay'='full_moon';
  'kuculen_siskin_ay'='waning_gibbous'; 'son_dordun'='last_quarter';
  'kuculen_hilal'='waning_crescent'
}
foreach ($pair in $moonPhases.GetEnumerator()) {
  Add-Derivative "ay-fazlari\$($pair.Key).png" "moon_phases\$($pair.Value)\$($pair.Value).png"
}

$elements = [ordered]@{ 'ates'='fire'; 'toprak'='earth'; 'hava'='air'; 'su'='water' }
foreach ($pair in $elements.GetEnumerator()) {
  Add-Derivative "element\$($pair.Key).png" "elements\$($pair.Value)\$($pair.Value).png"
}

foreach ($name in @('general_energy','love','money','career','health_balance','luck','important_hours')) {
  Add-Derivative "kategori\$name.png" "daily_frequency\$name\$name.png"
}

Add-Derivative 'logo\logo.png' 'branding\logo\brand_mark.png' 1024 860
Add-Derivative 'logo\1logo.png' 'branding\logo\brand_lockup_full.png' 1536 1260
Add-Derivative 'logo\2logo.png' 'branding\logo\brand_lockup_compact.png' 1024 860

Add-Derivative 'natal_chart\asc.png' 'natal_chart\asc\asc.png'
Add-Derivative 'natal_chart\mc.png' 'natal_chart\mc\mc.png'
Add-Derivative 'natal_chart\aspect_line.png' 'natal_chart\overlays\aspect_line.png'
Add-Derivative 'natal_chart\ev_cemberi.png' 'natal_chart\overlays\house_wheel.png'
Add-Derivative 'natal_chart\retrograde.png' 'natal_chart\retrograde\retrograde.png'
Add-Derivative 'natal_chart\zodiac_wheel.png' 'natal_chart\zodiac_wheel\zodiac_wheel.png'

foreach ($job in $jobs) {
  if (-not (Test-Path -LiteralPath $job.Source -PathType Leaf)) { throw "Missing source: $($job.Source)" }
  if (-not (Test-Path -LiteralPath $job.Destination)) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $job.Destination) -Force | Out-Null
  }
}

Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public static class TransparentDerivativeProcessor
{
    public static void Process(string inputPath, string outputPath, int canvas, int maxObject)
    {
        using (var original = new Bitmap(inputPath))
        using (var source = new Bitmap(original.Width, original.Height, PixelFormat.Format32bppArgb))
        {
            using (var g = Graphics.FromImage(source))
            {
                g.CompositingMode = CompositingMode.SourceCopy;
                g.DrawImageUnscaled(original, 0, 0);
            }

            int width = source.Width, height = source.Height;
            var rect = new Rectangle(0, 0, width, height);
            var data = source.LockBits(rect, ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
            int stride = Math.Abs(data.Stride);
            byte[] pixels = new byte[stride * height];
            Marshal.Copy(data.Scan0, pixels, 0, pixels.Length);

            int[][] corners = new int[][] {
                new int[]{0,0}, new int[]{width-1,0}, new int[]{0,height-1}, new int[]{width-1,height-1}
            };
            int bgB = 0, bgG = 0, bgR = 0;
            foreach (var c in corners)
            {
                int p = c[1] * stride + c[0] * 4;
                bgB += pixels[p]; bgG += pixels[p+1]; bgR += pixels[p+2];
            }
            bgB /= 4; bgG /= 4; bgR /= 4;

            Func<int, int, int, bool> isBackground = (b, g, r) =>
            {
                int db = b - bgB, dg = g - bgG, dr = r - bgR;
                double distance = Math.Sqrt(db*db + dg*dg + dr*dr);
                int max = Math.Max(r, Math.Max(g, b));
                return distance <= 58 && max <= 115;
            };

            bool[] background = new bool[width * height];
            var queue = new Queue<int>(width * 2 + height * 2);
            Action<int,int> enqueue = (x,y) =>
            {
                int id = y * width + x;
                if (background[id]) return;
                int p = y * stride + x * 4;
                if (!isBackground(pixels[p], pixels[p+1], pixels[p+2])) return;
                background[id] = true;
                queue.Enqueue(id);
            };
            for (int x=0; x<width; x++) { enqueue(x,0); enqueue(x,height-1); }
            for (int y=0; y<height; y++) { enqueue(0,y); enqueue(width-1,y); }
            while (queue.Count > 0)
            {
                int id = queue.Dequeue();
                int x = id % width, y = id / width;
                if (x>0) enqueue(x-1,y); if (x+1<width) enqueue(x+1,y);
                if (y>0) enqueue(x,y-1); if (y+1<height) enqueue(x,y+1);
            }

            bool[] fringe = new bool[width * height];
            for (int y=1; y<height-1; y++) for (int x=1; x<width-1; x++)
            {
                int id = y*width+x;
                if (background[id]) continue;
                for (int dy=-2; dy<=2 && !fringe[id]; dy++) for (int dx=-2; dx<=2; dx++)
                {
                    int nx=x+dx, ny=y+dy;
                    if (nx>=0 && nx<width && ny>=0 && ny<height && background[ny*width+nx]) { fringe[id]=true; break; }
                }
            }

            int minX=width, minY=height, maxX=-1, maxY=-1;
            for (int y=0; y<height; y++) for (int x=0; x<width; x++)
            {
                int id=y*width+x, p=y*stride+x*4;
                byte alpha=255;
                if (background[id])
                {
                    alpha=0; pixels[p]=pixels[p+1]=pixels[p+2]=0;
                }
                else if (fringe[id])
                {
                    int db=pixels[p]-bgB, dg=pixels[p+1]-bgG, dr=pixels[p+2]-bgR;
                    double distance=Math.Sqrt(db*db+dg*dg+dr*dr);
                    alpha=(byte)Math.Max(0,Math.Min(255,(int)Math.Round(distance*255.0/58.0)));
                    if (alpha>8 && alpha<255)
                    {
                        double a=alpha/255.0;
                        pixels[p]=(byte)Math.Max(0,Math.Min(255,(pixels[p]-(1-a)*bgB)/a));
                        pixels[p+1]=(byte)Math.Max(0,Math.Min(255,(pixels[p+1]-(1-a)*bgG)/a));
                        pixels[p+2]=(byte)Math.Max(0,Math.Min(255,(pixels[p+2]-(1-a)*bgR)/a));
                    }
                }
                pixels[p+3]=alpha;
                if (alpha>16) { if(x<minX)minX=x; if(x>maxX)maxX=x; if(y<minY)minY=y; if(y>maxY)maxY=y; }
            }

            Marshal.Copy(pixels,0,data.Scan0,pixels.Length);
            source.UnlockBits(data);
            if(maxX<minX||maxY<minY) throw new InvalidOperationException("No foreground detected: "+inputPath);
            var bounds=Rectangle.FromLTRB(minX,minY,maxX+1,maxY+1);
            double scale=Math.Min((double)maxObject/bounds.Width,(double)maxObject/bounds.Height);
            int drawWidth=Math.Max(1,(int)Math.Round(bounds.Width*scale));
            int drawHeight=Math.Max(1,(int)Math.Round(bounds.Height*scale));
            int drawX=(canvas-drawWidth)/2, drawY=(canvas-drawHeight)/2;

            using(var output=new Bitmap(canvas,canvas,PixelFormat.Format32bppArgb))
            using(var g=Graphics.FromImage(output))
            {
                g.Clear(Color.Transparent);
                g.CompositingMode=CompositingMode.SourceCopy;
                g.CompositingQuality=CompositingQuality.HighQuality;
                g.InterpolationMode=InterpolationMode.HighQualityBicubic;
                g.PixelOffsetMode=PixelOffsetMode.HighQuality;
                g.SmoothingMode=SmoothingMode.HighQuality;
                g.DrawImage(source,new Rectangle(drawX,drawY,drawWidth,drawHeight),bounds,GraphicsUnit.Pixel);
                output.Save(outputPath,ImageFormat.Png);
            }
        }
    }
}
'@

foreach ($job in $jobs) {
  if (-not (Test-Path -LiteralPath $job.Destination)) {
    [TransparentDerivativeProcessor]::Process($job.Source, $job.Destination, $job.Canvas, $job.MaxObject)
  }
}

$created = @($jobs | Where-Object { Test-Path -LiteralPath $_.Destination }).Count
Write-Output "Transparent derivatives available: $created / $($jobs.Count)"
