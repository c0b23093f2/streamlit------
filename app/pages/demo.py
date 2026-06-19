"""
株式デモトレード（ペーパートレード）アプリ — 日本株専用
- データソース: yfinance（Yahoo Finance の実データ）
- 機能: 成行売買、ポートフォリオ管理、現金残高、損益表示、価格チャート、取引履歴、自動価格更新

実行方法:
    pip install -r requirements.txt
    streamlit run demo.py
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
INITIAL_CASH = 1_000_000  # 初期資金（円）
DEFAULT_TICKERS = ["7203.T", "9984.T", "6758.T", "8306.T", "9432.T", "6861.T", "8035.T", "7974.T"]
TICKER_NAMES = {
    "7203.T": "トヨタ自動車",
    "9984.T": "ソフトバンクG",
    "6758.T": "ソニーG",
    "8306.T": "三菱UFJ",
    "9432.T": "NTT",
    "6861.T": "キーエンス",
    "8035.T": "東京エレクトロン",
    "7974.T": "任天堂",
}
CACHE_TTL = 30  # 価格キャッシュの秒数（自動更新の実質的な間隔）

UP = "#16c784"    # 上昇・利益
DOWN = "#ea3943"  # 下落・損失
ACCENT = "#5b8def"

st.set_page_config(page_title="デモトレード", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
:root { --up:#16c784; --down:#ea3943; --accent:#5b8def; }
.block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1200px; }
#MainMenu, footer { visibility: hidden; }

.app-header {
    background: linear-gradient(120deg, #1e3a8a 0%, #2563eb 55%, #3b82f6 100%);
    border-radius: 16px; padding: 22px 26px; color: #fff; margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(37,99,235,.25);
}
.app-header h1 { margin: 0; font-size: 1.55rem; font-weight: 700; letter-spacing: .02em; }
.app-header p { margin: 6px 0 0; opacity: .9; font-size: .85rem; }

.card {
    background: var(--card-bg, #ffffff);
    border: 1px solid rgba(128,128,128,.18);
    border-radius: 14px; padding: 16px 18px; height: 100%;
    box-shadow: 0 2px 10px rgba(0,0,0,.04);
}
.card .label { font-size: .78rem; color: #8a94a6; font-weight: 600; letter-spacing: .03em; }
.card .value { font-size: 1.55rem; font-weight: 700; margin-top: 4px; line-height: 1.15; }
.card .sub { font-size: .82rem; margin-top: 2px; font-weight: 600; }
.up { color: var(--up); } .down { color: var(--down); } .muted { color:#8a94a6; }

section[data-testid="stSidebar"] { border-right: 1px solid rgba(128,128,128,.15); }
.stButton > button { border-radius: 10px; font-weight: 600; }
div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
h3 { font-weight: 700 !important; letter-spacing: .01em; }
.pill { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.72rem; font-weight:700; }
</style>
"""


def normalize_jp(code: str) -> str:
    """証券コードを東証ティッカーに正規化。'7203' -> '7203.T'"""
    code = (code or "").upper().strip()
    if not code:
        return ""
    if code.endswith(".T"):
        return code
    return f"{code.replace('.T', '')}.T"


def label_of(ticker: str) -> str:
    name = TICKER_NAMES.get(ticker)
    return f"{name}（{ticker}）" if name else ticker


def yen(x: float) -> str:
    return f"¥{x:,.0f}"


# ---------------------------------------------------------------------------
# データ取得（yfinance）
# ---------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_price(ticker: str) -> float | None:
    if yf is None:
        return None
    try:
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        if data.empty:
            data = yf.Ticker(ticker).history(period="5d")
        if data.empty:
            return None
        return float(data["Close"].dropna().iloc[-1])
    except Exception:
        return None


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    if yf is None:
        return pd.DataFrame()
    try:
        return yf.Ticker(ticker).history(period=period, interval=interval).dropna()
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# 状態管理
# ---------------------------------------------------------------------------
@dataclass
class Position:
    shares: int = 0
    cost_basis: float = 0.0


def init_state() -> None:
    ss = st.session_state
    ss.setdefault("cash", float(INITIAL_CASH))
    ss.setdefault("positions", {})
    ss.setdefault("trades", [])
    ss.setdefault("watchlist", list(DEFAULT_TICKERS))


def execute_trade(ticker: str, side: str, shares: int, price: float) -> tuple[bool, str]:
    ss = st.session_state
    ticker = normalize_jp(ticker)
    if shares <= 0:
        return False, "株数は1以上で指定してください。"
    if price is None or price <= 0:
        return False, "価格を取得できませんでした。"

    cost = shares * price
    pos: Position = ss.positions.get(ticker, Position())

    if side == "買い":
        if cost > ss.cash:
            return False, f"残高不足です。必要額 {yen(cost)} / 残高 {yen(ss.cash)}"
        new_shares = pos.shares + shares
        pos.cost_basis = (pos.cost_basis * pos.shares + cost) / new_shares
        pos.shares = new_shares
        ss.cash -= cost
    else:
        if shares > pos.shares:
            return False, f"保有株数が不足しています。保有 {pos.shares} 株"
        pos.shares -= shares
        ss.cash += cost
        if pos.shares == 0:
            pos.cost_basis = 0.0

    ss.positions[ticker] = pos
    ss.trades.append({
        "日時": dt.datetime.now().strftime("%m-%d %H:%M:%S"),
        "銘柄": label_of(ticker),
        "売買": side,
        "株数": shares,
        "価格": round(price, 1),
        "約定額": round(cost, 0),
    })
    if ticker not in ss.watchlist:
        ss.watchlist.append(ticker)
    return True, f"{side} 約定: {label_of(ticker)} {shares}株 @ ¥{price:,.1f}"


# ---------------------------------------------------------------------------
# UI パーツ
# ---------------------------------------------------------------------------
def card(label: str, value: str, sub: str = "", sub_cls: str = "muted") -> str:
    sub_html = f'<div class="sub {sub_cls}">{sub}</div>' if sub else ""
    return f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div>{sub_html}</div>'


def render_sidebar() -> None:
    ss = st.session_state
    with st.sidebar:
        st.markdown("### ⚙️ コントロール")
        auto = st.toggle("自動更新", value=False, help=f"{CACHE_TTL}秒ごとに価格を再取得")
        if auto:
            try:
                from streamlit_autorefresh import st_autorefresh
                st_autorefresh(interval=CACHE_TTL * 1000, key="auto_refresh")
                st.caption(f"🟢 自動更新中（{CACHE_TTL}秒間隔）")
            except ImportError:
                st.caption("`streamlit-autorefresh` 未導入のため手動更新します。")
        if st.button("🔄 価格を今すぐ更新", use_container_width=True):
            get_price.clear()
            get_history.clear()
            st.rerun()

        st.divider()
        st.markdown("#### クイック銘柄")
        st.caption("クリックで取引欄にセット")
        cols = st.columns(2)
        for i, tk in enumerate(DEFAULT_TICKERS):
            name = TICKER_NAMES.get(tk, tk)
            if cols[i % 2].button(name, key=f"q_{tk}", use_container_width=True):
                ss["trade_code"] = tk.replace(".T", "")
                ss["chart_code"] = tk.replace(".T", "")
                st.rerun()

        st.divider()
        if st.button("↩️ 口座をリセット", use_container_width=True):
            for k in ("cash", "positions", "trades", "watchlist"):
                ss.pop(k, None)
            init_state()
            st.rerun()
        st.caption("※ デモ（ペーパートレード）です。実際の取引は行われません。")


def render_summary() -> None:
    ss = st.session_state
    holdings_value = 0.0
    for ticker, pos in ss.positions.items():
        if pos.shares == 0:
            continue
        price = get_price(ticker)
        if price:
            holdings_value += pos.shares * price

    total = ss.cash + holdings_value
    total_pnl = total - INITIAL_CASH
    pct = total_pnl / INITIAL_CASH * 100
    cls = "up" if total_pnl > 0 else ("down" if total_pnl < 0 else "muted")
    arrow = "▲" if total_pnl > 0 else ("▼" if total_pnl < 0 else "—")

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(card("総資産", yen(total), f"{arrow} {yen(abs(total_pnl))}（{pct:+.2f}%）", cls), unsafe_allow_html=True)
    c2.markdown(card("現金残高", yen(ss.cash)), unsafe_allow_html=True)
    c3.markdown(card("株式評価額", yen(holdings_value)), unsafe_allow_html=True)
    c4.markdown(card("累計損益", f'<span class="{cls}">{total_pnl:+,.0f}</span>', f"{pct:+.2f}%", cls), unsafe_allow_html=True)


def render_positions() -> None:
    ss = st.session_state
    rows = []
    for ticker, pos in ss.positions.items():
        if pos.shares == 0:
            continue
        price = get_price(ticker)
        if price is None:
            continue
        mkt = pos.shares * price
        cost = pos.shares * pos.cost_basis
        pnl = mkt - cost
        rows.append({
            "銘柄": label_of(ticker),
            "保有株数": pos.shares,
            "平均取得単価": round(pos.cost_basis, 1),
            "現在価格": round(price, 1),
            "評価額": round(mkt, 0),
            "損益": round(pnl, 0),
            "損益率%": round(pnl / cost * 100, 2) if cost else 0.0,
        })

    st.markdown("### 📦 保有ポジション")
    if not rows:
        st.info("保有ポジションはありません。右の取引パネルから売買してください。")
        return
    df = pd.DataFrame(rows)
    styled = df.style.map(
        lambda v: f"color:{UP};font-weight:700" if v > 0 else (f"color:{DOWN};font-weight:700" if v < 0 else ""),
        subset=["損益", "損益率%"],
    ).format({"平均取得単価": "{:,.1f}", "現在価格": "{:,.1f}", "評価額": "{:,.0f}", "損益": "{:+,.0f}", "損益率%": "{:+.2f}"})
    st.dataframe(styled, use_container_width=True, hide_index=True)


def render_trade_panel() -> None:
    st.markdown("### 🛒 注文")
    code = st.text_input("証券コード", key="trade_code", placeholder="例: 7203")
    ticker = normalize_jp(code)
    price = get_price(ticker) if ticker else None

    if ticker:
        if price:
            st.markdown(
                f'<div class="card"><div class="label">{label_of(ticker)}</div>'
                f'<div class="value">¥{price:,.1f}</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.warning("価格を取得できませんでした。コードを確認してください。")

    c1, c2 = st.columns(2)
    side = c1.radio("売買", ["買い", "売り"], horizontal=True)
    shares = c2.number_input("株数", min_value=1, value=100, step=100)

    if price:
        st.caption(f"概算約定額　**{yen(shares * price)}**")
    label = "買い注文を出す" if side == "買い" else "売り注文を出す"
    if st.button(label, type="primary", use_container_width=True, disabled=not (ticker and price)):
        ok, msg = execute_trade(ticker, side, int(shares), price)
        (st.success if ok else st.error)(msg)
        if ok:
            st.rerun()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """テクニカル指標を計算して列を追加。"""
    out = df.copy()
    close = out["Close"]

    # 移動平均
    out["SMA25"] = close.rolling(25).mean()
    out["SMA75"] = close.rolling(75).mean()
    out["EMA12"] = close.ewm(span=12, adjust=False).mean()

    # ボリンジャーバンド（20日, ±2σ）
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    out["BB_mid"], out["BB_up"], out["BB_low"] = mid, mid + 2 * std, mid - 2 * std

    # RSI（14日）
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    out["RSI"] = 100 - 100 / (1 + rs)

    # MACD（12, 26, 9）
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["MACD"] = ema12 - ema26
    out["Signal"] = out["MACD"].ewm(span=9, adjust=False).mean()
    out["Hist"] = out["MACD"] - out["Signal"]
    return out


def render_chart() -> None:
    st.markdown("### 📈 価格チャート")
    c1, c2, c3 = st.columns([2, 1.1, 1.3])
    code = c1.text_input("証券コード", key="chart_code", placeholder="例: 7203",
                         help="証券コードを入力すると即チャート表示（.T自動付与）")
    period = c2.selectbox("期間", ["1mo", "3mo", "6mo", "1y", "5y"], index=1)
    chart_type = c3.radio("表示", ["ローソク足", "ライン"], horizontal=True)

    # テクニカル指標オプション（変更すると即リアルタイム反映）
    o1, o2 = st.columns(2)
    overlays = o1.multiselect(
        "価格チャートに重ねる", ["移動平均(25/75)", "EMA(12)", "ボリンジャーバンド"],
        default=["移動平均(25/75)"], key="chart_overlays",
    )
    panels = o2.multiselect(
        "サブパネル", ["出来高", "RSI(14)", "MACD"],
        default=["RSI(14)", "MACD"], key="chart_panels",
    )

    ticker = normalize_jp(code)
    if not ticker:
        st.info("証券コードを入力してください。")
        return

    interval_map = {"1mo": "1d", "3mo": "1d", "6mo": "1d", "1y": "1d", "5y": "1wk"}
    df = get_history(ticker, period, interval_map[period])
    if df.empty:
        st.warning(f"{ticker} のチャートデータを取得できませんでした。")
        return
    df = add_indicators(df)

    price = get_price(ticker)
    first = float(df["Close"].iloc[0])
    chg = (price - first) / first * 100 if price and first else 0
    cls = "up" if chg >= 0 else "down"
    st.markdown(
        f'<div style="margin:2px 0 10px"><span style="font-weight:700;font-size:1.05rem">{label_of(ticker)}</span>'
        f'&nbsp;&nbsp;<span style="font-size:1.2rem;font-weight:700">¥{price:,.1f}</span>'
        f'&nbsp;<span class="{cls}" style="font-weight:700">（{chg:+.2f}% / 期間内）</span></div>',
        unsafe_allow_html=True,
    )

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        st.caption("`plotly` 未導入のためラインで表示します。")
        st.line_chart(df["Close"], height=360, color=ACCENT)
        return

    # サブパネルの行構成を決定
    rows = ["price"] + [p for p in ["出来高", "RSI(14)", "MACD"] if p in panels]
    heights = {"price": 0.5, "出来高": 0.16, "RSI(14)": 0.17, "MACD": 0.17}
    row_h = [heights[r] for r in rows]
    s = sum(row_h)
    row_h = [h / s for h in row_h]

    fig = make_subplots(
        rows=len(rows), cols=1, shared_xaxes=True, vertical_spacing=0.03,
        row_heights=row_h,
        subplot_titles=[("" if r == "price" else r) for r in rows],
    )

    # --- 価格パネル ---
    if chart_type == "ローソク足":
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name="株価", increasing_line_color=UP, decreasing_line_color=DOWN,
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="終値",
                                 line=dict(color=ACCENT, width=2)), row=1, col=1)

    if "移動平均(25/75)" in overlays:
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA25"], name="SMA25",
                                 line=dict(color="#f0b90b", width=1.2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA75"], name="SMA75",
                                 line=dict(color="#9b59b6", width=1.2)), row=1, col=1)
    if "EMA(12)" in overlays:
        fig.add_trace(go.Scatter(x=df.index, y=df["EMA12"], name="EMA12",
                                 line=dict(color="#ff7f0e", width=1.2)), row=1, col=1)
    if "ボリンジャーバンド" in overlays:
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_up"], name="BB +2σ",
                                 line=dict(color="rgba(91,141,239,.5)", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_low"], name="BB -2σ", fill="tonexty",
                                 fillcolor="rgba(91,141,239,.08)",
                                 line=dict(color="rgba(91,141,239,.5)", width=1)), row=1, col=1)

    # --- サブパネル ---
    for i, r in enumerate(rows[1:], start=2):
        if r == "出来高":
            colors = [UP if c >= o else DOWN for o, c in zip(df["Open"], df["Close"])]
            fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="出来高",
                                 marker_color=colors, showlegend=False), row=i, col=1)
        elif r == "RSI(14)":
            fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI",
                                     line=dict(color="#8e44ad", width=1.4), showlegend=False), row=i, col=1)
            fig.add_hline(y=70, line=dict(color=DOWN, width=1, dash="dot"), row=i, col=1)
            fig.add_hline(y=30, line=dict(color=UP, width=1, dash="dot"), row=i, col=1)
            fig.update_yaxes(range=[0, 100], row=i, col=1)
        elif r == "MACD":
            hist_colors = [UP if v >= 0 else DOWN for v in df["Hist"]]
            fig.add_trace(go.Bar(x=df.index, y=df["Hist"], name="MACD Hist",
                                 marker_color=hist_colors, showlegend=False), row=i, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD",
                                     line=dict(color=ACCENT, width=1.3)), row=i, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["Signal"], name="Signal",
                                     line=dict(color="#f0b90b", width=1.3)), row=i, col=1)

    fig.update_layout(
        height=420 + 130 * (len(rows) - 1),
        margin=dict(l=0, r=0, t=18, b=0),
        xaxis_rangeslider_visible=False, template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
        hovermode="x unified",
    )
    fig.update_xaxes(rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # 直近のシグナル要約（リアルタイム）
    rsi = df["RSI"].iloc[-1]
    macd_cross = "ゴールデンクロス気味" if df["MACD"].iloc[-1] > df["Signal"].iloc[-1] else "デッドクロス気味"
    rsi_txt = "買われすぎ" if rsi >= 70 else ("売られすぎ" if rsi <= 30 else "中立")
    st.caption(f"📊 RSI {rsi:.1f}（{rsi_txt}）　/　MACD: {macd_cross}")


def render_history() -> None:
    ss = st.session_state
    st.markdown("### 🧾 取引履歴")
    if not ss.trades:
        st.info("まだ取引はありません。")
        return
    hist = pd.DataFrame(ss.trades[::-1])
    styled = hist.style.map(
        lambda v: f"color:{UP};font-weight:700" if v == "買い" else (f"color:{DOWN};font-weight:700" if v == "売り" else ""),
        subset=["売買"],
    ).format({"価格": "{:,.1f}", "約定額": "{:,.0f}"})
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.download_button("CSVをダウンロード", hist.to_csv(index=False).encode("utf-8-sig"),
                       file_name="trade_history.csv", mime="text/csv")


def main() -> None:
    init_state()
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="app-header"><h1>📈 株式デモトレード</h1>'
        '<p>yfinance（Yahoo Finance）の実データを使った日本株ペーパートレード</p></div>',
        unsafe_allow_html=True,
    )
    if yf is None:
        st.error("`yfinance` がインストールされていません。`pip install yfinance` を実行してください。")
        st.stop()

    render_sidebar()
    render_summary()
    st.write("")

    left, right = st.columns([1.7, 1])
    with left:
        render_chart()
    with right:
        render_trade_panel()

    st.write("")
    render_positions()
    st.write("")
    render_history()


if __name__ == "__main__":
    main()