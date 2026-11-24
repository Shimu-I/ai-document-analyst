"""HTML for the landing sections of the Home page (hero, formats, features, steps, numbers, call to action).

Written as flat strings without blank lines or indentation, so Streamlit's Markdown renderer keeps them as HTML.
"""
from __future__ import annotations

LANDING_CSS = """
<style>
.lp { --maxw: 1100px; }
.lp a { text-decoration: none !important; }
.lp-hero { display: grid; grid-template-columns: 1.05fr 1fr; gap: 3rem; align-items: center; padding: 2.4rem 0 2.2rem; }
.lp-badge { display: inline-block; font-size: .9rem; font-weight: 600; color: var(--concrete); background: rgba(205,159,160,.28);
            padding: .25rem .8rem; border-radius: 999px; margin-bottom: 1.1rem; }
.lp-hero h1 { font-size: 3rem !important; line-height: 1.1 !important; letter-spacing: -.02em; margin: 0 0 1rem !important; padding: 0 !important; }
.lp-hero p.lead { font-size: 1.2rem; line-height: 1.6; color: var(--ink); margin: 0 0 1.6rem; max-width: 33rem; }
.lp-cta { display: flex; flex-wrap: wrap; gap: .8rem; margin-bottom: 1.1rem; }
.btn { display: inline-block; padding: .8rem 1.5rem; border-radius: 10px; font-weight: 650; font-size: 1.05rem; }
.btn.primary { background: var(--concrete); color: #FBF3EC !important; }
.btn.primary:hover { filter: brightness(1.12); }
.btn.ghost { border: 1.5px solid var(--steel); color: var(--concrete) !important; }
.btn.ghost:hover { background: rgba(133,124,145,.14); }
.lp-note { font-size: .95rem; color: var(--muted); }
.win { border: 1px solid var(--line); border-radius: 14px; background: var(--card); box-shadow: 0 10px 30px rgba(82,88,113,.14); overflow: hidden; }
.win .bar { display: flex; gap: .4rem; padding: .7rem .9rem; border-bottom: 1px solid var(--line); }
.win .bar i { width: .65rem; height: .65rem; border-radius: 50%; background: var(--rose); opacity: .7; }
.win .bar span { margin-left: .6rem; font-size: .85rem; color: var(--muted); }
.win .panes { display: grid; grid-template-columns: 1fr 1fr; }
.win .pane { padding: 1rem 1.1rem 1.2rem; min-height: 13rem; }
.win .pane + .pane { border-left: 1px solid var(--line); }
.win .cap { font-size: .8rem; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; color: var(--steel); margin-bottom: .7rem; }
.win .slide { background: #FFFDFB; border-radius: 8px; padding: .9rem 1rem; color: #1d1d1d; font-weight: 700; font-size: 1.02rem; line-height: 1.75; border: 1px solid rgba(0,0,0,.06); }
.win .slide small { display: block; font-weight: 700; font-size: 1.02rem; padding-left: 1.4rem; }
.win pre { margin: 0; font-family: ui-monospace, Menlo, Consolas, monospace; font-size: .92rem; line-height: 1.75; color: var(--ink); white-space: pre-wrap; background: none; padding: 0; }
.win .tags { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .9rem; }
.win .tags span { font-size: .8rem; padding: .15rem .6rem; border-radius: 999px; background: rgba(205,159,160,.28); color: var(--concrete); }
.lp-formats { text-align: center; color: var(--muted); font-size: 1rem; padding: 1.1rem 0 .4rem; border-top: 1px solid var(--line); }
.lp-formats b { color: var(--concrete); font-weight: 650; margin: 0 .35rem; }
.lp-sec { padding: 3.2rem 0 0; }
.lp-sec .kick { font-size: .9rem; font-weight: 650; letter-spacing: .1em; text-transform: uppercase; color: var(--steel); }
.lp-sec h2 { font-size: 2rem !important; margin: .3rem 0 .6rem !important; padding: 0 !important; }
.lp-sec .sub { font-size: 1.1rem; color: var(--muted); max-width: 40rem; margin-bottom: 1.6rem; }
.fgrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0; border-top: 1px solid var(--line); }
.fitem { padding: 1.4rem 1.5rem 1.5rem 0; border-bottom: 1px solid var(--line); }
.fitem + .fitem { }
.fitem .ic { width: 2.1rem; height: 2.1rem; border-radius: 9px; display: flex; align-items: center; justify-content: center; font-weight: 700;
             color: var(--concrete); background: var(--peach); margin-bottom: .8rem; }
.fitem h3 { font-size: 1.2rem !important; margin: 0 0 .35rem !important; padding: 0 !important; }
.fitem p { margin: 0; font-size: 1rem; color: var(--ink); opacity: .9; }
.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 2rem; counter-reset: s; }
.step { position: relative; padding-top: 3.2rem; }
.step::before { counter-increment: s; content: counter(s); position: absolute; top: 0; left: 0; width: 2.4rem; height: 2.4rem; border-radius: 50%;
                background: var(--concrete); color: #FBF3EC; display: flex; align-items: center; justify-content: center; font-weight: 700; }
.step::after { content: ""; position: absolute; top: 1.2rem; left: 3.2rem; right: -1rem; border-top: 2px dashed var(--line); }
.step:last-child::after { display: none; }
.step h3 { font-size: 1.2rem !important; margin: 0 0 .3rem !important; padding: 0 !important; }
.step p { margin: 0; font-size: 1rem; }
.band { margin-top: 3.2rem; background: var(--concrete); border-radius: 16px; padding: 2.2rem 2rem; display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }
.band .n { font-size: 2.4rem; font-weight: 750; color: #F8CCAA; line-height: 1.1; }
.band .l { font-size: .98rem; color: #EADFD6; margin-top: .3rem; }
.band-note { font-size: .9rem; color: var(--muted); margin-top: .7rem; }
.endcta { margin-top: 3.2rem; text-align: center; padding: 2.4rem 1rem; border-radius: 16px; background: rgba(248,204,170,.45); }
.endcta h2 { font-size: 1.85rem !important; margin: 0 0 .4rem !important; padding: 0 !important; }
.endcta p { font-size: 1.1rem; margin: 0 0 1.3rem; }
@media (max-width: 900px) {
  .lp-hero { grid-template-columns: 1fr; gap: 1.8rem; padding-top: 1.2rem; }
  .lp-hero h1 { font-size: 2.3rem !important; }
  .fgrid { grid-template-columns: 1fr 1fr; }
  .steps { grid-template-columns: 1fr; gap: 1.4rem; } .step::after { display: none; }
  .band { grid-template-columns: 1fr; }
}
@media (max-width: 560px) {
  .lp-hero h1 { font-size: 1.9rem !important; } .lp-hero p.lead { font-size: 1.08rem; }
  .fgrid { grid-template-columns: 1fr; } .fitem { padding-right: 0; }
  .win .panes { grid-template-columns: 1fr; } .win .pane + .pane { border-left: 0; border-top: 1px solid var(--line); }
  .lp-sec h2 { font-size: 1.6rem !important; }
}
</style>
"""


def hero() -> str:
    return ('<div class="lp"><div class="lp-hero"><div>'
            '<span class="lp-badge">Free · runs on this computer</span>'
            '<h1>Turn any document into clean Markdown for AI chats</h1>'
            '<p class="lead">Drop in a PDF, slide deck, spreadsheet, scan or screenshot. Get back the text with its tables, '
            'equations and layout kept, in far fewer tokens than the original file.</p>'
            '<div class="lp-cta"><a class="btn primary" target="_self" href="/convert">Open the app</a>'
            '<a class="btn ghost" target="_self" href="/guide">Read the guide</a></div>'
            '<div class="lp-note">No account, no upload to other services, no API key.</div></div>'
            '<div class="win"><div class="bar"><i></i><i></i><i></i><span>slides.pptx → slides.md</span></div>'
            '<div class="panes"><div class="pane"><div class="cap">Slide (a picture)</div>'
            '<div class="slide">• Development Methodologies<br>• Agile Development<br>• Extreme Programming (XP)'
            '<small>• How It Works for Me?</small>• Develop Your Own Methodology</div></div>'
            '<div class="pane"><div class="cap">Markdown</div>'
            '<pre>- Development Methodologies\n- Agile Development\n- Extreme Programming (XP)\n  - How It Works for Me?\n- Develop Your Own Methodology</pre>'
            '<div class="tags"><span>Text from the picture</span><span>Bullets kept</span><span>Nesting kept</span></div></div>'
            '</div></div></div>'
            '<div class="lp-formats">Works with <b>PDF</b> · <b>Word</b> · <b>Excel</b> · <b>PowerPoint</b> · <b>Images</b> · '
            '<b>JSON</b> · <b>HTML</b> · <b>Notebooks</b> · <b>Code</b></div></div>')


FEATURES = [
    ("T", "Tables stay tables", "Tables in PDFs, Word, PowerPoint and spreadsheets become Markdown tables."),
    ("∑", "Equations kept", "Word equations become LaTeX. PDF equations are saved as images with their text."),
    ("▦", "Diagrams and figures", "Charts and diagrams are saved as image files and linked, with their labels as text."),
    ("Aa", "Slides that are pictures", "Text inside pictures is read with OCR and keeps its bullets and indentation."),
    ("−", "Fewer tokens", "Compact mode trims padding, and long files can be split into parts of a chosen size."),
    ("✓", "Honest summary", "A document type and short summary built only from sentences already in the file."),
]
STEPS = [("Add files", "Drop one or more files on the Convert page."),
         ("Choose options", "Keep images, compact mode, optional split size. The defaults suit most files."),
         ("Download", "Take the .md file, or a .zip with images, and paste it into a chat.")]


def features() -> str:
    items = "".join(f'<div class="fitem"><div class="ic">{ic}</div><h3>{h}</h3><p>{p}</p></div>' for ic, h, p in FEATURES)
    return ('<div class="lp"><div class="lp-sec"><div id="features" class="anchor"></div><div class="kick">Features</div>'
            '<h2>What it does</h2><div class="sub">Built to keep what matters in a document and drop what only costs tokens.</div>'
            f'<div class="fgrid">{items}</div></div></div>')


def steps() -> str:
    items = "".join(f'<div class="step"><h3>{h}</h3><p>{p}</p></div>' for h, p in STEPS)
    return ('<div class="lp"><div class="lp-sec"><div id="how" class="anchor"></div><div class="kick">How it works</div>'
            f'<h2>Three steps</h2><div class="steps">{items}</div></div></div>')


def numbers() -> str:
    cells = [("100%", "reading order on 3 sample PDFs (comparison tool: 52% to 93%)"),
             ("−49%", "estimated tokens for a 40-record JSON file against minified JSON"),
             ("99%", "word recall on a clean scanned sample page")]
    inner = "".join(f'<div><div class="n">{n}</div><div class="l">{l}</div></div>' for n, l in cells)
    return ('<div class="lp"><div class="band">' + inner + '</div>'
            '<div class="band-note">Measured on small generated sample files. Real documents vary; the Technical information section lists the method and limits.</div></div>')


def about() -> str:
    return ('<div class="lp"><div class="lp-sec"><div id="about" class="anchor"></div><div class="kick">About</div>'
            '<h2>Why this exists</h2><div class="sub">AI chats count and limit tokens. Documents waste many of them on repeated page headers, '
            'layout noise and padded tables, and asking a chatbot to convert a file spends more tokens and sends the file to a third party. '
            'This tool converts once, on this computer, keeps the text, tables, equations and diagrams, and lists everything it could not carry over.</div></div></div>')


def end_cta() -> str:
    return ('<div class="lp"><div class="endcta"><h2>Ready to try it?</h2><p>Convert a file now. It takes a few seconds for most documents.</p>'
            '<a class="btn primary" target="_self" href="/convert">Open the app</a></div></div>')
