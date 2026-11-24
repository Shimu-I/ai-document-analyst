"""Runs the desktop window code against a stand-in for tkinter (the real one is not installed in the build
environment), to catch typos, wrong calls and broken logic in the window code. It does not draw anything."""
import io
import sys
import types
import unittest
from unittest import mock

from tests.test_picture_ocr import HAVE_TESSERACT, slide_png


class FakeWidget:
    def __init__(self, *a, **k):
        self.kids, self.opts, self.calls, self.content, self.tags = [], dict(k), [], "", {}
        master = a[0] if a else None
        if isinstance(master, FakeWidget):
            master.kids.append(self)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def f(*a, **k):
            self.calls.append((name, a, k))
            return None
        return f

    def configure(self, **k):
        self.opts.update(k)
    config = configure

    def cget(self, k):
        return self.opts.get(k, "")

    def winfo_width(self):
        return 800

    def winfo_height(self):
        return 600

    def winfo_children(self):
        return list(self.kids)

    def destroy(self):
        pass

    # Text
    def insert(self, idx, s):
        self.content += s

    def delete(self, a, b=None):
        self.content = ""

    def get(self, a=None, b=None):
        return self.content

    def index(self, what):
        return self.opts.get("_insert", "1.0")

    # Tk
    def after(self, ms, fn=None):
        return None

    def bind(self, *a, **k):
        pass


class FakeVar:
    def __init__(self, value=None):
        self.v = value

    def get(self):
        return self.v

    def set(self, v):
        self.v = v


def fake_modules():
    tk = types.ModuleType("tkinter")
    for n in ("Tk", "Frame", "Label", "Button", "Canvas", "Text", "PanedWindow", "Checkbutton"):
        setattr(tk, n, type(n, (FakeWidget,), {}))
    tk.BooleanVar, tk.StringVar, tk.TclError = FakeVar, FakeVar, type("TclError", (Exception,), {})
    ttk = types.ModuleType("tkinter.ttk")
    for n in ("Combobox", "Progressbar", "Scrollbar"):
        setattr(ttk, n, type(n, (FakeWidget,), {}))
    fd, mb = types.ModuleType("tkinter.filedialog"), types.ModuleType("tkinter.messagebox")
    fd.askopenfilename = lambda **k: ""
    fd.asksaveasfilename = lambda **k: ""
    mb.showerror = lambda *a, **k: None
    tk.ttk, tk.filedialog, tk.messagebox = ttk, fd, mb
    return {"tkinter": tk, "tkinter.ttk": ttk, "tkinter.filedialog": fd, "tkinter.messagebox": mb}


class FakePhotoImage:
    def __init__(self, img=None, *a, **k):
        self.img = img


@unittest.skipUnless(HAVE_TESSERACT, "tesseract is not installed")
class DesktopSmokeTests(unittest.TestCase):
    def setUp(self):
        self.patch = mock.patch.dict(sys.modules, fake_modules())
        self.patch.start()
        sys.modules.pop("app.desktop", None)
        import importlib
        self.mod = importlib.import_module("app.desktop")
        self.mod.ImageTk = types.SimpleNamespace(PhotoImage=FakePhotoImage)

    def tearDown(self):
        sys.modules.pop("app.desktop", None)
        self.patch.stop()

    def _app_with_slide(self):
        from src.slides import read_slides
        app = self.mod.App(self.mod.tk.Tk())
        app.load("talk.png", read_slides(slide_png(), "talk.png"))
        return app

    def test_load_select_and_linked_clicks(self):
        app = self._app_with_slide()
        self.assertEqual(len(app.thumbs), 1)
        self.assertIn("business needs", app.text.content)
        self.assertFalse(app.deck.edited(0))                  # loading must not count as an edit
        self.assertIn("tokens", app.total.opts["text"])
        # click on the text: line 1 is linked to a place on the slide
        app.text.opts["_insert"] = "1.3"
        app.on_text_click()
        self.assertIsNotNone(app.hl)
        # click on the slide, inside the first line's box: that line is selected
        s = app.deck.slides[0]
        x0, y0, x1, y1 = app.hl.bbox
        scale, ox, oy = app._geom
        ev = types.SimpleNamespace(x=ox + (x0 + x1) / 2 * s.size[0] * scale, y=oy + (y0 + y1) / 2 * s.size[1] * scale)
        app.hl = None
        app.on_canvas_click(ev)
        self.assertIsNotNone(app.hl)

    def test_edit_theme_view_and_save(self):
        app = self._app_with_slide()
        app.text.content = "- Edited line"
        app._store_edit()
        self.assertTrue(app.deck.edited(0))
        app.update_status()
        self.assertIn("edited", app.status.opts["text"])
        app.toggle_theme()
        self.assertEqual(app.theme, "dim")
        app.show_original.set(False)
        app.toggle_original()
        saved = {}
        self.mod.filedialog.asksaveasfilename = lambda **k: "/tmp/_desk_test.md"
        app.save()
        with open("/tmp/_desk_test.md", encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("- Edited line", text)
        self.assertIn("## Slide 1", text)

    def test_error_from_worker_is_reported(self):
        app = self.mod.App(self.mod.tk.Tk())
        shown = []
        self.mod.messagebox.showerror = lambda *a, **k: shown.append(a)
        app.q.put(("err", "the file is empty", None))
        app._poll()
        self.assertTrue(shown)
        self.assertEqual(app.btn_open.opts["state"], "normal")


if __name__ == "__main__":
    unittest.main()
