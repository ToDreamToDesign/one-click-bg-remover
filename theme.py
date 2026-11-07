"""DREAM 視覺語言（取自 DREAM Ledger docs/design-system.md）：深色、精準、無多餘裝飾。

色票：背景 #090d10、面板 #11171e、面板 hover #161f29、主文字 #f1f5f9、次要文字 #64748b；
品牌/互動色 霓虹青 #32d4d7、琥珀 #fbbf24（提醒）、玫瑰 #f43f5e（警示）。
字體：Noto Sans TC（沒有則用微軟正黑體）。
兩個去背工具各放一份相同的檔案（獨立 repo 發佈，不互相引用）。
"""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

BG = "#090d10"
PANEL = "#11171e"
HOVER = "#161f29"
BORDER = "#222b36"
TEXT = "#f1f5f9"
MUTED = "#64748b"
CYAN = "#32d4d7"
CYAN_HI = "#6ee7e9"
AMBER = "#fbbf24"
ROSE = "#f43f5e"
ON_CYAN = "#04202a"
CHECKER = ((36, 44, 54, 255), (52, 62, 74, 255))   # 透明預覽用的深色棋盤格


def _family(root):
    have = set(tkfont.families(root))
    for f in ("Noto Sans TC", "Microsoft JhengHei UI", "Microsoft JhengHei", "Segoe UI"):
        if f in have:
            return f
    return "TkDefaultFont"


def apply(root):
    fam = _family(root)
    base = (fam, 10)
    root.configure(bg=BG)
    root.option_add("*Font", base)
    root.option_add("*TCombobox*Listbox.background", PANEL)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", CYAN)
    root.option_add("*TCombobox*Listbox.selectForeground", ON_CYAN)
    root.option_add("*TCombobox*Listbox.font", base)
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL, bordercolor=BORDER,
                lightcolor=BORDER, darkcolor=BORDER, troughcolor=PANEL, focuscolor=BG, font=base)
    s.configure("TFrame", background=BG)
    s.configure("TLabel", background=BG, foreground=TEXT)
    s.configure("Muted.TLabel", background=BG, foreground=MUTED)
    s.configure("Title.TLabel", background=BG, foreground=TEXT, font=(fam, 15, "bold"))
    s.configure("Brand.TLabel", background=BG, foreground=CYAN, font=(fam, 9, "bold"))
    s.configure("Status.TLabel", background=PANEL, foreground=MUTED, padding=(10, 5), relief="flat")
    s.configure("Preview.TLabel", background=PANEL, foreground=MUTED, anchor="center")
    s.configure("TButton", background=PANEL, foreground=TEXT, bordercolor=BORDER, padding=(12, 6), relief="flat")
    s.map("TButton", background=[("disabled", BG), ("active", HOVER)], foreground=[("disabled", MUTED)],
          bordercolor=[("active", CYAN)])
    s.configure("Accent.TButton", background=CYAN, foreground=ON_CYAN, bordercolor=CYAN, padding=(16, 6),
                font=(fam, 10, "bold"))
    s.map("Accent.TButton", background=[("disabled", HOVER), ("active", CYAN_HI)],
          foreground=[("disabled", MUTED)], bordercolor=[("disabled", BORDER), ("active", CYAN_HI)])
    for w in ("TEntry", "TSpinbox"):
        s.configure(w, fieldbackground=PANEL, foreground=TEXT, insertcolor=TEXT, bordercolor=BORDER, padding=4)
    s.map("TEntry", bordercolor=[("focus", CYAN)])
    s.map("TSpinbox", bordercolor=[("focus", CYAN)])
    s.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=TEXT, arrowcolor=MUTED,
                bordercolor=BORDER, padding=4, selectbackground=PANEL, selectforeground=TEXT)
    s.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)],
          selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", TEXT)],
          bordercolor=[("focus", CYAN)], arrowcolor=[("active", CYAN)])
    s.configure("Horizontal.TScale", background=CYAN, troughcolor=PANEL, bordercolor=BORDER,
                lightcolor=CYAN, darkcolor=CYAN)
    s.configure("Horizontal.TProgressbar", background=CYAN, troughcolor=PANEL, bordercolor=BORDER,
                lightcolor=CYAN, darkcolor=CYAN, thickness=6)
    s.configure("TCheckbutton", background=BG, foreground=TEXT, indicatorcolor=PANEL, indicatorbackground=PANEL,
                indicatorforeground=CYAN, bordercolor=MUTED)
    s.map("TCheckbutton", indicatorcolor=[("selected", CYAN)], background=[("active", BG)],
          foreground=[("active", CYAN)])
    s.configure("Vertical.TScrollbar", background=PANEL, troughcolor=BG, bordercolor=BG, arrowcolor=MUTED)


def listbox(parent, **kw):
    return tk.Listbox(parent, exportselection=False, bg=PANEL, fg=TEXT, selectbackground=CYAN,
                      selectforeground=ON_CYAN, highlightthickness=1, highlightbackground=BORDER,
                      highlightcolor=CYAN, bd=0, relief="flat", activestyle="none", **kw)


def header(parent, title, sub="雙子座 · DREAM"):
    f = ttk.Frame(parent, padding=(12, 10, 12, 0))
    f.pack(fill="x")
    ttk.Label(f, text=title, style="Title.TLabel").pack(side="left")
    ttk.Label(f, text="  " + sub, style="Brand.TLabel").pack(side="left", pady=(6, 0))
    return f
