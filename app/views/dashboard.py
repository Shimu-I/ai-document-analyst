"""Dashboard: history of every conversion, with time spent and document types."""
import pandas as pd
import streamlit as st

import ui
from src import history

ui.page_title("Dashboard", "Every conversion made in this app: when, what type, how long it took.")

try:
    rows = history.fetch()
except Exception as e:
    st.error(f"The history could not be read: {e}")
    rows = []

if not rows:
    with st.container(border=True):
        st.markdown("**No conversions yet.**")
        st.caption("Each file converted on the Convert page is recorded here with its date, type, size and "
                   "processing time. Only names and counts are stored, never the document text.")
        if st.button("Go to Convert", type="primary"):
            st.switch_page("views/convert.py")
    st.stop()

df = pd.DataFrame(rows)
df["ts"] = pd.to_datetime(df["ts"])
df["date"] = df["ts"].dt.date
df["doc_type"] = df["doc_type"].replace("", "(failed)")

# ------------------------------------------------------------------ filters
with st.container(border=True):
    f1, f2, f3 = st.columns(3)
    lo, hi = df["date"].min(), df["date"].max()
    period = f1.date_input("Period", value=(lo, hi), min_value=lo, max_value=hi)
    types = f2.multiselect("Document type", sorted(df["doc_type"].unique()))
    status = f3.selectbox("Status", ["All", "Converted", "Failed"])
if isinstance(period, (tuple, list)) and len(period) == 2:
    df = df[(df["date"] >= period[0]) & (df["date"] <= period[1])]
if types:
    df = df[df["doc_type"].isin(types)]
if status == "Converted":
    df = df[df["ok"] == 1]
elif status == "Failed":
    df = df[df["ok"] == 0]

if df.empty:
    st.info("No conversions match these filters.")
    st.stop()

# ------------------------------------------------------------------ totals
good = df[df["ok"] == 1]
k = st.columns(5)
k[0].metric("Documents", f"{len(df):,}")
k[1].metric("Processing time", ui.human_time(float(df["seconds"].sum())))
k[2].metric("Words converted", f"{int(good['words'].sum()):,}")
k[3].metric("≈ Tokens produced", f"{int(good['tokens'].sum()):,}")
k[4].metric("Success rate", f"{100 * len(good) / len(df):.0f}%")
k2 = st.columns(5)
k2[0].metric("Average time", ui.human_time(float(good["seconds"].mean())) if len(good) else "–")
k2[1].metric("Data processed", ui.human_size(float(df["size_bytes"].sum())))
k2[2].metric("Tables found", f"{int(good['tables'].sum()):,}")
k2[3].metric("Figures saved", f"{int(good['figures'].sum()):,}")
k2[4].metric("Equations kept", f"{int(good['formulas'].sum()):,}")

# ------------------------------------------------------------------ charts
st.write("")
c1, c2 = st.columns(2)
with c1.container(border=True):
    st.markdown("**Documents per day**")
    st.bar_chart(df.groupby("date").size().rename("documents"), color="#525871")
with c2.container(border=True):
    st.markdown("**Processing time per day (seconds)**")
    st.bar_chart(df.groupby("date")["seconds"].sum().rename("seconds"), color="#CD9FA0")
c3, c4 = st.columns(2)
with c3.container(border=True):
    st.markdown("**By document type**")
    st.bar_chart(good.groupby("doc_type").size().rename("documents"), color="#525871") \
        if len(good) else st.caption("Nothing converted yet in this selection.")
with c4.container(border=True):
    st.markdown("**By file format**")
    st.bar_chart(df.groupby("ext").size().rename("documents"), color="#CD9FA0")

# ------------------------------------------------------------------ table
st.write("")
st.subheader("History")
show = df[["ts", "filename", "doc_type", "ext", "size_bytes", "pages", "words", "tokens", "tables", "figures",
           "formulas", "seconds", "ok", "error"]].copy()
show["size"] = show["size_bytes"].map(ui.human_size)
show["status"] = show["ok"].map({1: "Converted", 0: "Failed"})
show = show.rename(columns={"ts": "When", "filename": "File", "doc_type": "Type", "ext": "Format",
                            "pages": "Pages", "words": "Words", "tokens": "≈ Tokens", "tables": "Tables",
                            "figures": "Figures", "formulas": "Equations", "seconds": "Seconds", "error": "Error"})
st.dataframe(show[["When", "File", "Type", "Format", "size", "Pages", "Words", "≈ Tokens", "Tables", "Figures",
                   "Equations", "Seconds", "status", "Error"]],
             use_container_width=True, hide_index=True)

d1, d2, _ = st.columns([1, 1.4, 3])
d1.download_button("⬇️ Export CSV", history.to_csv(rows), file_name="conversion_history.csv", mime="text/csv",
                   use_container_width=True)
with st.expander("Clear history"):
    st.caption("Deletes every record shown here. Converted files are not affected.")
    if st.checkbox("Confirm deletion of the whole history") and st.button("Delete history"):
        n = history.clear()
        st.success(f"Deleted {n} record(s).")
        st.rerun()
