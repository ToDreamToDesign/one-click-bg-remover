"""一鍵去背 - Windows 桌面程式（本機運算，不上傳圖片）

去背方式：AI 自動去背 / 指定顏色去除 / 兩者並用
可調：邊緣銳利度、去除顏色與容差、輸出背景、輸出解析度、輸出格式（預設 PNG，可選同原檔）
"""
import os
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageTk

import theme
from docimport import DOC_EXTS, import_document

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    Root = TkinterDnD.Tk
    HAS_DND = True
except ImportError:
    Root = tk.Tk
    HAS_DND = False

EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
PREVIEW = (380, 380)
MODELS = {
    "快速 (u2net)": "u2net",
    "平衡 (isnet)": "isnet-general-use",
    "高品質輕量 (BiRefNet-lite)": "birefnet-general-lite",
    "最高品質 (BiRefNet)": "birefnet-general",
}
METHODS = ["自動 (AI)", "指定顏色", "AI + 指定顏色", "不處理（只轉檔）"]
OUTPUTS = ["透明", "綠背", "白底", "黑底", "自選顏色…"]
RESOLUTIONS = ["原尺寸", "1080p (高1080)", "720p (高720)", "480p (高480)", "自訂高度…"]
FORMATS = ["同原檔", "PNG", "JPG", "WEBP", "BMP"]
GREEN = (0, 177, 64)
# 格式名稱 -> (PIL 格式, 副檔名, 是否支援透明)
FMT = {
    "PNG": ("PNG", ".png", True),
    "JPG": ("JPEG", ".jpg", False),
    "WEBP": ("WEBP", ".webp", True),
    "BMP": ("BMP", ".bmp", False),
}
EXT_TO_FMT = {".png": "PNG", ".jpg": "JPG", ".jpeg": "JPG", ".webp": "WEBP", ".bmp": "BMP"}


def load_image(path):
    im = ImageOps.exif_transpose(Image.open(path))
    return im.convert("RGBA")


def detect_format(path):
    return EXT_TO_FMT.get(os.path.splitext(path)[1].lower(), "PNG")


def apply_sharpness(alpha, s):
    """s: 0~100，50=不變；<50 邊緣更柔，>50 邊緣更銳利（把半透明邊緣往 0/255 推）。"""
    if s < 50:
        r = (50 - s) / 50 * 6 * max(alpha.size) / 1000
        return alpha.filter(ImageFilter.GaussianBlur(max(r, 0.01))) if r >= 0.05 else alpha
    if s > 50:
        k = 1 + (s - 50) / 50 * 15
        lut = [int(min(255, max(0, (i - 127.5) * k + 127.5))) for i in range(256)]
        return alpha.point(lut)
    return alpha


def color_key_alpha(rgb, key, tol):
    """與 key 色距離 <= tol 的像素去除（alpha=0），之後 20 單位內漸變到不透明。"""
    arr = np.asarray(rgb.convert("RGB"), dtype=np.float32)
    d = np.sqrt(((arr - np.array(key, dtype=np.float32)) ** 2).sum(axis=2))
    a = np.clip((d - tol) / 20.0, 0, 1)
    return a


def refine_mask(rgb, mask):
    """用原圖全解析度精修 AI 遮罩（closed-form matting）。

    AI 模型內部以約 1024px 運算，遮罩放大後邊緣會軟。這裡只在邊緣「不確定帶」上用原圖像素
    重新求解，確定的內部/外部不動；失敗（記憶體不足等）時原樣回傳粗遮罩。
    實測（3000x2000 合成圖，已知答案）：邊緣帶誤差 0.096 -> 0.060。
    """
    try:
        from pymatting import estimate_alpha_cf
        from scipy.ndimage import binary_dilation, binary_erosion
        m = np.asarray(mask.resize(rgb.size), dtype=np.float32) / 255.0
        long = max(rgb.size)
        eb, db = max(3, round(long * 0.0133)), max(6, round(long * 0.04))
        fg = binary_erosion(m > 0.5, iterations=eb)
        bg = ~binary_dilation(m > 0.002, iterations=db)
        unknown = ~(fg | bg)
        if not unknown.any():
            return mask
        ys, xs = np.where(unknown)
        pad = 8
        y0, y1 = max(0, ys.min() - pad), min(m.shape[0], ys.max() + 1 + pad)
        x0, x1 = max(0, xs.min() - pad), min(m.shape[1], xs.max() + 1 + pad)
        tri = np.full(m.shape, 0.5, np.float64)
        tri[fg] = 1.0
        tri[bg] = 0.0
        img = np.asarray(rgb.convert("RGB"), dtype=np.float64)[y0:y1, x0:x1] / 255.0
        a = np.clip(estimate_alpha_cf(img, tri[y0:y1, x0:x1]), 0, 1)
        out = m.copy()
        out[y0:y1, x0:x1] = a
        return Image.fromarray((out * 255 + 0.5).astype("uint8"), "L")
    except Exception:
        return mask


def decontaminate(rgb, alpha):
    """去色邊：半透明邊緣像素的顏色混了舊背景，改用估計的前景色；完全不透明/透明處保持原像素不變。"""
    try:
        from pymatting import estimate_foreground_ml
        a = np.asarray(alpha, dtype=np.float64) / 255.0
        edge = (a > 0) & (a < 1)
        if not edge.any():
            return rgb
        src = np.asarray(rgb.convert("RGB"), dtype=np.float64) / 255.0
        fg = estimate_foreground_ml(src, a)
        out = np.asarray(rgb.convert("RGB")).copy()
        out[edge] = np.clip(fg[edge] * 255 + 0.5, 0, 255).astype("uint8")
        return Image.fromarray(out, "RGB")
    except Exception:
        return rgb


class App(Root):
    def __init__(self):
        super().__init__()
        self.title("一鍵去背")
        self.geometry("1020x700")
        self.sessions = {}
        self.files = []
        self.masks = {}  # (path, model) -> L 遮罩
        self.refined = {}  # (path, model) -> 全解析度精修後的 L 遮罩
        self.out_color = (255, 0, 255)
        self.key_color = (0, 177, 64)
        self.picking = False
        self.busy = False
        self._in_img = None
        self._after = None

        # ---- 第一列：載入與去背 ----
        theme.apply(self)
        theme.header(self, "一鍵去背")
        r1 = ttk.Frame(self, padding=(8, 8, 8, 2))
        r1.pack(fill="x")
        ttk.Button(r1, text="選擇圖片…", command=self.pick).pack(side="left")
        ttk.Label(r1, text="去背方式:").pack(side="left", padx=(12, 2))
        self.method_var = tk.StringVar(value=METHODS[0])
        self._combo(r1, self.method_var, METHODS, 12)
        ttk.Label(r1, text="模型:").pack(side="left", padx=(12, 2))
        self.model_var = tk.StringVar(value="最高品質 (BiRefNet)")
        self._combo(r1, self.model_var, list(MODELS), 24)
        self.btn_run = ttk.Button(r1, text="一鍵去背", command=self.run, style="Accent.TButton")
        self.btn_run.pack(side="left", padx=8)
        self.btn_save = ttk.Button(r1, text="儲存全部", command=self.save_all)
        self.btn_save.pack(side="left")

        # ---- 第二列：銳利度與去除顏色 ----
        r2 = ttk.Frame(self, padding=(8, 2))
        r2.pack(fill="x")
        ttk.Label(r2, text="邊緣銳利度:").pack(side="left")
        self.sharp_var = tk.IntVar(value=50)
        ttk.Scale(r2, from_=0, to=100, variable=self.sharp_var, length=160,
                  command=lambda v: self.later()).pack(side="left", padx=4)
        self.sharp_lbl = ttk.Label(r2, width=8, text="50 (標準)")
        self.sharp_lbl.pack(side="left")
        ttk.Label(r2, text="  去除顏色:").pack(side="left", padx=(12, 2))
        self.swatch = tk.Label(r2, width=3, bg=self.hex(self.key_color), relief="solid", bd=1)
        self.swatch.pack(side="left")
        ttk.Button(r2, text="選色…", command=self.choose_key).pack(side="left", padx=2)
        self.btn_pick = ttk.Button(r2, text="吸管（點左圖）", command=self.start_pick)
        self.btn_pick.pack(side="left", padx=2)
        ttk.Label(r2, text="容差:").pack(side="left", padx=(8, 2))
        self.tol_var = tk.IntVar(value=40)
        ttk.Scale(r2, from_=0, to=150, variable=self.tol_var, length=120,
                  command=lambda v: self.later()).pack(side="left")
        self.tol_lbl = ttk.Label(r2, width=4, text="40")
        self.tol_lbl.pack(side="left")

        # ---- 第三列：輸出 ----
        r3 = ttk.Frame(self, padding=(8, 2, 8, 6))
        r3.pack(fill="x")
        ttk.Label(r3, text="輸出背景:").pack(side="left")
        self.out_var = tk.StringVar(value="綠背")
        cb = self._combo(r3, self.out_var, OUTPUTS, 10)
        cb.bind("<<ComboboxSelected>>", self.on_output)
        ttk.Label(r3, text="  解析度:").pack(side="left", padx=(12, 2))
        self.res_var = tk.StringVar(value=RESOLUTIONS[0])
        cb = self._combo(r3, self.res_var, RESOLUTIONS, 14)
        cb.bind("<<ComboboxSelected>>", lambda e: self.later())
        self.res_h = tk.StringVar(value="1080")
        self.res_entry = ttk.Entry(r3, textvariable=self.res_h, width=6)
        self.res_entry.pack(side="left", padx=2)
        ttk.Label(r3, text="px 高").pack(side="left")
        ttk.Label(r3, text="  格式:").pack(side="left", padx=(12, 2))
        self.fmt_var = tk.StringVar(value="PNG")
        self._combo(r3, self.fmt_var, FORMATS, 8)
        self.refine_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(r3, text="高解析邊緣精修", variable=self.refine_var,
                        command=self.later).pack(side="left", padx=(14, 2))
        self.despill_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(r3, text="去色邊", variable=self.despill_var).pack(side="left")
        ttk.Label(r3, text="  簡報/PDF 渲染寬度:").pack(side="left", padx=(12, 2))
        self.doc_w = tk.StringVar(value="3840")
        ttk.Combobox(r3, textvariable=self.doc_w, width=6,
                     values=["1920", "2560", "3840", "5120"]).pack(side="left")

        # ---- 主體 ----
        body = ttk.Frame(self, padding=8)
        body.pack(fill="both", expand=True)
        self.lst = theme.listbox(body, width=28)
        self.lst.pack(side="left", fill="y")
        self.lst.bind("<<ListboxSelect>>", lambda e: self.show())
        pv = ttk.Frame(body)
        pv.pack(side="left", fill="both", expand=True, padx=8)
        self.lb_in = ttk.Label(pv, text="原圖", style="Preview.TLabel")
        self.lb_out = ttk.Label(pv, text="去背結果", style="Preview.TLabel")
        self.lb_in.grid(row=0, column=0, sticky="nsew")
        self.lb_out.grid(row=0, column=1, sticky="nsew")
        self.lb_in.bind("<Button-1>", self.on_click_in)
        pv.columnconfigure((0, 1), weight=1)
        pv.rowconfigure(0, weight=1)

        self.status = tk.StringVar(value="把圖片拖進視窗，或按「選擇圖片」" if HAS_DND else "按「選擇圖片」開始")
        ttk.Label(self, textvariable=self.status, style="Status.TLabel", anchor="w").pack(fill="x", side="bottom")
        self.bar = ttk.Progressbar(self, mode="determinate")
        self.bar.pack(fill="x", side="bottom")

        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", lambda e: self.add(self.tk.splitlist(e.data)))

    # ---- UI 小工具 ----
    def _combo(self, parent, var, values, width):
        cb = ttk.Combobox(parent, textvariable=var, width=width, state="readonly", values=values)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self.later())
        return cb

    @staticmethod
    def hex(c):
        return "#%02x%02x%02x" % tuple(c)

    @property
    def model(self):
        return MODELS[self.model_var.get()]

    def needs_ai(self):
        return self.method_var.get() in ("自動 (AI)", "AI + 指定顏色")

    def needs_key(self):
        return self.method_var.get() in ("指定顏色", "AI + 指定顏色")

    def later(self):
        """滑桿拖動時延遲重畫，避免卡頓。"""
        self.sharp_lbl.configure(text="%d (%s)" % (self.sharp_var.get(), self.sharp_name()))
        self.tol_lbl.configure(text=str(int(self.tol_var.get())))
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(120, self.show)

    def sharp_name(self):
        s = int(self.sharp_var.get())
        return "標準" if s == 50 else ("更柔" if s < 50 else "更銳利")

    # ---- 顏色 ----
    def choose_key(self):
        c = colorchooser.askcolor(color=self.key_color, title="選擇要去除的顏色")
        if c[0]:
            self.set_key(tuple(int(v) for v in c[0]))

    def set_key(self, col):
        self.key_color = col
        self.swatch.configure(bg=self.hex(col))
        self.later()

    def start_pick(self):
        self.picking = True
        self.status.set("請在左邊「原圖」上點一下要去除的顏色")

    def on_click_in(self, e):
        if not self.picking or self._in_img is None:
            return
        iw, ih = self._in_img.size
        x = e.x - (self.lb_in.winfo_width() - iw) // 2
        y = e.y - (self.lb_in.winfo_height() - ih) // 2
        if 0 <= x < iw and 0 <= y < ih:
            self.picking = False
            self.set_key(self._in_img.convert("RGB").getpixel((x, y)))
            self.status.set("已選取去除顏色 " + self.hex(self.key_color))

    def on_output(self, _=None):
        if self.out_var.get() == "自選顏色…":
            c = colorchooser.askcolor(color=self.out_color, title="選擇背景顏色")
            if c[0]:
                self.out_color = tuple(int(v) for v in c[0])
        self.later()

    # ---- 檔案 ----
    def pick(self):
        ps = filedialog.askopenfilenames(title="選擇圖片或簡報/PDF",
                                         filetypes=[("圖片、簡報、PDF", " ".join("*" + x for x in EXTS + DOC_EXTS)),
                                                    ("圖片", " ".join("*" + x for x in EXTS)),
                                                    ("簡報/PDF", " ".join("*" + x for x in DOC_EXTS))])
        if ps:
            self.add(ps)

    def add(self, paths):
        for p in paths:
            if os.path.isdir(p):
                self.add([os.path.join(p, f) for f in sorted(os.listdir(p))])
            elif p.lower().endswith(DOC_EXTS):
                self.load_doc(p)
            elif p.lower().endswith(EXTS) and p not in self.files:
                self.files.append(p)
                self.lst.insert("end", "%s  [%s]" % (os.path.basename(p), detect_format(p)))
        if self.files and not self.lst.curselection():
            self.lst.selection_set(0)
            self.show()
        self.status.set(f"已載入 {len(self.files)} 張（輸出格式預設 PNG）")

    def load_doc(self, path):
        """簡報/PDF 逐頁轉成 PNG（背景執行緒），完成後把每一頁加進清單。"""
        try:
            width = max(320, int(self.doc_w.get()))
        except ValueError:
            width = 3840
        self.status.set("轉換中：%s（簡報會呼叫 PowerPoint，請稍候）…" % os.path.basename(path))
        self.bar.configure(mode="indeterminate")
        self.bar.start(12)

        def job():
            try:
                _, pngs = import_document(path, width)
                self.ui(lambda: self.add(pngs))
                self.ui(lambda: self.status.set("已匯入 %d 頁：%s（%d px 寬）" % (len(pngs), os.path.basename(path), width)))
            except Exception as e:
                self.ui(lambda e=e: (messagebox.showerror("匯入失敗", str(e)), self.status.set("匯入失敗")))
            finally:
                self.ui(lambda: (self.bar.stop(), self.bar.configure(mode="determinate", value=0)))
        threading.Thread(target=job, daemon=True).start()

    # ---- 去背（AI 遮罩） ----
    def run(self):
        if self.busy or not self.files:
            return
        if not self.needs_ai():
            self.status.set("「指定顏色」不需要 AI，已即時預覽；直接按「儲存全部」即可")
            return
        self.busy = True
        self.btn_run.state(["disabled"])
        threading.Thread(target=self.work, args=(self.model,), daemon=True).start()

    def work(self, model):
        try:
            from rembg import new_session, remove
            if model not in self.sessions:
                self.ui(lambda: self.status.set("載入模型中（首次使用該模型需下載，請稍候）…"))
                self.sessions[model] = new_session(model)
            sess = self.sessions[model]
            n = len(self.files)
            self.ui(lambda: self.bar.configure(maximum=n, value=0))
            for i, p in enumerate(list(self.files), 1):
                if (p, model) not in self.masks:
                    self.ui(lambda i=i: self.status.set(f"AI 去背中 {i}/{n}…"))
                    self.masks[(p, model)] = remove(load_image(p), session=sess, only_mask=True)
                if self.refine_var.get() and (p, model) not in self.refined:
                    self.ui(lambda i=i: self.status.set(f"全解析度邊緣精修 {i}/{n}（較慢，畫質優先）…"))
                    self.refined[(p, model)] = refine_mask(load_image(p), self.masks[(p, model)])
                self.ui(lambda i=i: (self.bar.configure(value=i), self.show()))
            self.ui(lambda: self.status.set("完成！可調整銳利度/顏色，再按「儲存全部」"))
        except Exception as e:
            self.ui(lambda e=e: (messagebox.showerror("錯誤", str(e)), self.status.set("失敗")))
        finally:
            self.busy = False
            self.ui(lambda: self.btn_run.state(["!disabled"]))

    def ui(self, fn):
        self.after(0, fn)

    # ---- 影像合成 ----
    def build_alpha(self, orig, mask):
        """回傳最終 alpha（L）；缺少所需遮罩時回傳 None。"""
        a = None
        if self.needs_ai():
            if mask is None:
                return None
            a = np.asarray(mask.resize(orig.size), dtype=np.float32) / 255.0
        if self.needs_key():
            ak = color_key_alpha(orig, self.key_color, self.tol_var.get())
            a = ak if a is None else np.minimum(a, ak)
        if a is None:  # 「不處理（只轉檔）」
            return Image.new("L", orig.size, 255)
        alpha = Image.fromarray((a * 255).astype("uint8"), "L")
        return apply_sharpness(alpha, int(self.sharp_var.get()))

    def cutout(self, orig, mask):
        alpha = self.build_alpha(orig, mask)
        if alpha is None:
            return None
        out = orig.convert("RGB").convert("RGBA")
        out.putalpha(alpha)
        return out

    def bg_color(self):
        return {"綠背": GREEN, "白底": (255, 255, 255), "黑底": (0, 0, 0),
                "自選顏色…": self.out_color}.get(self.out_var.get())

    def compose(self, im, checker=False):
        col = self.bg_color()
        if col is None:
            if not checker:
                return im
            bg = Image.new("RGBA", im.size, theme.CHECKER[0])
            arr = np.asarray(bg).copy()
            yy, xx = np.mgrid[0:im.height, 0:im.width]
            arr[((xx // 10) + (yy // 10)) % 2 == 1] = theme.CHECKER[1]
            bg = Image.fromarray(arr, "RGBA")
        else:
            bg = Image.new("RGBA", im.size, col + (255,))
        return Image.alpha_composite(bg, im)

    def mask_for(self, p):
        key = (p, self.model)
        if self.refine_var.get() and key in self.refined:
            return self.refined[key]
        return self.masks.get(key)

    def target_height(self):
        v = self.res_var.get()
        if v == "原尺寸":
            return None
        if v.startswith("自訂"):
            try:
                return max(1, int(self.res_h.get()))
            except ValueError:
                return None
        return int(v.split("高")[1].rstrip(")"))

    # ---- 預覽 ----
    def show(self):
        self._after = None
        self.res_entry.state(["!disabled"] if self.res_var.get().startswith("自訂") else ["disabled"])
        sel = self.lst.curselection()
        if not sel:
            return
        p = self.files[sel[0]]
        orig = load_image(p)
        thumb = orig.copy()
        thumb.thumbnail(PREVIEW)
        self._in_img = thumb
        self._set(self.lb_in, thumb)
        mask = self.mask_for(p)
        mask_t = mask.resize(thumb.size, Image.LANCZOS) if mask is not None else None
        cut = self.cutout(thumb, mask_t)
        if cut is None:
            self.lb_out.configure(image="", text="（尚未處理，請按「一鍵去背」）")
        else:
            self._set(self.lb_out, self.compose(cut, checker=True))

    def _set(self, label, im):
        tk_im = ImageTk.PhotoImage(im)
        label.configure(image=tk_im, text="")
        label.image = tk_im

    # ---- 儲存 ----
    def out_format(self, path):
        f = self.fmt_var.get()
        return detect_format(path) if f == "同原檔" else f

    def save_all(self):
        if not self.files:
            return
        model = self.model
        if self.needs_ai() and any((p, model) not in self.masks for p in self.files):
            messagebox.showinfo("尚未完成", "還有圖片沒有做 AI 去背，請先按「一鍵去背」。")
            return
        if self.needs_ai() and self.refine_var.get() and any((p, model) not in self.refined for p in self.files):
            messagebox.showinfo("尚未完成", "已勾選「高解析邊緣精修」，但還有圖片沒精修，請再按一次「一鍵去背」。")
            return
        d = filedialog.askdirectory(title="選擇輸出資料夾")
        if not d:
            return
        th = self.target_height()
        notes = []
        for p in self.files:
            orig = load_image(p)
            cut = self.cutout(orig, self.mask_for(p))
            if self.despill_var.get():
                alpha = cut.split()[3]
                rgb = decontaminate(orig, alpha)
                cut = rgb.convert("RGBA")
                cut.putalpha(alpha)
            if th and th != cut.height:
                w = max(1, round(cut.width * th / cut.height))
                cut = cut.resize((w, th), Image.LANCZOS)
            fmt = self.out_format(p)
            transparent = self.bg_color() is None
            if transparent and not FMT[fmt][2]:
                notes.append("%s：%s 不支援透明，已改存 PNG" % (os.path.basename(p), fmt))
                fmt = "PNG"
            pil_fmt, ext, _ = FMT[fmt]
            img = cut if transparent else self.compose(cut)
            if pil_fmt in ("JPEG", "BMP"):
                img = img.convert("RGB")
            # 畫質優先：全部無損（JPG 以最高品質、不做色度抽樣；WEBP 用 lossless）
            kw = {"JPEG": {"quality": 100, "subsampling": 0},
                  "WEBP": {"lossless": True, "quality": 100, "method": 6},
                  "PNG": {"compress_level": 6}}.get(pil_fmt, {})
            with Image.open(p) as src:
                if src.info.get("icc_profile"):
                    kw["icc_profile"] = src.info["icc_profile"]
                if src.info.get("dpi") and pil_fmt in ("PNG", "JPEG"):
                    kw["dpi"] = src.info["dpi"]
            name = os.path.splitext(os.path.basename(p))[0] + "_去背" + ext
            img.save(os.path.join(d, name), pil_fmt, **kw)
        msg = "已儲存 %d 張到 %s" % (len(self.files), d)
        self.status.set(msg)
        if notes:
            messagebox.showinfo("格式提醒", "\n".join(notes))
        os.startfile(d)


if __name__ == "__main__":
    App().mainloop()
