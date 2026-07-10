# -*- coding: utf-8 -*-
"""OKX 策略交易 — Streamlit Cloud 远程监控面板。

部署到 Streamlit Cloud，手机/电脑浏览器随时查看。
只读数据，不控制交易。数据由本地桌面应用导出到 data/monitor_*.json。

部署步骤：
  1. 将项目推送到 GitHub
  2. 在 streamlit.io 创建应用，指向 dashboard.py
  3. 设置 Python 版本和依赖（requirements_streamlit.txt）
"""
import json
import os
import glob
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="OKX 策略监控",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===== 数据加载 =====
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

STRATEGY_LABELS = {
    "ETH-USDT": "🇺🇸 U本位 ETH-USDT",
    "ETH-USD": "💰 币本位 ETH-USD",
}


def load_monitor(filename):
    """加载监控 JSON 文件。"""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_strategies():
    """列出所有可用策略监控数据。"""
    strategies = {}
    for f in glob.glob(os.path.join(DATA_DIR, "monitor_*.json")):
        name = os.path.basename(f).replace("monitor_", "").replace(".json", "")
        data = load_monitor(os.path.basename(f))
        if data:
            strategies[name] = data
    return strategies


def calc_max_drawdown(equity_curve):
    """从净值曲线计算最大回撤。"""
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


# ===== 主界面 =====
st.title("📈 OKX 策略交易监控")

# 加载策略数据
strategies = get_strategies()
if not strategies:
    st.warning("未找到策略数据。请确保 data/ 目录下有 monitor_*.json 文件。")
    st.info("💡 数据由本地桌面应用自动导出，请确保本地程序正在运行并已推送到 GitHub。")
    st.stop()

# 策略选择
strategy_names = list(strategies.keys())
options = [STRATEGY_LABELS.get(s, s) for s in strategy_names]
selected_label = st.sidebar.selectbox("选择策略", options, index=0)
selected_idx = options.index(selected_label)
selected = strategy_names[selected_idx]

data = strategies[selected]
capital = data.get("capital", 10000)
equity = data.get("equity", capital)
trades = data.get("trades", [])
stats = data.get("stats", {})
position = data.get("position")
eq_curve = data.get("equity_curve", [])
demo_mode = data.get("demo_mode", True)
is_inverse = "USD" in selected and "USDT" not in selected

# 侧边栏信息
mode_text = "🧪 模拟盘" if demo_mode else "⚠️ 实盘"
st.sidebar.markdown("---")
st.sidebar.markdown(f"**模式**: {mode_text}")
st.sidebar.markdown(f"**初始资金**: {capital:,.0f} {'ETH' if is_inverse else 'USDT'}")
st.sidebar.markdown(f"**杠杆**: {data.get('leverage', 1)}x")
st.sidebar.markdown(f"**当前价格**: {data.get('current_price', 0):.2f}")
st.sidebar.markdown(f"**更新时间**: {data.get('updated_at', '?')}")
st.sidebar.markdown(f"**交易数**: {len(trades) // 2}")

# ===== 统计卡片 =====
total_return = stats.get("total_return", 0) * 100
n_trades = stats.get("n_trades", len(trades) // 2)
win_rate = stats.get("win_rate", 0) * 100
profit_factor = stats.get("profit_factor", 0)
max_dd = calc_max_drawdown([p.get("equity", capital) for p in eq_curve]) if eq_curve else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    delta = equity - capital
    st.metric("当前权益", f"{equity:,.2f}", f"{delta:+,.2f}")
with col2:
    st.metric("收益率", f"{total_return:+.2f}%")
with col3:
    st.metric("胜率", f"{win_rate:.1f}%")
with col4:
    st.metric("最大回撤", f"{max_dd:.2f}%")

col5, col6, col7, col8 = st.columns(4)
with col5:
    st.metric("盈亏比", f"{profit_factor:.2f}")
with col6:
    st.metric("总交易", n_trades)
with col7:
    st.metric("现金", f"{stats.get('cash', 0):,.2f}")
with col8:
    unit = "ETH" if is_inverse else "USDT"
    pnl_total = equity - capital
    st.metric("总盈亏", f"{pnl_total:+,.2f} {unit}")

# ===== 当前持仓 =====
st.markdown("---")
if position:
    side_text = "多" if position.get("side") == "LONG" else "空"
    color = "🟢" if position.get("side") == "LONG" else "🔴"
    st.info(
        f"{color} **当前持仓**: {side_text} "
        f"| 开仓价: {position.get('entry_price', 0):.2f} "
        f"| 数量: {position.get('qty', 0):.4f} "
        f"| 开仓时间: {position.get('entry_time', '?')[:19]}"
    )
else:
    st.success("✅ 当前无持仓")

# ===== 净值曲线 =====
st.subheader("📈 净值曲线")
if len(eq_curve) > 1:
    eq_df = pd.DataFrame(eq_curve)
    eq_df = eq_df.dropna(subset=["equity"])
    eq_df["equity"] = eq_df["equity"].astype(float)
    st.line_chart(eq_df.set_index("time")["equity"], height=300)
else:
    st.caption("暂无足够数据绘制净值曲线")

# ===== 交易记录 =====
st.subheader("📋 交易记录")
if trades:
    records = []
    for t in reversed(trades[-50:]):  # 最近50条，最新在前
        action = t.get("action", "")
        side = t.get("side", "")
        side_cn = "多" if side == "LONG" else "空"

        if action == "OPEN":
            records.append({
                "时间": t.get("time", "")[:19],
                "操作": f"开{side_cn}",
                "价格": t.get("price", 0),
                "数量": t.get("size", 0),
                "盈亏": "--",
            })
        else:
            pnl = t.get("pnl_settle", 0)
            unit = "ETH" if is_inverse else "USDT"
            records.append({
                "时间": t.get("time", "")[:19],
                "操作": f"平{side_cn}",
                "价格": t.get("exit", t.get("price", 0)),
                "数量": t.get("size", 0),
                "盈亏": f"{pnl:+.4f} {unit}" if is_inverse else f"{pnl:+.2f} {unit}",
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
    time.sleep(60)
    st.rerun()
