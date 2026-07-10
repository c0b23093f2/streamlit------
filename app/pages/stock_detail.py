"""
株式銘柄詳細ページ — yfinance 実データ版
- 検索/demo.py から渡された銘柄の情報をダウンロードして data/ フォルダに保存し、表示
- 2回目以降は保存済みデータを再利用（一定時間経過後は自動で再ダウンロード）
- サイドバーのメニューからデモトレード（demo.py）を開ける
- 期間ボタン（1日/3日/1ヶ月/3ヶ月/6ヶ月/1年）でチャートを切替

実行方法（マルチページ構成）:
    demo.py と同じ階層に pages/ フォルダを作り、このファイルを置く
    streamlit run demo.py
"""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

st.set_page_config(page_title="銘柄詳細", page_icon="📊", layout="wide")

UP = "#16c784"
DOWN = "#ea3943"

# 保存先: アプリ直下の data/<ティッカー>/
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# (表示名, 保存キー, yfinance period, interval)
PERIODS = [
    ("1日", "1d", "1d", "5m"),
    ("3日", "3d", "5d", "15m"),
    ("1ヶ月", "1mo", "1mo", "1d"),
    ("3ヶ月", "3mo", "3mo", "1d"),
    ("6ヶ月", "6mo", "6mo", "1d"),
    ("1年", "1y", "1y", "1d"),
]
INTRADAY_KEYS = {"1d", "3d"}


def normalize_jp(code: str) -> str:
    """証券コードを東証ティッカーに正規化。'7203' -> '7203.T'"""
    code = (code or "").upper().strip()
    if not code:
        return ""
    if code.endswith(".T"):
        return code
    return f"{code.replace('.T', '')}.T"


def _fresh(path: Path, ttl: int) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < ttl


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, index_col=0, parse_dates=True)
    except Exception:
        return pd.DataFrame()


def load_or_download_history(ticker: str, key: str, period: str, interval: str) -> tuple[pd.DataFrame, str]:
    """保存済みCSVが新しければ読込、なければyfinanceでDLしてdata/に保存。
    戻り値: (DataFrame, データ源ラベル)"""
    f = DATA_DIR / ticker / f"{key}.csv"
    ttl = 300 if key in INTRADAY_KEYS else 3600  # 日中足5分・日足1時間で更新
    if _fresh(f, ttl):
        df = _read_csv(f)
        if not df.empty:
            return df, "保存済みデータ"

    if yf is None:
        return _read_csv(f), "保存済みデータ（yfinance未導入）"

    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval).dropna()
    except Exception:
        df = pd.DataFrame()

    if df.empty:
        # DL失敗時は古い保存データにフォールバック
        old = _read_csv(f)
        return old, ("保存済みデータ（DL失敗のため）" if not old.empty else "")

    if key == "3d":  # 5日分取得して直近3営業日に絞る
        days = sorted({ts.date() for ts in df.index})[-3:]
        df = df[[ts.date() in days for ts in df.index]]

    f.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(f)
    return df, "ダウンロード（保存済み）"


def load_or_download_info(ticker: str) -> dict:
    """銘柄基本情報をDLしてJSON保存（1日キャッシュ）。"""
    f = DATA_DIR / ticker / "info.json"
    if _fresh(f, 86400):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass

    info = {"name": ticker}
    if yf is not None:
        try:
            raw = yf.Ticker(ticker).info or {}
            info = {
                "name": raw.get("longName") or raw.get("shortName") or ticker,
                "previous_close": raw.get("previousClose"),
                "market_cap": raw.get("marketCap"),
                "per": raw.get("trailingPE"),
                "pbr": raw.get("priceToBook"),
                "dividend_yield": raw.get("dividendYield"),
                "saved_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception:
            pass

    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return info


def load_or_download_news(ticker: str) -> list[dict]:
    """関連ニュースをDLしてJSON保存（30分キャッシュ）。yfinanceの新旧フォーマット両対応。"""
    f = DATA_DIR / ticker / "news.json"
    if _fresh(f, 1800):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass

    items: list[dict] = []
    if yf is not None:
        try:
            for n in (yf.Ticker(ticker).news or [])[:10]:
                c = n.get("content") or {}
                title = n.get("title") or c.get("title")
                link = (n.get("link")
                        or (c.get("canonicalUrl") or {}).get("url")
                        or (c.get("clickThroughUrl") or {}).get("url"))
                pub = n.get("publisher") or (c.get("provider") or {}).get("displayName") or ""
                ts_ = n.get("providerPublishTime")
                if ts_:
                    date = dt.datetime.fromtimestamp(ts_).strftime("%Y-%m-%d %H:%M")
                else:
                    date = str(c.get("pubDate", ""))[:16].replace("T", " ")
                if title:
                    items.append({"title": title, "link": link, "publisher": pub, "date": date})
        except Exception:
            pass

    if items:
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return items
    # DL失敗時は古い保存分にフォールバック
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []


def render_news_tab(ticker: str) -> None:
    news = load_or_download_news(ticker)
    if not news:
        st.info("ニュースを取得できませんでした（Yahoo Financeにニュースがない銘柄もあります）。")
        return
    for n in news:
        meta = "　".join(x for x in (n.get("publisher"), n.get("date")) if x)
        if n.get("link"):
            st.markdown(f"**[{n['title']}]({n['link']})**  \n{meta}")
        else:
            st.markdown(f"**{n['title']}**  \n{meta}")
    st.caption("出典: Yahoo Finance（30分ごとに更新・data/ に保存）")


def render_report_tab(info: dict, df_year: pd.DataFrame) -> None:
    st.markdown("### 参考指標")
    c1, c2, c3, c4 = st.columns(4)
    mc = info.get("market_cap")
    c1.metric("時価総額", f"{mc / 1e8:,.0f} 億円" if mc else "—")
    per, pbr = info.get("per"), info.get("pbr")
    c2.metric("PER（実績）", f"{per:.2f} 倍" if per else "—")
    c3.metric("PBR", f"{pbr:.2f} 倍" if pbr else "—")
    dy = info.get("dividend_yield")
    if dy:
        dy_pct = dy * 100 if dy < 1 else dy  # yfinanceは小数/％の両方があり得る
        c4.metric("配当利回り", f"{dy_pct:.2f}%")
    else:
        c4.metric("配当利回り", "—")

    if not df_year.empty:
        price = float(df_year["Close"].iloc[-1])
        hi, lo = float(df_year["High"].max()), float(df_year["Low"].min())
        pos_pct = (price - lo) / (hi - lo) * 100 if hi > lo else 50.0
        st.markdown("### 52週レンジ内の位置")
        st.progress(min(max(pos_pct / 100, 0.0), 1.0),
                    text=f"安値 ¥{lo:,.0f} ─ 現在 ¥{price:,.0f}（{pos_pct:.0f}%）─ 高値 ¥{hi:,.0f}")
    st.caption("Yahoo Finance由来の参考値です。投資判断の際は最新の開示資料もご確認ください。")


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### ⚙️ コントロール")
        if st.button("🔄 データを再ダウンロード", use_container_width=True):
            ticker = normalize_jp(st.session_state.get("detail_search", ""))
            if ticker and (DATA_DIR / ticker).exists():
                for p in (DATA_DIR / ticker).glob("*"):
                    try:
                        p.unlink()
                    except OSError:
                        pass
            st.rerun()
        st.caption("保存先: `data/`（銘柄ごとにCSV/JSONで保存）")


def render_price_tab(ticker: str, info: dict, df_day: pd.DataFrame, df_year: pd.DataFrame) -> None:
    # 現在値・前日終値（当日より前の直近日足終値を優先。info.jsonは1日キャッシュで古い場合があるため）
    price = float(df_day["Close"].iloc[-1]) if not df_day.empty else None
    prev_close = None
    if not df_day.empty and not df_year.empty:
        day_date = df_day.index[-1].date()
        prior = df_year[[ts.date() < day_date for ts in df_year.index]]
        if not prior.empty:
            prev_close = float(prior["Close"].iloc[-1])
    if prev_close is None:
        prev_close = info.get("previous_close")
    if prev_close is None and len(df_year) >= 2:
        prev_close = float(df_year["Close"].iloc[-2])

    c1, c2, c3 = st.columns(3)
    if price is not None and prev_close:
        chg = price - prev_close
        pct = chg / prev_close * 100
        c1.metric("現在値", f"¥{price:,.1f}", f"{chg:+,.1f} ({pct:+.2f}%)")
    else:
        c1.metric("現在値", f"¥{price:,.1f}" if price else "—")
    c2.metric("前日終値", f"¥{prev_close:,.1f}" if prev_close else "—")
    c3.metric("更新", dt.datetime.now().strftime("%m/%d %H:%M"))

    st.divider()

    # 当日の始値/高値/安値/VWAP/出来高/売買代金
    col1, col2, col3 = st.columns(3)
    if not df_day.empty:
        t_open = df_day.index[0].strftime("%H:%M")
        hi_idx, lo_idx = df_day["High"].idxmax(), df_day["Low"].idxmin()
        vol = int(df_day["Volume"].sum())
        turnover = float((df_day["Close"] * df_day["Volume"]).sum())
        vwap = turnover / vol if vol else None

        with col1:
            st.markdown("**始値**")
            st.markdown(f"### {df_day['Open'].iloc[0]:,.1f} ({t_open})")
            st.markdown("**安値**")
            st.markdown(f"### {df_day['Low'].min():,.1f} ({lo_idx.strftime('%H:%M')})")
        with col2:
            st.markdown("**高値**")
            st.markdown(f"### {df_day['High'].max():,.1f} ({hi_idx.strftime('%H:%M')})")
            st.markdown("**出来高**")
            st.markdown(f"### {vol:,}")
        with col3:
            st.markdown("**VWAP**")
            st.markdown(f"### {vwap:,.4f}" if vwap else "### —")
            st.markdown("**売買代金**")
            st.markdown(f"### {turnover/1000:,.0f} (千円)")
    else:
        col1.info("当日データを取得できませんでした。")

    st.divider()

    # 年初来高値・安値（1年データから計算）
    col1, col2, col3 = st.columns(3)
    if not df_year.empty:
        ytd = df_year[df_year.index >= pd.Timestamp(dt.date.today().replace(month=1, day=1), tz=df_year.index.tz)]
        src = ytd if not ytd.empty else df_year
        hi_i, lo_i = src["High"].idxmax(), src["Low"].idxmin()
        with col1:
            st.markdown("**年初来高値**")
            st.markdown(f"### {src['High'].max():,.1f} ({hi_i.strftime('%y/%m/%d')})")
        with col2:
            st.markdown("**年初来安値**")
            st.markdown(f"### {src['Low'].min():,.1f} ({lo_i.strftime('%y/%m/%d')})")

    # 参考指標
    with col3:
        st.markdown("**PER / PBR**")
        per, pbr = info.get("per"), info.get("pbr")
        st.markdown(f"### {per:,.2f} / {pbr:,.2f}" if per and pbr else "### —")


def _rangebreaks(df: pd.DataFrame, intraday: bool) -> list[dict]:
    """取引のない時間帯（夜間・昼休み・週末・祝日）をチャートから除外する設定。"""
    breaks: list[dict] = []
    # 週末・祝日など、データが1本もない日をまとめて除外
    try:
        days = pd.date_range(df.index.min().normalize(), df.index.max().normalize(), freq="D")
        have = {ts.date() for ts in df.index}
        missing = [d for d in days if d.date() not in have]
        if missing:
            breaks.append(dict(values=missing, dvalue=24 * 3600 * 1000))
    except Exception:
        breaks.append(dict(bounds=["sat", "mon"]))
    if intraday:
        breaks.append(dict(bounds=[15.55, 8.99], pattern="hour"))   # 夜間（大引け後〜寄付前）
        breaks.append(dict(bounds=[11.55, 12.45], pattern="hour"))  # 昼休み
    return breaks


def render_chart_tab(ticker: str) -> None:
    st.markdown("### チャート期間")

    if "detail_period" not in st.session_state:
        st.session_state.detail_period = "1d"

    cols = st.columns(len(PERIODS))
    for i, (label, key, _, _) in enumerate(PERIODS):
        btn_type = "primary" if st.session_state.detail_period == key else "secondary"
        if cols[i].button(label, key=f"dperiod_{key}", use_container_width=True, type=btn_type):
            st.session_state.detail_period = key
            st.rerun()

    sel = next(p for p in PERIODS if p[1] == st.session_state.detail_period)
    label, key, period, interval = sel

    chart_type = st.radio("チャート形式", ["ローソク足", "ライン"],
                          horizontal=True, key="detail_chart_type")

    df, source = load_or_download_history(ticker, key, period, interval)
    if df.empty:
        st.warning(f"{ticker} のチャートデータを取得できませんでした。")
        return

    st.caption(f"📁 データ源: {source}　/　期間: {label}（足: {interval}）　/　{len(df)}本")

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        st.line_chart(df["Close"], height=400)
        st.bar_chart(df["Volume"], height=150)
        return

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.75, 0.25], vertical_spacing=0.03)

    if chart_type == "ローソク足":
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name="株価", increasing_line_color=UP, decreasing_line_color=DOWN,
        ), row=1, col=1)
    else:
        line_color = UP if df["Close"].iloc[-1] >= df["Close"].iloc[0] else DOWN
        fig.add_trace(go.Scatter(
            x=df.index, y=df["Close"], name="終値", mode="lines",
            line=dict(color=line_color, width=1.8),
            fill="tozeroy", fillcolor=f"rgba{(*[int(line_color[i:i+2], 16) for i in (1, 3, 5)], 0.08)}",
        ), row=1, col=1)
        pad = (df["Close"].max() - df["Close"].min()) * 0.05 or df["Close"].iloc[-1] * 0.01
        fig.update_yaxes(range=[df["Low"].min() - pad, df["High"].max() + pad], row=1, col=1)

    vol_colors = [UP if c >= o else DOWN for o, c in zip(df["Open"], df["Close"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="出来高",
                         marker_color=vol_colors, showlegend=False), row=2, col=1)

    fig.update_layout(
        height=550, template="plotly_white",
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis_rangeslider_visible=False, showlegend=False,
        hovermode="x unified",
    )
    # 夜間・昼休み・週末・祝日のギャップを詰めて連続表示にする
    fig.update_xaxes(rangeslider_visible=False,
                     rangebreaks=_rangebreaks(df, key in INTRADAY_KEYS))
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    render_sidebar()

    # ヘッダー: タイトル（左）＋ デモトレードボタン（右上）
    try:
        head_l, head_r = st.columns([4, 1], vertical_alignment="center")
    except TypeError:  # 古いStreamlitでは vertical_alignment 未対応
        head_l, head_r = st.columns([4, 1])
    head_l.title("📊 株式銘柄詳細")
    if head_r.button("📈 デモトレード", type="primary", use_container_width=True):
        try:
            st.switch_page("demo.py")
        except Exception:
            st.warning("demo.py が見つかりません。`streamlit run demo.py` で起動してください。")

    # demo.py から渡された銘柄コード（detail_search）を検索欄の初期値として使う
    code = st.text_input("🔍 銘柄検索（証券コード）", key="detail_search", placeholder="例: 7203")
    ticker = normalize_jp(code)

    if not ticker:
        st.info("証券コードを入力するか、デモトレード画面から銘柄を開いてください。")
        return
    if yf is None:
        st.error("`yfinance` がインストールされていません。`pip install yfinance` を実行してください。")

    with st.spinner("銘柄情報を取得中..."):
        info = load_or_download_info(ticker)
        df_day, _ = load_or_download_history(ticker, "1d", "1d", "5m")
        df_year, _ = load_or_download_history(ticker, "1y", "1y", "1d")

    if df_day.empty and df_year.empty:
        st.warning(f"{ticker} のデータを取得できませんでした。コードを確認してください。")
        return

    st.markdown(f"## {info.get('name', ticker)}（{ticker.replace('.T', '')}）")

    tab1, tab2, tab3, tab4 = st.tabs(["株価", "チャート", "ニュース", "評価レポート"])
    with tab1:
        render_price_tab(ticker, info, df_day, df_year)
    with tab2:
        render_chart_tab(ticker)
    with tab3:
        render_news_tab(ticker)
    with tab4:
        render_report_tab(info, df_year)

    st.divider()
    st.caption("データは data/ フォルダに保存され、次回以降は保存済みデータを利用します。")


main()
