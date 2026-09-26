Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class ArtAlphaAudit {
  public static long[] Inspect(string file) {
    using (var b = new Bitmap(file)) {
      var d = b.LockBits(new Rectangle(0,0,b.Width,b.Height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
      try {
        var row = new byte[b.Width*4];
        long zero=0, partial=0, solid=0, xmin=b.Width, ymin=b.Height, xmax=-1, ymax=-1, center=0, borderMax=0;
        for(int y=0;y<b.Height;y++) {
          Marshal.Copy(IntPtr.Add(d.Scan0,y*d.Stride),row,0,row.Length);
          for(int x=0;x<b.Width;x++) {
            int a=row[x*4+3];
            if(a==0)zero++; else if(a==255)solid++; else partial++;
            if(a>8) {xmin=Math.Min(xmin,x);ymin=Math.Min(ymin,y);xmax=Math.Max(xmax,x);ymax=Math.Max(ymax,y);}
            if(x==b.Width/2 && y==b.Height/2)center=a;
            if(x==0 || y==0 || x==b.Width-1 || y==b.Height-1)borderMax=Math.Max(borderMax,a);
          }
        }
        return new long[]{b.Width,b.Height,zero,partial,solid,xmin,ymin,xmax,ymax,center,borderMax};
      } finally {b.UnlockBits(d);}
    }
  }
}
'@
$packageRoot = Join-Path (Get-Location) 'art/imagegen/mvp-v1'
$manifest = Get-Content -Raw (Join-Path $packageRoot 'manifest.json') | ConvertFrom-Json
$rows = @($manifest.assets | Where-Object { $_.status -like 'generated*' -and $_.alpha } | ForEach-Object {
  $a = [ArtAlphaAudit]::Inspect((Join-Path $packageRoot $_.path))
  [PSCustomObject]@{ id=$_.id; width=$a[0]; height=$a[1]; transparentPixels=$a[2]; partialPixels=$a[3]; opaquePixels=$a[4]; visibleBounds=@($a[5],$a[6],$a[7],$a[8]); centerAlpha=$a[9]; outerBorderMaxAlpha=$a[10] }
})
$report = [PSCustomObject]@{ note='Read-only alpha inspection. Bounds use alpha > 8. Does not prove compositing, runtime sizing or artistic acceptance.'; assets=$rows }
$report | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $packageRoot 'alpha-audit.json')
[PSCustomObject]@{ inspected=$rows.Count; noTransparentPixels=@($rows | Where-Object transparentPixels -eq 0).Count; borderAlphaAbove8=@($rows | Where-Object outerBorderMaxAlpha -gt 8 | Select-Object -ExpandProperty id) } | ConvertTo-Json -Compress
