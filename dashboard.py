# -*- coding: utf-8 -*-
"""
OKX 交易系统 - 远程监控面板
部署到 Streamlit Cloud，手机/电脑浏览器随时查看。
只读数据，不控制交易。
"""
import streamlit as st
import json, os, glob
from datetime import datetime
import pandas as pd

st.set_page_config(
    page_title="OKX 交易监控",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===== 数据加载 =====
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def load_ledger(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def get_strategies():
    """列出所有可用策略"""
    strategies = {}
    for f in glob.glob(os.path.join(DATA_DIR, "trades_*.json")):
        name = os.path.basename(f).replace("trades_", "").replace(".json", "")
        data = load_ledger(os.path.basename(f))
        if data:
            strategies[name] = data
    return strategies

def calc_stats(trades, capital):
    """计算策略统计"""
    closes = [t for t in trades if t.get("action") == "CLOSE"]
    if not closes:
        return {
            "total_trades": 0, "win_rate": 0, "total_pnl": 0,
            "return_pct": 0, "max_dd": 0, "profit_factor": 0,
            "avg_win": 0, "avg_loss": 0,
        }
    wins = [t for t in closes if t.get("pnl_settle", 0) > 0]
    losses = [t for t in closes if t.get("pnl_settle", 0) <= 0]
    total_pnl = sum(t.get("pnl_settle", 0) for t in closes)
    avg_win = sum(t["pnl_settle"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl_settle"] for t in losses) / len(losses) if losses else 0
    gross_win = sum(t["pnl_settle"] for t in wins)
    gross_loss = abs(sum(t["pnl_settle"] for t in losses))
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")

    # 最大回撤
    equities = [capital]
    for t in closes:
        eq = t.get("equity")
        if eq:
            equities.append(eq)
    peak = equities[0]
    max_dd = 0
    for eq in equities:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    return {
        "total_trades": len(closes),
        "win_rate": len(wins) / len(closes) * 100,
        "total_pnl": total_pnl,
        "return_pct": (total_pnl / capital * 100) if capital > 0 else 0,
        "max_dd": max_dd * 100,
        "profit_factor": pf,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
    }

def build_equity_curve(trades, capital):
    """从交易记录构建净值曲线"""
    points = [{"time": None, "equity": capital}]
    for t in trades:
        if t.get("action") == "CLOSE" and t.get("equity"):
            time_str = t.get("time", "")
            points.append({"time": time_str, "equity": t["equity"]})
    return points

# ===== 主界面 =====
st.title("📈 OKX 交易监控")

# 加载所有策略
strategies = get_strategies()
if not strategies:
    st.warning("未找到策略数据。请确保 data/ 目录下有 trades_*.json 文件。")
    st.stop()

# 策略选择
strategy_names = list(strategies.keys())
labels = {
    "usdt": "🇺🇸 U本位 ETH-USDT",
    "usd": "💰 币本位 ETH-USD",
    "usd_sim": "🧪 币本位本地模拟",
    "usd_original": "📜 原版ETH-USD模拟",
    "usdt_original": "📜 原版ETH-USDT模拟",
}
options = [labels.get(s, s) for s in strategy_names]
selected_label = st.sidebar.selectbox("选择策略", options, index=0)
selected_idx = options.index(selected_label)
selected = strategy_names[selected_idx]

data = strategies[selected]
capital = data.get("capital", 5000)
trades = data.get("trades", [])
is_inverse = "usd" in selected

# 侧边栏信息
st.sidebar.markdown("---")
st.sidebar.markdown(f"**初始资金**: {capital} {'ETH' if is_inverse else 'USDT'}")
st.sidebar.markdown(f"**杠杆**: {data.get('leverage', 10)}x")
st.sidebar.markdown(f"**模式**: {data.get('capital_mode', 'fixed')}")
st.sidebar.markdown(f"**交易数**: {len(trades)}")
st.sidebar.markdown(f"**更新时间**: {datetime.now().strftime('%H:%M:%S')}")

# ===== 统计卡片 =====
stats = calc_stats(trades, capital)

col1, col2, col3, col4 = st.columns(4)
with col1:
    pnl_str = f"{stats['total_pnl']:+.6f}" if is_inverse else f"{stats['total_pnl']:+.2f}"
    st.metric("总收益", pnl_str)
with col2:
    st.metric("收益率", f"{stats['return_pct']:+.2f}%")
with col3:
    st.metric("胜率", f"{stats['win_rate']:.1f}%")
with col4:
    st.metric("最大回撤", f"{stats['max_dd']:.2f}%")

col5, col6, col7, col8 = st.columns(4)
with col5:
    st.metric("盈亏比", f"{stats['profit_factor']:.2f}")
with col6:
    st.metric("总交易", stats["total_trades"])
with col7:
    avg_w_str = f"{stats['avg_win']:.6f}" if is_inverse else f"{stats['avg_win']:.2f}"
    st.metric("平均盈利", avg_w_str)
with col8:
    avg_l_str = f"{stats['avg_loss']:.6f}" if is_inverse else f"{stats['avg_loss']:.2f}"
    st.metric("平均亏损", avg_l_str)

# ===== 当前持仓 =====
opens = [t for t in trades if t.get("action") == "OPEN"]
closes = [t for t in trades if t.get("action") == "CLOSE"]

# 判断是否有未平仓
if len(opens) > len(closes):
    last_open = opens[-1]
    st.info(
        f"📊 **当前持仓**: {last_open.get('side', '?')} "
        f"| 开仓价: {last_open.get('price', '?')} "
        f"| 数量: {last_open.get('size', '?')} "
        f"| 开仓时间: {last_open.get('time', '?')[:19]}"
    )
else:
    st.success("✅ 当前无持仓")

# ===== 净值曲线 =====
st.subheader("📈 净值曲线")
equity_points = build_equity_curve(trades, capital)
if len(equity_points) > 1:
    eq_df = pd.DataFrame(equity_points)
    eq_df = eq_df.dropna(subset=["equity"])
    eq_df["equity"] = eq_df["equity"].astype(float)
    st.line_chart(eq_df.set_index("time")["equity"], height=300)
else:
    st.caption("暂无足够数据绘制净值曲线")

# ===== 交易记录 =====
st.subheader("📋 交易记录")
if trades:
    records = []
    for t in reversed(trades[-50:]):  # 最近50笔，最新在前
        action = t.get("action", "")
        side = t.get("side", "")
        pnl = t.get("pnl_settle", 0)
        reason = t.get("reason", "")

        if action == "OPEN":
            records.append({
                "时间": t.get("time", "")[:19],
                "操作": f"开{'多' if side == 'LONG' else '空'}",
                "价格": t.get("price", 0),
                "数量": t.get("size", 0),
                "盈亏": "--",
                "原因": "--",
            })
        else:
            pnl_color = "+" if pnl > 0 else ""
            unit = "ETH" if is_inverse else "USDT"
            records.append({
                "时间": t.get("time", "")[:19],
                "操作": f"平{'多' if side == 'LONG' else '空'}",
                "价格": t.get("exit", 0),
                "数量": t.get("size", 0),
                "盈亏": f"{pnl_color}{pnl:.6f} {unit}" if is_inverse else f"{pnl_color}{pnl:.2f} {unit}",
                "原因": reason or "--",
            })

    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.caption("暂无交易记录")

# ===== 自动刷新 =====
st.sidebar.markdown("---")
auto_refresh = st.sidebar.checkbox("自动刷新 (60秒)", value=True)
if auto_refresh:
    import time
    time.sleep(1)
    st.rerun()
