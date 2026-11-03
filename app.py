"""一鍵去背 - Windows 桌面程式（本機運算，不上傳圖片）"""
import os
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageTk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    Root = TkinterDnD.Tk
    HAS_DND = True
except ImportError:
    Root = tk.Tk
    HAS_DND = False

EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
PREVIEW = (360, 360)
MODELS = {
    "快速 (u2net)": "u2net",
    "平衡 (isnet)": "isnet-general-use",
    "高品質輕量 (BiRefNet-lite)": "birefnet-general-lite",
    "最高品質 (BiRefNet)": "birefnet-general",
}
OUTPUTS = ["透明 PNG", "綠背", "白底", "黑底", "自選顏色…"]
GREEN = (0, 177, 64)


class App(Root):
    def __init__(self):
        super().__init__()
        self.title("一鍵去背")
        self.geometry("900x580")
        self.sessions = {}
        self.files = []
        self.results = {}  # (path, model) -> RGBA Image
        self.custom = (255, 0, 255)
        self.busy = False

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="選擇圖片…", command=self.pick).pack(side="left")
        ttk.Label(top, text="模型:").pack(side="left", padx=(12, 2))
        self.model_var = tk.StringVar(value="最高品質 (BiRefNet)")
        mcb = ttk.Combobox(top, textvariable=self.model_var, width=24, state="readonly",
                           values=list(MODELS))
        mcb.pack(side="left")
        mcb.bind("<<ComboboxSelected>>", lambda e: self.show())
        self.btn_run = ttk.Button(top, text="一鍵去背", command=self.run)
        self.btn_run.pack(side="left", padx=8)
        ttk.Label(top, text="輸出:").pack(side="left", padx=(4, 2))
        self.out_var = tk.StringVar(value="綠背")
        ocb = ttk.Combobox(top, textvariable=self.out_var, width=10, state="readonly", values=OUTPUTS)
        ocb.pack(side="left")
        ocb.bind("<<ComboboxSelected>>", self.on_output)
        self.btn_save = ttk.Button(top, text="儲存全部", command=self.save_all, state="disabled")
        self.btn_save.pack(side="left", padx=8)

        body = ttk.Frame(self, padding=8)
        body.pack(fill="both", expand=True)
        self.lst = tk.Listbox(body, width=28, exportselection=False)
        self.lst.pack(side="left", fill="y")
        self.lst.bind("<<ListboxSelect>>", lambda e: self.show())
        pv = ttk.Frame(body)
        pv.pack(side="left", fill="both", expand=True, padx=8)
        self.lb_in = ttk.Label(pv, text="原圖", anchor="center")
        self.lb_out = ttk.Label(pv, text="去背結果", anchor="center")
        self.lb_in.grid(row=0, column=0, sticky="nsew")
        self.lb_out.grid(row=0, column=1, sticky="nsew")
        pv.columnconfigure((0, 1), weight=1)
        pv.rowconfigure(0, weight=1)

        self.status = tk.StringVar(value="把圖片拖進視窗，或按「選擇圖片」" if HAS_DND else "按「選擇圖片」開始")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")
        self.bar = ttk.Progressbar(self, mode="determinate")
        self.bar.pack(fill="x", side="bottom")

        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", lambda e: self.add(self.tk.splitlist(e.data)))

    @property
    def model(self):
        return MODELS[self.model_var.get()]

    # ---- 檔案 ----
    def pick(self):
        ps = filedialog.askopenfilenames(title="選擇圖片",
                                         filetypes=[("圖片", " ".join("*" + x for x in EXTS))])
        if ps:
            self.add(ps)

    def add(self, paths):
        for p in paths:
            if os.path.isdir(p):
                self.add([os.path.join(p, f) for f in sorted(os.listdir(p))])
            elif p.lower().endswith(EXTS) and p not in self.files:
                self.files.append(p)
                self.lst.insert("end", os.path.basename(p))
        if self.files and not self.lst.curselection():
            self.lst.selection_set(0)
            self.show()
        self.status.set(f"已載入 {len(self.files)} 張")

    # ---- 去背 ----
    def run(self):
        if self.busy or not self.files:
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
                if (p, model) not in self.results:
                    self.ui(lambda i=i: self.status.set(f"處理中 {i}/{n}…"))
                    img = Image.open(p).convert("RGBA")
                    self.results[(p, model)] = remove(img, session=sess)
                self.ui(lambda i=i: (self.bar.configure(value=i), self.show()))
            self.ui(lambda: (self.status.set("完成！按「儲存全部」輸出"),
                             self.btn_save.state(["!disabled"])))
        except Exception as e:
            self.ui(lambda e=e: (messagebox.showerror("錯誤", str(e)), self.status.set("失敗")))
        finally:
            self.busy = False
            self.ui(lambda: self.btn_run.state(["!disabled"]))

    def ui(self, fn):
        self.after(0, fn)

    # ---- 輸出合成 ----
    def on_output(self, _=None):
        if self.out_var.get() == "自選顏色…":
            c = colorchooser.askcolor(color=self.custom, title="選擇背景顏色")
            if c[0]:
                self.custom = tuple(int(v) for v in c[0])
        self.show()

    def background(self):
        return {"綠背": GREEN, "白底": (255, 255, 255), "黑底": (0, 0, 0),
                "自選顏色…": self.custom}.get(self.out_var.get())

    def compose(self, im, checker=False):
        col = self.background()
        if col is None:
            if not checker:
                return im
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            px = bg.load()
            for y in range(im.height):
                for x in range(im.width):
                    if ((x // 10) + (y // 10)) % 2:
                        px[x, y] = (204, 204, 204, 255)
        else:
            bg = Image.new("RGBA", im.size, col + (255,))
        return Image.alpha_composite(bg, im)

    # ---- 預覽 ----
    def show(self):
        sel = self.lst.curselection()
        if not sel:
            return
        p = self.files[sel[0]]
        self._set(self.lb_in, self.fit(Image.open(p).convert("RGBA")))
        r = self.results.get((p, self.model))
        if r:
            self._set(self.lb_out, self.compose(self.fit(r), checker=True))
        else:
            self.lb_out.configure(image="", text="（此模型尚未處理）")

    def fit(self, im):
        im = im.copy()
        im.thumbnail(PREVIEW)
        return im

    def _set(self, label, im):
        tk_im = ImageTk.PhotoImage(im)
        label.configure(image=tk_im, text="")
        label.image = tk_im

    # ---- 儲存 ----
    def save_all(self):
        model = self.model
        items = [(p, r) for (p, m), r in self.results.items() if m == model]
        if not items:
            return
        d = filedialog.askdirectory(title="選擇輸出資料夾")
        if not d:
            return
        tag = {"透明 PNG": "去背", "綠背": "綠背"}.get(self.out_var.get(), "換背")
        for p, r in items:
            name = os.path.splitext(os.path.basename(p))[0] + f"_{tag}.png"
            self.compose(r).save(os.path.join(d, name))
        self.status.set(f"已儲存 {len(items)} 張到 {d}")
        os.startfile(d)


if __name__ == "__main__":
    App().mainloop()
