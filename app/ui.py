"""Shared look and small helpers for every page of the web app."""
from __future__ import annotations

import re

import streamlit as st

CSS = """
<style>
/* palette: Concrete #525871 · Warm Steel #857C91 · Rosewood #CD9FA0 · Peaches & Cream #F2C1A3 · Dawn #F8CCAA */
:root { --concrete:#525871; --steel:#857C91; --rose:#CD9FA0; --peach:#F2C1A3; --dawn:#F8CCAA;
        --ink:#3E4358; --muted:#6E667B; --line:rgba(82,88,113,.16); --card:#F8EBDF; --bg:#F1E3D6; --drop:#F4E5D7;
        --solid:#525871; --on-solid:#FBF3EC; --solid-hover:#444A63; --band:#525871; }
/* no sidebar anywhere: navigation is the top bar */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display:none !important; }
.block-container, [data-testid="stMainBlockContainer"] { max-width: 1180px !important; width: 100%; margin-left: auto !important; margin-right: auto !important; padding-top: 1.2rem; padding-bottom: 3rem; }
html, body, [class*="st-"] { -webkit-font-smoothing: antialiased; }
/* type scale: body 16px, page title 36px, section heading 30px, sub-heading 20px, hero 44px */
html { font-size: 16px; }
.stApp, .stApp p, .stApp li, .stApp label, [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { font-size: 1rem; }
h1 { font-size: 2.25rem !important; font-weight: 700 !important; color: var(--concrete); letter-spacing: -0.015em; line-height: 1.15 !important; padding: .3rem 0 .4rem !important; }
h2 { font-size: 1.85rem !important; font-weight: 680 !important; color: var(--concrete); line-height: 1.2 !important; }
h3 { font-size: 1.25rem !important; font-weight: 650 !important; color: var(--concrete); }
p, li { line-height: 1.65; }
[data-testid="stCaptionContainer"] { color: var(--muted); font-size: .94rem !important; }
[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 680; color: var(--concrete); }
[data-testid="stMetricLabel"] p { font-size: .94rem !important; color: var(--muted); }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; border-color: var(--line); background: var(--card); }
.stButton > button, .stDownloadButton > button { border-radius: 9px; padding: .45rem 1.1rem; font-weight: 550; border-color: var(--line); }
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] { background: var(--solid); border-color: var(--solid); color: var(--on-solid); }
.stButton > button[kind="primary"]:hover { background: var(--solid-hover); border-color: var(--solid-hover); color: var(--on-solid); }
[data-testid="stFileUploaderDropzone"] { border-radius: 10px; background: var(--drop); border: 1.5px dashed var(--steel); }
[data-testid="stTabs"] button p { font-size: .98rem; }
/* top bar */
.brand { font-size: 1.05rem; font-weight: 650; color: var(--concrete); }
.brand span { display:inline-block; width:.8rem; height:.8rem; border-radius:3px; margin-right:.5rem;
              background: linear-gradient(135deg, var(--rose), var(--peach)); }
[data-testid="stPageLink"] a { border-radius: 8px; padding: .35rem .6rem; font-size: 1rem; white-space: nowrap; color: var(--ink); justify-content: center; }
[data-testid="stPageLink"] a:hover { background: rgba(82,88,113,.08); }
[data-testid="stPageLink"] a[aria-current="page"] { background: rgba(205,159,160,.28); color: var(--concrete); font-weight: 650; }
.topline { border: 0; border-top: 1px solid var(--line); margin: .5rem 0 1.4rem; }
/* home */
.hero { padding: 2.6rem 2rem 2.2rem; border-radius: 16px; background: linear-gradient(160deg, rgba(248,204,170,.55), rgba(205,159,160,.28)); }
.hero .eyebrow { font-size: .85rem; letter-spacing: .12em; text-transform: uppercase; color: var(--concrete); font-weight: 650; opacity:.8; }
.hero h1 { font-size: 2.75rem !important; line-height: 1.12; margin: .4rem 0 .7rem; padding: 0; }
.hero p { font-size: 1.15rem; max-width: 40rem; margin: 0; color: var(--ink); }
.palette { display:flex; height: 6px; border-radius: 6px; overflow:hidden; margin: 1.1rem 0 0; max-width: 16rem; }
.palette i { flex:1; }
.sec { margin-top: 2.6rem; }
.sec .kicker { font-size: .85rem; letter-spacing: .12em; text-transform: uppercase; color: var(--steel); font-weight: 650; }
.sec h2 { margin: .1rem 0 .3rem; padding: 0; }
.feat { font-size: 1rem; color: var(--ink); }
.feat b { color: var(--concrete); font-size: 1.1rem; }
.chip { display: inline-block; padding: .12rem .65rem; margin: .15rem .1rem; border-radius: 999px; background: rgba(205,159,160,.25);
        color: #5B4659; font-size: .9rem; }
.stat { font-size: 1.9rem; font-weight: 700; color: var(--concrete); line-height: 1.1; }
.stat small { display:block; font-size: .85rem; font-weight: 400; color: var(--muted); margin-top: .25rem; }
.step-no { display:inline-flex; width:1.7rem; height:1.7rem; border-radius:50%; align-items:center; justify-content:center;
           background: var(--peach); color: var(--concrete); font-weight: 700; font-size:.9rem; margin-bottom:.4rem; }
.stbadge { display:inline-block; padding:.18rem .7rem; border-radius:999px; font-size:.8rem; font-weight:600; white-space:nowrap;
           border:1px solid var(--line); color:var(--concrete); background:rgba(133,124,145,.16); }
.stbadge::before { content:""; display:inline-block; width:.5rem; height:.5rem; border-radius:50%; margin-right:.45rem; background:var(--steel); }
.stbadge.ok { background:rgba(110,160,120,.2); } .stbadge.ok::before { background:#5E9A6E; }
.stbadge.warn { background:rgba(224,170,90,.22); } .stbadge.warn::before { background:#D69A3C; }
.stbadge.bad { background:rgba(200,110,110,.2); } .stbadge.bad::before { background:#C25B5B; }
.foot { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .94rem; }
/* top bar: one row; items centred on one line; the last two items (app button, theme switch) sit at the right */
.st-key-topbar, .st-key-topbar * { overflow: visible !important; }
.st-key-topbar [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: .25rem .3rem; align-items: center !important; }
@media (min-width: 1100px) { .st-key-topbar [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; } }
.st-key-topbar [data-testid="stColumn"] { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; align-self: center !important; padding: 0 !important; }
.st-key-topbar [data-testid="stVerticalBlock"], .st-key-topbar [data-testid="stElementContainer"], .st-key-topbar [data-testid="stMarkdownContainer"],
.st-key-topbar [data-testid="stPageLink"] { margin: 0 !important; gap: 0 !important; padding-top: 0 !important; padding-bottom: 0 !important; }
.st-key-topbar [data-testid="stMarkdownContainer"] p, .st-key-topbar a p { margin: 0 !important; line-height: 1.2 !important; }
.st-key-topbar .brand, .st-key-topbar .chipwrap { padding: 0; display: flex; align-items: center; min-height: 2.4rem; }
.st-key-topbar [data-testid="stColumn"] a { display: inline-flex !important; align-items: center; min-height: 2.4rem; padding: 0 .6rem !important; white-space: nowrap; }
.st-key-topbar [data-testid="stColumn"] button { min-height: 2.4rem; padding: 0 .7rem; white-space: nowrap; }
.st-key-topbar [data-testid="stColumn"]:nth-last-child(2) { margin-left: auto; }
.st-key-topbar [data-testid="stColumn"]:nth-last-child(2) a { background: var(--solid); font-weight: 650; }
.st-key-topbar [data-testid="stColumn"]:nth-last-child(2) a, .st-key-topbar [data-testid="stColumn"]:nth-last-child(2) a * { color: var(--on-solid) !important; }
.st-key-topbar [data-testid="stColumn"]:nth-last-child(2) a:hover { background: var(--solid-hover); }
.navlink { display: inline-flex; align-items: center; min-height: 2.4rem; padding: 0 .6rem; border-radius: 8px; color: var(--ink) !important; text-decoration: none !important;
           font-size: 1rem; white-space: nowrap; }
.navlink:hover { background: rgba(82,88,113,.08); }
/* tablet and phone */
@media (max-width: 900px) {
  .block-container { padding-left: 1rem; padding-right: 1rem; }
  h1 { font-size: 1.9rem !important; } h2 { font-size: 1.55rem !important; }
  .hero { padding: 1.8rem 1.2rem; } .hero h1 { font-size: 2.1rem !important; }
}
@media (max-width: 560px) {
  h1 { font-size: 1.65rem !important; } h2 { font-size: 1.4rem !important; }
  .hero h1 { font-size: 1.8rem !important; } .hero p { font-size: 1.05rem; }
  .stat { font-size: 1.6rem; }
}
.doc-group { font-size: .85rem; font-weight: 650; letter-spacing: .1em; text-transform: uppercase; color: var(--steel); margin: 1rem 0 .3rem; }
.anchor { position: relative; top: -70px; visibility: hidden; height: 0; }
</style>
"""


# Dim mode: darker surfaces for low light, same palette. Streamlit's own widgets get their colours from the theme
# file, so the main surfaces and widgets are overridden here.
DIM_CSS = """
<style>
:root { --concrete:#F2C1A3; --steel:#B6ADC2; --ink:#EADFD6; --muted:#B9B0C4; --line:rgba(242,193,163,.20);
        --card:#363B4F; --bg:#2A2E3E; --drop:#32374A;
        --solid:#F2C1A3; --on-solid:#2A2E3E; --solid-hover:#F8CCAA; --band:#3A4056; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background: var(--bg) !important; color: var(--ink); }
.stApp p, .stApp li, .stApp label, .stApp span, .stApp small, .stApp td, .stApp th,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] p, [data-testid="stCaptionContainer"] { color: var(--ink); }
h1, h2, h3, h4 { color: #F8CCAA !important; }
[data-baseweb="input"] > div, [data-baseweb="select"] > div, [data-baseweb="textarea"], textarea, input
  { background: #2F3447 !important; color: var(--ink) !important; border-color: var(--line) !important; }
[data-testid="stExpander"] details, [data-testid="stTable"], [data-testid="stDataFrame"] { background: var(--card); border-color: var(--line); }
.stButton > button, .stDownloadButton > button { background: var(--card); color: var(--ink); border-color: var(--line); }
.hero { background: linear-gradient(160deg, rgba(205,159,160,.28), rgba(133,124,145,.25)); }
.hero p, .feat, .stat { color: var(--ink); } .feat b, .stat { color: #F8CCAA; }
.chip { background: rgba(205,159,160,.22); color: #F3DCD0; }
.endcta { background: rgba(205,159,160,.16) !important; }
.lp-badge, .win .tags span { color: #F8CCAA !important; }
.step-no { background: var(--solid); color: var(--on-solid); }
[data-testid="stPageLink"] a { color: var(--ink); } [data-testid="stPageLink"] a:hover { background: rgba(242,193,163,.12); }
[data-testid="stPageLink"] a[aria-current="page"] { background: rgba(205,159,160,.30); color:#F8CCAA; }
[data-testid="stTabs"] button p { color: var(--ink); }
[data-testid="stMetricValue"] { color:#F8CCAA; }
code { background: rgba(0,0,0,.25) !important; color:#F3DCD0 !important; }
</style>
"""


def dim() -> bool:
    return st.session_state.get("dim", st.query_params.get("theme") == "dim")


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    # backgrounds: soft instead of bright white
    st.markdown("<style>.stApp, [data-testid='stAppViewContainer'], [data-testid='stHeader'] { background: var(--bg); }</style>",
                unsafe_allow_html=True)
    if dim():
        st.markdown(DIM_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=60, show_spinner=False)
def _status() -> dict:
    from src.model_status import model_status
    return model_status()


def status_chip() -> str:
    s = _status()
    return f'<span class="stbadge {s["level"]}" title="{s["detail"]}">{s["label"]}</span>'


def topbar(current: str) -> None:
    """Brand, status chip and page links on one wrapping row; the app button and theme switch at the right.
    ``st.page_link`` needs the pages registered first (``st.navigation`` runs before this). Features, How it
    works and About are in-page links on the Home page."""
    home = current == "Home"
    pre = "" if home else "/"
    with st.container(key="topbar"):
        c = st.columns(11)
        c[0].markdown('<div class="brand"><span></span>Document Analyst</div>', unsafe_allow_html=True)
        c[1].markdown('<div class="chipwrap">' + status_chip() + '</div>', unsafe_allow_html=True)
        c[2].page_link("views/home.py", label="Home")
        for col, (anchor, label) in zip(c[3:6], [("features", "Features"), ("how", "How it works"), ("about", "About")]):
            col.markdown(f'<a class="navlink" target="_self" href="{pre}#{anchor}">{label}</a>', unsafe_allow_html=True)
        c[6].page_link("views/guide.py", label="User guide")
        c[7].page_link("views/dashboard.py", label="Dashboard")
        c[8].page_link("views/docs.py", label="Docs")
        c[9].page_link("views/convert.py", label="Open the app")
        if c[10].button("☀" if dim() else "☾", key="theme_toggle", help="Switch between soft light and dim mode (currently " + ("dim" if dim() else "light") + ")"):
            st.session_state["dim"] = not dim()
            st.rerun()
    st.markdown('<hr class="topline">', unsafe_allow_html=True)


def page_title(title: str, subtitle: str = "") -> None:
    st.title(title)
    if subtitle:
        st.caption(subtitle)


def chips(items) -> None:
    st.markdown("".join(f'<span class="chip">{i}</span>' for i in items), unsafe_allow_html=True)


def render_markdown(md: str, assets: dict[str, bytes], limit: int = 200_000, show_original: bool = False) -> None:
    """Rendered preview. A picture that has text read from it is shown as that text only; with
    ``show_original`` the picture appears beside its text. Pictures with no text of their own (diagrams,
    equations) are always shown. Images come from memory, because a plain link to ``assets/...`` would not
    resolve in the browser."""
    from src.preview import split_blocks
    for blk in split_blocks(md[:limit], assets):
        if blk[0] == "md":
            st.markdown(blk[1])
            continue
        _, alt, name, text = blk
        if not text:
            st.image(assets[name], caption=alt)
        elif show_original:
            left, right = st.columns(2)
            left.image(assets[name], caption="Original")
            right.markdown(text)
        else:
            st.markdown(text)


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def human_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f} s"
    m, s = divmod(int(round(seconds)), 60)
    return f"{m} min {s:02d} s" if m < 60 else f"{m // 60} h {m % 60:02d} min"
