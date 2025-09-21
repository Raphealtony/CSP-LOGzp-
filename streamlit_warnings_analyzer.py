
import io
from datetime import datetime
import streamlit as st, pandas as pd, matplotlib.pyplot as plt

st.set_page_config(page_title="Warnings Analyzer (Web)", layout="wide")

def parse(ts):
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except Exception:
            pass
    return pd.to_datetime(ts, errors="coerce")

st.header("Warnings Analyzer — Web")
up = st.file_uploader("上傳 WarningsLog.txt / CSV / TXT（無表頭）", type=["txt","csv"])
if up:
    df = pd.read_csv(up, header=None, dtype=str)
    cols = ["Timestamp","Code","Status","Subsystem","Category","Detail1","Message"]
    df.columns = cols[:df.shape[1]]
    df["Timestamp"] = df["Timestamp"].apply(parse)
    df = df.dropna(subset=["Timestamp"]).copy()
    df["Minute"] = df["Timestamp"].dt.floor("min")
    mins = df["Minute"].sort_values().drop_duplicates()
    s,e = st.slider("時間範圍（分鐘）", min_value=mins.iloc[0].to_pydatetime(), max_value=mins.iloc[-1].to_pydatetime(), value=(mins.iloc[0].to_pydatetime(), mins.iloc[-1].to_pydatetime()), step=pd.Timedelta(minutes=1))
    m = (df["Timestamp"]>=s)&(df["Timestamp"]<=e)
    q = df.loc[m]
    st.caption(f"筆數：{len(q)}")
    cp = q.groupby("Minute").size()
    fig = plt.figure(figsize=(10,5)); ax = fig.gca()
    ax.plot(cp.index, cp.values, marker="o"); ax.grid(True)
    st.pyplot(fig)
