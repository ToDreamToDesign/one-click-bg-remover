"""把簡報（PPT/PPTX…）與 PDF 的每一頁轉成 PNG。

- 簡報：用本機的 Microsoft PowerPoint（COM）匯出，版面、字型、動畫終態與在 PowerPoint 看到的一致。
- PDF：用 PyMuPDF 以指定寬度算繪。
輸出都是 PNG（無損），檔名「原檔名_第01頁.png」。
"""
import os
import subprocess
import sys
import tempfile

SLIDE_EXTS = (".pptx", ".ppt", ".pps", ".ppsx", ".potx", ".pot")
PDF_EXTS = (".pdf",)
DOC_EXTS = SLIDE_EXTS + PDF_EXTS

_PS = r"""
param([string]$Path, [string]$OutDir, [string]$Stem, [int]$Width)
$ErrorActionPreference = 'Stop'
$wasRunning = [bool](Get-Process POWERPNT -ErrorAction SilentlyContinue)
$ppt = New-Object -ComObject PowerPoint.Application
try {
    $pres = $ppt.Presentations.Open($Path, -1, 0, 0)   # ReadOnly, 無標題=否, 不開視窗
    $sw = $pres.PageSetup.SlideWidth; $sh = $pres.PageSetup.SlideHeight
    $h = [int][Math]::Round($Width * $sh / $sw)
    $i = 0
    foreach ($s in $pres.Slides) {
        $i++
        $s.Export((Join-Path $OutDir ('{0}_第{1:D2}頁.png' -f $Stem, $i)), 'PNG', $Width, $h)
    }
    $pres.Close()
} finally {
    if (-not $wasRunning) { $ppt.Quit() }
}
"""


def _flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def render_slides(path, out_dir, width):
    stem = os.path.splitext(os.path.basename(path))[0]
    ps1 = os.path.join(out_dir, "_export.ps1")
    with open(ps1, "w", encoding="utf-8-sig") as f:
        f.write(_PS)
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1,
         "-Path", os.path.abspath(path), "-OutDir", out_dir, "-Stem", stem, "-Width", str(width)],
        capture_output=True, creationflags=_flags(), timeout=1800)
    os.remove(ps1)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or b"").decode("utf-8", "replace").strip()
        raise RuntimeError("PowerPoint 匯出失敗（需要安裝 Microsoft PowerPoint）：" + err[:400])


def render_pdf(path, out_dir, width):
    import pymupdf
    stem = os.path.splitext(os.path.basename(path))[0]
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, 1):
            zoom = width / page.rect.width
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            pix.save(os.path.join(out_dir, "%s_第%02d頁.png" % (stem, i)))


def import_document(path, width=3840):
    """回傳 (輸出資料夾, [PNG 路徑…])；PNG 依頁碼排序。"""
    out_dir = tempfile.mkdtemp(prefix="yijian_")
    ext = os.path.splitext(path)[1].lower()
    if ext in PDF_EXTS:
        render_pdf(path, out_dir, width)
    else:
        render_slides(path, out_dir, width)
    pngs = sorted(os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.lower().endswith(".png"))
    if not pngs:
        raise RuntimeError("沒有匯出任何頁面：" + os.path.basename(path))
    return out_dir, pngs
