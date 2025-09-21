
import io
import os
import zipfile
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager

st.set_page_config(page_title="Warnings Analyzer (Web)", layout="wide")

APP_TITLE = "Warnings Analyzer — Web (Minute-Level, Subsystem, Time Range)"
DEFAULT_TIME_FMT = "%Y-%m-%d %H:%M:%S"

def use_font(font_path: str):
    """Register a font file and set it as default for matplotlib."""
    try:
        font_manager.fontManager.addfont(font_path)
        prop = font_manager.FontProperties(fname=font_path)
        family_name = prop.get_name()
        plt.rcParams["font.sans-serif"] = [family_name]
        plt.rcParams["axes.unicode_minus"] = False
        return family_name
    except Exception as e:
        return None

def load_cjk_font():
    """Try 3 strategies (in order):
    1) fonts/ directory in repo (e.g., fonts/NotoSansTC-Regular.otf)
    2) built-in system fonts (rare on Streamlit Cloud)
    3) user-uploaded font (via sidebar)
    Returns (family_name, source_str)
    """
    # 1) fonts/ bundled with repo
    fonts_dir = Path(__file__).parent / "fonts"
    if fonts_dir.exists():
        # prefer common Noto names first
        preferred = [
            "NotoSansTC-Regular.otf",
            "NotoSansCJKtc-Regular.otf",
            "NotoSansTC-Regular.ttf",
            "NotoSansCJKtc-Regular.ttf",
        ]
        for name in preferred:
            p = fonts_dir / name
            if p.exists():
                fam = use_font(str(p))
                if fam:
                    return fam, f"bundled: {p.name}"
        # any .otf/.ttf
        for p in fonts_dir.glob("*.[ot]tf"):
            fam = use_font(str(p))
            if fam:
                return fam, f"bundled: {p.name}"

    # 2) system fonts (unlikely on Streamlit Cloud but try)
    candidates = [
        "Microsoft JhengHei", "Microsoft YaHei",
        "Noto Sans CJK TC", "Noto Sans TC", "Noto Sans CJK SC",
        "PingFang TC", "Heiti TC",
        "Arial Unicode MS", "SimHei",
        "WenQuanYi Zen Hei", "DejaVu Sans"
    ]
    available = set(f.name for f in font_manager.fontManager.ttflist)
    for name in candidates:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            plt.rcParams["axes.unicode_minus"] = False
            return name, "system"

    # 3) wait for user upload (handled in sidebar)
    plt.rcParams["axes.unicode_minus"] = False
    return None, None

def sidebar_font_controls():
    st.sidebar.markdown("### 字型設定（修正圖表中文顯示）")
    st.sidebar.write(
        "Cloud 環境通常沒有內建中文字型。請在 repo 的 **`fonts/`** 資料夾放入 "
        "**NotoSansTC-Regular.otf**（或任何 .ttf/.otf CJK 字型），或在下方上傳臨時字型檔。"
    )
    uploaded = st.sidebar.file_uploader("上傳 .otf / .ttf 字型檔（此工作階段有效）", type=["otf", "ttf"])
    if uploaded is not None:
        tmp_path = Path("/tmp") / uploaded.name
        tmp_path.write_bytes(uploaded.getvalue())
        fam = use_font(str(tmp_path))
        if fam:
            st.sidebar.success(f"已套用字型：{fam}")
            st.session_state["_chart_font_family"] = fam
            st.experimental_rerun()
        else:
            st.sidebar.error("字型載入失敗，請換一個檔案試試。")

    if "_chart_font_family" in st.session_state:
        st.sidebar.caption(f"目前字型：{st.session_state['_chart_font_family']}")

def parse_ts(s):
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return pd.to_datetime(s, errors="coerce")

@st.cache_data(show_spinner=False)
def parse_file(file_bytes: bytes, filename_hint: str):
    df = pd.read_csv(io.BytesIO(file_bytes), header=None, dtype=str)
    col_count = df.shape[1]
    if col_count >= 13:
        cols = [
            "Timestamp", "Code", "Status", "Subsystem", "Category",
            "Detail1", "Message", "Flag1", "Detail2",
            "Value1", "Value2", "Value3", "Flag2"
        ]
        df = df.iloc[:, :13]
        df.columns = cols
    else:
        base_cols = ["Timestamp", "Code", "Status", "Subsystem", "Category", "Detail1", "Message"]
        keep = min(col_count, len(base_cols))
        df = df.iloc[:, :keep]
        df.columns = base_cols[:keep]
    df["Timestamp"] = df["Timestamp"].apply(parse_ts)
    df = df.dropna(subset=["Timestamp"]).copy()
    df["Minute"] = df["Timestamp"].dt.floor("min")
    return df

def fig_to_bytes(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

def section_header(title):
    st.markdown(f"### {title}")

def main():
    # Font handling
    if "_chart_font_family" not in st.session_state:
        fam, src = load_cjk_font()
        if fam:
            st.session_state["_chart_font_family"] = fam
    sidebar_font_controls()

    st.markdown(f"# {APP_TITLE}")
    fam = st.session_state.get("_chart_font_family")
    if fam:
        st.caption(f"圖表字型：{fam}")
    else:
        st.warning("尚未偵測到中文字型。請在 repo 的 `fonts/` 放 `NotoSansTC-Regular.otf`，或在左側上傳一個 .otf/.ttf 字型檔。")

    uploaded = st.file_uploader("上傳 WarningsLog.txt / CSV / TXT（無表頭）", type=["txt", "csv"])
    if not uploaded:
        st.info("請先上傳檔案。")
        return

    df = parse_file(uploaded.read(), uploaded.name)
    if df.empty:
        st.error("無有效資料。請確認檔案內容。")
        return

    # Time range slider based on minute granularity
    minutes = df["Minute"].sort_values().drop_duplicates()
    min_t = minutes.iloc[0]
    max_t = minutes.iloc[-1]
    st.write(f"資料時間範圍：**{min_t} ~ {max_t}**，共 **{len(minutes)}** 個分鐘刻度。")

    use_filter = st.checkbox("啟用時間篩選（使用下方滑桿選擇）", value=False)
    sel_start, sel_end = st.slider(
        "選擇時間範圍（以分鐘為單位）",
        min_value=min_t.to_pydatetime(),
        max_value=max_t.to_pydatetime(),
        value=(min_t.to_pydatetime(), max_t.to_pydatetime()),
        step=pd.Timedelta(minutes=1),
        format="YYYY-MM-DD HH:mm",
        disabled=not use_filter,
    )

    if use_filter:
        mask = (df["Timestamp"] >= sel_start) & (df["Timestamp"] <= sel_end)
        dfq = df.loc[mask].copy()
        st.caption(f"篩選後筆數：{len(dfq)}")
        if dfq.empty:
            st.error("此時間範圍內沒有資料，請調整滑桿。")
            return
    else:
        dfq = df

    images = {}  # name -> bytes
    section_header("每分鐘訊息數量統計")
    count_per_minute = dfq.groupby("Minute").size()
    fig1 = plt.figure(figsize=(10,5))
    ax1 = fig1.gca()
    ax1.plot(count_per_minute.index, count_per_minute.values, marker="o")
    ax1.set_title("每分鐘訊息數量統計")
    ax1.set_xlabel("時間 (分鐘)")
    ax1.set_ylabel("訊息數量")
    ax1.grid(True)
    st.pyplot(fig1)
    images["count_per_minute.png"] = fig_to_bytes(fig1).getvalue()

    if "Subsystem" in dfq.columns:
        section_header("每分鐘 × 子系統")
        spm = dfq.groupby(["Minute", "Subsystem"]).size().unstack(fill_value=0)
        fig2 = plt.figure(figsize=(12,6))
        ax2 = fig2.gca()
        for subsystem in spm.columns:
            ax2.plot(spm.index, spm[subsystem], label=subsystem)
        ax2.set_title("每分鐘各子系統訊息數量統計")
        ax2.set_xlabel("時間 (分鐘)")
        ax2.set_ylabel("訊息數量")
        ax2.grid(True)
        ax2.legend(loc="upper right", bbox_to_anchor=(1.25, 1))
        st.pyplot(fig2)
        images["subsystem_per_minute.png"] = fig_to_bytes(fig2).getvalue()

        subsystem_total = dfq["Subsystem"].value_counts()
        topN = st.number_input("Top-N 子系統（預設 5）", min_value=1, max_value=int(min(20, len(subsystem_total))), value=int(min(5, len(subsystem_total))))
        top_list = subsystem_total.head(int(topN)).index
        top_data = dfq[dfq["Subsystem"].isin(top_list)]
        top_per_minute = top_data.groupby(["Minute", "Subsystem"]).size().unstack(fill_value=0)

        section_header(f"前 {len(top_list)} 大子系統 — 每分鐘趨勢")
        fig3 = plt.figure(figsize=(12,6))
        ax3 = fig3.gca()
        for subsystem in top_per_minute.columns:
            ax3.plot(top_per_minute.index, top_per_minute[subsystem], label=subsystem)
        ax3.set_title(f"前 {len(top_list)} 大子系統訊息數量趨勢 (每分鐘)")
        ax3.set_xlabel("時間 (分鐘)")
        ax3.set_ylabel("訊息數量")
        ax3.grid(True)
        ax3.legend(loc="upper right", bbox_to_anchor=(1.25, 1))
        st.pyplot(fig3)
        images["topN_trend.png"] = fig_to_bytes(fig3).getvalue()

        section_header(f"前 {len(top_list)} 大子系統 — 堆疊面積圖")
        fig4 = plt.figure(figsize=(12,6))
        ax4 = fig4.gca()
        ax4.stackplot(top_per_minute.index, top_per_minute.T, labels=top_per_minute.columns)
        ax4.set_title(f"前 {len(top_list)} 大子系統訊息數量堆疊圖 (每分鐘)")
        ax4.set_xlabel("時間 (分鐘)")
        ax4.set_ylabel("訊息數量")
        ax4.grid(True, alpha=0.3)
        ax4.legend(loc="upper right", bbox_to_anchor=(1.25, 1))
        st.pyplot(fig4)
        images["topN_stack.png"] = fig_to_bytes(fig4).getvalue()

        section_header(f"前 {len(top_list)} 大子系統 — 累積曲線")
        cumulative = top_per_minute.cumsum()
        fig5 = plt.figure(figsize=(12,6))
        ax5 = fig5.gca()
        for subsystem in cumulative.columns:
            ax5.plot(cumulative.index, cumulative[subsystem], label=subsystem)
        ax5.set_title(f"前 {len(top_list)} 大子系統累積訊息數量趨勢")
        ax5.set_xlabel("時間 (分鐘)")
        ax5.set_ylabel("累積訊息數量")
        ax5.grid(True)
        ax5.legend(loc="upper left")
        st.pyplot(fig5)
        images["topN_cumsum.png"] = fig_to_bytes(fig5).getvalue()

        # Summary table
        st.markdown("### 統整表")
        peak_time = {}
        peak_value = {}
        for s in spm.columns:
            col = spm[s]
            if col.sum() > 0:
                idxmax = col.idxmax()
                peak_time[s] = idxmax
                peak_value[s] = col.max()
            else:
                peak_time[s] = pd.NaT
                peak_value[s] = 0

        summary = pd.DataFrame({
            "訊息總數": subsystem_total,
            "每分鐘平均訊息數": spm.mean(axis=0) if not spm.empty else pd.Series(dtype=float),
            "子系統峰值時間": pd.Series(peak_time),
            "子系統峰值數量": pd.Series(peak_value),
        })
        st.dataframe(summary)

        # Downloads: CSV and ZIP of images
        csv_buf = io.BytesIO()
        summary.to_csv(csv_buf, encoding="utf-8-sig")
        csv_buf.seek(0)
        st.download_button("下載統整表（CSV）", data=csv_buf, file_name="summary.csv", mime="text/csv")

        if images:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, content in images.items():
                    zf.writestr(name, content)
            zip_buf.seek(0)
            st.download_button("下載所有圖表（ZIP）", data=zip_buf, file_name="charts.zip", mime="application/zip")

    else:
        st.info("此資料不包含 Subsystem 欄位，因此僅顯示每分鐘總數圖。")

if __name__ == "__main__":
    main()
