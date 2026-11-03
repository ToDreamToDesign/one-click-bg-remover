# 一鍵去背

Windows 桌面程式（Python + tkinter + rembg），本機運算，圖片不會上傳。

- 模型可選：u2net（快速）／isnet／BiRefNet-lite／BiRefNet（最高品質）
- 輸出：透明 PNG、綠背 (#00B140)、白底、黑底、自選色
- 支援拖放與批次

## 下載使用（Windows）

1. 到 [Releases](../../releases/latest) 下載 `OneClickBG-win64.zip`
2. 解壓縮，執行資料夾內的 `一鍵去背.exe`（不需要安裝 Python）
3. 第一次使用某個模型時會自動下載該模型檔（數十到數百 MB），需連網，之後存在 `C:\Users\<你>\.rembg\models\` 離線可用

Windows 可能跳出 SmartScreen 警告（程式沒有簽章）：選「其他資訊」→「仍要執行」。

## 從原始碼執行

```
pip install -r requirements.txt
python app.py
```

## 速度參考（CPU）

BiRefNet-lite 約 20 秒/張（含載入）；BiRefNet 約 101 秒（含首次載入）。

## 授權注意

程式碼使用 rembg（MIT）。各模型權重授權各自獨立，商用前請自行確認：RMBG-2.0 為 CC BY-NC 4.0（僅限非商用）；BiRefNet 授權請查其官方 repo。
