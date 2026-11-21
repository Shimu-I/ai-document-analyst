"""Shared test helpers: sample files and small generated documents."""
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "samples"


def sample(name: str) -> bytes:
    return (SAMPLES / name).read_bytes()


def rotated_pdf() -> bytes:
    """One page with normal text, a vertical margin stamp, an upside-down line and a diagonal watermark."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    c.setFont("Helvetica", 11)
    c.drawString(72, 780, "Normal first line of the page with several words in it.")
    c.drawString(72, 764, "Second normal line follows right below it.")
    c.saveState(); c.translate(30, 300); c.rotate(90)
    c.drawString(0, 0, "arXiv:2406.01234v1 [cs.SE] 19 Jun 2024"); c.restoreState()
    c.saveState(); c.translate(400, 500); c.rotate(180)
    c.drawString(0, 0, "Upside down sentence here"); c.restoreState()
    c.saveState(); c.translate(150, 200); c.rotate(45); c.setFont("Helvetica", 40)
    c.drawString(0, 0, "DRAFT"); c.restoreState()
    c.showPage(); c.save()
    return b.getvalue()
