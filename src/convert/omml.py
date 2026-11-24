"""Word equations (Office Math, OMML) -> LaTeX text.

Word stores an equation as a tree of ``m:`` elements (fraction, superscript, radical, n-ary operator...).
Each element maps to a LaTeX construct; unknown elements fall back to the text of their children, so an
equation is never lost, only less pretty.
"""
from __future__ import annotations

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"

SYMBOLS = {
    "α": r"\alpha ", "β": r"\beta ", "γ": r"\gamma ", "δ": r"\delta ", "ε": r"\epsilon ", "ζ": r"\zeta ",
    "η": r"\eta ", "θ": r"\theta ", "ι": r"\iota ", "κ": r"\kappa ", "λ": r"\lambda ", "μ": r"\mu ",
    "ν": r"\nu ", "ξ": r"\xi ", "π": r"\pi ", "ρ": r"\rho ", "σ": r"\sigma ", "τ": r"\tau ", "υ": r"\upsilon ",
    "φ": r"\phi ", "χ": r"\chi ", "ψ": r"\psi ", "ω": r"\omega ", "Γ": r"\Gamma ", "Δ": r"\Delta ",
    "Θ": r"\Theta ", "Λ": r"\Lambda ", "Ξ": r"\Xi ", "Π": r"\Pi ", "Σ": r"\Sigma ", "Φ": r"\Phi ",
    "Ψ": r"\Psi ", "Ω": r"\Omega ", "∑": r"\sum ", "∏": r"\prod ", "∫": r"\int ", "∬": r"\iint ",
    "∮": r"\oint ", "√": r"\sqrt ", "∞": r"\infty ", "∂": r"\partial ", "∇": r"\nabla ", "±": r"\pm ",
    "∓": r"\mp ", "×": r"\times ", "÷": r"\div ", "·": r"\cdot ", "≤": r"\le ", "≥": r"\ge ", "≠": r"\ne ",
    "≈": r"\approx ", "≡": r"\equiv ", "∈": r"\in ", "∉": r"\notin ", "⊂": r"\subset ", "⊆": r"\subseteq ",
    "∪": r"\cup ", "∩": r"\cap ", "→": r"\to ", "←": r"\leftarrow ", "⇒": r"\Rightarrow ",
    "⇔": r"\Leftrightarrow ", "∀": r"\forall ", "∃": r"\exists ", "∅": r"\emptyset ", "∝": r"\propto ",
    "…": r"\ldots ", "⋯": r"\cdots ", "−": "-", "′": "'", "ℝ": r"\mathbb{R}", "ℕ": r"\mathbb{N}",
    "ℤ": r"\mathbb{Z}", "ℚ": r"\mathbb{Q}", "ℂ": r"\mathbb{C}",
}
FUNCTIONS = {"sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "lim", "exp", "max", "min", "sup", "inf",
             "det", "dim", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh", "gcd", "mod"}
ACCENTS = {"̂": r"\hat", "̃": r"\tilde", "̄": r"\bar", "̇": r"\dot", "̈": r"\ddot", "⃗": r"\vec", "^": r"\hat",
           "~": r"\tilde", "¯": r"\bar", "→": r"\vec", "˙": r"\dot"}


def _t(e) -> str:
    return e.tag.rsplit("}", 1)[-1] if isinstance(e.tag, str) else ""


def _child(e, name):
    for c in e:
        if _t(c) == name:
            return c
    return None


def _val(e, name, default=None):
    """Attribute m:val of the property element ``name`` inside e (e.g. m:chr)."""
    if e is None:
        return default
    for c in e.iter():
        if _t(c) == name:
            v = c.get(f"{{{M}}}val")
            return v if v is not None else default
    return default


def _text(s: str) -> str:
    out = []
    for ch in s:
        out.append(SYMBOLS.get(ch, ch))
    return "".join(out)


def _arg(e, name) -> str:
    c = _child(e, name)
    return _seq(c) if c is not None else ""


def _seq(e) -> str:
    return "".join(_node(c) for c in e).strip() if e is not None else ""


def _grp(s: str) -> str:
    return s if len(s) == 1 else "{" + s + "}"


def _node(e) -> str:
    n = _t(e)
    if n == "r":
        txt = "".join(c.text or "" for c in e if _t(c) == "t")
        if _child(e, "rPr") is not None and _val(_child(e, "rPr"), "nor") is not None:
            return r"\text{" + txt + "}"
        if txt in FUNCTIONS:
            return "\\" + txt + " "
        return _text(txt)
    if n == "f":
        kind = _val(_child(e, "fPr"), "type", "bar")
        num, den = _arg(e, "num"), _arg(e, "den")
        if kind == "noBar":
            return r"\binom{" + num + "}{" + den + "}"
        return r"\frac{" + num + "}{" + den + "}"
    if n == "sSup":
        return _grp(_arg(e, "e")) + "^" + _grp(_arg(e, "sup"))
    if n == "sSub":
        return _grp(_arg(e, "e")) + "_" + _grp(_arg(e, "sub"))
    if n == "sSubSup":
        return _grp(_arg(e, "e")) + "_" + _grp(_arg(e, "sub")) + "^" + _grp(_arg(e, "sup"))
    if n == "sPre":
        return "{}_" + _grp(_arg(e, "sub")) + "^" + _grp(_arg(e, "sup")) + _arg(e, "e")
    if n == "rad":
        deg = _arg(e, "deg")
        return (r"\sqrt[" + deg + "]{" if deg else r"\sqrt{") + _arg(e, "e") + "}"
    if n == "nary":
        op = _text(_val(_child(e, "naryPr"), "chr", "∫"))
        sub, sup = _arg(e, "sub"), _arg(e, "sup")
        return op.strip() + ("_" + _grp(sub) if sub else "") + ("^" + _grp(sup) if sup else "") + " " + _arg(e, "e")
    if n == "d":
        pr = _child(e, "dPr")
        beg, end, sep = _val(pr, "begChr", "("), _val(pr, "endChr", ")"), _val(pr, "sepChr", "|")
        inner = f" {sep} ".join(_seq(c) for c in e if _t(c) == "e")
        lb = {"{": r"\{", "": "."}.get(beg, beg)
        rb = {"}": r"\}", "": "."}.get(end, end)
        return r"\left" + lb + " " + inner + r" \right" + rb
    if n == "func":
        name = _arg(e, "fName").strip()
        return (("\\" + name + " ") if name in FUNCTIONS else name + " ") + _arg(e, "e")
    if n == "acc":
        ch = _val(_child(e, "accPr"), "chr", "̂")
        return ACCENTS.get(ch, r"\hat") + "{" + _arg(e, "e") + "}"
    if n == "bar":
        return (r"\underline{" if _val(_child(e, "barPr"), "pos", "top") == "bot" else r"\overline{") \
            + _arg(e, "e") + "}"
    if n in ("limLow", "limUpp"):
        base, lim = _arg(e, "e"), _arg(e, "lim")
        return base + ("_" if n == "limLow" else "^") + _grp(lim)
    if n == "m":
        rows = [" & ".join(_seq(c) for c in r if _t(c) == "e") for r in e if _t(r) == "mr"]
        return r"\begin{matrix} " + r" \\ ".join(rows) + r" \end{matrix}"
    if n == "eqArr":
        rows = [_seq(c) for c in e if _t(c) == "e"]
        return r"\begin{aligned} " + r" \\ ".join(rows) + r" \end{aligned}"
    if n in ("e", "num", "den", "sub", "sup", "deg", "lim", "fName", "oMath", "box", "phant", "groupChr",
             "borderBox"):
        return _seq(e)
    if n.endswith("Pr"):
        return ""
    return _seq(e) or "".join(c.text or "" for c in e.iter() if _t(c) == "t")


def omml_to_latex(elem) -> str:
    """LaTeX source for an ``m:oMath`` element (or the ``m:oMathPara`` that wraps several)."""
    if _t(elem) == "oMathPara":
        return r" \\ ".join(omml_to_latex(c) for c in elem if _t(c) == "oMath")
    s = _seq(elem)
    return " ".join(s.split())
