"""
📈 うめぇ〜go株 — 統合版（1ファイル・マルチページ）

構成:
    ホーム（銘柄検索・ランキング） → 銘柄詳細（チャート/テクニカル判定/予測/ニュース/決算）
    左上の ☰ ハンバーガーメニューから 指標解説・お気に入り銘柄・デモトレード へ移動

実行方法:
    pip install -r requirements.txt
    streamlit run app.py
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

# ---------------------------------------------------------------------------
# 基本設定
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="うめぇ〜go株",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

UP = "#16c784"
DOWN = "#ea3943"
ACCENT = "#5b8def"
INITIAL_CASH = 1_000_000  # デモトレード初期資金（円）

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "favorites.db"

# 日本語名 → ティッカー
JMAP = {
    "トヨタ": "7203.T", "トヨタ自動車": "7203.T",
    "ソニー": "6758.T", "ソニーグループ": "6758.T",
    "日立": "6501.T", "日立製作所": "6501.T",
    "三菱UFJ": "8306.T", "三菱UFJフィナンシャル": "8306.T",
    "任天堂": "7974.T",
    "ホンダ": "7267.T", "本田技研": "7267.T",
    "日産": "7201.T", "日産自動車": "7201.T",
    "キヤノン": "7751.T", "キャノン": "7751.T",
    "NTT": "9432.T", "日本電信電話": "9432.T",
    "KDDI": "9433.T",
    "ソフトバンクG": "9984.T", "ソフトバンク": "9984.T", "ソフトバンクグループ": "9984.T",
    "楽天": "4755.T", "楽天グループ": "4755.T",
    "ユニクロ": "9983.T", "ファーストリテイリング": "9983.T",
    "パナソニック": "6752.T", "東芝": "6502.T", "富士通": "6702.T",
    "三菱商事": "8058.T", "三井物産": "8031.T", "伊藤忠商事": "8001.T",
    "武田": "4502.T", "武田薬品": "4502.T", "第一三共": "4568.T",
    "味の素": "2802.T", "キリン": "2503.T", "アサヒ": "2502.T",
    "資生堂": "4911.T", "花王": "4452.T",
    "東京エレクトロン": "8035.T", "信越化学": "4063.T", "村田製作所": "6981.T",
    "キーエンス": "6861.T",
    "ファナック": "6954.T", "日本製鉄": "5401.T", "三菱重工": "7011.T",
    "JR東日本": "9020.T", "ANA": "9202.T", "全日空": "9202.T", "JAL": "9201.T",
    "東京海上": "8766.T", "野村": "8604.T", "野村證券": "8604.T",
    "みずほ": "8411.T", "三井住友": "8316.T", "りそな": "8308.T",
    "オリックス": "8591.T", "セブン＆アイ": "3382.T", "セブンイレブン": "3382.T",
    "ニトリ": "9843.T", "良品計画": "7453.T", "無印良品": "7453.T",
    "メルカリ": "4385.T", "LINEヤフー": "4689.T",
    "日経平均": "^N225", "日経平均株価": "^N225", "日経225": "^N225",
}

# ティッカー → 日本語名（JMAPの逆引き。最初に出た名前を採用）
CODE2NAME: dict[str, str] = {}
for _name, _code in JMAP.items():
    CODE2NAME.setdefault(_code, _name)

QUICK_TICKERS = ["7203.T", "9984.T", "6758.T", "8306.T", "9432.T", "6861.T", "8035.T", "7974.T"]

# ランキング対象（JMAP収載の個別銘柄）
RANK_UNIVERSE = tuple(sorted({c for c in JMAP.values() if not c.startswith("^")}))

CSS = """
<style>
/* Streamlit Cloud等の固定ヘッダーと重ならないよう上部に余白を確保 */
.block-container { padding-top: 4rem; padding-bottom: 2rem; max-width: 1200px; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

.app-header {
    background: linear-gradient(120deg, #1e3a8a 0%, #2563eb 55%, #3b82f6 100%);
    border-radius: 16px; padding: 18px 24px; color: #fff; margin-bottom: 16px;
    box-shadow: 0 8px 24px rgba(37,99,235,.25);
}
.app-header h1 { margin: 0; font-size: 1.4rem; font-weight: 700; }
.app-header p { margin: 4px 0 0; opacity: .9; font-size: .82rem; }

.card {
    background: #ffffff; border: 1px solid rgba(128,128,128,.18);
    border-radius: 14px; padding: 14px 16px; height: 100%;
    box-shadow: 0 2px 10px rgba(0,0,0,.04);
}
.card .label { font-size: .75rem; color: #8a94a6; font-weight: 600; }
.card .value { font-size: 1.35rem; font-weight: 700; margin-top: 4px; line-height: 1.15; }
.card .sub { font-size: .8rem; margin-top: 2px; font-weight: 600; }
.up { color: #16c784; } .down { color: #ea3943; } .muted { color: #8a94a6; }
.stButton > button { border-radius: 10px; font-weight: 600; }
div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
</style>
"""


# ---------------------------------------------------------------------------
# 共通ユーティリティ
# ---------------------------------------------------------------------------
def normalize_jp(code: str) -> str:
    """'7203' -> '7203.T'（既に .T / 米国株 / 指数はそのまま）"""
    code = (code or "").strip()
    if not code:
        return ""
    if code.startswith("^") or code.upper().endswith(".T"):
        return code.upper()
    if code.isdigit() and len(code) == 4:
        return f"{code}.T"
    return code.upper()


def label_of(ticker: str) -> str:
    name = CODE2NAME.get(ticker)
    return f"{name}（{ticker}）" if name else ticker


def cur_of(ticker: str) -> str:
    return "¥" if (ticker.endswith(".T") or ticker.startswith("^")) else "$"


def yen(x: float) -> str:
    return f"¥{x:,.0f}"


def card_html(label: str, value: str, sub: str = "", sub_cls: str = "muted") -> str:
    sub_html = f'<div class="sub {sub_cls}">{sub}</div>' if sub else ""
    return f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div>{sub_html}</div>'


# ---------------------------------------------------------------------------
# データ取得（yfinance / キャッシュ付き）
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def get_price(ticker: str) -> float | None:
    if yf is None or not ticker:
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


@st.cache_data(ttl=60, show_spinner=False)
def get_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    if yf is None or not ticker:
        return pd.DataFrame()
    try:
        return yf.Ticker(ticker).history(period=period, interval=interval).dropna()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def get_info(ticker: str) -> dict:
    if yf is None or not ticker:
        return {}
    try:
        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}


@st.cache_data(ttl=600, show_spinner=False)
def get_news(ticker: str) -> list[dict]:
    if yf is None or not ticker:
        return []
    try:
        return yf.Ticker(ticker).news or []
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def get_earnings(ticker: str) -> tuple[list[str], pd.DataFrame]:
    """(次回決算予定日リスト, 過去決算の売上高/純利益テーブル)"""
    dates: list[str] = []
    table = pd.DataFrame()
    if yf is None or not ticker:
        return dates, table
    t = yf.Ticker(ticker)
    try:
        cal = t.calendar
        ed = None
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
        elif cal is not None and hasattr(cal, "empty") and not cal.empty and "Earnings Date" in cal.index:
            ed = cal.loc["Earnings Date"]
        if ed is not None:
            if not isinstance(ed, (list, tuple)):
                ed = [ed]
            for d in ed:
                if d is None or (hasattr(pd, "isna") and pd.isna(d)):
                    continue
                dates.append(d.strftime("%Y/%m/%d") if hasattr(d, "strftime") else str(d))
    except Exception:
        pass
    try:
        income = t.quarterly_income_stmt
        if income is not None and not income.empty:
            table = pd.DataFrame(index=income.columns)
            if "Total Revenue" in income.index:
                table["売上高"] = income.loc["Total Revenue"].values
            if "Net Income" in income.index:
                table["純利益"] = income.loc["Net Income"].values
            table.index = pd.to_datetime(table.index).strftime("%Y-%m-%d")
            table.index.name = "決算日"
    except Exception:
        table = pd.DataFrame()
    return dates, table


def _extract_ticker_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    """yfinance一括DLの単層・多層カラム両対応で1銘柄を取り出す。"""
    if raw is None or raw.empty:
        return None
    if not isinstance(raw.columns, pd.MultiIndex):
        return raw.copy()
    lv0 = raw.columns.get_level_values(0)
    lv1 = raw.columns.get_level_values(1)
    if ticker in lv0:
        frame = raw[ticker].copy()
    elif ticker in lv1:
        frame = raw.xs(ticker, axis=1, level=1).copy()
    else:
        return None
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(-1)
    return frame


@st.cache_data(ttl=900, show_spinner=False)
def get_batch_quotes(tickers: tuple[str, ...], period: str = "1mo") -> pd.DataFrame:
    """複数銘柄の 現在値/前日比率/出来高/直近推移 を一括取得。"""
    if yf is None or not tickers:
        return pd.DataFrame()
    try:
        raw = yf.download(
            tickers=list(tickers), period=period, interval="1d",
            group_by="ticker", auto_adjust=False, actions=False,
            threads=True, progress=False,
        )
    except Exception:
        return pd.DataFrame()
    rows = []
    for tk in tickers:
        frame = _extract_ticker_frame(raw, tk)
        if frame is None or "Close" not in frame.columns:
            continue
        close = pd.to_numeric(frame["Close"], errors="coerce").dropna()
        if len(close) < 2:
            continue
        last, prev = float(close.iloc[-1]), float(close.iloc[-2])
        if prev <= 0:
            continue
        vol = 0
        if "Volume" in frame.columns:
            v = pd.to_numeric(frame["Volume"], errors="coerce").dropna()
            vol = int(v.iloc[-1]) if len(v) else 0
        rows.append({
            "yahoo_code": tk,
            "銘柄名": CODE2NAME.get(tk, tk),
            "現在値": round(last, 1),
            "前日比率": round((last - prev) / prev * 100, 2),
            "出来高": vol,
            "直近推移": close.tail(10).round(1).tolist(),
        })
    return pd.DataFrame(rows)


def search_stock(kw: str) -> list[dict]:
    """銘柄名・コードから検索。"""
    if not kw or yf is None:
        return []
    k = kw.strip()
    targets: list[str] = []
    if k in JMAP:
        targets.append(JMAP[k])
    else:
        for name, code in JMAP.items():
            if k in name or name in k:
                targets.append(code)
        if not targets:
            targets.append(normalize_jp(k))
            if not k.isdigit():
                targets.append(k.upper())
    targets = list(dict.fromkeys(t for t in targets if t))
    results = []
    for code in targets[:8]:
        info = get_info(code)
        if info and (info.get("longName") or info.get("shortName")):
            results.append({
                "code": code,
                "name": CODE2NAME.get(code) or info.get("longName") or info.get("shortName") or code,
                "sector": info.get("sector", "") or "",
                "price": get_price(code),
            })
    return results


# ---------------------------------------------------------------------------
# テクニカル指標
# ---------------------------------------------------------------------------
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["Close"]
    out["SMA5"] = close.rolling(5).mean()
    out["SMA25"] = close.rolling(25).mean()
    out["SMA75"] = close.rolling(75).mean()
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    out["BB_mid"], out["BB_up"], out["BB_low"] = mid, mid + 2 * std, mid - 2 * std
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    out["RSI"] = 100 - 100 / (1 + gain / loss)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["MACD"] = ema12 - ema26
    out["Signal"] = out["MACD"].ewm(span=9, adjust=False).mean()
    out["Hist"] = out["MACD"] - out["Signal"]
    return out


def technical_judgment(df: pd.DataFrame) -> dict:
    """テクニカル分析.py の総合判定ロジック"""
    rsi = float(df["RSI"].iloc[-1])
    macd_buy = df["MACD"].iloc[-1] > df["Signal"].iloc[-1]
    ma_buy = df["SMA5"].iloc[-1] > df["SMA25"].iloc[-1]
    rsi_buy = rsi < 30
    score = int(macd_buy) + int(ma_buy) + int(rsi_buy)
    if score == 3:
        j = ("買い", "★★★★★", "#16a34a", "🟢",
             "現在は複数の指標が買いシグナルを示しています。ただし、投資判断は他の情報もあわせて行ってください。")
    elif score == 2:
        j = ("やや買い", "★★★★☆", "#22c55e", "🟢",
             "買いシグナルがやや優勢ですが、他の指標も確認しながら慎重に判断してください。")
    elif score == 1:
        j = ("様子見", "★★★☆☆", "#eab308", "🟡",
             "指標が混在しているため、今後の値動きを確認してから判断することが推奨されます。")
    else:
        j = ("売り", "★☆☆☆☆", "#dc2626", "🔴",
             "現在は弱気シグナルが多く見られます。新規購入は慎重に検討してください。")
    return {
        "judgment": j[0], "stars": j[1], "color": j[2], "emoji": j[3], "comment": j[4],
        "rsi": rsi, "macd": float(df["MACD"].iloc[-1]), "signal": float(df["Signal"].iloc[-1]),
        "sma5": float(df["SMA5"].iloc[-1]), "sma25": float(df["SMA25"].iloc[-1]),
        "checks": {"MACD > シグナル": macd_buy, "短期MA > 長期MA（ゴールデンクロス方向）": ma_buy, "RSI < 30（売られすぎ）": rsi_buy},
    }


# ---------------------------------------------------------------------------
# お気に入り（SQLite永続化）
# ---------------------------------------------------------------------------
def _db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS favorites ("
        "code TEXT PRIMARY KEY, name TEXT, note TEXT DEFAULT '', created_at TEXT)"
    )
    return conn


def _mem() -> dict:
    """SQLiteが使えない環境（一部のネットワークドライブ等）用のフォールバック"""
    return st.session_state.setdefault("fav_mem", {})


def _use_mem() -> None:
    st.session_state["fav_persist_err"] = True


def fav_all() -> pd.DataFrame:
    cols = ["code", "name", "note", "created_at"]
    try:
        with _db() as conn:
            df = pd.read_sql_query("SELECT * FROM favorites ORDER BY created_at DESC", conn)
        return df if not df.empty else pd.DataFrame(columns=cols)
    except sqlite3.Error:
        _use_mem()
        rows = [{"code": k, **v} for k, v in _mem().items()]
        return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)


def fav_codes() -> set[str]:
    try:
        with _db() as conn:
            return {r[0] for r in conn.execute("SELECT code FROM favorites")}
    except sqlite3.Error:
        _use_mem()
        return set(_mem())


def fav_add(code: str, name: str) -> None:
    now = dt.datetime.now().strftime("%Y/%m/%d %H:%M")
    try:
        with _db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO favorites (code, name, note, created_at) VALUES (?,?,?,?)",
                (code, name, "", now),
            )
    except sqlite3.Error:
        _use_mem()
        _mem().setdefault(code, {"name": name, "note": "", "created_at": now})


def fav_remove(code: str) -> None:
    try:
        with _db() as conn:
            conn.execute("DELETE FROM favorites WHERE code=?", (code,))
    except sqlite3.Error:
        _use_mem()
        _mem().pop(code, None)


def fav_note(code: str, note: str) -> None:
    try:
        with _db() as conn:
            conn.execute("UPDATE favorites SET note=? WHERE code=?", (note, code))
    except sqlite3.Error:
        _use_mem()
        if code in _mem():
            _mem()[code]["note"] = note


def fav_clear() -> int:
    try:
        with _db() as conn:
            n = conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
            conn.execute("DELETE FROM favorites")
            return n
    except sqlite3.Error:
        _use_mem()
        n = len(_mem())
        _mem().clear()
        return n


def fav_toggle_button(code: str, name: str, key: str) -> None:
    """お気に入り追加/解除トグルボタン"""
    if code in fav_codes():
        if st.button("⭐ お気に入り解除", key=key, use_container_width=True):
            fav_remove(code)
            st.toast("お気に入りから削除しました。", icon="🗑️")
            st.rerun()
    else:
        if st.button("☆ お気に入りに追加", key=key, use_container_width=True):
            fav_add(code, name)
            st.toast("お気に入りに追加しました。", icon="⭐")
            st.rerun()


# ---------------------------------------------------------------------------
# デモトレード（セッション状態）
# ---------------------------------------------------------------------------
@dataclass
class Position:
    shares: int = 0
    cost_basis: float = 0.0


def init_trade_state() -> None:
    ss = st.session_state
    ss.setdefault("cash", float(INITIAL_CASH))
    ss.setdefault("positions", {})
    ss.setdefault("trades", [])


def execute_trade(ticker: str, side: str, shares: int, price: float) -> tuple[bool, str]:
    ss = st.session_state
    init_trade_state()
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
    return True, f"{side} 約定: {label_of(ticker)} {shares}株 @ ¥{price:,.1f}"


# ---------------------------------------------------------------------------
# ページ間遷移
# ---------------------------------------------------------------------------
def open_detail(code: str) -> None:
    st.session_state["sym"] = code
    st.switch_page(PG_DETAIL)


# ===========================================================================
# ページ: ホーム（銘柄検索 + ランキング）
# ===========================================================================
def page_home() -> None:
    st.markdown(
        '<div class="app-header"><h1>🏠 銘柄検索</h1>'
        '<p>銘柄名や証券コードで検索して、銘柄詳細（チャート・ニュース・予測）へ</p></div>',
        unsafe_allow_html=True,
    )

    ss = st.session_state
    ss.setdefault("hist", [])
    ss.setdefault("_res", [])

    c1, c2 = st.columns([3, 1])
    kw = c1.text_input("検索キーワード", placeholder="例: トヨタ, 7203, AAPL, 日経平均",
                       label_visibility="collapsed", key="skw")
    go = c2.button("🔍 検索", type="primary", use_container_width=True)

    # 検索履歴チップ
    if ss["hist"]:
        with st.expander(f"📜 検索履歴（{len(ss['hist'])}件）"):
            cols = st.columns(4)
            for i, h in enumerate(ss["hist"][-12:]):
                if cols[i % 4].button(h, key=f"h_{i}_{h}", use_container_width=True):
                    ss["_sr"] = h
                    st.rerun()
    sr = ss.pop("_sr", "")
    if sr:
        kw, go = sr, True

    # クイック銘柄
    st.caption("クイック銘柄（クリックで詳細へ）")
    qcols = st.columns(len(QUICK_TICKERS))
    for i, tk in enumerate(QUICK_TICKERS):
        if qcols[i].button(CODE2NAME.get(tk, tk), key=f"q_{tk}", use_container_width=True):
            open_detail(tk)

    if go and kw:
        kw = kw.strip()
        if kw not in ss["hist"]:
            ss["hist"].append(kw)
        with st.spinner("検索中..."):
            res = search_stock(kw)
        if res:
            st.success(f"✅ {len(res)}件見つかりました")
            ss["_res"] = res
        else:
            st.warning("❌ 該当する銘柄が見つかりませんでした")
            ss["_res"] = []

    for idx, r in enumerate(ss["_res"]):
        code = r["code"]
        cu = cur_of(code)
        ps = f"{cu}{r['price']:,.2f}" if r.get("price") else "N/A"
        with st.container(border=True):
            a, b, c, d, e = st.columns([2.2, 1.3, 1.3, 1, 1])
            a.markdown(f"**{r['name']}**")
            if r.get("sector"):
                a.caption(f"🏷️ {r['sector']}")
            b.metric("コード", code)
            c.metric("現在値", ps)
            with d:
                if st.button("📊 詳細", key=f"dt_{code}_{idx}", use_container_width=True):
                    open_detail(code)
            with e:
                fav_toggle_button(code, r["name"], key=f"fv_{code}_{idx}")

    # --- ランキング ---
    st.divider()
    st.markdown("### 📊 銘柄ランキング（主要銘柄）")
    with st.spinner("ランキングデータを取得しています…"):
        rank = get_batch_quotes(RANK_UNIVERSE, period="5d")
    if rank.empty:
        st.info("ランキングデータを取得できませんでした。")
        return

    tab_up, tab_down, tab_vol = st.tabs(["📈 値上がり率", "📉 値下がり率", "🔥 出来高"])
    views = [
        (tab_up, rank.sort_values("前日比率", ascending=False), "rank_up"),
        (tab_down, rank.sort_values("前日比率", ascending=True), "rank_down"),
        (tab_vol, rank.sort_values("出来高", ascending=False), "rank_vol"),
    ]
    for tab, df_v, key in views:
        with tab:
            df_show = df_v.head(15).reset_index(drop=True)
            event = st.dataframe(
                df_show[["銘柄名", "yahoo_code", "現在値", "前日比率", "出来高", "直近推移"]],
                use_container_width=True, hide_index=True,
                on_select="rerun", selection_mode="single-row", key=key,
                column_config={
                    "yahoo_code": st.column_config.TextColumn("コード", width="small"),
                    "現在値": st.column_config.NumberColumn("現在値", format="%.1f"),
                    "前日比率": st.column_config.NumberColumn("前日比（%）", format="%+.2f"),
                    "出来高": st.column_config.NumberColumn("出来高", format="%d"),
                    "直近推移": st.column_config.LineChartColumn("直近10日", width="medium"),
                },
            )
            try:
                rows = list(event.selection.rows)
            except Exception:
                rows = []
            if rows:
                open_detail(str(df_show.iloc[rows[0]]["yahoo_code"]))


# ===========================================================================
# ページ: 銘柄詳細
# ===========================================================================
def page_detail() -> None:
    ss = st.session_state
    c1, c2 = st.columns([3, 1])
    code_in = c1.text_input("証券コード・銘柄名", placeholder="例: 7203, トヨタ, AAPL",
                            label_visibility="collapsed", key="detail_kw")
    if c2.button("表示", type="primary", use_container_width=True) and code_in:
        k = code_in.strip()
        ss["sym"] = JMAP.get(k, normalize_jp(k))
        st.rerun()

    sym = ss.get("sym")
    if not sym:
        st.info("ホームで銘柄を検索するか、上の入力欄にコードを入力してください。")
        return

    info = get_info(sym)
    name = CODE2NAME.get(sym) or info.get("longName") or info.get("shortName") or sym
    cu = cur_of(sym)
    price = get_price(sym)

    # ヘッダー行
    h1, h2 = st.columns([3, 1])
    h1.markdown(f"## 📊 {name}（{sym}）")
    with h2:
        fav_toggle_button(sym, name, key=f"fv_detail_{sym}")

    # 前日比
    hist5 = get_history(sym, "5d", "1d")
    chg = pct = None
    if price is not None and len(hist5) >= 2:
        prev = float(hist5["Close"].iloc[-2])
        if prev > 0:
            chg = price - prev
            pct = chg / prev * 100

    r1 = st.columns(4)
    if price is not None:
        sub = f"{'▲' if (chg or 0) >= 0 else '▼'} {chg:+,.1f}（{pct:+.2f}%）" if chg is not None else ""
        cls = "up" if (chg or 0) >= 0 else "down"
        r1[0].markdown(card_html("現在値", f"{cu}{price:,.1f}", sub, cls), unsafe_allow_html=True)
    else:
        r1[0].markdown(card_html("現在値", "N/A"), unsafe_allow_html=True)
    r1[1].markdown(card_html("業種", info.get("sector") or "N/A"), unsafe_allow_html=True)
    mc = info.get("marketCap")
    mc_s = f"{mc/1e8:,.0f}億円" if isinstance(mc, (int, float)) and cu == "¥" else (
        f"${mc/1e9:,.1f}B" if isinstance(mc, (int, float)) else "N/A")
    r1[2].markdown(card_html("時価総額", mc_s), unsafe_allow_html=True)
    pe = info.get("trailingPE")
    r1[3].markdown(card_html("PER", f"{pe:.2f}倍" if isinstance(pe, (int, float)) else "N/A"),
                   unsafe_allow_html=True)

    r2 = st.columns(4)
    eps = info.get("trailingEps")
    r2[0].markdown(card_html("EPS", f"{eps:.2f}" if isinstance(eps, (int, float)) else "N/A"),
                   unsafe_allow_html=True)
    dy = info.get("dividendYield")
    dy_s = f"{dy:.2f}%" if isinstance(dy, (int, float)) else "N/A"
    r2[1].markdown(card_html("配当利回り", dy_s), unsafe_allow_html=True)
    vol = info.get("volume")
    r2[2].markdown(card_html("出来高", f"{vol:,}" if isinstance(vol, (int, float)) and vol else "N/A"),
                   unsafe_allow_html=True)
    r2[3].markdown(card_html("市場", info.get("market") or ("東証" if cu == "¥" else "N/A")),
                   unsafe_allow_html=True)

    st.write("")
    tab_chart, tab_tech, tab_pred, tab_news, tab_earn, tab_trade = st.tabs(
        ["📈 チャート", "🤖 テクニカル判定", "🔮 予測", "📰 ニュース", "📅 決算", "💼 取引（デモ）"]
    )

    with tab_chart:
        render_chart(sym)
    with tab_tech:
        render_technical(sym, name, cu)
    with tab_pred:
        render_prediction(sym)
    with tab_news:
        render_news(sym)
    with tab_earn:
        render_earnings(sym)
    with tab_trade:
        render_order_form(sym, price)


def render_chart(sym: str) -> None:
    period = st.radio("期間", ["1mo", "3mo", "6mo", "1y", "5y"],
                      format_func=lambda p: {"1mo": "1ヶ月", "3mo": "3ヶ月", "6mo": "6ヶ月",
                                             "1y": "1年", "5y": "5年"}[p],
                      index=1, horizontal=True, key="chart_period")
    o1, o2 = st.columns(2)
    overlays = o1.multiselect("価格チャートに重ねる",
                              ["移動平均(25/75)", "ボリンジャーバンド"],
                              default=["移動平均(25/75)"], key="ovl")
    panels = o2.multiselect("サブパネル", ["出来高", "RSI(14)", "MACD"],
                            default=["RSI(14)", "MACD"], key="pnl")

    interval = "1wk" if period == "5y" else "1d"
    df = get_history(sym, period, interval)
    if df.empty:
        st.warning("チャートデータを取得できませんでした。")
        return
    df = add_indicators(df)

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        st.line_chart(df["Close"], height=360)
        return

    rows = ["price"] + [p for p in ["出来高", "RSI(14)", "MACD"] if p in panels]
    heights = {"price": 0.5, "出来高": 0.16, "RSI(14)": 0.17, "MACD": 0.17}
    row_h = [heights[r] for r in rows]
    s = sum(row_h)
    fig = make_subplots(rows=len(rows), cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[h / s for h in row_h],
                        subplot_titles=[("" if r == "price" else r) for r in rows])

    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
                                 low=df["Low"], close=df["Close"], name="株価",
                                 increasing_line_color=UP, decreasing_line_color=DOWN), row=1, col=1)
    if "移動平均(25/75)" in overlays:
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA25"], name="SMA25",
                                 line=dict(color="#f0b90b", width=1.2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA75"], name="SMA75",
                                 line=dict(color="#9b59b6", width=1.2)), row=1, col=1)
    if "ボリンジャーバンド" in overlays:
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_up"], name="BB +2σ",
                                 line=dict(color="rgba(91,141,239,.5)", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_low"], name="BB -2σ", fill="tonexty",
                                 fillcolor="rgba(91,141,239,.08)",
                                 line=dict(color="rgba(91,141,239,.5)", width=1)), row=1, col=1)

    for i, r in enumerate(rows[1:], start=2):
        if r == "出来高":
            colors = [UP if c >= o else DOWN for o, c in zip(df["Open"], df["Close"])]
            fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=colors,
                                 showlegend=False), row=i, col=1)
        elif r == "RSI(14)":
            fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], line=dict(color="#8e44ad", width=1.4),
                                     showlegend=False), row=i, col=1)
            fig.add_hline(y=70, line=dict(color=DOWN, width=1, dash="dot"), row=i, col=1)
            fig.add_hline(y=30, line=dict(color=UP, width=1, dash="dot"), row=i, col=1)
            fig.update_yaxes(range=[0, 100], row=i, col=1)
        elif r == "MACD":
            hist_colors = [UP if v >= 0 else DOWN for v in df["Hist"]]
            fig.add_trace(go.Bar(x=df.index, y=df["Hist"], marker_color=hist_colors,
                                 showlegend=False), row=i, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD",
                                     line=dict(color=ACCENT, width=1.3)), row=i, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["Signal"], name="Signal",
                                     line=dict(color="#f0b90b", width=1.3)), row=i, col=1)

    fig.update_layout(height=420 + 120 * (len(rows) - 1), margin=dict(l=0, r=0, t=18, b=0),
                      xaxis_rangeslider_visible=False, template="plotly_white",
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
                      hovermode="x unified")
    fig.update_xaxes(rangeslider_visible=False)
    if interval == "1d":
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    st.plotly_chart(fig, use_container_width=True)

    rsi = df["RSI"].iloc[-1]
    macd_cross = "ゴールデンクロス気味" if df["MACD"].iloc[-1] > df["Signal"].iloc[-1] else "デッドクロス気味"
    rsi_txt = "買われすぎ" if rsi >= 70 else ("売られすぎ" if rsi <= 30 else "中立")
    st.caption(f"📊 RSI {rsi:.1f}（{rsi_txt}）　/　MACD: {macd_cross}")


def render_technical(sym: str, name: str, cu: str) -> None:
    df = get_history(sym, "6mo", "1d")
    if len(df) < 30:
        st.warning("判定に必要なデータが不足しています。")
        return
    df = add_indicators(df)
    t = technical_judgment(df)
    price = float(df["Close"].iloc[-1])
    st.markdown(f"""
<div style="border:1px solid #e0e0e0;border-radius:16px;padding:28px;background-color:#fafafa;margin-bottom:12px;">
  <div style="font-size:22px;font-weight:bold;margin-bottom:4px;">{name}</div>
  <div style="color:#666;font-size:14px;margin-bottom:14px;">現在価格</div>
  <div style="font-size:30px;font-weight:bold;margin-bottom:14px;">{cu}{price:,.0f}</div>
  <div style="font-size:26px;letter-spacing:2px;margin-bottom:10px;">{t['stars']}</div>
  <div style="display:inline-block;padding:6px 18px;border-radius:20px;background-color:{t['color']};
              color:white;font-weight:bold;font-size:17px;margin-bottom:18px;">{t['emoji']} 総合判定：{t['judgment']}</div>
  <div style="display:flex;gap:32px;margin-top:18px;">
    <div><div style="color:#666;font-size:13px;">RSI</div><div style="font-size:18px;font-weight:bold;">{t['rsi']:.1f}</div></div>
    <div><div style="color:#666;font-size:13px;">MACD</div><div style="font-size:18px;font-weight:bold;">{t['macd']:+.2f}</div></div>
    <div><div style="color:#666;font-size:13px;">MA25</div><div style="font-size:18px;font-weight:bold;">{cu}{t['sma25']:,.0f}</div></div>
  </div>
</div>
""", unsafe_allow_html=True)
    st.info(t["comment"])
    with st.expander("判定の内訳"):
        for label, ok in t["checks"].items():
            st.write(("✅ " if ok else "❌ ") + label)
        st.caption("3つのシグナルのうち一致した数で判定します（3=買い / 2=やや買い / 1=様子見 / 0=売り）。")


def render_prediction(sym: str) -> None:
    df = get_history(sym, "1y", "1d")
    if len(df) < 30:
        st.warning("予測に必要なデータが不足しています。")
        return
    close = df["Close"]
    ma25 = close.rolling(25).mean().dropna()
    if len(ma25) < 2:
        st.warning("移動平均を計算できませんでした。")
        return
    last_ma, prev_ma = float(ma25.iloc[-1]), float(ma25.iloc[-2])
    trend = last_ma - prev_ma
    future_days = 30
    future_index = pd.bdate_range(start=close.index[-1] + pd.Timedelta(days=1), periods=future_days)
    future = []
    v = last_ma
    for _ in range(future_days):
        v += trend
        future.append(v)

    try:
        import plotly.graph_objects as go
    except ImportError:
        st.line_chart(close)
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=close.index, y=close, mode="lines", name="終値",
                             line=dict(color=ACCENT, width=1.6)))
    fig.add_trace(go.Scatter(x=ma25.index, y=ma25, mode="lines", name="25日移動平均",
                             line=dict(color="#f0b90b", width=1.4)))
    fig.add_trace(go.Scatter(x=[ma25.index[-1]] + list(future_index),
                             y=[last_ma] + future, mode="lines", name="30営業日予測",
                             line=dict(dash="dash", color="red")))
    fig.update_layout(title="株価・25日移動平均・30営業日予測", hovermode="x unified",
                      template="plotly_white", legend=dict(orientation="h", y=1.08),
                      height=440, margin=dict(l=0, r=0, t=60, b=0))
    st.plotly_chart(fig, use_container_width=True)

    direction = "上昇" if trend > 0 else ("下落" if trend < 0 else "横ばい")
    st.metric("30営業日後の予測値（簡易）", f"{future[-1]:,.1f}", f"トレンド: {direction}（{trend:+.2f}/日）")
    st.caption("予測線は25日移動平均の直近の傾きをそのまま30営業日先まで延長した簡易的な予測です。実際の株価を予測するものではありません。")


def render_news(sym: str) -> None:
    items = get_news(sym)
    if not items:
        st.info("📰 ニュースはありません")
        return
    for n in items[:10]:
        c = n.get("content", {}) or {}
        link = (c.get("canonicalUrl", {}) or {}).get("url", "") or ""
        title = c.get("title", "")
        if not title:
            continue
        with st.container(border=True):
            st.markdown(f"##### [{title}]({link})" if link else f"##### {title}")
            st.caption(f"🏢 {(c.get('provider', {}) or {}).get('displayName', '')}　🕐 {c.get('pubDate', '')}")
            if c.get("summary"):
                st.write(c["summary"][:300])


def render_earnings(sym: str) -> None:
    dates, table = get_earnings(sym)
    st.subheader("次回決算予定日")
    if dates:
        cols = st.columns(max(len(dates), 1))
        for i, d in enumerate(dates):
            cols[i].markdown(card_html("決算日", d), unsafe_allow_html=True)
    else:
        st.info("📌 決算日情報なし")

    st.subheader("過去の決算（四半期）")
    if table.empty:
        st.warning("過去の決算情報は取得できませんでした。")
        return
    show = table.copy()
    for col in show.columns:
        show[col] = show[col].apply(lambda x: f"{x/1e8:,.0f} 億円" if pd.notnull(x) else "-")
    st.dataframe(show, use_container_width=True)
    if "純利益" in table.columns:
        try:
            import plotly.graph_objects as go
            ni = pd.to_numeric(table["純利益"], errors="coerce") / 1e8
            fig = go.Figure(go.Bar(x=table.index, y=ni,
                                   marker_color=[UP if v >= 0 else DOWN for v in ni.fillna(0)]))
            fig.update_layout(title="四半期純利益（億円）", template="plotly_white",
                              height=300, margin=dict(l=0, r=0, t=50, b=0))
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            pass


def render_order_form(sym: str, price: float | None) -> None:
    init_trade_state()
    if price is None:
        st.warning("価格を取得できないため注文できません。")
        return
    st.caption(f"仮想資金でのペーパートレードです（現金残高 {yen(st.session_state.cash)}）")
    c1, c2 = st.columns(2)
    side = c1.radio("売買", ["買い", "売り"], horizontal=True, key=f"side_{sym}")
    shares = c2.number_input("株数", min_value=1, value=100, step=100, key=f"sh_{sym}")
    st.caption(f"概算約定額　**{yen(shares * price)}**")
    if st.button("注文を出す", type="primary", use_container_width=True, key=f"ord_{sym}"):
        ok, msg = execute_trade(sym, side, int(shares), price)
        (st.success if ok else st.error)(msg)
    st.page_link(PG_TRADE, label="💼 ポートフォリオ全体を見る（デモトレード）")


# ===========================================================================
# ページ: お気に入り銘柄
# ===========================================================================
def page_favorites() -> None:
    st.markdown(
        '<div class="app-header"><h1>⭐ お気に入り銘柄</h1>'
        '<p>登録銘柄はこのPCの data/favorites.db に保存され、アプリを閉じても残ります</p></div>',
        unsafe_allow_html=True,
    )
    favorites = fav_all()
    if st.session_state.get("fav_persist_err"):
        st.caption("⚠️ この環境ではファイル保存（SQLite）が使えないため、お気に入りはセッション内のみ保持されます。")
    if favorites.empty:
        st.info("お気に入りはまだ登録されていません。検索結果や銘柄詳細の「☆ お気に入りに追加」から登録できます。")
        st.page_link(PG_HOME, label="🏠 銘柄検索へ")
        return

    with st.spinner("お気に入り銘柄の最新株価を取得しています…"):
        quotes = get_batch_quotes(tuple(favorites["code"].tolist()))
    data = favorites.merge(quotes, left_on="code", right_on="yahoo_code", how="left") \
        if not quotes.empty else favorites.assign(現在値=None, 前日比率=None, 直近推移=None)

    chg = pd.to_numeric(data.get("前日比率"), errors="coerce")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("登録銘柄", f"{len(data)}件")
    m2.metric("値上がり", f"{int((chg > 0).sum())}件")
    m3.metric("値下がり", f"{int((chg < 0).sum())}件")
    m4.metric("株価未取得", f"{int(chg.isna().sum())}件")

    c1, c2, c3 = st.columns([2.3, 1.4, 1])
    keyword = c1.text_input("検索", placeholder="銘柄名・コード・メモ", label_visibility="collapsed")
    sort_option = c2.selectbox("並び順", ["登録が新しい順", "値上がり率が高い順", "値下がり率が大きい順", "銘柄名順"],
                               label_visibility="collapsed")
    if c3.button("🔄 株価を更新", use_container_width=True):
        get_batch_quotes.clear()
        st.rerun()

    filtered = data.copy()
    if keyword.strip():
        k = keyword.strip()
        mask = (
            filtered["name"].astype(str).str.contains(k, case=False, regex=False, na=False)
            | filtered["code"].astype(str).str.contains(k, case=False, regex=False, na=False)
            | filtered["note"].astype(str).str.contains(k, case=False, regex=False, na=False)
        )
        filtered = filtered.loc[mask]
    if sort_option == "値上がり率が高い順":
        filtered = filtered.sort_values("前日比率", ascending=False, na_position="last")
    elif sort_option == "値下がり率が大きい順":
        filtered = filtered.sort_values("前日比率", ascending=True, na_position="last")
    elif sort_option == "銘柄名順":
        filtered = filtered.sort_values("name")
    filtered = filtered.reset_index(drop=True)

    if filtered.empty:
        st.warning("検索条件に該当するお気に入り銘柄がありません。")
        return

    display = filtered[["code", "name", "現在値", "前日比率", "直近推移", "note", "created_at"]].copy()
    display.columns = ["コード", "銘柄名", "現在値", "前日比率", "直近推移", "メモ", "登録日時"]
    st.caption("行を選択すると、下にメモ編集・削除・詳細表示の操作が出ます。")
    event = st.dataframe(
        display, use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row", key="fav_table",
        column_config={
            "現在値": st.column_config.NumberColumn("現在値", format="%.1f"),
            "前日比率": st.column_config.NumberColumn("前日比（%）", format="%+.2f"),
            "直近推移": st.column_config.LineChartColumn("直近10日", width="medium"),
        },
    )
    try:
        rows = list(event.selection.rows)
    except Exception:
        rows = []
    if rows and 0 <= rows[0] < len(filtered):
        sel = filtered.iloc[rows[0]]
        code = str(sel["code"])
        with st.container(border=True):
            t1, t2 = st.columns([3, 1])
            t1.subheader(f"{sel['name']}（{code}）")
            with t2:
                if st.button("📊 銘柄詳細を開く", use_container_width=True, key=f"open_{code}"):
                    open_detail(code)
            note = st.text_area("メモ", value=str(sel.get("note", "") or ""),
                                placeholder="例：決算後の値動きを確認する", max_chars=500,
                                key=f"note_{code}")
            b1, b2 = st.columns(2)
            if b1.button("💾 メモを保存", type="primary", use_container_width=True, key=f"sv_{code}"):
                fav_note(code, note)
                st.toast("メモを保存しました。", icon="✅")
                st.rerun()
            confirm = b2.checkbox("削除を確認", key=f"cf_{code}")
            if b2.button("🗑️ お気に入りから削除", use_container_width=True,
                         disabled=not confirm, key=f"rm_{code}"):
                fav_remove(code)
                st.toast("削除しました。", icon="🗑️")
                st.rerun()

    csv = display.drop(columns=["直近推移"], errors="ignore")
    st.download_button("お気に入り一覧をCSVで保存",
                       data=csv.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"お気に入り銘柄_{dt.datetime.now():%Y%m%d}.csv", mime="text/csv")
    with st.expander("その他の操作"):
        st.warning("すべて削除すると元に戻せません。")
        ok_all = st.checkbox("すべてのお気に入りを削除することを確認しました")
        if st.button("すべて削除", disabled=not ok_all):
            n = fav_clear()
            st.toast(f"{n}件削除しました。", icon="🗑️")
            st.rerun()


# ===========================================================================
# ページ: 指標解説
# ===========================================================================
GLOSSARY = pd.DataFrame({
    "分類": ["ファンダメンタル"] * 7 + ["テクニカル"] * 7,
    "指標": ["PER", "PBR", "ROE", "EPS", "BPS", "配当利回り", "時価総額",
             "移動平均線", "RSI", "MACD", "ボリンジャーバンド", "出来高", "ゴールデンクロス", "デッドクロス"],
    "意味": [
        "株価が1株当たり利益(EPS)の何倍かを示す指標",
        "株価が1株当たり純資産(BPS)の何倍かを示す指標",
        "企業の収益性を表す自己資本利益率",
        "1株当たり利益",
        "1株当たり純資産",
        "年間配当金が株価に対して何％か",
        "企業全体の市場価値",
        "一定期間の株価平均",
        "買われすぎ・売られすぎを判断する指標",
        "売買タイミングを判断する指標",
        "株価の変動幅を表す指標",
        "売買された株数",
        "短期移動平均線が長期移動平均線を上抜け",
        "短期移動平均線が長期移動平均線を下抜け",
    ],
    "見方": [
        "15倍前後が一般的。低いほど割安とされる。",
        "1倍未満は割安の目安。",
        "10%以上が優良企業の目安。",
        "高いほど利益を多く生み出している。",
        "株価との比較に利用する。",
        "3〜4%以上なら高配当株とされることが多い。",
        "企業規模を比較するときに利用する。",
        "株価の大きな流れを確認する。",
        "70以上は買われすぎ、30以下は売られすぎ。",
        "MACD線とシグナル線の交差を見る。",
        "±2σを超えると反転する場合がある。",
        "増加すると注目度が高いことを示す。",
        "買いシグナルとして利用される。",
        "売りシグナルとして利用される。",
    ],
})


def page_glossary() -> None:
    st.markdown(
        '<div class="app-header"><h1>📚 株式指標一覧と解説</h1>'
        '<p>株式投資でよく使用される代表的な指標を一覧で確認できます</p></div>',
        unsafe_allow_html=True,
    )
    cat = st.radio("分類で絞り込み", ["すべて", "ファンダメンタル", "テクニカル"], horizontal=True)
    df = GLOSSARY if cat == "すべて" else GLOSSARY[GLOSSARY["分類"] == cat]
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.info(
        "ファンダメンタル分析：企業の業績や財務状況、将来性などを分析し、企業本来の価値を評価する分析方法です。\n\n"
        "テクニカル分析：過去の株価や出来高などの値動きを分析し、今後の株価の動きを予測する分析方法です。"
    )
    st.caption("テクニカル指標の実際の動きは、銘柄詳細の「📈 チャート」「🤖 テクニカル判定」タブで確認できます。")


# ===========================================================================
# ページ: デモトレード
# ===========================================================================
def page_trade() -> None:
    init_trade_state()
    ss = st.session_state
    st.markdown(
        '<div class="app-header"><h1>💼 デモトレード</h1>'
        '<p>yfinance の実データを使った日本株ペーパートレード（仮想資金100万円）</p></div>',
        unsafe_allow_html=True,
    )

    # サマリー
    holdings_value = 0.0
    for tk, pos in ss.positions.items():
        if pos.shares:
            p = get_price(tk)
            if p:
                holdings_value += pos.shares * p
    total = ss.cash + holdings_value
    pnl = total - INITIAL_CASH
    pct = pnl / INITIAL_CASH * 100
    cls = "up" if pnl > 0 else ("down" if pnl < 0 else "muted")
    arrow = "▲" if pnl > 0 else ("▼" if pnl < 0 else "—")
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(card_html("総資産", yen(total), f"{arrow} {yen(abs(pnl))}（{pct:+.2f}%）", cls), unsafe_allow_html=True)
    c2.markdown(card_html("現金残高", yen(ss.cash)), unsafe_allow_html=True)
    c3.markdown(card_html("株式評価額", yen(holdings_value)), unsafe_allow_html=True)
    c4.markdown(card_html("累計損益", f"{pnl:+,.0f}", f"{pct:+.2f}%", cls), unsafe_allow_html=True)
    st.write("")

    left, right = st.columns([1.6, 1])
    with left:
        st.markdown("### 📦 保有ポジション")
        rows = []
        for tk, pos in ss.positions.items():
            if not pos.shares:
                continue
            p = get_price(tk)
            if p is None:
                continue
            mkt = pos.shares * p
            cost = pos.shares * pos.cost_basis
            rows.append({
                "銘柄": label_of(tk), "保有株数": pos.shares,
                "平均取得単価": round(pos.cost_basis, 1), "現在価格": round(p, 1),
                "評価額": round(mkt, 0), "損益": round(mkt - cost, 0),
                "損益率%": round((mkt - cost) / cost * 100, 2) if cost else 0.0,
            })
        if rows:
            df = pd.DataFrame(rows)
            styled = df.style.map(
                lambda v: f"color:{UP};font-weight:700" if isinstance(v, (int, float)) and v > 0
                else (f"color:{DOWN};font-weight:700" if isinstance(v, (int, float)) and v < 0 else ""),
                subset=["損益", "損益率%"],
            ).format({"平均取得単価": "{:,.1f}", "現在価格": "{:,.1f}", "評価額": "{:,.0f}",
                      "損益": "{:+,.0f}", "損益率%": "{:+.2f}"})
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.info("保有ポジションはありません。右の注文フォームから取引できます。")

        st.markdown("### 🧾 取引履歴")
        if ss.trades:
            hist = pd.DataFrame(ss.trades[::-1])
            st.dataframe(hist, use_container_width=True, hide_index=True)
            st.download_button("CSVをダウンロード", hist.to_csv(index=False).encode("utf-8-sig"),
                               file_name="trade_history.csv", mime="text/csv")
        else:
            st.info("まだ取引はありません。")

    with right:
        st.markdown("### 🛒 注文フォーム")
        # クイック銘柄で選んだコードを、ウィジェット生成前に反映する
        pending = ss.pop("_trade_code_pending", None)
        if pending is not None:
            ss["trade_code"] = pending
        code = st.text_input("証券コード", placeholder="例: 7203", key="trade_code")
        ticker = normalize_jp(code)
        price = get_price(ticker) if ticker else None
        if ticker and price:
            st.markdown(card_html(label_of(ticker), f"¥{price:,.1f}"), unsafe_allow_html=True)
            s1, s2 = st.columns(2)
            side = s1.radio("売買", ["買い", "売り"], horizontal=True, key="pt_side")
            shares = s2.number_input("株数", min_value=1, value=100, step=100, key="pt_shares")
            st.caption(f"概算約定額　**{yen(shares * price)}**")
            if st.button("注文を出す", type="primary", use_container_width=True):
                ok, msg = execute_trade(ticker, side, int(shares), price)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()
        elif ticker:
            st.warning("価格を取得できませんでした。コードを確認してください。")
        else:
            st.info("証券コードを入力してください。")

        st.markdown("#### クイック銘柄")
        qcols = st.columns(2)
        for i, tk in enumerate(QUICK_TICKERS):
            if qcols[i % 2].button(CODE2NAME.get(tk, tk), key=f"pq_{tk}", use_container_width=True):
                ss["_trade_code_pending"] = tk.replace(".T", "")
                st.rerun()

        st.divider()
        if st.button("↩️ 口座をリセット", use_container_width=True):
            for k in ("cash", "positions", "trades"):
                ss.pop(k, None)
            init_trade_state()
            st.rerun()
        st.caption("※ デモ（ペーパートレード）です。実際の取引は行われません。")


# ===========================================================================
# ナビゲーション（左上ハンバーガーメニュー）
# ===========================================================================
PG_HOME = st.Page(page_home, title="ホーム（銘柄検索）", icon="🏠", url_path="home", default=True)
PG_DETAIL = st.Page(page_detail, title="銘柄詳細", icon="📊", url_path="detail")
PG_FAV = st.Page(page_favorites, title="お気に入り銘柄", icon="⭐", url_path="favorites")
PG_GLOSSARY = st.Page(page_glossary, title="指標解説", icon="📚", url_path="glossary")
PG_TRADE = st.Page(page_trade, title="デモトレード", icon="💼", url_path="trade")


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    nav = st.navigation([PG_HOME, PG_DETAIL, PG_FAV, PG_GLOSSARY, PG_TRADE], position="hidden")

    # 左上ハンバーガーメニュー（全ページ共通・固定）
    mcol, tcol = st.columns([0.08, 0.92])
    with mcol:
        with st.popover("☰", use_container_width=True):
            st.markdown("**メニュー**")
            st.page_link(PG_HOME, label="ホーム（銘柄検索）", icon="🏠")
            st.page_link(PG_DETAIL, label="銘柄詳細", icon="📊")
            st.page_link(PG_FAV, label="お気に入り銘柄", icon="⭐")
            st.page_link(PG_GLOSSARY, label="指標解説", icon="📚")
            st.page_link(PG_TRADE, label="デモトレード", icon="💼")
    tcol.markdown(
        f'<div style="font-weight:700;font-size:1.05rem;padding-top:6px;">📈 うめぇ〜go株'
        f'<span style="color:#8a94a6;font-weight:600;font-size:.8rem;">'
        f'　{dt.datetime.now():%Y/%m/%d %H:%M} 時点</span></div>',
        unsafe_allow_html=True,
    )

    if yf is None:
        st.error("`yfinance` がインストールされていません。`pip install yfinance` を実行してください。")
        st.stop()

    nav.run()


if __name__ == "__main__":
    main()
