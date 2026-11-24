"""Documentation: the project documents with a section list, contents, search and previous/next buttons."""
import streamlit as st

import ui
from src import docview

docs = docview.list_docs()
by_key = {d["key"]: d for d in docs}
if st.session_state.get("doc") not in by_key:
    st.session_state["doc"] = docs[0]["key"]


def go(key: str) -> None:
    st.session_state["doc"] = key


ui.page_title("Documentation", "How the project works, how to install and run it, how it was tested, and where it falls short.")
side, main = st.columns([1, 3], gap="large")

# ------------------------------------------------------------------ left: search and section list
with side:
    query = st.text_input("Search the documentation", placeholder="for example: OCR, equations, install",
                          label_visibility="collapsed", key="doc_query")
    if query.strip():
        hits = docview.search(query, docs)
        st.caption(f"{len(hits)} document(s) match" if hits else "No document matches.")
        for h in hits:
            st.button(f"{h['number'] + ' · ' if h['number'] else ''}{h['title']}", key=f"hit_{h['key']}",
                      on_click=go, args=(h["key"],), use_container_width=True, help=h["snippet"])
    else:
        for group in [g for g, _ in docview.GROUPS] + ["Deep dive"]:
            items = [d for d in docs if d["group"] == group]
            if not items:
                continue
            st.markdown(f'<div class="doc-group">{group}</div>', unsafe_allow_html=True)
            for d in items:
                cur = d["key"] == st.session_state["doc"]
                st.button(f"{d['number'] + ' · ' if d['number'] else ''}{d['title']}", key=f"nav_{d['key']}",
                          on_click=go, args=(d["key"],), use_container_width=True,
                          type="primary" if cur else "secondary")

# ------------------------------------------------------------------ right: the document
cur = by_key[st.session_state["doc"]]
md = cur["path"].read_text(encoding="utf-8")
with main:
    heads = docview.toc(md)
    if heads:
        with st.expander("On this page"):
            st.markdown("\n".join(f"{'  ' * (lvl - 2)}- [{text}](#{anchor})" for lvl, text, anchor in heads))
    for blk in docview.split_blocks(md, cur["path"]):
        if blk[0] == "md":
            st.markdown(blk[1])
        elif blk[0] == "img":
            st.image(str(blk[1]), caption=blk[2] or None)
        elif blk[1] is not None:
            st.image(str(blk[1]))
        else:
            st.caption("Diagram (picture not generated; run scripts/make_diagrams.py). Source:")
            st.code(blk[2], language="text")
    order = [d for d in docs if d["number"]]
    if cur["number"]:
        i = order.index(cur)
        st.divider()
        p, n = st.columns(2)
        if i > 0:
            p.button(f"← {order[i - 1]['number']} {order[i - 1]['title']}", key="prev", on_click=go,
                     args=(order[i - 1]["key"],), use_container_width=True)
        if i < len(order) - 1:
            n.button(f"{order[i + 1]['number']} {order[i + 1]['title']} →", key="next", on_click=go,
                     args=(order[i + 1]["key"],), use_container_width=True)
