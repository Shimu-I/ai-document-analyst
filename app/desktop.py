"""Document Analyst - desktop window (Tkinter, no browser).

    python app/desktop.py [file]

Left: filmstrip of the slides or pages. Middle: the original slide. Right: the text read from it, in the same layout
and editable. "Linked reading": a click on a line of text marks the place it came from on the slide, and a click on the
slide selects the matching line of text. English and Bengali are read together (language: auto).

Needs Python's tkinter (Ubuntu: sudo apt install python3-tk), Pillow, pytesseract and the tesseract program.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import slides as slides_mod                      # noqa: E402
from src.convert.base import ConversionError              # noqa: E402
from src.desktop_model import Deck, fit, to_canvas        # noqa: E402

try:
    from PIL import Image, ImageTk
except ImportError:                                       # reported when the window opens
    Image = ImageTk = None

FILETYPES = [("Slides, documents and images", "*.pdf *.pptx *.ppt *.odp *.docx *.doc *.odt *.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp"),
             ("All files", "*.*")]
LANGS = ["auto", "eng", "ben", "eng+ben"]
THUMB_W = 150

PALETTES = {
    "light": dict(bg="#F1E3D6", panel="#F8EBDF", ink="#3E4358", muted="#857C91", accent="#525871", accent_fg="#FBF3EC",
                  hl="#CD9FA0", line_bg="#F8CCAA", text_bg="#FBF3EC", canvas="#E8D4C2", sel="#CD9FA0"),
    "dim": dict(bg="#2A2E3E", panel="#363B4F", ink="#EADFD6", muted="#B9B0C4", accent="#CD9FA0", accent_fg="#2A2E3E",
                hl="#F2C1A3", line_bg="#4A4F66", text_bg="#2F3447", canvas="#23263A", sel="#F2C1A3"),
}


class App:
    def __init__(self, root: tk.Tk, path: str | None = None):
        self.root = root
        self.deck: Deck | None = None
        self.cur = 0
        self.hl = None                       # the Item currently marked on the slide
        self.thumbs: list = []
        self.thumb_frames: list = []
        self._img_cache: dict = {}
        self.q: queue.Queue = queue.Queue()
        self.theme = "light"
        self.show_original = tk.BooleanVar(value=True)
        self.lang = tk.StringVar(value=os.getenv("OCR_LANG", "auto"))
        root.title("Document Analyst")
        root.geometry("1380x820")
        root.minsize(900, 560)
        self._build()
        self.apply_theme()
        root.bind("<Control-o>", lambda e: self.open_file())
        root.bind("<Control-s>", lambda e: self.save())
        root.bind("<Alt-Left>", lambda e: self.step(-1))
        root.bind("<Alt-Right>", lambda e: self.step(1))
        root.after(100, self._poll)
        if path:
            root.after(200, lambda: self.open_file(path))

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        r = self.root
        self.bar = tk.Frame(r, padx=10, pady=8)
        self.bar.pack(fill="x")
        self.btn_open = tk.Button(self.bar, text="Open…", command=self.open_file, relief="flat", padx=14, pady=4, cursor="hand2")
        self.btn_open.pack(side="left")
        tk.Label(self.bar, text="  Language").pack(side="left")
        self.lang_box = ttk.Combobox(self.bar, textvariable=self.lang, values=LANGS, width=9)
        self.lang_box.pack(side="left", padx=(4, 12))
        self.btn_save = tk.Button(self.bar, text="Save .md", command=self.save, relief="flat", padx=10, pady=4, cursor="hand2")
        self.btn_save.pack(side="left", padx=2)
        self.btn_copy = tk.Button(self.bar, text="Copy all", command=self.copy_all, relief="flat", padx=10, pady=4, cursor="hand2")
        self.btn_copy.pack(side="left", padx=2)
        self.chk = tk.Checkbutton(self.bar, text="Show original", variable=self.show_original, command=self.toggle_original)
        self.chk.pack(side="left", padx=14)
        self.btn_theme = tk.Button(self.bar, text="Dim", command=self.toggle_theme, relief="flat", padx=10, pady=4, cursor="hand2")
        self.btn_theme.pack(side="right")
        self.total = tk.Label(self.bar, text="")
        self.total.pack(side="right", padx=12)
        self.progress = ttk.Progressbar(r, mode="indeterminate", length=200)

        self.paned = tk.PanedWindow(r, orient="horizontal", sashwidth=6, bd=0)
        self.paned.pack(fill="both", expand=True)

        # filmstrip
        self.strip_wrap = tk.Frame(self.paned, width=THUMB_W + 34)
        self.strip = tk.Canvas(self.strip_wrap, width=THUMB_W + 24, highlightthickness=0)
        sb = ttk.Scrollbar(self.strip_wrap, orient="vertical", command=self.strip.yview)
        self.strip.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.strip.pack(side="left", fill="both", expand=True)
        self.strip_inner = tk.Frame(self.strip)
        self.strip.create_window((0, 0), window=self.strip_inner, anchor="nw")
        self.strip_inner.bind("<Configure>", lambda e: self.strip.configure(scrollregion=self.strip.bbox("all")))
        self.paned.add(self.strip_wrap)

        # original slide
        self.view = tk.Frame(self.paned)
        self.canvas = tk.Canvas(self.view, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.paned.add(self.view, minsize=300, stretch="always")

        # text
        self.side = tk.Frame(self.paned)
        self.head = tk.Label(self.side, text="Text (editable)", anchor="w", padx=8, pady=4)
        self.head.pack(fill="x")
        body = tk.Frame(self.side)
        body.pack(fill="both", expand=True)
        self.text = tk.Text(body, wrap="word", undo=True, padx=10, pady=8, font=("DejaVu Sans Mono", 12), relief="flat", width=46)
        tsb = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("cur")
        self.text.bind("<ButtonRelease-1>", self.on_text_click)
        self.text.bind("<KeyRelease>", self.on_text_key)
        self.paned.add(self.side, minsize=280, stretch="always")

        self.status = tk.Label(r, anchor="w", padx=10, pady=5, text="Open a PDF, PowerPoint, Word file or image to begin (Ctrl+O).")
        self.status.pack(fill="x", side="bottom")

    def apply_theme(self) -> None:
        p = PALETTES[self.theme]
        self.root.configure(bg=p["bg"])
        for w in (self.bar, self.strip_wrap, self.view, self.side, self.strip_inner):
            w.configure(bg=p["bg"])
        for w in (self.paned,):
            w.configure(bg=p["bg"])
        for w in self.bar.winfo_children():
            if isinstance(w, tk.Label):
                w.configure(bg=p["bg"], fg=p["ink"])
        self.chk.configure(bg=p["bg"], fg=p["ink"], selectcolor=p["panel"], activebackground=p["bg"], activeforeground=p["ink"])
        self.btn_open.configure(bg=p["accent"], fg=p["accent_fg"], activebackground=p["accent"], activeforeground=p["accent_fg"])
        for b in (self.btn_save, self.btn_copy, self.btn_theme):
            b.configure(bg=p["panel"], fg=p["ink"], activebackground=p["canvas"], activeforeground=p["ink"])
        self.btn_theme.configure(text="Light" if self.theme == "dim" else "Dim")
        self.strip.configure(bg=p["bg"])
        self.canvas.configure(bg=p["canvas"])
        self.head.configure(bg=p["bg"], fg=p["muted"])
        self.text.configure(bg=p["text_bg"], fg=p["ink"], insertbackground=p["ink"], selectbackground=p["sel"], selectforeground=p["accent_fg"])
        self.text.tag_configure("cur", background=p["line_bg"])
        self.status.configure(bg=p["panel"], fg=p["ink"])
        for k, f in enumerate(self.thumb_frames):
            self._style_thumb(k, f)
        self.redraw()

    def toggle_theme(self) -> None:
        self.theme = "dim" if self.theme == "light" else "light"
        self.apply_theme()

    def toggle_original(self) -> None:
        if self.show_original.get():
            self.paned.add(self.view, before=self.side, minsize=300, stretch="always")
        else:
            self.paned.forget(self.view)
        self.redraw()

    # ------------------------------------------------------------------ opening
    def open_file(self, path: str | None = None) -> None:
        if Image is None or ImageTk is None:
            messagebox.showerror("Document Analyst", "Pillow with Tk support is needed: pip install pillow (and sudo apt install python3-pil.imagetk)")
            return
        path = path or filedialog.askopenfilename(title="Open", filetypes=FILETYPES)
        if not path:
            return
        self.status.configure(text=f"Reading {Path(path).name} … pictures are read with OCR, this can take a while.")
        self.progress.pack(side="bottom", fill="x")
        self.progress.start(12)
        self.btn_open.configure(state="disabled")
        lang = self.lang.get().strip() or "auto"

        def work() -> None:
            try:
                data = Path(path).read_bytes()
                self.q.put(("ok", Path(path).name, slides_mod.read_slides(data, path, lang)))
            except ConversionError as e:
                self.q.put(("err", str(e), None))
            except Exception as e:                           # never leave the window frozen
                self.q.put(("err", f"unexpected problem: {type(e).__name__}: {e}", None))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self) -> None:
        try:
            kind, a, b = self.q.get_nowait()
        except queue.Empty:
            self.root.after(120, self._poll)
            return
        self.progress.stop()
        self.progress.pack_forget()
        self.btn_open.configure(state="normal")
        if kind == "err":
            self.status.configure(text="Could not read the file.")
            messagebox.showerror("Document Analyst", a)
        else:
            self.load(a, b)
        self.root.after(120, self._poll)

    def load(self, name: str, slides: list) -> None:
        self.deck = Deck(slides, name)
        self.root.title(f"Document Analyst - {name}")
        self.thumbs.clear()
        self._img_cache.clear()
        for w in self.strip_inner.winfo_children():
            w.destroy()
        self.thumb_frames = []
        for k, s in enumerate(slides):
            img = Image.open(__import__("io").BytesIO(s.png))
            img.thumbnail((THUMB_W, THUMB_W))
            ph = ImageTk.PhotoImage(img)
            self.thumbs.append(ph)
            f = tk.Frame(self.strip_inner, padx=3, pady=3)
            lab = tk.Label(f, image=ph, bd=0)
            lab.pack()
            num = tk.Label(f, text=str(s.number), font=("DejaVu Sans", 9))
            num.pack()
            for w in (f, lab, num):
                w.bind("<Button-1>", lambda e, k=k: self.select(k))
            f.pack(pady=2, padx=4)
            self.thumb_frames.append(f)
        self.apply_theme()
        self.select(0, store=False)      # the text box still holds the previous file's text

    # ------------------------------------------------------------------ slides
    def _style_thumb(self, k: int, f) -> None:
        p = PALETTES[self.theme]
        on = self.deck is not None and k == self.cur
        bg = p["sel"] if on else p["bg"]
        f.configure(bg=bg)
        for c in f.winfo_children():
            c.configure(bg=bg)
            if isinstance(c, tk.Label) and not c.cget("image"):          # the slide number under the thumbnail
                c.configure(fg=p["accent_fg"] if on else p["muted"])

    def step(self, d: int) -> None:
        if self.deck and 0 <= self.cur + d < len(self.deck.slides):
            self.select(self.cur + d)

    def _store_edit(self) -> None:
        if self.deck is not None:
            self.deck.set_text(self.cur, self.text.get("1.0", "end-1c"))

    def select(self, k: int, store: bool = True) -> None:
        if not self.deck:
            return
        if store:
            self._store_edit()                # keep the corrections made on the slide being left
        self.cur, self.hl = k, None
        for j, f in enumerate(self.thumb_frames):
            self._style_thumb(j, f)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.deck.text(k))
        self.text.edit_reset()
        self.redraw()
        self.update_status()

    def update_status(self) -> None:
        if not self.deck:
            return
        s = self.deck.slides[self.cur]
        bits = [f"Slide {self.cur + 1} of {len(self.deck.slides)}", f"{self.deck.words(self.cur)} words",
                f"≈ {self.deck.tokens(self.cur)} tokens"]
        bits.append("text layer" if s.source == "text layer" else f"OCR {s.lang}" + (f", confidence {s.confidence:.0f}%" if s.confidence else ""))
        if self.deck.edited(self.cur):
            bits.append("edited")
        if s.note:
            bits.append(s.note)
        self.status.configure(text="  ·  ".join(bits))
        self.total.configure(text=f"All slides ≈ {self.deck.tokens()} tokens")

    # ------------------------------------------------------------------ drawing and links
    def redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        if not self.deck or not self.show_original.get():
            if not self.deck:
                c.create_text(max(c.winfo_width(), 400) // 2, max(c.winfo_height(), 300) // 2,
                              text="Open a file to see the original slide here.", fill=PALETTES[self.theme]["muted"], font=("DejaVu Sans", 13))
            return
        s = self.deck.slides[self.cur]
        w, h = max(c.winfo_width(), 50), max(c.winfo_height(), 50)
        scale, ox, oy = fit(s.size, (w, h))
        key = (self.cur, round(s.size[0] * scale), round(s.size[1] * scale))
        ph = self._img_cache.get(key)
        if ph is None:
            img = Image.open(__import__("io").BytesIO(s.png)).resize((max(1, key[1]), max(1, key[2])), Image.LANCZOS)
            ph = self._img_cache[key] = ImageTk.PhotoImage(img)
        c.create_image(ox, oy, image=ph, anchor="nw")
        self._geom = (scale, ox, oy)
        if self.hl is not None:
            c.create_rectangle(*to_canvas(self.hl.bbox, s.size, scale, ox, oy), outline=PALETTES[self.theme]["hl"], width=3)

    def _mark_line(self, line: int | None) -> None:
        self.text.tag_remove("cur", "1.0", "end")
        if line is not None:
            self.text.tag_add("cur", f"{line + 1}.0", f"{line + 1}.end+1c")

    def on_text_click(self, _e=None) -> None:
        self.on_text_key()

    def on_text_key(self, _e=None) -> None:
        if not self.deck:
            return
        self._store_edit()
        self.update_status()
        line = int(self.text.index("insert").split(".")[0]) - 1
        self.hl = self.deck.item_for_line(self.cur, line)
        self._mark_line(line if self.hl is not None else None)
        self.redraw()

    def on_canvas_click(self, e) -> None:
        if not self.deck or not hasattr(self, "_geom"):
            return
        s = self.deck.slides[self.cur]
        scale, ox, oy = self._geom
        x, y = (e.x - ox) / (s.size[0] * scale), (e.y - oy) / (s.size[1] * scale)
        line = self.deck.line_for_point(self.cur, x, y)
        self.hl = self.deck.item_for_line(self.cur, line) if line is not None else None
        self._mark_line(line)
        if line is not None:
            self.text.see(f"{line + 1}.0")
        self.redraw()

    # ------------------------------------------------------------------ output
    def save(self) -> None:
        if not self.deck:
            return
        self._store_edit()
        path = filedialog.asksaveasfilename(defaultextension=".md", initialfile=self.deck.suggested_name(),
                                            filetypes=[("Markdown", "*.md"), ("All files", "*.*")])
        if path:
            Path(path).write_text(self.deck.markdown(), encoding="utf-8")
            self.status.configure(text=f"Saved {path}")

    def copy_all(self) -> None:
        if not self.deck:
            return
        self._store_edit()
        self.root.clipboard_clear()
        self.root.clipboard_append(self.deck.markdown())
        self.status.configure(text=f"Copied all slides (≈ {self.deck.tokens()} tokens) to the clipboard.")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        root = tk.Tk()
    except tk.TclError as e:
        print(f"Cannot open a window: {e}\nOn a server without a display, use the command line or the web app instead.", file=sys.stderr)
        return 1
    App(root, argv[0] if argv else None)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
