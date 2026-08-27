# -*- coding: utf-8 -*-
"""OKX 策略监控面板（Streamlit Cloud，2026-08-16 单策略 P5 版）。

读取 data/monitor_{strategy_id}.json（本地程序每 10 分钟经 GitHub 推送）。
单卡片：组合权益 + 策略快照 + 仓位槽表 + 净值曲线 + 最近交易。
"""
import os
import json
import glob

import pandas as pd
import streamlit as st
import altair as alt

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ===== 主题配色（与桌面端 theme.py 同步；Streamlit Cloud 无 config 时默认 aurora） =====
THEME_COLORS = {
    "aurora":   {"up": "#10b981", "down": "#ef4444", "line": "#10b981",
                 "bg": "#0b101b", "card": "#131c2e", "text": "#e8ecf4", "accent": "#6366f1"},
    "cyber":    {"up": "#00e676", "down": "#ff5252", "line": "#00e676",
                 "bg": "#0a0a0a", "card": "#161616", "text": "#e8e8e8", "accent": "#00d4ff"},
    "graphite": {"up": "#34d399", "down": "#f87171", "line": "#34d399",
                 "bg": "#121317", "card": "#1b1d23", "text": "#e4e6eb", "accent": "#2dd4bf"},
    "daylight": {"up": "#059669", "down": "#dc2626", "line": "#059669",
                 "bg": "#f4f6f9", "card": "#ffffff", "text": "#1e293b", "accent": "#2563eb"},
}


def get_theme_colors():
    name = "aurora"
    try:
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "data", "okx_config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                name = json.load(f).get("ui_theme", "aurora")
    except Exception:
        pass
    return THEME_COLORS.get(name, THEME_COLORS["aurora"])


TC = get_theme_colors()

# 注入 CSS：背景/文字/卡片/强调色跟随主题
st.markdown(f"""
<style>
.stApp {{ background-color: {TC['bg']}; color: {TC['text']}; }}
[data-testid="stMetricValue"] {{ color: {TC['text']}; }}
[data-testid="stMetricLabel"] {{ color: {TC['accent']}; }}
[data-testid="stHeader"] {{ background: transparent; }}
h1, h2, h3, h4, .stCaption {{ color: {TC['text']} !important; }}
.block-container {{ padding-top: 1.5rem; }}
</style>
""", unsafe_allow_html=True)

STRATEGY_LABELS = {
    "all_abc": "A+B+C 三腿波动率目标 by HS",
}

# Streamlit 只展示当前在用策略（ALL），旧 P5 面板不再显示
ACTIVE_STRATEGY = "all_abc"

ASSET_LABELS = {
    "BTC-USDT-SWAP": "BTC", "ETH-USDT-SWAP": "ETH", "SOL-USDT-SWAP": "SOL",
    "DOGE-USDT-SWAP": "DOGE", "XRP-USDT-SWAP": "XRP",
    "ADA-USDT-SWAP": "ADA", "LINK-USDT-SWAP": "LINK",
}


def load_monitor(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_strategies():
    strategies = {}
    for f in glob.glob(os.path.join(DATA_DIR, "monitor_*.json")):
        name = os.path.basename(f).replace("monitor_", "").replace(".json", "")
        if name != ACTIVE_STRATEGY:
            continue
        data = load_monitor(os.path.basename(f))
        if data:
            strategies[name] = data
    return strategies


def calc_max_drawdown(equity_curve):
    if not equity_curve:
        return 0
    peak = equity_curve[0]
    max_dd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return max_dd * 100


def fmt_pnl(val):
    return f"{'+' if val >= 0 else ''}{val:,.2f}"


def fmt_price(val):
    """价格显示：>=1 用两位小数（带千分位），<1 用四位小数（避免科学计数法）。"""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return f"{val}"
    return f"{v:,.2f}" if v >= 1 else f"{v:.4f}"


def render_card(data):
    """渲染单策略卡片（P5：组合权益 + 仓位槽）。"""
    capital = data.get("capital", 10000)
    equity = data.get("equity", capital)
    trades = data.get("trades", [])
    stats = data.get("stats", {})
    slots = data.get("slots", [])
    snapshot = data.get("snapshot", {})
    eq_curve = data.get("equity_curve", [])
    demo_mode = data.get("demo_mode", True)
    prices = data.get("prices", {})

    total_return = stats.get("total_return", 0) * 100
    n_trades = stats.get("n_trades", len(trades))
    win_rate = stats.get("win_rate", 0) * 100
    profit_factor = stats.get("profit_factor", 0)
    max_dd = calc_max_drawdown([p.get("equity", capital) for p in eq_curve]) if eq_curve else 0
    pnl_total = equity - capital
    price = data.get("current_price", 0)

    mode_text = "🧪 模拟盘" if demo_mode else "⚠️ 实盘"
    label = STRATEGY_LABELS.get(data.get("strategy_id", ""), data.get("strategy_id", "?"))
    st.markdown(f"#### {label} · {mode_text}")
    price_row = "  ".join(
        f"{ASSET_LABELS.get(k, k)} {fmt_price(v)}" for k, v in prices.items()
    ) if prices else (f"ETH {fmt_price(price)}" if price else "")
    st.caption(f"{price_row} | 更新 {data.get('updated_at', '?')[:19]}")

    # 策略参数不对外展示（2026-08-16：策略保密，仅内部使用）

    available = stats.get("available", stats.get("cash", 0))
    frozen = stats.get("frozen", 0)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("组合权益", f"{equity:,.2f}", fmt_pnl(pnl_total))
    with c2:
        st.metric("收益率", f"{total_return:+.2f}%")
    with c3:
        st.metric("可用资金", f"{available:,.2f}")
    with c4:
        st.metric("冻结资金", f"{frozen:,.2f}")

    c5, c6, c7 = st.columns(3)
    with c5:
        st.metric("胜率", f"{win_rate:.0f}%")
    with c6:
        st.metric("盈亏比", f"{profit_factor:.2f}")
    with c7:
        st.metric("回撤", f"{max_dd:.2f}%")

    st.caption(f"交易数: {n_trades}")

    # 仓位槽表
    if slots:
        st.markdown("**仓位槽**")
        rows = []
        for s in slots:
            side_cn = "多" if s.get("side", 0) > 0 else "空"
            rows.append({
                "槽位": f"{s.get('slot', '')}{'-' + s.get('leg', '') if s.get('leg') else ''}",
                "标的": ASSET_LABELS.get(s.get("inst", ""), s.get("inst", "")),
                "方向": side_cn,
                "数量": s.get("qty", 0),
                "开仓价": s.get("entry", 0),
                "当前价": s.get("price", 0),
                "份额": s.get("frac", 0),
                "未实现盈亏": s.get("unrealized", 0),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("✅ 空仓")

    # 各标的价格
    if prices:
        st.caption(" | ".join(f"{ASSET_LABELS.get(k, k)} {fmt_price(v)}"
                              for k, v in prices.items()))

    # 净值曲线
    if len(eq_curve) > 1:
        eq_df = pd.DataFrame(eq_curve)
        eq_df = eq_df.dropna(subset=["equity"])
        eq_df["equity"] = eq_df["equity"].astype(float)
        if capital > 0:
            eq_df["equity"] = eq_df["equity"] / capital
        eq_df["date"] = pd.to_datetime(eq_df["time"]).dt.date
        eq_df = eq_df.groupby("date").last().reset_index()
        y_min = min(1.0, eq_df["equity"].min())
        y_max = max(1.0, eq_df["equity"].max())
        y_pad = (y_max - y_min) * 0.05 if y_max > y_min else 0.01
        chart = alt.Chart(eq_df).mark_line(color=TC['line'], strokeWidth=2).encode(
            x=alt.X('date:T', title=None, axis=alt.Axis(format='%Y-%m-%d', labelAngle=-45)),
            y=alt.Y('equity:Q', title=None,
                    scale=alt.Scale(domain=[y_min - y_pad, y_max + y_pad])),
        ).properties(height=180)
        rule = alt.Chart(pd.DataFrame({'y': [1.0]})).mark_rule(
            color='gray', strokeDash=[4, 4]
        ).encode(y='y:Q')
        st.altair_chart(chart + rule, use_container_width=True)
    else:
        st.caption("净值数据不足")

    # 最近交易（开仓/平仓/资金费）
    if trades:
        records = []
        reason_map = {"close": "信号", "close_sl": "止损", "close_trail": "轨道",
                      "flip": "反手", "换仓": "换仓", "end": "期末"}
        for t in reversed(trades[-20:]):
            act = str(t.get("action", "OPEN")).upper()
            side_cn = "多" if t.get("side") == "LONG" else ("空" if t.get("side") == "SHORT" else "")
            if act == "OPEN":
                op = f"开{side_cn}"
            elif act == "FUNDING":
                op = "资金费"
            else:
                rsn = t.get("reason", "") or "close"
                op = f"平{side_cn}({reason_map.get(rsn, rsn)})"
            records.append({
                "时间": t.get("time", "")[5:16],
                "标的": ASSET_LABELS.get(t.get("inst", ""), t.get("inst", "") or "-"),
                "操作": op,
                "价格": fmt_price(t.get("price", 0)),
                "数量": f"{t.get('qty', 0):,.4f}",
                "手续费": f"{t.get('fee', 0):.4f}",
                "盈亏": "" if t.get("pnl") is None else fmt_pnl(t.get("pnl", 0)),
            })
        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True, height=200)
    else:
        st.caption("暂无交易")


# ===== 主界面 =====
st.set_page_config(page_title="OKX 策略监控", page_icon="📈", layout="wide")
st.markdown("## 📈 OKX 策略监控")

strategies = get_strategies()
if not strategies:
    st.warning("未找到策略数据。请确保本地程序正在运行并已推送到 GitHub。")
    st.stop()

top_cols = st.columns([4, 1, 1])
with top_cols[0]:
    n = len(strategies)
    updated = max((d.get("updated_at", "") for d in strategies.values()), default="")
    label = STRATEGY_LABELS.get(next(iter(strategies), ""), "策略")
    st.caption(f"{label} | 最近更新: {updated[:19]}")
with top_cols[1]:
    auto_refresh = st.checkbox("自动刷新", value=True)
with top_cols[2]:
    refresh_sec = st.number_input("秒", 30, 600, 60, step=30, label_visibility="collapsed")

st.markdown("---")

for sid, data in strategies.items():
    render_card(data)

if auto_refresh:
    import time
    time.sleep(int(refresh_sec))
    st.rerun()
