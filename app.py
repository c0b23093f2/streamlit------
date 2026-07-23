"""
📈 うめぇ〜go株 — UI再設計版（修正）

修正点:
- トップバーの高さを元に戻す
- 銘柄詳細の指標表示を元のカードスタイルに戻す
"""

from __future__ import annotations

import datetime as dt
import sqlite3
import time
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
ACCENT_LIGHT = "#7ca5f0"
INITIAL_CASH = 1_000_000

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

CODE2NAME: dict[str, str] = {}
for _name, _code in JMAP.items():
    CODE2NAME.setdefault(_code, _name)

QUICK_TICKERS = ["7203.T", "9984.T", "6758.T", "8306.T", "9432.T", "6861.T", "8035.T", "7974.T"]
RANK_UNIVERSE = tuple(sorted({c for c in JMAP.values() if not c.startswith("^")}))

# ===========================================================================
# CSS（トップバー高さ修正・指標カードは元のスタイルに戻す）
# ===========================================================================
CSS = """
<style>
/* ===========================================================================
   うめぇ〜go株 PRO ダッシュボードテーマ
   （ライトモード / ダークモード 完全対応版）
=========================================================================== */

/* ===== ライトモード（デフォルト） ===== */
:root {
    --bg: #f5f7fb;
    --card: #ffffff;
    --border: #eef1f6;
    --text-main: #1a2234;
    --text-sub: #8a94a6;
    --blue-1: #1a2a6c;
    --blue-2: #4f7df3;
    --blue-3: #7ca5f0;
    --up: #16c784;
    --down: #ea3943;
    --tag-bg: #f0f4ff;
    --tag-border: #e1e9fb;
    --table-header: #f7f9fd;
    --news-thumb: #dbe6fb;
    --widget-light-bg: #f7f9fd;
    --tint-bg: #f8faff;
    --tint-border: #eef2f6;
}

/* ===== ダークモード（Chrome/OS が暗い場合に自動適用） ===== */
@media (prefers-color-scheme: dark) {
    :root {
        --bg: #0e1117;          /* Streamlit 標準のダーク背景 */
        --card: #262730;        /* ダークモードのカード背景 */
        --border: #3e4049;      /* ダークモードの枠線 */
        --text-main: #f0f2f6;   /* 明るいメイン文字色 */
        --text-sub: #a3a8b8;    /* 明るいサブ文字色 */
        --tag-bg: rgba(79, 125, 243, 0.15);
        --tag-border: #3e4049;
        --table-header: #262730;
        --news-thumb: #1f2128;
        --widget-light-bg: #262730;
        --tint-bg: #262730;
        --tint-border: #3e4049;
    }
}

/* ===== 全体背景 ===== */
html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text-main) !important;
}

.block-container {
    padding-top: 0rem !important;
    padding-bottom: 1rem !important;
    max-width: 1360px !important;
}
#MainMenu, footer { visibility: hidden; }

/* Streamlit標準ヘッダー: ぼかしを無効化し、クリックを下の要素へ通す
   （公開サーバーで白いもやのバーが上部の操作を妨げる問題への対策） */
header[data-testid="stHeader"] {
    background: transparent !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    box-shadow: none;
    height: 0px !important;
    padding: 0px !important;
    pointer-events: none;      /* もや領域のクリックを下のUIへ通す */
}
header[data-testid="stHeader"] > * {
    pointer-events: auto;      /* 右上のメニュー・ツールバー自体は操作可能のまま */
}
div[data-testid="stDecoration"] { display: none; }  /* 上端のグラデーションバーを非表示 */

/* =========================== サイドバー =========================== */
section[data-testid="stSidebar"] {
    background: var(--card) !important;
    border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] > div {
    padding-top: 1.1rem;
}
.brand-box {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 0.4rem 1.1rem 0.4rem;
    margin-bottom: 0.6rem;
    border-bottom: 1px solid var(--border);
}
.brand-icon {
    width: 34px; height: 34px;
    border-radius: 10px;
    background: linear-gradient(145deg, var(--blue-1), var(--blue-2));
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem;
    flex-shrink: 0;
}
.brand-name {
    font-size: 1.02rem;
    font-weight: 800;
    color: var(--text-main);
    letter-spacing: -0.3px;
    line-height: 1.1;
}
.brand-badge {
    display: inline-block;
    margin-top: 2px;
    background: linear-gradient(145deg, var(--blue-2), #2d5bd9);
    color: #fff;
    font-size: 0.55rem;
    font-weight: 800;
    padding: 1px 8px;
    border-radius: 30px;
    letter-spacing: 0.5px;
}

section[data-testid="stSidebar"] div[data-testid="stPageLink"] {
    border-radius: 10px !important;
    margin: 2px 0.4rem !important;
    transition: all 0.14s ease;
}
section[data-testid="stSidebar"] div[data-testid="stPageLink"] a,
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
    padding: 9px 12px !important;
    font-size: 0.86rem !important;
    font-weight: 600 !important;
    color: var(--text-sub) !important;
    border-radius: 10px !important;
}
section[data-testid="stSidebar"] div[data-testid="stPageLink"]:hover {
    background: rgba(79,125,243,0.1);
}
section[data-testid="stSidebar"] div[data-testid="stPageLink"] a:hover {
    color: var(--blue-2) !important;
}
.nav-active div[data-testid="stPageLink"] {
    background: linear-gradient(145deg, var(--blue-2), #4471e8) !important;
}
.nav-active div[data-testid="stPageLink"] a,
.nav-active a[data-testid="stPageLink-NavLink"] {
    color: #ffffff !important;
}

.side-widget {
    margin: 0.9rem 0.4rem 0 0.4rem;
    border-radius: 16px;
    padding: 14px 16px;
    background: linear-gradient(150deg, var(--blue-1) 0%, var(--blue-2) 65%, var(--blue-3) 130%);
    color: #fff;
    box-shadow: 0 8px 22px rgba(79,125,243,0.28);
}
.side-widget .sw-label { font-size: 0.68rem; opacity: 0.85; font-weight: 600; }
.side-widget .sw-value { font-size: 1.3rem; font-weight: 800; margin-top: 2px; }
.side-widget .sw-sub   { font-size: 0.72rem; margin-top: 3px; font-weight: 700; }
.side-widget-light {
    margin: 0.7rem 0.4rem 0 0.4rem;
    border-radius: 16px;
    padding: 14px 16px;
    background: var(--widget-light-bg);
    border: 1px solid var(--border);
}
.side-widget-light .sw-label { font-size: 0.68rem; color: var(--text-sub); font-weight: 700; display:flex; justify-content:space-between; }
.side-widget-light .sw-value { font-size: 1.15rem; font-weight: 800; color: var(--text-main); margin-top: 2px; }
.side-widget-light .sw-sub   { font-size: 0.72rem; margin-top: 3px; font-weight: 700; }

/* =========================== トップバー =========================== */
.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.2rem 0 1.1rem 0;
    flex-wrap: wrap;
}
.topbar-time {
    color: var(--text-sub);
    font-size: 0.72rem;
    font-weight: 600;
    background: var(--card);
    border: 1px solid var(--border);
    padding: 6px 16px;
    border-radius: 30px;
    display: flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
    margin-top: 10px; 
}
.topbar-time .dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--up);
    display: inline-block;
    box-shadow: 0 0 0 3px rgba(22,199,132,0.15);
}
.topbar-search input {
    border-radius: 30px !important;
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    height: 38px !important;
    margin-top: 14px !important;
    color: var(--text-main) !important;
}

/* =========================== グラデーションヒーロー =========================== */
.gradient-header {
    background: linear-gradient(150deg, #1a2a6c 0%, #4f7df3 55%, #6c9cf5 100%);
    border-radius: 20px;
    padding: 20px 28px;
    color: #fff;
    margin-bottom: 1.2rem;
    box-shadow: 0 10px 34px rgba(79,125,243,0.25);
    position: relative;
    overflow: hidden;
}
.gradient-header::after {
    content: '';
    position: absolute;
    top: -50%; right: -20%;
    width: 60%; height: 200%;
    background: radial-gradient(ellipse, rgba(255,255,255,0.08) 0%, transparent 70%);
    pointer-events: none;
}
.gradient-header h2 { margin: 0; font-size: 1.45rem; font-weight: 800; letter-spacing: -0.3px; position: relative; z-index: 1; }
.gradient-header p { margin: 5px 0 0; opacity: 0.88; font-size: 0.84rem; position: relative; z-index: 1; }

/* =========================== カード（統計・指標） =========================== */
.original-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 16px 18px;
    height: 100%;
    box-shadow: 0 2px 12px rgba(20,30,60,.04);
    color: var(--text-main);
}
.original-card .label { font-size: .74rem; color: var(--text-sub); font-weight: 700; }
.original-card .value { font-size: 1.4rem; font-weight: 800; margin-top: 5px; line-height: 1.15; color: var(--text-main); }
.original-card .sub { font-size: .8rem; margin-top: 3px; font-weight: 700; }
.up { color: var(--up); }
.down { color: var(--down); }
.muted { color: var(--text-sub); }

.panel-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 18px 20px;
    box-shadow: 0 2px 14px rgba(20,30,60,.04);
    margin-bottom: 1.1rem;
}
.panel-title { font-size: 0.98rem; font-weight: 800; color: var(--text-main); margin-bottom: 4px; }

/* =========================== 検索結果カード =========================== */
.result-item {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 12px 16px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
    transition: all 0.18s ease;
}
.result-item:hover { border-color: #cfdcf7; box-shadow: 0 6px 18px rgba(79,125,243,0.08); }
.result-item .ri-name { font-weight: 700; font-size: 0.95rem; color: var(--text-main); }
.result-item .ri-code { font-size: 0.75rem; color: var(--text-sub); font-weight: 600; }
.result-item .ri-price { font-weight: 800; font-size: 1.05rem; color: var(--text-main); }
.result-item .ri-actions { display: flex; gap: 6px; }

/* =========================== クイックタグ =========================== */
.quick-tags { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 4px 0; }
.quick-tags .stButton button {
    border-radius: 30px !important;
    padding: 4px 16px !important;
    font-size: 0.75rem !important;
    background: var(--tag-bg) !important;
    border: 1px solid var(--tag-border) !important;
    color: var(--blue-2) !important;
    font-weight: 700 !important;
}
.quick-tags .stButton button:hover { background: #e1eaff !important; border-color: #c6d7fa !important; }

/* =========================== タブ =========================== */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: var(--bg);
    border-radius: 14px;
    padding: 5px;
    border: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
    padding: 6px 18px;
    font-weight: 600;
    font-size: 0.82rem;
    color: var(--text-sub);
    transition: all 0.15s ease;
    background: transparent !important;
}
.stTabs [data-baseweb="tab"]:hover { background: rgba(79,125,243,0.15) !important; }
.stTabs [aria-selected="true"] {
    background: var(--card) !important;
    color: var(--blue-2) !important;
    box-shadow: 0 2px 12px rgba(79,125,243,0.12);
    font-weight: 800;
}

/* =========================== ボタン =========================== */
.stButton > button {
    border-radius: 30px !important;
    font-weight: 700 !important;
    transition: all 0.15s ease !important;
    padding: 0.4rem 1.2rem !important;
    font-size: 0.82rem !important;
}
.stButton > button:active { transform: scale(0.96); }
.stButton > button[kind="primary"] {
    background: linear-gradient(145deg, var(--blue-2), #2d5bd9) !important;
    border: none !important;
    box-shadow: 0 6px 16px rgba(79,125,243,0.3) !important;
    color: #fff !important;
}

/* =========================== データフレーム =========================== */
div[data-testid="stDataFrame"] {
    border-radius: 16px !important;
    overflow: hidden !important;
    border: 1px solid var(--border) !important;
    background: var(--card) !important;
}
div[data-testid="stDataFrame"] thead tr th {
    background: var(--table-header) !important;
    font-weight: 700 !important;
    font-size: 0.7rem !important;
    color: var(--text-main) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.4px !important;
    padding: 8px 12px !important;
}

/* =========================== ポップオーバー =========================== */
div[data-testid="stPopover"] {
    border-radius: 16px !important;
    border: 1px solid var(--border) !important;
    box-shadow: 0 16px 48px rgba(0,0,0,0.10) !important;
    padding: 0.3rem 0 !important;
    background: var(--card) !important;
    backdrop-filter: blur(12px) !important;
}
div[data-testid="stPopover"] a {
    display: flex !important;
    align-items: center;
    gap: 12px;
    padding: 8px 16px !important;
    border-radius: 10px !important;
    transition: all 0.12s !important;
    text-decoration: none !important;
    color: var(--text-main) !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    margin: 2px 6px !important;
}
div[data-testid="stPopover"] a:hover { background: var(--tag-bg) !important; color: var(--blue-2) !important; }

/* =========================== ヒーローカード =========================== */
.hero-card {
    background: linear-gradient(150deg, #1a2a6c 0%, #3f6bea 55%, #6c9cf5 100%);
    border-radius: 18px;
    padding: 18px 22px;
    color: #fff;
    height: 100%;
    box-shadow: 0 10px 30px rgba(63,107,234,0.28);
    position: relative;
    overflow: hidden;
    min-height: 168px;
}
.hero-card::after {
    content: '';
    position: absolute;
    right: -30px; bottom: -60px;
    width: 220px; height: 220px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(255,255,255,0.10) 0%, transparent 70%);
}
.hero-top { display: flex; align-items: center; justify-content: space-between; font-size: 0.8rem; font-weight: 700; opacity: 0.92; position: relative; z-index: 1; }
.hero-value { font-size: 2rem; font-weight: 800; margin-top: 10px; position: relative; z-index: 1; letter-spacing: -0.5px; }
.hero-sub { font-size: 0.82rem; font-weight: 700; margin-top: 6px; position: relative; z-index: 1; opacity: 0.95; }

/* =========================== 統計ミニカード =========================== */
.stat-mini {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 14px 16px;
    height: 100%;
    min-height: 168px;
    box-shadow: 0 2px 12px rgba(20,30,60,.04);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.stat-mini .sm-label { font-size: 0.72rem; color: var(--text-sub); font-weight: 700; }
.stat-mini .sm-value { font-size: 1.28rem; font-weight: 800; color: var(--text-main); margin-top: 8px; }
.stat-mini .sm-sub { font-size: 0.76rem; font-weight: 700; margin-top: 4px; }
.stat-mini .sm-icon { width: 34px; height: 34px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1rem; align-self: flex-end; margin-top: 8px; }
.icon-teal { background: #e3fbf1; }
.icon-green { background: #e5faf0; }
.icon-gold { background: #fff6df; }
.icon-blue { background: #eaf1ff; }

/* =========================== パネルカード =========================== */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 18px !important;
    box-shadow: 0 2px 14px rgba(20,30,60,.04) !important;
    padding: 4px 2px !important;
}
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.panel-head .ph-title { font-size: 0.95rem; font-weight: 800; color: var(--text-main); }
.panel-head .ph-more { font-size: 0.74rem; color: var(--blue-2); font-weight: 700; }

/* =========================== ニュースカード =========================== */
.news-item {
    display: flex; gap: 10px; align-items: flex-start;
    padding: 9px 2px; border-bottom: 1px solid var(--border);
}
.news-item:last-child { border-bottom: none; }
.news-thumb {
    width: 52px; height: 40px; border-radius: 8px; flex-shrink: 0;
    background: var(--news-thumb);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; overflow: hidden;
}
.news-thumb img { width: 100%; height: 100%; object-fit: cover; }
.news-title { font-size: 0.8rem; font-weight: 700; color: var(--text-main); line-height: 1.35; margin: 0; }
.news-meta { font-size: 0.68rem; color: var(--text-sub); margin-top: 3px; font-weight: 600; }

/* =========================== レスポンシブ =========================== */
@media (max-width: 640px) {
    .result-item { flex-direction: column; align-items: stretch; }
    .result-item .ri-actions { justify-content: flex-end; }
    .gradient-header { padding: 14px 18px; }
    .gradient-header h2 { font-size: 1.15rem; }
    .stTabs [data-baseweb="tab-list"] { flex-wrap: wrap; }
}
</style>
"""


# ---------------------------------------------------------------------------
# 共通ユーティリティ
# ---------------------------------------------------------------------------
def normalize_jp(code: str) -> str:
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
    return f'<div class="original-card"><div class="label">{label}</div><div class="value">{value}</div>{sub_html}</div>'


# ---------------------------------------------------------------------------
# データ取得
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
# お気に入り
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
# デモトレード
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
# ページ: ホーム
# ===========================================================================
def _rank_panel(title: str, df_sorted: pd.DataFrame, key: str) -> None:
    """値上がり率/値下がり率ランキングを表示（行選択で自動遷移）"""
    with st.container(border=True):
        # パネルタイトル（見出しとして表示）
        st.markdown(
            f'<div class="panel-head"><span class="ph-title">{title}</span>'
            f'<span class="ph-more">選択してクリックで詳細へ ›</span></div>',
            unsafe_allow_html=True,
        )
        df_show = df_sorted.head(5).reset_index(drop=True)
        
        # st.dataframe の行選択イベントを利用
        event = st.dataframe(
            df_show[["銘柄名", "yahoo_code", "現在値", "前日比率"]],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",          # 選択で自動リラン
            selection_mode="single-row", # 単一行のみ選択可
            key=key,
            column_config={
                "銘柄名": st.column_config.TextColumn("銘柄名"),
                "yahoo_code": st.column_config.TextColumn("コード", width="small"),
                "現在値": st.column_config.NumberColumn("現在値", format="%.1f"),
                "前日比率": st.column_config.NumberColumn("前日比（%）", format="%+.2f"),
            },
        )
        
        # 行が選択されたら銘柄詳細へ遷移
        try:
            rows = list(event.selection.rows)
        except Exception:
            rows = []
            
        if rows:
            # 戻ったときに再遷移しないよう選択状態をクリア
            st.session_state.pop(key, None)
            # 選択行の銘柄コードを取得して遷移
            code = str(df_show.iloc[rows[0]]["yahoo_code"])
            open_detail(code)
def page_home() -> None:
    ss = st.session_state
    ss.setdefault("hist", [])
    ss.setdefault("_res", [])
    init_trade_state()
    # ---------------------------------------------------------------
    # 検索バー
    # ---------------------------------------------------------------
    col1, col2, col3 = st.columns([4, 1, 1])
    
    # 検索入力欄
    kw = col1.text_input(
        "検索キーワード",
        placeholder="例: 7203, トヨタ, 9984.T, 日経平均",
        label_visibility="collapsed",
        key="skw"
    )
    
    # 検索結果が複数ある場合は候補の選択ボックスを表示
    if kw and len(kw) >= 2:  # 2文字以上で検索開始（負荷軽減）
        res = search_stock(kw)
        if len(res) > 1:
            # 「トヨタ自動車 (7203.T)」形式の候補リストを作成
            options = {f"{r['name']} ({r['code']})": r['code'] for r in res}
            selected_label = col2.selectbox(
                "候補から選択",
                options=list(options.keys()),
                index=0,
                label_visibility="collapsed",
                key="search_select"
            )
            selected_code = options.get(selected_label)
            if selected_code:
                if col3.button("選択", type="primary", use_container_width=True):
                    st.session_state["_sr"] = selected_code
                    st.rerun()
        elif len(res) == 1:
            # 候補が1件だけの場合は銘柄名を表示し、すぐ移動できるボタンを出す
            col2.caption(f"✅ {res[0]['name']}")
            if col3.button("前往", type="primary", use_container_width=True):
                st.session_state["_sr"] = res[0]['code']
                st.rerun()
        else:
            col2.caption("")

    # 検索ボタン（従来の検索動作）
    go = col3.button("🔍 検索", key="search_btn", use_container_width=True)

    # 検索履歴クリックやトップバー検索からの引き継ぎ
    sr = ss.pop("_sr", "")
    if sr:
        kw, go = sr, True

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
    if ss["_res"]:
        st.markdown("### 📋 検索結果")
        for idx, r in enumerate(ss["_res"]):
            code = r["code"]
            cu = cur_of(code)
            price_str = f"{cu}{r['price']:,.2f}" if r.get("price") else "N/A"

            col_a, col_b, col_c, col_d, col_e = st.columns([2.5, 1.2, 1.5, 0.9, 0.9])
            with col_a:
                st.markdown(f'<span class="ri-name">{r["name"]}</span>', unsafe_allow_html=True)
                if r.get("sector"):
                    st.caption(f"🏷️ {r['sector']}")
            col_b.markdown(f'<span class="ri-code">{code}</span>', unsafe_allow_html=True)
            col_c.markdown(f'<span class="ri-price">{price_str}</span>', unsafe_allow_html=True)
            with col_d:
                if st.button("📊 詳細", key=f"dt_{code}_{idx}", use_container_width=True):
                    open_detail(code)
            with col_e:
                fav_toggle_button(code, r["name"], key=f"fv_{code}_{idx}")
        st.divider()

    # ---------------------------------------------------------------
    # 資産サマリー（ヒーローカード）＋ 統計ミニカード４枚
    # ---------------------------------------------------------------
    holdings_value = 0.0
    n_positions = 0
    annual_div = 0.0
    for tk, pos in ss.positions.items():
        if pos.shares:
            n_positions += 1
            p = get_price(tk)
            if p:
                holdings_value += pos.shares * p
                dy = get_info(tk).get("dividendYield")
                if isinstance(dy, (int, float)):
                    annual_div += pos.shares * p * (dy / 100 if dy > 1 else dy)
    total = ss.cash + holdings_value
    pnl = total - INITIAL_CASH
    pct = pnl / INITIAL_CASH * 100 if INITIAL_CASH else 0.0
    cls = "up" if pnl > 0 else ("down" if pnl < 0 else "muted")
    arrow = "▲" if pnl > 0 else ("▼" if pnl < 0 else "—")

    hc, s1, s2, s3 = st.columns([2.1, 1, 1, 1])
    with hc:
        st.markdown(
            '<div class="hero-card">'
            '<div class="hero-top"><span>💼 資産サマリー（デモ口座）</span></div>'
            f'<div class="hero-value">{yen(total)}</div>'
            f'<div class="hero-sub">累計損益 {arrow} {yen(abs(pnl))}（{pct:+.2f}%）</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with s1:
        st.markdown(
            '<div class="stat-mini"><div class="sm-label">保有銘柄数</div>'
            f'<div class="sm-value">{n_positions} 銘柄</div>'
            '<div class="sm-icon icon-teal">📦</div></div>',
            unsafe_allow_html=True,
        )
    with s2:
        st.markdown(
            '<div class="stat-mini"><div class="sm-label">評価損益</div>'
            f'<div class="sm-value {cls}">{arrow} {yen(abs(pnl))}</div>'
            f'<div class="sm-sub {cls}">{pct:+.2f}%</div>'
            '<div class="sm-icon icon-green">💹</div></div>',
            unsafe_allow_html=True,
        )
    with s3:
        st.markdown(
            '<div class="stat-mini"><div class="sm-label">買付余力（現金）</div>'
            f'<div class="sm-value">{yen(ss.cash)}</div>'
            '<div class="sm-icon icon-blue">👛</div></div>',
            unsafe_allow_html=True,
        )
    st.write("")
    if annual_div > 0:
        st.caption(f"🎁 保有銘柄の年間配当金（予想・実データより概算）: {yen(annual_div)}")
        st.write("")

    # ---------------------------------------------------------------
    # 日経平均チャート ＋ 値上がり／値下がりランキング
    # ---------------------------------------------------------------
    left, right1, right2 = st.columns([1.7, 1, 1])

    with left:
        with st.container(border=True):
            st.markdown('<div class="panel-head"><span class="ph-title">📈 日経平均チャート</span></div>',
                        unsafe_allow_html=True)
            period_map = {
                "1日": ("1d", "5m"), "1週間": ("5d", "30m"), "1ヶ月": ("1mo", "1d"),
                "3ヶ月": ("3mo", "1d"), "1年": ("1y", "1wk"),
            }
            p_label = st.radio("期間", list(period_map.keys()), index=0, horizontal=True,
                                key="n225_period", label_visibility="collapsed")
            period, interval = period_map[p_label]
            n_df = get_history("^N225", period, interval)
            if n_df.empty and period != "5d":
                n_df = get_history("^N225", "5d", "1d")
            if n_df.empty:
                st.info("日経平均のデータを取得できませんでした。")
            else:
                last = float(n_df["Close"].iloc[-1])
                base = float(n_df["Close"].iloc[0])
                d = last - base
                p_pct = d / base * 100 if base else 0.0
                cls_n = "up" if d >= 0 else "down"
                arrow_n = "▲" if d >= 0 else "▼"
                st.markdown(
                    f'<div style="font-size:1.7rem;font-weight:800;color:var(--text-main);margin:2px 0 0 2px;">{last:,.2f}'
                    f'<span class="{cls_n}" style="font-size:0.95rem;font-weight:800;margin-left:10px;">'
                    f'{arrow_n} {d:+,.2f}（{p_pct:+.2f}%）</span></div>',
                    unsafe_allow_html=True,
                )
                try:
                    import plotly.graph_objects as go
                    fig = go.Figure(go.Scatter(
                        x=n_df.index, y=n_df["Close"], mode="lines", line=dict(color=UP, width=2),
                        fill="tozeroy", fillcolor="rgba(22,199,132,0.08)",
                    ))
                    fig.update_yaxes(range=[float(n_df["Close"].min()) * 0.998, float(n_df["Close"].max()) * 1.002])
                    fig.update_layout(
                        height=260, margin=dict(l=0, r=0, t=8, b=0),
                        template="plotly_white", showlegend=False, hovermode="x unified",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    st.line_chart(n_df["Close"], height=260)
                st.caption(
                    f"始値 {n_df['Open'].iloc[0]:,.2f}　高値 {n_df['High'].max():,.2f}　"
                    f"安値 {n_df['Low'].min():,.2f}　直近終値 {last:,.2f}"
                )

    with st.spinner("ランキングデータを取得しています…"):
        rank = get_batch_quotes(RANK_UNIVERSE, period="5d")

    if not rank.empty:
        with right1:
            _rank_panel("📈 値上がり率ランキング", rank.sort_values("前日比率", ascending=False), "rank_up")
        with right2:
            _rank_panel("📉 値下がり率ランキング", rank.sort_values("前日比率", ascending=True), "rank_down")

        with st.expander("🔥 出来高ランキングも見る", expanded=False):
            df_show = rank.sort_values("出来高", ascending=False).head(15).reset_index(drop=True)
            event = st.dataframe(
                df_show[["銘柄名", "yahoo_code", "現在値", "前日比率", "出来高", "直近推移"]],
                use_container_width=True, hide_index=True,
                on_select="rerun", selection_mode="single-row", key="rank_vol",
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
    else:
        with right1:
            st.info("ランキングデータを取得できませんでした。")

    st.write("")

    # ---------------------------------------------------------------
    # 保有銘柄一覧（デモ口座）＋ 最新ニュース
    # ---------------------------------------------------------------
    hold_col, news_col = st.columns([1.7, 1])

    with hold_col:
        with st.container(border=True):
            st.markdown('<div class="panel-head"><span class="ph-title">📦 保有銘柄一覧（デモ口座）</span></div>',
                        unsafe_allow_html=True)
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
                    "銘柄名": CODE2NAME.get(tk, tk), "コード": tk, "保有数": pos.shares,
                    "平均取得単価": round(pos.cost_basis, 1), "現在値": round(p, 1),
                    "評価額": round(mkt, 0), "評価損益": round(mkt - cost, 0),
                    "評価損益率%": round((mkt - cost) / cost * 100, 2) if cost else 0.0,
                })
            if rows:
                hdf = pd.DataFrame(rows)
                styled = hdf.style.map(
                    lambda v: f"color:{UP};font-weight:700" if isinstance(v, (int, float)) and v > 0
                    else (f"color:{DOWN};font-weight:700" if isinstance(v, (int, float)) and v < 0 else ""),
                    subset=["評価損益", "評価損益率%"],
                ).format({"平均取得単価": "{:,.1f}", "現在値": "{:,.1f}", "評価額": "{:,.0f}",
                          "評価損益": "{:+,.0f}", "評価損益率%": "{:+.2f}"})
                st.dataframe(styled, use_container_width=True, hide_index=True)
            else:
                st.info("保有銘柄はまだありません。「💼 デモトレード」から取引できます。")
            st.page_link(PG_TRADE, label="もっと見る（デモトレードへ） ›")

    with news_col:
        with st.container(border=True):
            st.markdown('<div class="panel-head"><span class="ph-title">📰 最新ニュース</span></div>',
                        unsafe_allow_html=True)
            news_tickers = [tk for tk in ss.positions if ss.positions[tk].shares] or QUICK_TICKERS[:3]
            items = []
            for tk in news_tickers[:3]:
                items.extend(get_news(tk)[:3])
            if not items:
                st.info("📰 ニュースはありません")
            else:
                for n in items[:5]:
                    c = n.get("content", {}) or {}
                    title = c.get("title", "")
                    if not title:
                        continue
                    link = (c.get("canonicalUrl", {}) or {}).get("url", "") or ""
                    provider = (c.get("provider", {}) or {}).get("displayName", "")
                    pub = c.get("pubDate", "")
                    thumb = ""
                    try:
                        thumb = (c.get("thumbnail", {}) or {}).get("resolutions", [{}])[0].get("url", "")
                    except Exception:
                        thumb = ""
                    thumb_html = f'<img src="{thumb}"/>' if thumb else "📰"
                    title_html = f'<a href="{link}" target="_blank" style="text-decoration:none;color:inherit;">{title}</a>' if link else title
                    st.markdown(
                        f'<div class="news-item"><div class="news-thumb">{thumb_html}</div>'
                        f'<div><p class="news-title">{title_html}</p>'
                        f'<div class="news-meta">{provider}　・　{pub}</div></div></div>',
                        unsafe_allow_html=True,
                    )


# ===========================================================================
# ページ: 銘柄詳細
# ===========================================================================
def page_detail() -> None:
    ss = st.session_state
    
    with st.container():
        c1, c2 = st.columns([4, 1])
        
        # 銘柄入力欄
        code_in = c1.text_input(
            "証券コード・銘柄名",
            placeholder="例: 7203.T, トヨタ, 9984.T, ^N225",
            label_visibility="collapsed",
            key="detail_kw",
            help="4桁の数字（例: 7203）、.T付きコード（例: 7203.T）、または銘柄名（例: トヨタ）を入力してください"
        )
        
        if c2.button("表示", type="primary", use_container_width=True) and code_in:
            k = code_in.strip()
            target_code = None
            
            # 1. 日本語名の辞書に載っているか確認
            if k in JMAP:
                target_code = JMAP[k]
            # 2. 4桁の数字なら日本株コードとして扱う
            elif k.isdigit() and len(k) == 4:
                target_code = f"{k}.T"  # .T を自動補完
            # 3. .T付きコード・指数コードはそのまま利用
            elif k.upper().endswith(".T") or k.startswith("^"):
                target_code = k.upper()
                
            # 4. 候補コードのデータが実在するか検証
            if target_code:
                @st.cache_data(ttl=10, show_spinner=False)
                def validate_price(code):
                    if yf is None: return False
                    try:
                        data = yf.Ticker(code).history(period="1d")
                        return not data.empty
                    except:
                        return False
                
                if validate_price(target_code):
                    ss["sym"] = target_code
                    st.rerun()
                else:
                    # データが存在しない場合（例: 0000）
                    st.error(f"❌ 入力エラー：'{k}' はデータを取得できない、または存在しない銘柄です。")
                    ss["sym"] = None
            else:
                # 辞書にない入力にはコード入力を促す案内を表示
                st.info(f"💡 「{k}」は現在の辞書に登録されていません。確実に検索するには、**4桁の証券コード**（例：7203.T）をご利用ください。")
                ss["sym"] = None

    sym = ss.get("sym")
    if not sym:
        # 未選択時はコード入力を案内
        st.info("💡 **4桁の証券コード**（例: 7203.T）を入力して「表示」をクリックすると、すべての銘柄を検索できます。")
        return

    # ---- 銘柄名の解決 ----
    info = get_info(sym)
    
    # yfinance公式の銘柄名を優先し、取得できない場合のみ辞書（CODE2NAME）を参照
    if info and (info.get("longName") or info.get("shortName")):
        name = info.get("longName") or info.get("shortName") or sym
    else:
        name = CODE2NAME.get(sym, sym)
        
    cu = cur_of(sym)
    price = get_price(sym)
    # ===============================================

    # 銘柄ヘッダー
    h1, h2 = st.columns([3, 1])
    with h1:
        st.markdown(f"## 📊 {name}")
        st.caption(f"コード: {sym}")
    with h2:
        fav_toggle_button(sym, name, key=f"fv_detail_{sym}")
        
    # 価格と前日比
    hist5 = get_history(sym, "5d", "1d")
    chg = pct = None
    if price is not None and len(hist5) >= 2:
        prev = float(hist5["Close"].iloc[-2])
        if prev > 0:
            chg = price - prev
            pct = chg / prev * 100

    # ===== 元のカードスタイルで指標表示（4列×2行） =====
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

    # タブ
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
    period = st.radio(
        "期間",
        ["1mo", "3mo", "6mo", "1y", "5y"],
        format_func=lambda p: {"1mo": "1ヶ月", "3mo": "3ヶ月", "6mo": "6ヶ月", "1y": "1年", "5y": "5年"}[p],
        index=1,
        horizontal=True,
        key="chart_period"
    )
    
    o1, o2 = st.columns(2)
    overlays = o1.multiselect(
        "価格チャートに重ねる",
        ["移動平均(25/75)", "ボリンジャーバンド"],
        default=["移動平均(25/75)"],
        key="ovl"
    )
    panels = o2.multiselect(
        "サブパネル",
        ["出来高", "RSI(14)", "MACD"],
        default=["RSI(14)", "MACD"],
        key="pnl"
    )

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
    fig = make_subplots(
        rows=len(rows), cols=1, shared_xaxes=True, vertical_spacing=0.08,  # サブパネル間の余白
        row_heights=[h / s for h in row_h],
        subplot_titles=[("" if r == "price" else r) for r in rows]
    )

    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="株価",
            increasing_line_color=UP, decreasing_line_color=DOWN
        ),
        row=1, col=1
    )
    
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

    fig.update_layout(
        height=420 + 120 * (len(rows) - 1),
        margin=dict(l=0, r=0, t=18, b=0),
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
        hovermode="x unified"
    )
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
    <div style="background:var(--tint-bg);border-radius:16px;padding:24px;border:1px solid var(--tint-border);margin-bottom:12px;color:var(--text-main);">
        <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap;">
            <div>
                <div style="font-size:0.7rem;color:var(--text-sub);font-weight:600;text-transform:uppercase;letter-spacing:0.4px;">{name}</div>
                <div style="font-size:1.8rem;font-weight:700;color:var(--text-main);">{cu}{price:,.0f}</div>
            </div>
            <div style="flex:1;min-width:120px;">
                <div style="font-size:1.8rem;letter-spacing:2px;color:var(--text-main);">{t['stars']}</div>
                <span style="display:inline-block;padding:4px 18px;border-radius:30px;background-color:{t['color']};color:white;font-weight:bold;font-size:0.9rem;">
                    {t['emoji']} {t['judgment']}
                </span>
            </div>
            <div style="display:flex;gap:28px;flex-wrap:wrap;">
                <div><div style="font-size:0.6rem;color:var(--text-sub);font-weight:600;text-transform:uppercase;letter-spacing:0.4px;">RSI</div><div style="font-size:1.1rem;font-weight:700;color:var(--text-main);">{t['rsi']:.1f}</div></div>
                <div><div style="font-size:0.6rem;color:var(--text-sub);font-weight:600;text-transform:uppercase;letter-spacing:0.4px;">MACD</div><div style="font-size:1.1rem;font-weight:700;color:var(--text-main);">{t['macd']:+.2f}</div></div>
                <div><div style="font-size:0.6rem;color:var(--text-sub);font-weight:600;text-transform:uppercase;letter-spacing:0.4px;">MA25</div><div style="font-size:1.1rem;font-weight:700;color:var(--text-main);">{cu}{t['sma25']:,.0f}</div></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.info(t["comment"])
    
    with st.expander("判定の内訳", expanded=False):
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
                             line=dict(dash="dash", color="#ea3943", width=2)))
    fig.update_layout(
        title="株価・25日移動平均・30営業日予測",
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", y=1.08),
        height=440,
        margin=dict(l=0, r=0, t=60, b=0)
    )
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
    
    st.markdown("### 📅 次回決算予定日")
    if dates:
        cols = st.columns(max(len(dates), 1))
        for i, d in enumerate(dates):
            cols[i].markdown(card_html("決算日", d), unsafe_allow_html=True)
    else:
        st.info("📌 決算日情報なし")

    st.markdown("### 📊 過去の決算（四半期）")
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
    
    st.caption(f"💰 現金残高: {yen(st.session_state.cash)}")
    
    c1, c2 = st.columns(2)
    side = c1.radio("売買", ["買い", "売り"], horizontal=True, key=f"side_{sym}")
    shares = c2.number_input("株数", min_value=1, value=100, step=100, key=f"sh_{sym}")
    st.caption(f"概算約定額: **{yen(shares * price)}**")
    
    if st.button("🚀 注文を出す", type="primary", use_container_width=True, key=f"ord_{sym}"):
        ok, msg = execute_trade(sym, side, int(shares), price)
        if ok:
            st.success(f"✅ {msg}")
            st.rerun()
        else:
            st.error(f"❌ {msg}")
    
    st.divider()
    st.page_link(PG_TRADE, label="💼 ポートフォリオ全体を見る（デモトレード）")


# ===========================================================================
# ページ: お気に入り銘柄
# ===========================================================================
def page_favorites() -> None:
    st.markdown(
        '<div class="gradient-header">'
        '<h2>⭐ お気に入り銘柄</h2>'
        '<p>登録銘柄はこのPCの data/favorites.db に保存され、アプリを閉じても残ります</p>'
        '</div>',
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

    # サマリー（元のカードスタイルで表示）
    chg = pd.to_numeric(data.get("前日比率"), errors="coerce")
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(card_html("登録銘柄", f"{len(data)}件"), unsafe_allow_html=True)
    col2.markdown(card_html("値上がり", f"{int((chg > 0).sum())}件"), unsafe_allow_html=True)
    col3.markdown(card_html("値下がり", f"{int((chg < 0).sum())}件"), unsafe_allow_html=True)
    col4.markdown(card_html("株価未取得", f"{int(chg.isna().sum())}件"), unsafe_allow_html=True)

    # フィルター
    c1, c2, c3 = st.columns([2.5, 1.5, 1])
    keyword = c1.text_input("🔍 検索", placeholder="銘柄名・コード・メモ", label_visibility="collapsed")
    sort_option = c2.selectbox(
        "並び順",
        ["登録が新しい順", "値上がり率が高い順", "値下がり率が大きい順", "銘柄名順"],
        label_visibility="collapsed"
    )
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
        display,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="fav_table",
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
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### {sel['name']}")
                st.caption(f"コード: {code}")
            with col2:
                if st.button("📊 銘柄詳細を開く", use_container_width=True, key=f"open_{code}"):
                    open_detail(code)
            
            note = st.text_area(
                "📝 メモ",
                value=str(sel.get("note", "") or ""),
                placeholder="例：決算後の値動きを確認する",
                max_chars=500,
                key=f"note_{code}"
            )
            
            b1, b2 = st.columns(2)
            if b1.button("💾 メモを保存", type="primary", use_container_width=True, key=f"sv_{code}"):
                fav_note(code, note)
                st.toast("メモを保存しました。", icon="✅")
                st.rerun()
            
            confirm = b2.checkbox("削除を確認", key=f"cf_{code}")
            if b2.button("🗑️ お気に入りから削除", use_container_width=True, disabled=not confirm, key=f"rm_{code}"):
                fav_remove(code)
                st.toast("削除しました。", icon="🗑️")
                st.rerun()

    csv = display.drop(columns=["直近推移"], errors="ignore")
    st.download_button(
        "📥 CSVで保存",
        data=csv.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"お気に入り銘柄_{dt.datetime.now():%Y%m%d}.csv",
        mime="text/csv"
    )
    
    with st.expander("⚠️ その他の操作", expanded=False):
        st.warning("すべて削除すると元に戻せません。")
        ok_all = st.checkbox("すべてのお気に入りを削除することを確認しました")
        if st.button("🗑️ すべて削除", disabled=not ok_all):
            n = fav_clear()
            st.toast(f"{n}件削除しました。", icon="🗑️")
            st.rerun()


# ===========================================================================
# ページ: 指標解説
# ===========================================================================
GLOSSARY = pd.DataFrame({
    "分類": ["ファンダメンタル"] * 7 + ["テクニカル"] * 18,
    "指標": ["PER", "PBR", "ROE", "EPS", "BPS", "配当利回り", "時価総額",
             "移動平均線", "RSI", "MACD", "ボリンジャーバンド", "出来高", "ゴールデンクロス", "デッドクロス",
             "KDJ", "AR", "VR", "OSC", "移動平均乖離率", "W%R", "CCI", "DMI/ADX", "PSY", "モメンタム", "一目均衡表"],
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
        "ストキャスティクスを応用した短期売買指標（K・D・Jの3線）",
        "一定期間の値動きから買い人気の強さを測る指標",
        "上昇日と下落日の出来高の比率",
        "終値と移動平均線の差で相場の勢いを見る指標",
        "株価が移動平均線からどれだけ離れているかの割合",
        "期間中の高値・安値に対する終値の位置（ウィリアムズ%R）",
        "平均的な価格からの偏差で過熱感を測る指標",
        "トレンドの方向（+DI/-DI）と強さ（ADX）を測る指標",
        "一定期間のうち上昇した日の割合（投資家心理）",
        "現在値とN日前の価格差で上昇・下落の勢いを測る指標",
        "転換線・基準線・雲などで相場を総合的に見る日本発の指標",
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
        "KがDを上抜けたら買い。Jが0以下で売られすぎ、100以上で買われすぎ。",
        "150以上は過熱、70以下は人気離散で反発が近いとされる。",
        "70%以下は底値圏、300%以上は買われすぎの目安。",
        "0より上なら上昇圧力、下なら下落圧力。差の拡大・縮小で勢いを判断。",
        "±5%を超えると行き過ぎで、反動（逆方向の動き）が出やすい。",
        "-20より上は買われすぎ、-80より下は売られすぎ。",
        "+100超は買われすぎ、-100未満は売られすぎの目安。",
        "ADXが25以上でトレンド発生。+DIが-DIより上なら上昇トレンド。",
        "75%以上は強気過剰（反落注意）、25%以下は弱気過剰（反発期待）。",
        "0より上で上昇の勢い、0より下で下落の勢いを示す。",
        "株価が雲の上なら強気、雲の下なら弱気、雲の中はもみ合い。",
    ],
})


def page_glossary() -> None:
    st.markdown(
        '<div class="gradient-header">'
        '<h2>📚 株式指標一覧と解説</h2>'
        '<p>株式投資でよく使用される代表的な指標を一覧で確認できます</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    
    cat = st.radio("📂 分類で絞り込み", ["すべて", "ファンダメンタル", "テクニカル"], horizontal=True)
    df = GLOSSARY if cat == "すべて" else GLOSSARY[GLOSSARY["分類"] == cat]
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.info(
        "**ファンダメンタル分析**：企業の業績や財務状況、将来性などを分析し、企業本来の価値を評価する分析方法です。\n\n"
        "**テクニカル分析**：過去の株価や出来高などの値動きを分析し、今後の株価の動きを予測する分析方法です。"
    )
    st.caption("テクニカル指標の実際の動きは、銘柄詳細の「📈 チャート」「🤖 テクニカル判定」タブで確認できます。")


# ===========================================================================
# 自動売買（デモ）
# ===========================================================================
AUTO_STRATEGIES = [
    "ゴールデンクロス（SMA5/25）",
    "RSI逆張り（30/70）",
    "総合シグナル（テクニカル判定）",
    "総合診断（全指標スコア）",
    "指値・逆指値",
]

SIG_LABEL = {"buy": "🟢 買いシグナル", "sell": "🔴 売りシグナル", "hold": "⚪ 待機中"}


def init_auto_state() -> None:
    ss = st.session_state
    ss.setdefault("auto_rules", [])
    ss.setdefault("auto_log", [])
    ss.setdefault("auto_rule_seq", 1)
    ss.setdefault("auto_group_seq", 1)


def resolve_trade_symbol(kw: str) -> str:
    """『7203』『トヨタ』『AAPL』などをティッカーに解決する"""
    k = (kw or "").strip()
    if not k:
        return ""
    if k in JMAP:
        return JMAP[k]
    for name, code in JMAP.items():
        if k in name:
            return code
    return normalize_jp(k)


def _auto_signal(rule: dict) -> tuple[str, str]:
    """ルールを評価して ('buy' | 'sell' | 'hold', 説明) を返す"""
    tk = rule["ticker"]
    price = get_price(tk)
    if price is None:
        return "hold", "価格取得不可"

    strat = rule["strategy"]
    if strat == "指値・逆指値":
        if rule.get("buy_below") and price <= rule["buy_below"]:
            return "buy", f"現在値 {price:,.1f} ≤ 指値 {rule['buy_below']:,.1f}"
        if rule.get("sell_above") and price >= rule["sell_above"]:
            return "sell", f"現在値 {price:,.1f} ≥ 逆指値 {rule['sell_above']:,.1f}"
        return "hold", f"現在値 {price:,.1f}（条件未達）"

    df = get_history(tk, "6mo", "1d")
    if len(df) < 30:
        return "hold", "データ不足"
    df = add_indicators(df)

    if strat == "ゴールデンクロス（SMA5/25）":
        s5, s25 = df["SMA5"], df["SMA25"]
        if s5.dropna().empty or len(s5) < 2:
            return "hold", "データ不足"
        now_up = s5.iloc[-1] > s25.iloc[-1]
        prev_up = s5.iloc[-2] > s25.iloc[-2]
        if now_up and not prev_up:
            return "buy", "SMA5がSMA25を上抜け（ゴールデンクロス）"
        if not now_up and prev_up:
            return "sell", "SMA5がSMA25を下抜け（デッドクロス）"
        return "hold", "クロス発生なし"

    if strat == "RSI逆張り（30/70）":
        rsi = float(df["RSI"].iloc[-1])
        if rsi < 30:
            return "buy", f"RSI {rsi:.1f} < 30（売られすぎ）"
        if rsi > 70:
            return "sell", f"RSI {rsi:.1f} > 70（買われすぎ）"
        return "hold", f"RSI {rsi:.1f}（中立）"

    if strat == "総合診断（全指標スコア）":
        diags = _diagnose_indicators(add_extra_indicators(df))
        if not diags:
            return "hold", "データ不足"
        v = _overall_verdict(diags)
        base = f"買い{v['buy_n']}・売り{v['sell_n']}（スコア {v['score']:+d}・{v['label']}）"
        # 買いが全体的に優勢なら買い、売り指標が増えてきたら早めに売り
        if v["score"] >= 3:
            return "buy", "買い指標が優勢: " + base
        if v["score"] <= -2:
            return "sell", "売り指標が増加: " + base
        return "hold", base

    # 総合シグナル（テクニカル判定）
    t = technical_judgment(df)
    score = sum(t["checks"].values())
    if score >= 2:
        return "buy", f"買いシグナル {score}/3（{t['judgment']}）"
    if score == 0:
        return "sell", f"買いシグナル 0/3（{t['judgment']}）"
    return "hold", f"買いシグナル {score}/3（様子見）"


def _auto_log(rule: dict, action: str, detail: str) -> None:
    st.session_state["auto_log"].insert(0, {
        "日時": dt.datetime.now().strftime("%m-%d %H:%M:%S"),
        "銘柄": label_of(rule["ticker"]),
        "戦略": rule["strategy"],
        "アクション": action,
        "内容": detail,
    })
    st.session_state["auto_log"] = st.session_state["auto_log"][:100]


def run_auto_rules(force: bool = False) -> list[str]:
    """有効な全ルールを評価し、シグナルが変化した瞬間だけ自動発注する。

    毎回の画面更新で全ルールを再計算すると重いため、評価は60秒間隔に制限する
    （「今すぐ判定」ボタンやルール追加直後は即時評価）。
    """
    init_trade_state()
    init_auto_state()
    ss = st.session_state
    now_ts = time.time()
    if not force and now_ts - ss.get("auto_last_eval", 0.0) < 60:
        return []
    ss["auto_last_eval"] = now_ts
    executed: list[str] = []
    for rule in ss["auto_rules"]:
        if not rule.get("enabled", True):
            continue
        sig, detail = _auto_signal(rule)
        rule["last_detail"] = detail
        rule["last_checked"] = dt.datetime.now().strftime("%H:%M:%S")
        prev_sig = rule.get("last_signal", "hold")
        rule["last_signal"] = sig
        # シグナルが「変化した瞬間」のみ発注（毎回の再実行での連続発注を防ぐ）
        if sig == "hold" or sig == prev_sig:
            continue
        tk = rule["ticker"]
        price = get_price(tk)
        if price is None:
            continue
        if sig == "buy":
            ok, msg = execute_trade(tk, "買い", int(rule["shares"]), price)
        else:
            pos = ss.positions.get(tk)
            hold_shares = pos.shares if pos else 0
            if hold_shares <= 0:
                _auto_log(rule, "スキップ", f"{detail} → 保有なしのため売却せず")
                continue
            ok, msg = execute_trade(tk, "売り", int(min(rule["shares"], hold_shares)), price)
        if ok:
            ss.trades[-1]["売買"] += "🤖"
            _auto_log(rule, "買い" if sig == "buy" else "売り", f"{detail} → {msg}")
            executed.append(msg)
        else:
            _auto_log(rule, "失敗", f"{detail} → {msg}")
    return executed


# ===========================================================================
# ページ: デモトレード
# ===========================================================================
def _stat_strip_html(ticker: str, price: float) -> str:
    """moomoo風の価格スタッツ帯（前日終値・始値・高値・安値・出来高・52週レンジ）"""
    cu = cur_of(ticker)
    d5 = get_history(ticker, "5d", "1d")
    info = get_info(ticker)

    def _f(v, fmt="{:,.1f}"):
        return fmt.format(v) if isinstance(v, (int, float)) and pd.notna(v) else "—"

    prev = float(d5["Close"].iloc[-2]) if len(d5) >= 2 else None
    o = float(d5["Open"].iloc[-1]) if len(d5) else None
    hi = float(d5["High"].iloc[-1]) if len(d5) else None
    lo = float(d5["Low"].iloc[-1]) if len(d5) else None
    vol = float(d5["Volume"].iloc[-1]) if len(d5) and "Volume" in d5.columns else None
    hi52, lo52 = info.get("fiftyTwoWeekHigh"), info.get("fiftyTwoWeekLow")

    items = [
        ("前日終値", f"{cu}{_f(prev)}", "var(--text-main)"),
        ("始値", f"{cu}{_f(o)}", "var(--text-main)"),
        ("高値", f"{cu}{_f(hi)}", UP),
        ("安値", f"{cu}{_f(lo)}", DOWN),
        ("出来高", _f(vol, "{:,.0f}"), "var(--text-main)"),
        ("52週高値", f"{cu}{_f(hi52)}", "var(--text-main)"),
        ("52週安値", f"{cu}{_f(lo52)}", "var(--text-main)"),
    ]
    cells = "".join(
        f'<div style="min-width:86px;">'
        f'<div style="font-size:0.62rem;color:var(--text-sub);font-weight:700;">{label}</div>'
        f'<div style="font-size:0.85rem;font-weight:800;color:{color};">{value}</div></div>'
        for label, value, color in items
    )
    return (
        f'<div style="display:flex;flex-wrap:wrap;gap:14px 18px;padding:10px 14px;'
        f'background:var(--tint-bg);border:1px solid var(--tint-border);border-radius:12px;'
        f'margin-bottom:8px;">{cells}</div>'
    )


def add_extra_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """KDJ / AR / VR / OSC を追加計算する（add_indicators 適用後の df を渡す）"""
    out = df.copy()
    # --- KDJ（9,3,3）: ストキャスティクスの派生。K/DのクロスとJの行き過ぎを見る ---
    low9 = out["Low"].rolling(9).min()
    high9 = out["High"].rolling(9).max()
    rng = (high9 - low9).replace(0, float("nan"))
    rsv = (out["Close"] - low9) / rng * 100
    out["K"] = rsv.ewm(com=2, adjust=False).mean()
    out["D"] = out["K"].ewm(com=2, adjust=False).mean()
    out["J"] = 3 * out["K"] - 2 * out["D"]
    # --- AR（26日）: 人気指標。(高値-始値)の合計 ÷ (始値-安値)の合計 ×100 ---
    n = 26
    ar_den = (out["Open"] - out["Low"]).rolling(n).sum().replace(0, float("nan"))
    out["AR"] = (out["High"] - out["Open"]).rolling(n).sum() / ar_den * 100
    # --- VR（26日）: 出来高比率。上昇日の出来高 ÷ 下落日の出来高 ×100 ---
    chg = out["Close"].diff()
    vol = out["Volume"].astype(float)
    up_v = vol.where(chg > 0, 0.0).rolling(n).sum()
    dn_v = vol.where(chg < 0, 0.0).rolling(n).sum()
    fl_v = vol.where(chg == 0, 0.0).rolling(n).sum()
    vr_den = (dn_v + fl_v / 2).replace(0, float("nan"))
    out["VR"] = (up_v + fl_v / 2) / vr_den * 100
    # --- OSC（20日）: 終値と20日移動平均の差。0ラインとの位置と向きを見る ---
    out["OSC"] = out["Close"] - out["Close"].rolling(20).mean()
    # --- W%R（14日）: 期間高値・安値に対する終値の位置。-20より上は買われすぎ、-80より下は売られすぎ ---
    h14 = out["High"].rolling(14).max()
    l14 = out["Low"].rolling(14).min()
    wr_rng = (h14 - l14).replace(0, float("nan"))
    out["WR"] = (h14 - out["Close"]) / wr_rng * -100
    # --- CCI（20日）: 平均価格からの偏差で過熱感を測る。±100が目安 ---
    tp = (out["High"] + out["Low"] + out["Close"]) / 3
    tp_ma = tp.rolling(20).mean()
    md = (tp - tp_ma).abs().rolling(20).mean().replace(0, float("nan"))
    out["CCI"] = (tp - tp_ma) / (0.015 * md)
    # --- モメンタム（10日）: 現在値と10日前の価格差で勢いを見る ---
    out["MOM"] = out["Close"] - out["Close"].shift(10)
    # --- PSY（12日）: 直近12日のうち上昇日の割合（投資家心理） ---
    up_day = (out["Close"].diff() > 0).astype(float)
    out["PSY"] = up_day.rolling(12).mean() * 100
    # --- DMI / ADX（14日）: トレンドの方向（+DI/-DI）と強さ（ADX） ---
    up_move = out["High"].diff()
    down_move = -out["Low"].diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = pd.concat([
        out["High"] - out["Low"],
        (out["High"] - out["Close"].shift(1)).abs(),
        (out["Low"] - out["Close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().replace(0, float("nan"))
    out["PDI"] = plus_dm.rolling(14).mean() / atr * 100
    out["MDI"] = minus_dm.rolling(14).mean() / atr * 100
    dx = (out["PDI"] - out["MDI"]).abs() / (out["PDI"] + out["MDI"]).replace(0, float("nan")) * 100
    out["ADX"] = dx.rolling(14).mean()
    # --- 一目均衡表（雲）: 先行スパン1・2で作る雲と株価の位置関係 ---
    tenkan = (out["High"].rolling(9).max() + out["Low"].rolling(9).min()) / 2
    kijun = (out["High"].rolling(26).max() + out["Low"].rolling(26).min()) / 2
    out["TENKAN"], out["KIJUN"] = tenkan, kijun
    out["SPAN_A"] = ((tenkan + kijun) / 2).shift(26)
    out["SPAN_B"] = ((out["High"].rolling(52).max() + out["Low"].rolling(52).min()) / 2).shift(26)
    return out


def _diagnose_indicators(df: pd.DataFrame) -> list[dict]:
    """moomoo風の指標診断（9指標）。各指標を 買い(buy)/中立(neutral)/売り(sell) で判定する"""
    out: list[dict] = []
    close = float(df["Close"].iloc[-1])
    s5, s25, s75 = df["SMA5"].iloc[-1], df["SMA25"].iloc[-1], df["SMA75"].iloc[-1]

    # 1. トレンド（移動平均線の並び）
    if pd.notna(s75) and s5 > s25 > s75:
        out.append({"name": "トレンド(MA)", "verdict": "buy", "label": "強い上昇",
                    "detail": "SMA5 > SMA25 > SMA75 のパーフェクトオーダー。上昇トレンドが安定しています。"})
    elif s5 > s25:
        out.append({"name": "トレンド(MA)", "verdict": "buy", "label": "上昇",
                    "detail": "短期線(SMA5)が中期線(SMA25)より上にあり、上昇基調です。"})
    elif pd.notna(s75) and s5 < s25 < s75:
        out.append({"name": "トレンド(MA)", "verdict": "sell", "label": "強い下降",
                    "detail": "SMA5 < SMA25 < SMA75 の逆パーフェクトオーダー。下降トレンドです。"})
    elif s5 < s25:
        out.append({"name": "トレンド(MA)", "verdict": "sell", "label": "下降",
                    "detail": "短期線が中期線を下回っており、下降基調です。"})
    else:
        out.append({"name": "トレンド(MA)", "verdict": "neutral", "label": "横ばい",
                    "detail": "移動平均線が交錯しており、方向感がありません。"})

    # 2. MACD
    macd, sig = float(df["MACD"].iloc[-1]), float(df["Signal"].iloc[-1])
    hist = float(df["Hist"].iloc[-1])
    prev_hist = float(df["Hist"].iloc[-2]) if len(df) > 1 and pd.notna(df["Hist"].iloc[-2]) else hist
    momentum = "・勢い拡大" if abs(hist) >= abs(prev_hist) else "・勢い縮小"
    if macd > sig:
        out.append({"name": "MACD", "verdict": "buy", "label": "GC中" + momentum,
                    "detail": f"MACD({macd:+.2f})がシグナル({sig:+.2f})を上回っており、買い優勢です。"})
    else:
        out.append({"name": "MACD", "verdict": "sell", "label": "DC中" + momentum,
                    "detail": f"MACD({macd:+.2f})がシグナル({sig:+.2f})を下回っており、売り優勢です。"})

    # 3. RSI(14)
    rsi = float(df["RSI"].iloc[-1])
    if rsi < 30:
        out.append({"name": "RSI(14)", "verdict": "buy", "label": f"{rsi:.1f} 売られすぎ",
                    "detail": "RSIが30未満。売られすぎ水準で、反発が期待できる場面です。"})
    elif rsi > 70:
        out.append({"name": "RSI(14)", "verdict": "sell", "label": f"{rsi:.1f} 買われすぎ",
                    "detail": "RSIが70超。過熱感があり、反落に注意が必要です。"})
    else:
        out.append({"name": "RSI(14)", "verdict": "neutral", "label": f"{rsi:.1f} 中立",
                    "detail": "RSIは30〜70のレンジ内で、過熱感はありません。"})

    # 4. KDJ（9,3,3）
    k = df["K"].iloc[-1] if "K" in df.columns else float("nan")
    d_ = df["D"].iloc[-1] if "D" in df.columns else float("nan")
    j = df["J"].iloc[-1] if "J" in df.columns else float("nan")
    if pd.notna(k) and pd.notna(d_) and pd.notna(j):
        kdj_detail = f"K={k:.1f} / D={d_:.1f} / J={j:.1f}。"
        if j < 0:
            out.append({"name": "KDJ", "verdict": "buy", "label": f"J={j:.1f} 売られすぎ",
                        "detail": kdj_detail + "Jが0を割り込み、短期的な売られすぎです。"})
        elif j > 100:
            out.append({"name": "KDJ", "verdict": "sell", "label": f"J={j:.1f} 買われすぎ",
                        "detail": kdj_detail + "Jが100を超え、短期的な過熱状態です。"})
        elif k > d_:
            out.append({"name": "KDJ", "verdict": "buy", "label": "K＞D（GC中）",
                        "detail": kdj_detail + "K線がD線の上にあり、短期的に買い優勢です。"})
        elif k < d_:
            out.append({"name": "KDJ", "verdict": "sell", "label": "K＜D（DC中）",
                        "detail": kdj_detail + "K線がD線の下にあり、短期的に売り優勢です。"})
        else:
            out.append({"name": "KDJ", "verdict": "neutral", "label": "交錯",
                        "detail": kdj_detail + "K線とD線が交錯しており、方向感がありません。"})

    # 5. ボリンジャーバンド
    bb_up, bb_low, bb_mid = df["BB_up"].iloc[-1], df["BB_low"].iloc[-1], df["BB_mid"].iloc[-1]
    if pd.notna(bb_up) and close > bb_up:
        out.append({"name": "ボリンジャー", "verdict": "sell", "label": "+2σ超え",
                    "detail": "終値が+2σを上抜け。勢いは強いものの、短期的な過熱に注意です。"})
    elif pd.notna(bb_low) and close < bb_low:
        out.append({"name": "ボリンジャー", "verdict": "buy", "label": "-2σ割れ",
                    "detail": "終値が-2σを下回り、売られすぎからの反発候補です。"})
    else:
        pos = "上寄り" if pd.notna(bb_mid) and close >= bb_mid else "下寄り"
        out.append({"name": "ボリンジャー", "verdict": "neutral", "label": f"バンド内({pos})",
                    "detail": "±2σのバンド内で推移しており、異常な値動きではありません。"})

    # 6. 移動平均乖離率（25日）
    if pd.notna(s25) and s25:
        dev = (close - s25) / s25 * 100
        if dev <= -5:
            out.append({"name": "乖離率(25日)", "verdict": "buy", "label": f"{dev:+.1f}%",
                        "detail": "25日線から下に大きく乖離しており、リバウンドの余地があります。"})
        elif dev >= 5:
            out.append({"name": "乖離率(25日)", "verdict": "sell", "label": f"{dev:+.1f}%",
                        "detail": "25日線から上に大きく乖離しており、押し戻しに注意です。"})
        else:
            out.append({"name": "乖離率(25日)", "verdict": "neutral", "label": f"{dev:+.1f}%",
                        "detail": "25日線との乖離は±5%以内で、標準的な範囲です。"})

    # 7. OSC（20日オシレーター）
    if "OSC" in df.columns and pd.notna(df["OSC"].iloc[-1]):
        osc = float(df["OSC"].iloc[-1])
        prev_osc = float(df["OSC"].iloc[-2]) if len(df) > 1 and pd.notna(df["OSC"].iloc[-2]) else osc
        if osc > 0 and osc >= prev_osc:
            out.append({"name": "OSC(20日)", "verdict": "buy", "label": f"{osc:+,.0f} 上昇圧力",
                        "detail": "終値が20日線より上で、その差も拡大中。上昇圧力が続いています。"})
        elif osc > 0:
            out.append({"name": "OSC(20日)", "verdict": "neutral", "label": f"{osc:+,.0f} 上昇一服",
                        "detail": "終値は20日線より上ですが、差は縮小中。上昇の勢いが弱まっています。"})
        elif osc < 0 and osc <= prev_osc:
            out.append({"name": "OSC(20日)", "verdict": "sell", "label": f"{osc:+,.0f} 下落圧力",
                        "detail": "終値が20日線より下で、その差も拡大中。下落圧力が続いています。"})
        else:
            out.append({"name": "OSC(20日)", "verdict": "neutral", "label": f"{osc:+,.0f} 下げ止まり",
                        "detail": "終値は20日線より下ですが、差は縮小中。下げ止まりの兆しがあります。"})

    # 8. AR（26日・人気指標）
    if "AR" in df.columns and pd.notna(df["AR"].iloc[-1]):
        ar = float(df["AR"].iloc[-1])
        if ar <= 70:
            out.append({"name": "AR(26日)", "verdict": "buy", "label": f"{ar:.0f} 低水準",
                        "detail": "ARが70以下。買いエネルギーが枯れた低水準で、反発の素地があります。"})
        elif ar >= 150:
            out.append({"name": "AR(26日)", "verdict": "sell", "label": f"{ar:.0f} 過熱",
                        "detail": "ARが150以上。買いエネルギーが過熱気味で、反落に注意です。"})
        else:
            out.append({"name": "AR(26日)", "verdict": "neutral", "label": f"{ar:.0f} 標準",
                        "detail": "ARは70〜150の標準圏で、極端な偏りはありません。"})

    # 9. VR（26日・出来高比率）
    if "VR" in df.columns and pd.notna(df["VR"].iloc[-1]):
        vr = float(df["VR"].iloc[-1])
        if vr <= 70:
            out.append({"name": "VR(26日)", "verdict": "buy", "label": f"{vr:.0f}% 底値圏",
                        "detail": "VRが70%以下。売りの出来高が支配的な底値圏で、仕込み場とされる水準です。"})
        elif vr >= 300:
            out.append({"name": "VR(26日)", "verdict": "sell", "label": f"{vr:.0f}% 過熱",
                        "detail": "VRが300%以上。買いの出来高に偏りすぎており、天井圏の可能性があります。"})
        else:
            out.append({"name": "VR(26日)", "verdict": "neutral", "label": f"{vr:.0f}% 標準",
                        "detail": "VRは70〜300%の標準圏で、出来高の偏りは大きくありません。"})

    # 10. 一目均衡表（雲）
    if "SPAN_A" in df.columns:
        sa, sb = df["SPAN_A"].iloc[-1], df["SPAN_B"].iloc[-1]
        if pd.notna(sa) and pd.notna(sb):
            cloud_top, cloud_bot = max(sa, sb), min(sa, sb)
            if close > cloud_top:
                out.append({"name": "一目均衡表", "verdict": "buy", "label": "雲の上",
                            "detail": "株価が雲（抵抗帯）の上にあり、強気の形です。雲が下支えになります。"})
            elif close < cloud_bot:
                out.append({"name": "一目均衡表", "verdict": "sell", "label": "雲の下",
                            "detail": "株価が雲の下にあり、弱気の形です。雲が上値の抵抗になります。"})
            else:
                out.append({"name": "一目均衡表", "verdict": "neutral", "label": "雲の中",
                            "detail": "株価が雲の中にあり、もみ合い状態です。雲の抜けた方向に動きやすいとされます。"})

    # 11. DMI / ADX（14日）
    if "ADX" in df.columns:
        pdi, mdi, adx = df["PDI"].iloc[-1], df["MDI"].iloc[-1], df["ADX"].iloc[-1]
        if pd.notna(pdi) and pd.notna(mdi) and pd.notna(adx):
            if adx >= 25 and pdi > mdi:
                out.append({"name": "DMI/ADX", "verdict": "buy", "label": f"ADX {adx:.0f} 上昇トレンド",
                            "detail": f"+DI({pdi:.0f}) > -DI({mdi:.0f}) かつ ADXが25以上。明確な上昇トレンドです。"})
            elif adx >= 25 and mdi > pdi:
                out.append({"name": "DMI/ADX", "verdict": "sell", "label": f"ADX {adx:.0f} 下降トレンド",
                            "detail": f"-DI({mdi:.0f}) > +DI({pdi:.0f}) かつ ADXが25以上。明確な下降トレンドです。"})
            else:
                out.append({"name": "DMI/ADX", "verdict": "neutral", "label": f"ADX {adx:.0f} トレンドなし",
                            "detail": "ADXが25未満で、明確なトレンドが発生していません。"})

    # 12. CCI（20日）
    if "CCI" in df.columns and pd.notna(df["CCI"].iloc[-1]):
        cci = float(df["CCI"].iloc[-1])
        if cci <= -100:
            out.append({"name": "CCI(20日)", "verdict": "buy", "label": f"{cci:.0f} 売られすぎ",
                        "detail": "CCIが-100を下回り、平均から下に行き過ぎています。反発が期待できる水準です。"})
        elif cci >= 100:
            out.append({"name": "CCI(20日)", "verdict": "sell", "label": f"{cci:.0f} 買われすぎ",
                        "detail": "CCIが+100を上回り、平均から上に行き過ぎています。反落に注意です。"})
        else:
            out.append({"name": "CCI(20日)", "verdict": "neutral", "label": f"{cci:.0f} 中立",
                        "detail": "CCIは±100の範囲内で、行き過ぎはありません。"})

    # 13. W%R（14日）
    if "WR" in df.columns and pd.notna(df["WR"].iloc[-1]):
        wr = float(df["WR"].iloc[-1])
        if wr <= -80:
            out.append({"name": "W%R(14日)", "verdict": "buy", "label": f"{wr:.0f} 売られすぎ",
                        "detail": "W%Rが-80以下。期間中の安値圏に位置しており、反発候補です。"})
        elif wr >= -20:
            out.append({"name": "W%R(14日)", "verdict": "sell", "label": f"{wr:.0f} 買われすぎ",
                        "detail": "W%Rが-20以上。期間中の高値圏に位置しており、過熱気味です。"})
        else:
            out.append({"name": "W%R(14日)", "verdict": "neutral", "label": f"{wr:.0f} 中立",
                        "detail": "W%Rは-20〜-80の中間圏で、偏りはありません。"})

    # 14. モメンタム（10日）
    if "MOM" in df.columns and pd.notna(df["MOM"].iloc[-1]):
        mom = float(df["MOM"].iloc[-1])
        prev_mom = float(df["MOM"].iloc[-2]) if len(df) > 1 and pd.notna(df["MOM"].iloc[-2]) else mom
        if mom > 0 and mom >= prev_mom:
            out.append({"name": "モメンタム", "verdict": "buy", "label": f"{mom:+,.0f} 加速中",
                        "detail": "10日前より株価が高く、その差も拡大中。上昇の勢いが強まっています。"})
        elif mom < 0 and mom <= prev_mom:
            out.append({"name": "モメンタム", "verdict": "sell", "label": f"{mom:+,.0f} 下落加速",
                        "detail": "10日前より株価が低く、その差も拡大中。下落の勢いが強まっています。"})
        else:
            out.append({"name": "モメンタム", "verdict": "neutral", "label": f"{mom:+,.0f} 勢い鈍化",
                        "detail": "モメンタムの方向と勢いが一致しておらず、転換点の可能性があります。"})

    # 15. PSY（12日）
    if "PSY" in df.columns and pd.notna(df["PSY"].iloc[-1]):
        psy = float(df["PSY"].iloc[-1])
        if psy <= 25:
            out.append({"name": "PSY(12日)", "verdict": "buy", "label": f"{psy:.0f}% 弱気過剰",
                        "detail": "直近12日の上昇日が25%以下。悲観に傾きすぎており、反発が出やすい水準です。"})
        elif psy >= 75:
            out.append({"name": "PSY(12日)", "verdict": "sell", "label": f"{psy:.0f}% 強気過剰",
                        "detail": "直近12日の上昇日が75%以上。楽観に傾きすぎており、反落に注意です。"})
        else:
            out.append({"name": "PSY(12日)", "verdict": "neutral", "label": f"{psy:.0f}% 中立",
                        "detail": "上昇日と下落日のバランスが取れており、心理の偏りはありません。"})
    return out


def _overall_verdict(diags: list[dict]) -> dict:
    """9指標の買い/売り本数からスコア化して総合判断する"""
    buy_n = sum(1 for d in diags if d["verdict"] == "buy")
    sell_n = sum(1 for d in diags if d["verdict"] == "sell")
    score = buy_n - sell_n
    if score >= 6:
        v = ("強い買い", "#16a34a", "★★★★★", "🟢",
             "大半の指標が買いを示しています。ただし過熱の反動には注意してください。")
    elif score >= 3:
        v = ("買い", "#22c55e", "★★★★☆", "🟢",
             "買い優勢です。押し目やタイミングを見ながら検討しましょう。")
    elif score <= -6:
        v = ("強い売り", "#b91c1c", "★☆☆☆☆", "🔴",
             "大半の指標が売りを示しています。無理な逆張りは避けたい場面です。")
    elif score <= -3:
        v = ("売り", "#ef4444", "★★☆☆☆", "🔴",
             "売り優勢です。新規の買いは慎重に検討してください。")
    else:
        v = ("中立", "#eab308", "★★★☆☆", "🟡",
             "買いと売りが拮抗しています。方向感が出るまで様子見が無難です。")
    return {"score": score, "buy_n": buy_n, "sell_n": sell_n, "neu_n": len(diags) - buy_n - sell_n,
            "label": v[0], "color": v[1], "stars": v[2], "emoji": v[3], "comment": v[4]}


def _gauge_html(buy_n: int, neu_n: int, sell_n: int) -> str:
    """買い/中立/売りの割合バー（moomoo風ゲージ）"""
    total = max(buy_n + neu_n + sell_n, 1)
    b, n, s = buy_n / total * 100, neu_n / total * 100, sell_n / total * 100
    return (
        f'<div style="margin:8px 0 4px 0;">'
        f'<div style="display:flex;justify-content:space-between;font-size:0.72rem;font-weight:800;">'
        f'<span class="up">買い {buy_n}</span><span class="muted">中立 {neu_n}</span>'
        f'<span class="down">売り {sell_n}</span></div>'
        f'<div style="display:flex;height:8px;border-radius:6px;overflow:hidden;margin-top:4px;">'
        f'<div style="width:{b}%;background:{UP};"></div>'
        f'<div style="width:{n}%;background:var(--border);"></div>'
        f'<div style="width:{s}%;background:{DOWN};"></div></div></div>'
    )


def _diagnosis_html(diags: list[dict]) -> str:
    from html import escape
    styles = {
        "buy": f"background:rgba(22,199,132,.14);color:{UP};",
        "sell": f"background:rgba(234,57,67,.14);color:{DOWN};",
        "neutral": "background:var(--tag-bg);color:var(--text-sub);",
    }
    mark = {"buy": "▲", "sell": "▼", "neutral": "―"}
    chips = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;padding:5px 12px;'
        f'border-radius:30px;font-size:0.74rem;font-weight:700;{styles[d["verdict"]]}">'
        f'{mark[d["verdict"]]} {escape(d["name"])}: {escape(d["label"])}</span>'
        for d in diags
    )
    return f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 2px 0;">{chips}</div>'


def render_trade_chart(ticker: str) -> None:
    """デモトレード画面用のmoomoo風チャート（スタッツ帯＋多指標＋9指標総合診断）"""
    price = get_price(ticker)
    if price is not None:
        st.markdown(_stat_strip_html(ticker, price), unsafe_allow_html=True)

    period_map = {"1日": ("1d", "5m"), "1週間": ("5d", "15m"), "1ヶ月": ("1mo", "1d"),
                  "3ヶ月": ("3mo", "1d"), "6ヶ月": ("6mo", "1d"), "1年": ("1y", "1d")}
    pc1, pc2 = st.columns([1.4, 1.6])
    p_label = pc1.radio("チャート期間", list(period_map.keys()), index=2, horizontal=True,
                        key="trade_chart_period", label_visibility="collapsed")
    inds = pc2.multiselect(
        "表示指標", ["MA(5/25/75)", "ボリンジャーバンド", "出来高", "RSI(14)", "MACD", "KDJ"],
        default=["MA(5/25/75)", "出来高", "MACD"],
        key="trade_inds", label_visibility="collapsed",
    )
    period, interval = period_map[p_label]

    df = get_history(ticker, period, interval)
    if df.empty:
        st.info("チャートデータを取得できませんでした。")
        return
    df = add_extra_indicators(add_indicators(df))

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        st.line_chart(df["Close"], height=300)
        return

    panel_rows = [p for p in ["出来高", "RSI(14)", "MACD", "KDJ"] if p in inds]
    rows = ["price"] + panel_rows
    heights = {"price": 0.52, "出来高": 0.16, "RSI(14)": 0.16, "MACD": 0.16, "KDJ": 0.16}
    row_h = [heights[r] for r in rows]
    hs = sum(row_h)
    fig = make_subplots(rows=len(rows), cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        row_heights=[h / hs for h in row_h],
                        subplot_titles=[("" if r == "price" else r) for r in rows])

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="株価", increasing_line_color=UP, decreasing_line_color=DOWN), row=1, col=1)

    if "MA(5/25/75)" in inds:
        for col_name, color in (("SMA5", "#4f7df3"), ("SMA25", "#f0b90b"), ("SMA75", "#9b59b6")):
            if df[col_name].notna().any():
                fig.add_trace(go.Scatter(x=df.index, y=df[col_name], name=col_name,
                                         line=dict(color=color, width=1.1)), row=1, col=1)
    if "ボリンジャーバンド" in inds and df["BB_up"].notna().any():
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
            fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], line=dict(color="#8e44ad", width=1.3),
                                     showlegend=False), row=i, col=1)
            fig.add_hline(y=70, line=dict(color=DOWN, width=1, dash="dot"), row=i, col=1)
            fig.add_hline(y=30, line=dict(color=UP, width=1, dash="dot"), row=i, col=1)
            fig.update_yaxes(range=[0, 100], row=i, col=1)
        elif r == "MACD":
            hist_colors = [UP if pd.notna(v) and v >= 0 else DOWN for v in df["Hist"]]
            fig.add_trace(go.Bar(x=df.index, y=df["Hist"], marker_color=hist_colors,
                                 showlegend=False), row=i, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD",
                                     line=dict(color=ACCENT, width=1.2)), row=i, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["Signal"], name="Signal",
                                     line=dict(color="#f0b90b", width=1.2)), row=i, col=1)
        elif r == "KDJ":
            fig.add_trace(go.Scatter(x=df.index, y=df["K"], name="K",
                                     line=dict(color="#4f7df3", width=1.2)), row=i, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["D"], name="D",
                                     line=dict(color="#f0b90b", width=1.2)), row=i, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["J"], name="J",
                                     line=dict(color="#9b59b6", width=1.1, dash="dot")), row=i, col=1)
            fig.add_hline(y=80, line=dict(color=DOWN, width=1, dash="dot"), row=i, col=1)
            fig.add_hline(y=20, line=dict(color=UP, width=1, dash="dot"), row=i, col=1)

    fig.update_layout(height=360 + 105 * len(panel_rows), margin=dict(l=0, r=0, t=16, b=0),
                      template="plotly_white", xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
                      hovermode="x unified")
    fig.update_xaxes(rangeslider_visible=False)
    if interval == "1d":
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    else:
        hours = [15, 9] if cur_of(ticker) == "¥" else [16, 9.5]
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]),
                                      dict(bounds=hours, pattern="hour")])
    st.plotly_chart(fig, use_container_width=True)

    # ---- テクニカル診断（日足ベース・9指標の総合判断） ----
    d6 = get_history(ticker, "6mo", "1d")
    if len(d6) < 30:
        return
    dd = add_extra_indicators(add_indicators(d6))
    diags = _diagnose_indicators(dd)
    if not diags:
        return
    v = _overall_verdict(diags)

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin-top:6px;flex-wrap:wrap;">'
        f'<span style="font-weight:800;font-size:0.9rem;color:var(--text-main);">🩺 テクニカル診断（日足・{len(diags)}指標）</span>'
        f'<span style="display:inline-block;padding:3px 14px;border-radius:30px;'
        f'background-color:{v["color"]};color:#fff;font-weight:700;font-size:0.78rem;">'
        f'{v["emoji"]} 総合: {v["label"]}（スコア {v["score"]:+d}）</span>'
        f'<span class="muted" style="font-size:0.78rem;font-weight:700;">{v["stars"]}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(_gauge_html(v["buy_n"], v["neu_n"], v["sell_n"]), unsafe_allow_html=True)
    st.markdown(_diagnosis_html(diags), unsafe_allow_html=True)
    st.caption(f"💬 {v['comment']}")
    with st.expander("📖 各指標の見方・判定理由"):
        for d in diags:
            icon = {"buy": "🟢", "sell": "🔴", "neutral": "⚪"}[d["verdict"]]
            st.markdown(f"{icon} **{d['name']}**（{d['label']}）: {d['detail']}")
        st.caption("※ 診断は日足6ヶ月のデータに基づく参考情報です。スコア＝買い指標数−売り指標数。投資判断は他の情報もあわせて行ってください。")


def _trade_manual_tab(ss) -> None:
    pending = ss.pop("_trade_code_pending", None)
    if pending is not None:
        ss["trade_code"] = pending

    st.caption("銘柄コード（例: 7203）または銘柄名（例: トヨタ）を入力すると、チャートと注文フォームが表示されます。")
    in1, in2 = st.columns([3, 1])
    code = in1.text_input("証券コード・銘柄名", placeholder="例: 7203, トヨタ, AAPL",
                          label_visibility="collapsed", key="trade_code")
    with in2:
        with st.popover("⚡ クイック銘柄", use_container_width=True):
            for tk in QUICK_TICKERS:
                if st.button(CODE2NAME.get(tk, tk), key=f"pq_{tk}", use_container_width=True):
                    ss["_trade_code_pending"] = tk.replace(".T", "")
                    st.rerun()

    ticker = resolve_trade_symbol(code)
    price = get_price(ticker) if ticker else None

    if code and ticker and price is None:
        st.warning("価格を取得できませんでした。コードや銘柄名を確認してください。")

    if ticker and price:
        left, right = st.columns([1.8, 1])
        with left:
            with st.container(border=True):
                st.markdown(
                    f'<div class="panel-head"><span class="ph-title">📈 {label_of(ticker)}</span>'
                    f'<span class="ph-more">¥{price:,.1f}</span></div>',
                    unsafe_allow_html=True,
                )
                render_trade_chart(ticker)
        with right:
            with st.container(border=True):
                st.markdown('<div class="panel-head"><span class="ph-title">🛒 注文フォーム</span></div>',
                            unsafe_allow_html=True)
                st.markdown(
                    f'<div style="background:var(--tint-bg);border-radius:14px;padding:12px 16px;'
                    f'margin-bottom:10px;border:1px solid var(--tint-border);">'
                    f'<div style="font-weight:600;font-size:0.85rem;color:var(--text-sub);">{label_of(ticker)}</div>'
                    f'<div style="font-size:1.5rem;font-weight:700;color:var(--text-main);">¥{price:,.1f}</div></div>',
                    unsafe_allow_html=True,
                )
                pos = ss.positions.get(ticker)
                if pos and pos.shares:
                    st.caption(f"📦 保有 {pos.shares}株 ／ 平均取得 ¥{pos.cost_basis:,.1f}")
                st.caption(f"💰 現金残高: {yen(ss.cash)}")
                side = st.radio("売買", ["買い", "売り"], horizontal=True, key="pt_side")
                shares = st.number_input("株数", min_value=1, value=100, step=100, key="pt_shares")
                st.caption(f"概算約定額: **{yen(shares * price)}**")
                if st.button("🚀 注文を出す", type="primary", use_container_width=True, key="pt_order"):
                    ok, msg = execute_trade(ticker, side, int(shares), price)
                    if ok:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
    st.write("")

    left2, right2 = st.columns([1.6, 1])
    with left2:
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
            st.info("保有ポジションはありません。上の入力欄から銘柄を表示して取引できます。")

    with right2:
        st.markdown("### 🧾 取引履歴")
        if ss.trades:
            hist = pd.DataFrame(ss.trades[::-1])
            st.dataframe(hist, use_container_width=True, hide_index=True, height=280)
            st.download_button(
                "📥 CSVをダウンロード",
                hist.to_csv(index=False).encode("utf-8-sig"),
                file_name="trade_history.csv",
                mime="text/csv",
            )
            st.caption("🤖 マークが付いた取引は自動売買による約定です。")
        else:
            st.info("まだ取引はありません。")
        st.divider()
        if st.button("↩️ 口座をリセット", use_container_width=True):
            for k in ("cash", "positions", "trades", "auto_log"):
                ss.pop(k, None)
            init_trade_state()
            init_auto_state()
            st.rerun()
        st.caption("※ デモ（ペーパートレード）です。実際の取引は行われません。")


def _trade_auto_tab(ss) -> None:
    st.caption(
        "登録したルールは、アプリの画面が更新されるたびに自動で判定され、シグナルが変化した瞬間にデモ発注されます。"
        "ブラウザでアプリを開いている間だけ動作します（実際の取引は行われません）。"
        "複数銘柄にまとめて投資したい場合は、下の「🧺 分散投資」から一括作成できます。"
    )

    # --- ルール追加フォーム ---
    with st.container(border=True):
        st.markdown('<div class="panel-head"><span class="ph-title">➕ 自動売買ルールを追加</span></div>',
                    unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1.6, 1.8, 1])
        kw = c1.text_input("銘柄コード・銘柄名", placeholder="例: 7203, トヨタ", key="auto_kw")
        strat = c2.selectbox("戦略", AUTO_STRATEGIES, key="auto_strat",
                             help="ゴールデンクロス: SMA5/25のクロスで売買 ／ RSI逆張り: 30未満で買い・70超で売り ／ "
                                  "総合シグナル: テクニカル判定（3指標）で売買 ／ "
                                  "総合診断: 15指標の多数決。買い指標が優勢（スコア+3以上）で買い、"
                                  "売り指標が増えてきたら（スコア-2以下）早めに売り ／ "
                                  "指値・逆指値: 指定価格に達したら売買")
        shares = c3.number_input("株数", min_value=1, value=100, step=100, key="auto_shares")
        buy_below = sell_above = 0.0
        if strat == "指値・逆指値":
            b1, b2 = st.columns(2)
            buy_below = b1.number_input("この価格以下で買う（0=無効）", min_value=0.0, value=0.0,
                                        step=10.0, key="auto_buy_below")
            sell_above = b2.number_input("この価格以上で売る（0=無効）", min_value=0.0, value=0.0,
                                         step=10.0, key="auto_sell_above")
        if st.button("🤖 ルールを追加", type="primary", key="auto_add"):
            tk = resolve_trade_symbol(kw)
            if not tk or get_price(tk) is None:
                st.error("銘柄を特定できませんでした。コードや銘柄名を確認してください。")
            elif strat == "指値・逆指値" and not (buy_below or sell_above):
                st.error("指値・逆指値では、買い価格か売り価格の少なくとも一方を設定してください。")
            else:
                ss["auto_rules"].append({
                    "id": ss["auto_rule_seq"], "ticker": tk, "strategy": strat,
                    "shares": int(shares), "enabled": True,
                    "last_signal": "hold", "last_detail": "未判定", "last_checked": "-",
                    "buy_below": float(buy_below) or None,
                    "sell_above": float(sell_above) or None,
                })
                ss["auto_rule_seq"] += 1
                ss["auto_last_eval"] = 0.0  # 追加したルールを即時判定
                st.toast(f"ルールを追加しました: {label_of(tk)}", icon="🤖")
                st.rerun()

    st.write("")

    # --- 分散投資（ポートフォリオ一括ルール作成） ---
    with st.container(border=True):
        st.markdown('<div class="panel-head"><span class="ph-title">🧺 分散投資（複数銘柄にまとめて自動売買）</span></div>',
                    unsafe_allow_html=True)
        st.caption("投資予算を選択した銘柄に均等配分し、同じ戦略の自動売買ルールを一括作成します。"
                   "1銘柄あたりの株数は作成時の株価から自動計算されます。")
        for m in ss.pop("_pf_skipped", []):
            st.warning(m)
        opts = {f"{name}（{code}）": code for code, name in sorted(CODE2NAME.items())
                if not code.startswith("^")}
        defaults = [k for k, v in opts.items() if v in QUICK_TICKERS]
        sel = st.multiselect("対象銘柄（複数選択）", list(opts.keys()), default=defaults, key="pf_stocks")
        p1, p2 = st.columns(2)
        pf_strat = p1.selectbox("戦略", [s for s in AUTO_STRATEGIES if s != "指値・逆指値"],
                                index=3, key="pf_strat")
        pf_budget = p2.number_input("投資予算（円）", min_value=10_000, value=1_000_000,
                                    step=100_000, key="pf_budget")
        if sel:
            st.caption(f"1銘柄あたり約 {yen(pf_budget / len(sel))} を配分（現金残高 {yen(ss.cash)}）。"
                       "予算が現金残高を超えると、買いシグナル時に残高不足で約定しないことがあります。")
        if st.button("🧺 分散ルールを一括作成", type="primary", key="pf_add", disabled=not sel):
            group = f"分散{ss['auto_group_seq']}"
            alloc = pf_budget / len(sel)
            created, skipped = 0, []
            for label_sel in sel:
                code = opts[label_sel]
                price = get_price(code)
                if price is None:
                    skipped.append(f"{label_sel}: 価格を取得できないためスキップしました。")
                    continue
                shares = int(alloc // price)
                if shares < 1:
                    skipped.append(f"{label_sel}: 配分額 {yen(alloc)} では1株（¥{price:,.0f}）も"
                                   "買えないためスキップしました。銘柄数を減らすか予算を増やしてください。")
                    continue
                ss["auto_rules"].append({
                    "id": ss["auto_rule_seq"], "ticker": code, "strategy": pf_strat,
                    "shares": shares, "enabled": True, "group": group,
                    "last_signal": "hold", "last_detail": "未判定", "last_checked": "-",
                    "buy_below": None, "sell_above": None,
                })
                ss["auto_rule_seq"] += 1
                created += 1
            if created:
                ss["auto_group_seq"] += 1
                st.toast(f"{group}: {created}銘柄の分散ルールを作成しました。", icon="🧺")
            ss["_pf_skipped"] = skipped
            ss["auto_last_eval"] = 0.0  # 追加したルールを即時判定
            st.rerun()

    st.write("")

    # --- 登録ルール一覧 ---
    hc1, hc2 = st.columns([3, 1])
    hc1.markdown("#### 📋 登録ルール")
    if hc2.button("🔍 今すぐ判定", use_container_width=True, key="auto_check_now"):
        get_price.clear()
        get_history.clear()
        ss["auto_last_eval"] = 0.0
        st.rerun()

    # 分散投資グループの一括操作
    pf_groups: dict[str, list[dict]] = {}
    for r in ss["auto_rules"]:
        if r.get("group"):
            pf_groups.setdefault(r["group"], []).append(r)
    for g, rules_g in pf_groups.items():
        with st.container(border=True):
            g1, g2, g3, g4 = st.columns([2.6, 1, 1, 1])
            n_on = sum(1 for r in rules_g if r.get("enabled", True))
            g1.markdown(f"**🧺 {g}**")
            g1.caption(f"{rules_g[0]['strategy']}｜{len(rules_g)}銘柄（稼働 {n_on}）")
            if g2.button("全て有効", key=f"g_on_{g}", use_container_width=True):
                for r in rules_g:
                    r["enabled"] = True
                    ss[f"auto_en_{r['id']}"] = True
                st.rerun()
            if g3.button("全て無効", key=f"g_off_{g}", use_container_width=True):
                for r in rules_g:
                    r["enabled"] = False
                    ss[f"auto_en_{r['id']}"] = False
                st.rerun()
            if g4.button("🗑️ 一括削除", key=f"g_del_{g}", use_container_width=True):
                ids = {r["id"] for r in rules_g}
                ss["auto_rules"] = [r for r in ss["auto_rules"] if r["id"] not in ids]
                st.rerun()

    if not ss["auto_rules"]:
        st.info("ルールはまだ登録されていません。上のフォームから追加してください。")
    else:
        for rule in list(ss["auto_rules"]):
            with st.container(border=True):
                a, b, c, d = st.columns([1.8, 2.6, 0.9, 0.9])
                with a:
                    st.markdown(f"**{label_of(rule['ticker'])}**")
                    lim = ""
                    if rule["strategy"] == "指値・逆指値":
                        parts = []
                        if rule.get("buy_below"):
                            parts.append(f"買≤{rule['buy_below']:,.0f}")
                        if rule.get("sell_above"):
                            parts.append(f"売≥{rule['sell_above']:,.0f}")
                        lim = "／" + "・".join(parts)
                    grp = f"🧺{rule['group']}｜" if rule.get("group") else ""
                    st.caption(f"{grp}{rule['shares']}株{lim}")
                with b:
                    st.markdown(SIG_LABEL.get(rule.get("last_signal", "hold"), "⚪ 待機中"))
                    st.caption(f"{rule['strategy']}｜{rule.get('last_detail', '-')}"
                               f"（判定 {rule.get('last_checked', '-')}）")
                with c:
                    rule["enabled"] = st.toggle("有効", value=rule.get("enabled", True),
                                                key=f"auto_en_{rule['id']}")
                with d:
                    if st.button("🗑️ 削除", key=f"auto_del_{rule['id']}", use_container_width=True):
                        ss["auto_rules"] = [r for r in ss["auto_rules"] if r["id"] != rule["id"]]
                        st.rerun()

    # --- 実行ログ ---
    st.markdown("#### 🧾 自動売買ログ")
    if ss["auto_log"]:
        st.dataframe(pd.DataFrame(ss["auto_log"]), use_container_width=True,
                     hide_index=True, height=240)
    else:
        st.info("自動売買の実行履歴はまだありません。シグナルが変化すると、ここに記録されます。")

    st.divider()
    auto_ref = st.toggle("⏱️ 60秒ごとに自動判定（このページを開いている間のみ）",
                         value=False, key="auto_refresh")
    st.caption("※ オンにすると60秒ごとに株価を再取得してルールを判定します。ブラウザを閉じると停止します。")
    if auto_ref:
        time.sleep(60)
        st.rerun()


def page_trade() -> None:
    init_trade_state()
    init_auto_state()
    ss = st.session_state

    st.markdown(
        '<div class="gradient-header">'
        '<h2>💼 デモトレード</h2>'
        '<p>yfinance の実データを使った日本株ペーパートレード（仮想資金100万円）＋ 自動売買（デモ）</p>'
        '</div>',
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

    n_active = sum(1 for r in ss["auto_rules"] if r.get("enabled", True))
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(card_html("総資産", yen(total), f"{arrow} {yen(abs(pnl))}（{pct:+.2f}%）", cls),
                  unsafe_allow_html=True)
    col2.markdown(card_html("現金残高", yen(ss.cash)), unsafe_allow_html=True)
    col3.markdown(card_html("株式評価額", yen(holdings_value)), unsafe_allow_html=True)
    col4.markdown(card_html("自動売買ルール", f"{n_active}件 稼働中", f"登録 {len(ss['auto_rules'])}件"),
                  unsafe_allow_html=True)
    st.write("")

    tab_manual, tab_auto = st.tabs(["📈 取引", "🤖 自動売買"])
    with tab_manual:
        _trade_manual_tab(ss)
    with tab_auto:
        _trade_auto_tab(ss)


# ===========================================================================
# ナビゲーション
# ===========================================================================
PG_HOME = st.Page(page_home, title="ホーム（銘柄検索）", icon="🏠", url_path="home", default=True)
PG_DETAIL = st.Page(page_detail, title="銘柄詳細", icon="📊", url_path="detail")
PG_FAV = st.Page(page_favorites, title="お気に入り銘柄", icon="⭐", url_path="favorites")
PG_GLOSSARY = st.Page(page_glossary, title="指標解説", icon="📚", url_path="glossary")
PG_TRADE = st.Page(page_trade, title="デモトレード", icon="💼", url_path="trade")


def _sidebar_nav(current_title: str) -> None:
    """スクリーンショットのようなブランド付き左サイドナビを描画する。"""
    with st.sidebar:
        st.markdown(
            '<div class="brand-box">'
            '<div class="brand-icon">📈</div>'
            '<div><div class="brand-name">うめぇ〜go株</div>'
            '<span class="brand-badge">PRO</span></div>'
            '</div>',
            unsafe_allow_html=True,
        )

        pages = [
            (PG_HOME, "ホーム（銘柄検索）", "🏠"),
            (PG_DETAIL, "銘柄詳細", "📊"),
            (PG_FAV, "お気に入り銘柄", "⭐"),
            (PG_GLOSSARY, "指標解説", "📚"),
            (PG_TRADE, "デモトレード", "💼"),
        ]
        for page, label, icon in pages:
            active = (label == current_title)
            wrap_class = "nav-active" if active else "nav-inactive"
            st.markdown(f'<div class="{wrap_class}">', unsafe_allow_html=True)
            st.page_link(page, label=label, icon=icon, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # ミニウィジェット: デモ口座の資産サマリー（実データ）
        init_trade_state()
        ss = st.session_state
        holdings_value = 0.0
        for tk, pos in ss.positions.items():
            if pos.shares:
                p = get_price(tk)
                if p:
                    holdings_value += pos.shares * p
        total = ss.cash + holdings_value
        pnl = total - INITIAL_CASH
        pct = pnl / INITIAL_CASH * 100 if INITIAL_CASH else 0.0
        arrow = "▲" if pnl > 0 else ("▼" if pnl < 0 else "—")
        st.markdown(
            f'<div class="side-widget">'
            f'<div class="sw-label">デモ口座 総資産</div>'
            f'<div class="sw-value">{yen(total)}</div>'
            f'<div class="sw-sub">{arrow} {yen(abs(pnl))}（{pct:+.2f}%）</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ミニウィジェット: 日経平均（実データ）
        n225 = get_price("^N225")
        n225_hist = get_history("^N225", "5d", "1d")
        n_chg_html = ""
        if n225 is not None and len(n225_hist) >= 2:
            prev = float(n225_hist["Close"].iloc[-2])
            if prev > 0:
                d = n225 - prev
                p = d / prev * 100
                cls = "up" if d >= 0 else "down"
                arrow2 = "▲" if d >= 0 else "▼"
                n_chg_html = f'<div class="sw-sub {cls}">{arrow2} {d:+,.2f}（{p:+.2f}%）</div>'
        value_html = f'{n225:,.2f}' if n225 is not None else 'N/A'
        st.markdown(
            '<div class="side-widget-light">'
            '<div class="sw-label"><span>日経平均</span><span>^N225</span></div>'
            f'<div class="sw-value">{value_html}</div>'
            f'{n_chg_html}'
            '</div>',
            unsafe_allow_html=True,
        )


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    nav = st.navigation([PG_HOME, PG_DETAIL, PG_FAV, PG_GLOSSARY, PG_TRADE], position="hidden")

    if yf is None:
        st.error("`yfinance` がインストールされていません。`pip install yfinance` を実行してください。")
        st.stop()

    _sidebar_nav(nav.title)

    # 自動売買ルールの判定（どのページを開いていても、画面更新のたびに実行）
    for _m in run_auto_rules():
        st.toast(f"🤖 自動売買: {_m}", icon="🤖")

    # ===== トップバー（時刻表示とグローバル検索） =====
    c_left, c_mid, c_search = st.columns([3, 2, 3])
    
    with c_left:
        st.write("")  # 左側の余白
    
    with c_mid:
        now = dt.datetime.now()
        market_open = dt.time(9, 0) <= now.time() <= dt.time(15, 0) and now.weekday() < 5
        status_text = "市場は開いています" if market_open else "市場は閉じています"
        st.markdown(
            f'<div class="topbar-time" style="display:inline-flex; margin:0 auto;">'
            f'<span class="dot"></span>{now:%Y/%m/%d %H:%M} 時点　・　{status_text}</div>',
            unsafe_allow_html=True,
        )

    # トップバー検索（入力するとホームで検索を実行）
    with c_search:
        st.text_input(
            "🔍 銘柄名・コードを検索",
            placeholder="例: トヨタ, 7203.T",
            label_visibility="collapsed",
            key="global_search",
            on_change=lambda: st.session_state.update({"_sr": st.session_state.global_search}),
        )

    # ホーム以外のページでトップバー検索されたら、ホームへ移動して検索を実行
    if st.session_state.get("_sr") and nav.title != "ホーム（銘柄検索）":
        st.switch_page(PG_HOME)

    nav.run()

if __name__ == "__main__":
    main()
