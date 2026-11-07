# 一鍵去背

Windows 桌面程式（Python + tkinter + rembg），本機運算、不上傳圖片。畫質優先：不縮圖、無損輸出。

## 功能
- **輸入**：圖片（PNG/JPG/WEBP/BMP，可拖曳、可整個資料夾）、簡報（PPT/PPTX/PPS/PPSX/POT/POTX，需本機有 Microsoft PowerPoint）、PDF；簡報/PDF 每頁轉成 PNG（預設寬 3840，可選 1920/2560/3840/5120）。
- **去背方式**：自動 (AI) / 指定顏色（選色或吸管、可調容差）/ AI＋指定顏色 / 不處理（只轉檔）。
- **模型**：u2net、isnet、BiRefNet-lite、BiRefNet（最高品質）。
- **畫質**：高解析邊緣精修（closed-form matting，只重算邊緣帶）、去色邊（只動半透明邊緣像素）、邊緣銳利度滑桿。
- **輸出**：背景＝透明/綠背(#00B140)/白/黑/自選色；解析度＝原尺寸(預設)/1080p/720p/480p/自訂高度（等比例）；格式＝PNG(預設)/JPG/WEBP/BMP/同原檔；JPG 以 quality 100、不抽樣，WEBP lossless，保留 ICC 與 DPI；透明輸出遇不支援透明的格式自動改 PNG。

## 外觀
- 套用 DREAM 視覺語言（取自 DREAM Ledger `docs/design-system.md`）：深色、精準、無多餘裝飾；底 #090d10、面板 #11171e、品牌/互動色霓虹青 #32d4d7。兩個去背工具各有一份相同的 `theme.py`。

## 啟動與打包
- `python app.py`；打包用 PyInstaller（onedir、--windowed，collect-all：rembg、tkinterdnd2、onnxruntime、pymatting、skimage、numba、llvmlite、pymupdf）。
- 檔案：`app.py`（介面與流程）、`docimport.py`（簡報/PDF → PNG）。

## 實測（2026-11-02/03，CPU）
- 4K(3840×2160)輸入 → 4K 輸出；不透明像素 RGB 與原圖完全相同；DPI 保留。
- 邊緣精修（合成圖、已知答案）：邊緣帶誤差 0.263 → 0.191；4K 約 32 秒/張。
- 簡報：3 頁 PPTX → 3 張 3840×2160 PNG（約 15 秒）；PDF 以 PyMuPDF 算繪。
- 模型快取：`C:\Users\Meng\.rembg\models\`。
- 未驗證：打包後 exe 實際開啟、吸管/滑桿手動操作、真實照片效果。

## 開源去背調查
- RMBG-2.0 (Bria)：基於 BiRefNet，權重 CC BY-NC 4.0，**僅限非商用**
- BiRefNet：目前最強的開源選項之一；授權待查（商用前須確認）
- rembg：包裝工具（程式碼 MIT），各模型權重授權各自獨立；預設 u2net 品質最弱
- PyMuPDF（PDF 算繪）為 AGPL/商業雙授權；工作用途若要散布此工具請留意
- MatAnyone / RobustVideoMatting：影片摳像用，授權與硬體需求待查
