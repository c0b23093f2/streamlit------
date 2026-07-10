"""
自動売買ページ — デモトレード（demo.py）のポートフォリオを自動運用
- ① ボラティリティ予測: EWMA（RiskMetrics λ=0.94）による翌日ボラ予測 + ATR(14)
- ② 自動損切り・利確: 予測ボラに応じた損切り/利確ラインを全ポジションに設定し、
     到達したら自動で決済（エントリー戦略とは独立して動作）
- ③ 自動エントリー: RSI逆張り / SMAクロス順張り / MACDプラ転 / 複合シグナル
     （プリセットまたはカスタムでパラメーター調整可）

現金・ポジション・取引履歴は demo.py と共有（st.session_state）。
このページを開いている間（自動更新ON推奨）に判定サイクルが実行されます。

実行方法: streamlit run demo.py → サイドバーから「🤖 自動売買」
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

st.set_page_config(page_title="自動売買", page_icon="🤖", layout="wide")

UP = "#16c784"
DOWN = "#ea3943"
INITIAL_CASH = 1_000_000
CACHE_TTL = 30

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


STRATEGIES = ["RSI逆張り", "SMAクロス順張り", "MACDプラ転", "複合シグナル（2つ以上一致）"]

# 設定プリセット（リストから選択）。「🔧 カスタム」選択時のみ手動調整UIを表示
# trailing: トレーリングストップ / vol_max: エントリー時の予測ボラ上限(日次%)
# cooldown_h: 損切り後の再エントリー禁止時間 / loss_limit: 1日の実現損失上限(円)
PRESETS: dict[str, dict | None] = {
    "🛡️ 保守的": dict(strategy="複合シグナル（2つ以上一致）", rsi_buy=25, budget=100_000,
                       max_pos=2, k=1.5, m=3.0, trailing=True, vol_max=3.0,
                       cooldown_h=24, loss_limit=30_000),
    "⚖️ 標準":   dict(strategy="RSI逆張り", rsi_buy=30, budget=200_000,
                       max_pos=3, k=2.0, m=3.0, trailing=True, vol_max=4.0,
                       cooldown_h=12, loss_limit=50_000),
    "🚀 積極的": dict(strategy="MACDプラ転", rsi_buy=35, budget=300_000,
                       max_pos=5, k=2.5, m=4.0, trailing=False, vol_max=6.0,
                       cooldown_h=4, loss_limit=100_000),
    "🔧 カスタム": None,
}


@dataclass
class Position:
    shares: int = 0
    cost_basis: float = 0.0


def normalize_jp(code: str) -> str:
    code = (code or "").upper().strip()
    if not code:
        return ""
    return code if code.endswith(".T") else f"{code.replace('.T', '')}.T"


def label_of(ticker: str) -> str:
    name = TICKER_NAMES.get(ticker)
    return f"{name}（{ticker}）" if name else ticker


def yen(x: float) -> str:
    return f"¥{x:,.0f}"


# ---------------------------------------------------------------------------
# データ取得
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


@st.cache_data(ttl=300, show_spinner=False)
def get_daily(ticker: str) -> pd.DataFrame:
    if yf is None:
        return pd.DataFrame()
    try:
        return yf.Ticker(ticker).history(period="6mo", interval="1d").dropna()
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# ボラティリティ予測 & テクニカル指標
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def predict_vol(ticker: str) -> dict | None:
    """EWMA(λ=0.94)で翌日ボラを予測し、ATR(14)と合わせて返す。
    sigma: 損切り/利確幅の基準に使う日次ボラ（EWMAとATR%の大きい方＝保守的）"""
    df = get_daily(ticker)
    if df.empty or len(df) < 30:
        return None
    close = df["Close"]
    price = float(close.iloc[-1])

    # EWMA分散予測: σ²_{t+1} = λσ²_t + (1-λ)r²_t  （alpha = 1-λ = 0.06）
    ret = close.pct_change().dropna()
    sigma_day = float(math.sqrt(ret.pow(2).ewm(alpha=0.06).mean().iloc[-1]))

    # ATR(14)
    prev = close.shift(1)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - prev).abs(),
                    (df["Low"] - prev).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])
    atr_pct = atr / price if price else 0.0

    return {
        "price": price,
        "sigma_day": sigma_day,                      # EWMA翌日予測（日次）
        "sigma_annual": sigma_day * math.sqrt(252),  # 年率換算
        "atr": atr,
        "atr_pct": atr_pct,
        "sigma": max(sigma_day, atr_pct),
    }


@st.cache_data(ttl=300, show_spinner=False)
def indicators(ticker: str) -> dict | None:
    df = get_daily(ticker)
    if df.empty or len(df) < 30:
        return None
    close = df["Close"]
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = (100 - 100 / (1 + gain / loss)).iloc[-1]
    sma5, sma25 = close.rolling(5).mean(), close.rolling(25).mean()
    # MACD(12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return {
        "rsi": float(rsi),
        "sma5": float(sma5.iloc[-1]), "sma25": float(sma25.iloc[-1]),
        "sma5_prev": float(sma5.iloc[-2]), "sma25_prev": float(sma25.iloc[-2]),
        "macd": float(macd.iloc[-1]), "macd_sig": float(signal.iloc[-1]),
        "hist": float(hist.iloc[-1]), "hist_prev": float(hist.iloc[-2]),
    }


def entry_signal(ticker: str, strategy: str, rsi_buy: float) -> tuple[bool, str]:
    ind = indicators(ticker)
    if ind is None:
        return False, ""

    rsi_ok = ind["rsi"] <= rsi_buy
    sma_ok = ind["sma5_prev"] <= ind["sma25_prev"] and ind["sma5"] > ind["sma25"]
    macd_ok = ind["hist_prev"] <= 0 < ind["hist"]  # MACDヒストグラムのプラス転換

    if strategy == "RSI逆張り":
        return rsi_ok, (f"RSI {ind['rsi']:.1f} ≤ {rsi_buy:.0f}（売られすぎ）" if rsi_ok else "")
    if strategy == "SMAクロス順張り":
        return sma_ok, ("SMA5がSMA25を上抜け（ゴールデンクロス）" if sma_ok else "")
    if strategy == "MACDプラ転":
        return macd_ok, (f"MACDヒストグラムがプラ転（{ind['hist_prev']:+.2f}→{ind['hist']:+.2f}）"
                         if macd_ok else "")
    # 複合シグナル: 3指標のうち2つ以上が同時成立したときだけエントリー（高確度）
    hits = [name for ok, name in
            [(rsi_ok, "RSI売られすぎ"), (sma_ok, "SMAクロス"), (macd_ok, "MACDプラ転")] if ok]
    return len(hits) >= 2, ("複合シグナル: " + " + ".join(hits) if len(hits) >= 2 else "")


# ---------------------------------------------------------------------------
# 状態管理 & 売買実行
# ---------------------------------------------------------------------------
def init_state() -> None:
    ss = st.session_state
    ss.setdefault("cash", float(INITIAL_CASH))
    ss.setdefault("positions", {})
    ss.setdefault("trades", [])
    ss.setdefault("watchlist", list(DEFAULT_TICKERS))
    ss.setdefault("auto_targets", {})  # ticker -> {entry, stop, take, sigma, peak}
    ss.setdefault("auto_log", [])
    ss.setdefault("cooldown", {})      # ticker -> 損切りした時刻（再エントリー制限）
    ss.setdefault("day_pnl", {"date": dt.date.today().isoformat(), "pnl": 0.0})


def today_pnl() -> float:
    """当日の実現損益（日付が変わったらリセット）。"""
    ss = st.session_state
    today = dt.date.today().isoformat()
    if ss.day_pnl["date"] != today:
        ss.day_pnl = {"date": today, "pnl": 0.0}
    return ss.day_pnl["pnl"]


def record(ticker: str, side: str, shares: int, price: float, reason: str) -> None:
    """demo.py と同じ形式で取引履歴に記録し、自動売買ログにも残す。"""
    ss = st.session_state
    ss.trades.append({
        "日時": dt.datetime.now().strftime("%m-%d %H:%M:%S"),
        "銘柄": label_of(ticker),
        "売買": side,
        "株数": shares,
        "価格": round(price, 1),
        "約定額": round(shares * price, 0),
    })
    ss.auto_log.insert(0, {
        "日時": dt.datetime.now().strftime("%m-%d %H:%M:%S"),
        "銘柄": label_of(ticker),
        "売買": side,
        "株数": shares,
        "価格": round(price, 1),
        "理由": reason,
    })


def set_targets(ticker: str, base_price: float, sigma: float, k: float, m: float) -> dict:
    tgt = {
        "entry": base_price,
        "stop": base_price * (1 - k * sigma),
        "take": base_price * (1 + m * sigma),
        "sigma": sigma,
        "peak": base_price,  # トレーリングストップ用の高値
    }
    st.session_state.auto_targets[ticker] = tgt
    return tgt


def auto_sell(ticker: str, price: float, reason: str) -> str:
    ss = st.session_state
    pos: Position = ss.positions[ticker]
    shares = pos.shares
    pnl = (price - pos.cost_basis) * shares
    ss.cash += shares * price
    pos.shares, pos.cost_basis = 0, 0.0
    ss.auto_targets.pop(ticker, None)
    # デイリーロスリミット用に当日実現損益を集計
    today_pnl()
    ss.day_pnl["pnl"] += pnl
    # 損切りした銘柄はクールダウン（すぐ買い直さない）
    if "損切り" in reason:
        ss.cooldown[ticker] = dt.datetime.now()
    record(ticker, "売り", shares, price, f"{reason}（損益 {pnl:+,.0f}円）")
    return f"{reason}: {label_of(ticker)} {shares}株 @¥{price:,.1f}（損益 {pnl:+,.0f}円）"


def auto_buy(ticker: str, price: float, budget: float, sigma: float,
             k: float, m: float, reason: str) -> str | None:
    ss = st.session_state
    shares = int(budget // price)
    if shares <= 0 or shares * price > ss.cash:
        return None
    pos = ss.positions.get(ticker) or Position()
    new_shares = pos.shares + shares
    pos.cost_basis = (pos.cost_basis * pos.shares + shares * price) / new_shares
    pos.shares = new_shares
    ss.positions[ticker] = pos
    ss.cash -= shares * price
    tgt = set_targets(ticker, price, sigma, k, m)
    record(ticker, "買い", shares, price,
           f"エントリー: {reason} / 損切¥{tgt['stop']:,.1f} 利確¥{tgt['take']:,.1f}")
    if ticker not in ss.watchlist:
        ss.watchlist.append(ticker)
    return f"エントリー: {label_of(ticker)} {shares}株 @¥{price:,.1f}"


# ---------------------------------------------------------------------------
# 自動売買サイクル
# ---------------------------------------------------------------------------
def run_cycle(risk_on: bool, entry_on: bool, p: dict) -> list[str]:
    """1サイクル分の判定と執行。戻り値は発生イベントのメッセージ。"""
    ss = st.session_state
    events: list[str] = []
    k, m = p["k"], p["m"]

    # --- ② 損切り・利確（手動/自動を問わず全ポジションに適用） ---
    if risk_on:
        for tk, pos in list(ss.positions.items()):
            if getattr(pos, "shares", 0) <= 0:
                continue
            price = get_price(tk)
            if not price:
                continue
            tgt = ss.auto_targets.get(tk)
            if tgt is None:  # 手動で建てたポジション等にはここでラインを設定
                v = predict_vol(tk)
                if v is None:
                    continue
                base = pos.cost_basis or price
                tgt = set_targets(tk, base, v["sigma"], k, m)
                events.append(
                    f"監視開始: {label_of(tk)} 損切¥{tgt['stop']:,.1f} / 利確¥{tgt['take']:,.1f}")

            # トレーリングストップ: 高値を更新したら損切りラインを追従して引き上げ
            stop = tgt["stop"]
            if p.get("trailing"):
                tgt["peak"] = max(tgt.get("peak", tgt["entry"]), price)
                trail = tgt["peak"] * (1 - k * tgt["sigma"])
                if trail > stop:
                    stop = trail
            if price <= stop:
                reason = "🔺 トレーリング利確" if price > tgt["entry"] else "🔻 自動損切り"
                events.append(auto_sell(tk, price, reason))
            elif price >= tgt["take"]:
                events.append(auto_sell(tk, price, "🎯 自動利確"))

    # --- ③ 自動エントリー ---
    if entry_on:
        # デイリーロスリミット: 当日の実現損失が上限を超えたら新規停止
        if today_pnl() <= -p["loss_limit"]:
            events.append(f"⛔ 本日の実現損失が上限（{yen(p['loss_limit'])}）に達したため"
                          "新規エントリーを停止中")
            return events

        held = sum(1 for pos in ss.positions.values() if getattr(pos, "shares", 0) > 0)
        for tk in p["universe"]:
            if held >= p["max_pos"] or ss.cash < p["budget"]:
                break
            pos = ss.positions.get(tk)
            if pos and pos.shares > 0:
                continue
            # クールダウン: 損切り直後の銘柄は一定時間買い直さない
            cd = ss.cooldown.get(tk)
            if cd and (dt.datetime.now() - cd).total_seconds() < p["cooldown_h"] * 3600:
                continue
            ok, why = entry_signal(tk, p["strategy"], p["rsi_buy"])
            if not ok:
                continue
            price = get_price(tk)
            v = predict_vol(tk)
            if not price or v is None:
                continue
            # ボラフィルター: 荒れすぎている銘柄には入らない
            if v["sigma_day"] * 100 > p["vol_max"]:
                continue
            msg = auto_buy(tk, price, p["budget"], v["sigma"], k, m, why)
            if msg:
                events.append(msg)
                held += 1
    return events


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
def render_sidebar() -> tuple[bool, bool, bool]:
    with st.sidebar:
        st.markdown("### 🤖 稼働設定")
        risk_on = st.toggle("損切り・利確の自動執行", value=True,
                            help="全保有ポジションに予測ボラ基準のラインを設定し、到達で自動決済")
        entry_on = st.toggle("自動エントリー", value=False,
                             help="シグナル発生時に自動で買い建て")
        auto_ref = st.toggle("自動更新（30秒）", value=False)
        if auto_ref:
            try:
                from streamlit_autorefresh import st_autorefresh
                st_autorefresh(interval=30 * 1000, key="auto_trade_refresh")
                st.caption("🟢 30秒ごとに自動判定中")
            except ImportError:
                st.caption("`streamlit-autorefresh` 未導入のため手動実行してください。")
        st.divider()
        if st.button("↩️ 監視ライン/クールダウンをリセット", use_container_width=True):
            st.session_state.auto_targets = {}
            st.session_state.cooldown = {}
            st.rerun()
        st.caption("※ デモ（ペーパートレード）です。実際の取引は行われません。")
    return risk_on, entry_on, auto_ref


def render_params() -> dict:
    st.markdown("### ⚙️ パラメーター")
    c1, c2 = st.columns(2)

    with c1:
        universe_labels = st.multiselect(
            "対象銘柄", [label_of(t) for t in DEFAULT_TICKERS],
            default=[label_of(t) for t in DEFAULT_TICKERS[:4]], key="p_universe")
        extra = st.text_input("追加銘柄（証券コードをカンマ区切りで 例: 6501, 4063）",
                              key="p_extra", placeholder="リストにない銘柄も対象にできます")
    with c2:
        preset_name = st.selectbox("設定プリセット（リストから選択）",
                                   list(PRESETS.keys()), index=1, key="p_preset")

    preset = PRESETS[preset_name]
    if preset is not None:
        # プリセット選択時: 内容を一覧表示（調整不要）
        st.dataframe(pd.DataFrame([{
            "戦略": preset["strategy"],
            "RSI買い閾値": preset["rsi_buy"],
            "投資額/回": f"¥{preset['budget']:,}",
            "最大保有": preset["max_pos"],
            "損切りk": preset["k"],
            "利確m": preset["m"],
            "トレーリング": "ON" if preset["trailing"] else "OFF",
            "ボラ上限%": preset["vol_max"],
            "クールダウン": f"{preset['cooldown_h']}時間",
            "日次損失上限": f"¥{preset['loss_limit']:,}",
        }]), use_container_width=True, hide_index=True)
        params = dict(preset)
    else:
        # カスタム選択時: 手動調整UI
        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("**エントリー戦略**")
            strategy = st.selectbox("戦略", STRATEGIES, key="p_strategy")
            rsi_buy = st.slider("RSI買い閾値（RSI逆張り/複合時）", 10, 50, 30, key="p_rsi")
            b1, b2 = st.columns(2)
            budget = b1.number_input("1回の投資額（円）", 10_000, 1_000_000, 200_000,
                                     step=10_000, key="p_budget")
            max_pos = b2.number_input("最大保有銘柄数", 1, 10, 3, key="p_maxpos")
            vol_max = st.slider("エントリー時の予測ボラ上限（日次%）", 1.0, 10.0, 4.0, 0.5,
                                key="p_volmax",
                                help="予測ボラがこれを超える（荒れている）銘柄には新規で入らない")
        with cc2:
            st.markdown("**損切り・利確（予測ボラ基準）**")
            k = st.slider("損切り幅 = k × 予測ボラ", 0.5, 5.0, 2.0, 0.1, key="p_stop_k",
                          help="例: 予測ボラ2%・k=2 → 取得単価から -4% で損切り")
            m = st.slider("利確幅 = m × 予測ボラ", 0.5, 8.0, 3.0, 0.1, key="p_take_m",
                          help="例: 予測ボラ2%・m=3 → 取得単価から +6% で利確")
            trailing = st.toggle("トレーリングストップ", value=True, key="p_trailing",
                                 help="高値更新に合わせて損切りラインを引き上げ、利益を伸ばしつつ守る")
            cooldown_h = st.slider("損切り後のクールダウン（時間）", 0, 48, 12, key="p_cooldown",
                                   help="損切りした銘柄をすぐ買い直さない")
            loss_limit = st.number_input("1日の実現損失上限（円）", 10_000, 500_000, 50_000,
                                         step=10_000, key="p_losslimit",
                                         help="超えたらその日は新規エントリー停止")
        params = dict(strategy=strategy, rsi_buy=rsi_buy, budget=budget, max_pos=max_pos,
                      k=k, m=m, trailing=trailing, vol_max=vol_max,
                      cooldown_h=cooldown_h, loss_limit=loss_limit)

    universe = [t for t in DEFAULT_TICKERS if label_of(t) in universe_labels]
    for code in (extra or "").replace("、", ",").split(","):
        tk = normalize_jp(code)
        if tk and tk not in universe:
            universe.append(tk)
    params["universe"] = universe
    for key in ("rsi_buy", "budget", "k", "m", "vol_max", "cooldown_h", "loss_limit"):
        params[key] = float(params[key])
    params["max_pos"] = int(params["max_pos"])
    return params


def _vol_row(tk: str, held: list[str]) -> dict | None:
    """一覧テーブル用の1行を作成。"""
    ss = st.session_state
    v = predict_vol(tk)
    if v is None:
        return None
    tgt = ss.auto_targets.get(tk)
    ind = indicators(tk) or {}
    band1 = v["price"] * v["sigma_day"]  # ±1σ（円）
    band2 = band1 * 2                    # ±2σ（円）≒ 最大想定（95%カバー）
    return {
        "銘柄": label_of(tk),
        "現在値": round(v["price"], 1),
        "予測ボラ(日次)%": round(v["sigma_day"] * 100, 2),
        "予測変動(±円/1σ)": round(band1, 1),
        "最大想定(±円/2σ)": round(band2, 1),
        "想定レンジ(2σ)": f"{v['price'] - band2:,.0f} 〜 {v['price'] + band2:,.0f}",
        "RSI": round(ind.get("rsi", float("nan")), 1),
        "MACDヒスト": round(ind.get("hist", float("nan")), 2),
        "損切りライン": round(tgt["stop"], 1) if tgt else None,
        "利確ライン": round(tgt["take"], 1) if tgt else None,
        "状態": "📌 保有中" if tk in held else "👀 監視",
    }


def render_vol_table(universe: list[str]) -> None:
    st.markdown("### 🌡️ ボラティリティ予測")
    ss = st.session_state
    held = [t for t, p in ss.positions.items() if getattr(p, "shares", 0) > 0]
    tickers = list(dict.fromkeys(universe + held))
    if not tickers:
        st.info("対象銘柄を選択してください。")
        return

    # 銘柄をリストから選択して詳細を表示
    labels = [label_of(t) for t in tickers]
    sel = st.selectbox("銘柄を選択", labels, key="vol_select")
    tk = tickers[labels.index(sel)]

    v = predict_vol(tk)
    if v is None:
        st.warning(f"{label_of(tk)} のボラティリティを計算できませんでした。")
        return
    ind = indicators(tk) or {}
    tgt = ss.auto_targets.get(tk)
    band1 = v["price"] * v["sigma_day"]
    band2 = band1 * 2

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("現在値", f"¥{v['price']:,.1f}")
    c2.metric("予測ボラ（日次）", f"{v['sigma_day']*100:.2f}%",
              f"年率 {v['sigma_annual']*100:.1f}%", delta_color="off")
    c3.metric("予測変動（±1σ）", f"±¥{band1:,.1f}")
    c4.metric("最大想定（±2σ）", f"±¥{band2:,.1f}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("想定レンジ（2σ）", f"{v['price']-band2:,.0f}〜{v['price']+band2:,.0f}")
    hist = ind.get("hist", float("nan"))
    c2.metric("RSI(14)", f"{ind.get('rsi', float('nan')):.1f}",
              f"MACDヒスト {hist:+.2f}" + ("（プラ転中）" if hist > 0 >= ind.get("hist_prev", 0) else ""),
              delta_color="off")
    c3.metric("損切りライン", f"¥{tgt['stop']:,.1f}" if tgt else "—",
              "監視中" if tgt else None, delta_color="off")
    c4.metric("利確ライン", f"¥{tgt['take']:,.1f}" if tgt else "—",
              "監視中" if tgt else None, delta_color="off")

    st.caption("予測ボラ = EWMA(λ=0.94)による翌日ボラ予測（損切り/利確幅にはEWMAとATR%の大きい方を採用）。"
               "±1σ ≒ 約68%、±2σ ≒ 約95%の確率で収まる統計的な想定幅で、"
               "決算やニュースなどでこれを超えて動くこともあります。")

    with st.expander("📋 全銘柄の一覧を表示"):
        rows = [r for t in tickers if (r := _vol_row(t, held))]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.warning("データを取得できませんでした。")


def render_positions() -> None:
    """保有ポジションと監視ラインの一覧。"""
    ss = st.session_state
    rows = []
    for tk, pos in ss.positions.items():
        if getattr(pos, "shares", 0) <= 0:
            continue
        price = get_price(tk)
        tgt = ss.auto_targets.get(tk)
        pnl = (price - pos.cost_basis) * pos.shares if price else None
        rows.append({
            "銘柄": label_of(tk),
            "株数": pos.shares,
            "取得単価": round(pos.cost_basis, 1),
            "現在値": round(price, 1) if price else None,
            "含み損益": round(pnl, 0) if pnl is not None else None,
            "損切りライン": round(tgt["stop"], 1) if tgt else None,
            "利確ライン": round(tgt["take"], 1) if tgt else None,
        })
    st.markdown("### 📦 監視中のポジション")
    if not rows:
        st.info("保有ポジションはありません。")
        return
    df = pd.DataFrame(rows)
    styled = df.style.map(
        lambda v: "" if pd.isna(v) else (
            f"color:{UP};font-weight:700" if v > 0
            else (f"color:{DOWN};font-weight:700" if v < 0 else "")),
        subset=["含み損益"],
    ).format({"取得単価": "{:,.1f}", "現在値": "{:,.1f}", "含み損益": "{:+,.0f}",
              "損切りライン": "{:,.1f}", "利確ライン": "{:,.1f}"}, na_rep="—")
    st.dataframe(styled, use_container_width=True, hide_index=True)


def render_log() -> None:
    st.markdown("### 🧾 自動売買ログ")
    log = st.session_state.auto_log
    if not log:
        st.info("まだ自動売買はありません。")
        return
    df = pd.DataFrame(log)
    styled = df.style.map(
        lambda v: f"color:{UP};font-weight:700" if v == "買い"
        else (f"color:{DOWN};font-weight:700" if v == "売り" else ""),
        subset=["売買"],
    ).format({"価格": "{:,.1f}"})
    st.dataframe(styled, use_container_width=True, hide_index=True)


def main() -> None:
    init_state()
    ss = st.session_state

    # 決済済み（保有ゼロ）銘柄の古い監視ラインを掃除
    ss.auto_targets = {t: v for t, v in ss.auto_targets.items()
                       if getattr(ss.positions.get(t), "shares", 0) > 0}

    head_l, head_r = st.columns([4, 1])
    head_l.title("🤖 自動売買")
    if head_r.button("📈 デモトレード", type="primary", use_container_width=True):
        try:
            st.switch_page("demo.py")
        except Exception:
            st.warning("demo.py が見つかりません。")

    if yf is None:
        st.error("`yfinance` がインストールされていません。`pip install yfinance` を実行してください。")
        st.stop()

    risk_on, entry_on, _ = render_sidebar()
    params = render_params()
    st.divider()

    # --- サイクル実行 ---
    run_col1, run_col2 = st.columns([1, 3])
    manual = run_col1.button("▶️ 今すぐ1サイクル実行", type="primary", use_container_width=True)
    do_risk = risk_on or manual  # 手動実行時は損切り/利確チェックを必ず行う
    do_entry = entry_on
    if do_risk or do_entry:
        with st.spinner("判定中..."):
            events = run_cycle(do_risk, do_entry, params)
        if events:
            for e in events:
                st.success(e)
        else:
            run_col2.caption(f"✅ {dt.datetime.now().strftime('%H:%M:%S')} 判定完了 — "
                             "損切り/利確・エントリー条件に該当なし")
    else:
        run_col2.caption("稼働トグルをONにするか、ボタンで手動実行してください。")

    st.write("")
    render_vol_table(params["universe"])
    st.write("")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("現金残高", yen(ss.cash))
    held = {t: p for t, p in ss.positions.items() if getattr(p, "shares", 0) > 0}
    c2.metric("保有銘柄数", f"{len(held)} / {params['max_pos']}")
    c3.metric("監視ライン設定数", len(ss.auto_targets))
    pnl_today = today_pnl()
    c4.metric("本日の実現損益", f"{pnl_today:+,.0f}円",
              f"上限 -{yen(params['loss_limit'])}", delta_color="off")

    st.write("")
    render_positions()
    st.write("")
    render_log()


main()
