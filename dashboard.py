# -*- coding: utf-8 -*-
"""OKX 策略交易 — Streamlit Cloud 远程监控面板（双卡片首页版）。

两个策略卡片并排显示在首页，紧凑布局，窗口自适应。
数据由本地桌面应用导出到 data/monitor_*.json，每 10 分钟自动推送 GitHub。
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
    initial_sidebar_state="collapsed",
)

# ===== 自适应 CSS + 缩放记忆 =====
st.markdown("""
<style id="dynamic-zoom">
/* 紧凑全局 */
.block-container { padding-top: 1rem !important; padding-bottom: 0 !important; max-width: 100% !important; }
[data-testid="stMetric"] { background: rgba(255,255,255,0.03); border-radius: 6px; padding: 4px 8px !important; }
[data-testid="stMetricValue"] { font-size: 1.1rem !important; }
[data-testid="stMetricLabel"] { font-size: 0.75rem !important; }
[data-testid="stMetricDelta"] { font-size: 0.7rem !important; }

/* 卡片容器 */
div[data-testid="stVerticalBlockBorderWrapper"] { gap: 0.3rem !important; }

/* 表格紧凑 */
.stDataFrame { min-height: 0 !important; }
div[data-testid="stDataFrame"] { max-height: 180px; overflow-y: auto; }

/* 图表紧凑 */
div[data-testid="stVegaLiteChart"] { min-height: 160px !important; }

/* 响应式：窄屏切换为单列 */
@media (max-width: 900px) {
    div.row-widget.stHorizontal { flex-direction: column !important; }
}

/* 缩放控制按钮 */
.zoom-bar { position: fixed; top: 4px; right: 12px; z-index: 999;
            font-size: 0.7rem; color: #aaa; user-select: none;
            background: rgba(40,40,40,0.8); padding: 2px 8px; border-radius: 4px; }
.zoom-bar button { background: none; border: 1px solid #555; color: #aaa;
                    cursor: pointer; margin: 0 2px; border-radius: 3px;
                    width: 22px; height: 22px; font-size: 0.75rem; }
.zoom-bar button:hover { background: #333; color: #fff; }
.zoom-bar .label { margin: 0 4px; }
</style>

<!-- 缩放控制条 + localStorage 记忆 -->
<div class="zoom-bar">
    <span class="label">缩放</span>
    <button onclick="setZoom(-0.05)" title="缩小">−</button>
    <span id="zoom-val" style="display:inline-block;width:36px;text-align:center;">100%</span>
    <button onclick="setZoom(0.05)" title="放大">+</button>
    <button onclick="setZoom(0,true)" title="重置" style="width:auto;padding:0 6px;">R</button>
</div>

<script>
function applyZoom(scale) {
    scale = Math.max(0.6, Math.min(1.8, scale));
    document.body.style.zoom = scale;
    document.getElementById('zoom-val').textContent = Math.round(scale * 100) + '%';
    localStorage.setItem('okx_zoom', scale);
}
function setZoom(delta, reset) {
    var cur = parseFloat(localStorage.getItem('okx_zoom') || '1.0');
    if (reset) cur = 1.0;
    else cur += delta;
    applyZoom(cur);
}
// 启动时恢复记忆的缩放
(function() {
    var saved = parseFloat(localStorage.getItem('okx_zoom') || '1.0');
    applyZoom(saved);
})();
</script>
""", unsafe_allow_html=True)


# ===== 数据加载 =====
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

STRATEGY_LABELS = {
    "ETH-USDT": "🇺🇸 U本位 ETH-USDT",
    "ETH-USD": "💰 币本位 ETH-USD",
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


def fmt_pnl(val, unit="USDT"):
    sign = "+" if val >= 0 else ""
    if unit == "ETH":
        return f"{sign}{val:.4f} ETH"
    return f"{sign}{val:.2f}"


def render_strategy_card(data, key_prefix):
    """渲染单个策略卡片。"""
    capital = data.get("capital", 10000)
    equity = data.get("equity", capital)
    trades = data.get("trades", [])
    stats = data.get("stats", {})
    position = data.get("position")
    eq_curve = data.get("equity_curve", [])
    demo_mode = data.get("demo_mode", True)
    is_inverse = "USD" in data.get("strategy_id", "") and "USDT" not in data.get("strategy_id", "")
    unit = "ETH" if is_inverse else "USDT"
    label = STRATEGY_LABELS.get(data.get("strategy_id", ""), data.get("strategy_id", "?"))

    total_return = stats.get("total_return", 0) * 100
    n_trades = stats.get("n_trades", len(trades) // 2)
    win_rate = stats.get("win_rate", 0) * 100
    profit_factor = stats.get("profit_factor", 0)
    max_dd = calc_max_drawdown([p.get("equity", capital) for p in eq_curve]) if eq_curve else 0
    pnl_total = equity - capital
    price = data.get("current_price", 0)

    mode_text = "🧪 模拟盘" if demo_mode else "⚠️ 实盘"

    # 卡片标题
    if position:
        side_text = "多" if position.get("side") == "LONG" else "空"
        pos_icon = "🟢" if position.get("side") == "LONG" else "🔴"
        pos_str = f"{pos_icon} 持{side_text} @ {position.get('entry_price', 0):.2f} · {position.get('qty', 0):.4f}"
    else:
        pos_str = "✅ 空仓"

    st.markdown(f"#### {label} · {mode_text}")
    st.caption(f"{pos_str} | 价格 {price:.2f} | 更新 {data.get('updated_at', '?')[:19]}")

    # 指标行（2x3 紧凑网格）
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("权益", f"{equity:,.0f}", fmt_pnl(pnl_total, unit))
    with c2:
        ret_color = "normal"
        st.metric("收益率", f"{total_return:+.2f}%")
    with c3:
        st.metric("胜率", f"{win_rate:.0f}%")

    c4, c5, c6 = st.columns(3)
    with c4:
        st.metric("盈亏比", f"{profit_factor:.2f}")
    with c5:
        st.metric("回撤", f"{max_dd:.2f}%")
    with c6:
        st.metric("交易数", n_trades)

    # 净值曲线
    if len(eq_curve) > 1:
        eq_df = pd.DataFrame(eq_curve)
        eq_df = eq_df.dropna(subset=["equity"])
        eq_df["equity"] = eq_df["equity"].astype(float)
        st.line_chart(eq_df.set_index("time")["equity"], height=180, use_container_width=True)
    else:
        st.caption("净值数据不足")

    # 最近交易记录（紧凑表格）
    if trades:
        records = []
        for t in reversed(trades[-10:]):
            action = t.get("action", "")
            side = t.get("side", "")
            side_cn = "多" if side == "LONG" else "空"
            if action == "OPEN":
                records.append({
                    "时间": t.get("time", "")[5:16],
                    "操作": f"开{side_cn}",
                    "价格": t.get("price", 0),
                    "盈亏": "—",
                })
            else:
                pnl = t.get("pnl_settle", 0)
                records.append({
                    "时间": t.get("time", "")[5:16],
                    "操作": f"平{side_cn}",
                    "价格": t.get("exit", t.get("price", 0)),
                    "盈亏": fmt_pnl(pnl, unit),
                })
        df = pd.DataFrame(records)
        st.dataframe(df, use_container_width=True, hide_index=True, height=150)
    else:
        st.caption("暂无交易")


# ===== 主界面 =====
st.markdown("## 📈 OKX 策略监控")

strategies = get_strategies()
if not strategies:
    st.warning("未找到策略数据。请确保本地程序正在运行并已推送到 GitHub。")
    st.stop()

# 顶部信息条
top_cols = st.columns([4, 1, 1])
with top_cols[0]:
    n = len(strategies)
    updated = max((d.get("updated_at", "") for d in strategies.values()), default="")
    st.caption(f"{n} 个策略 | 最近更新: {updated[:19]}")
with top_cols[1]:
    auto_refresh = st.checkbox("自动刷新", value=True)
with top_cols[2]:
    refresh_sec = st.number_input("秒", 30, 600, 60, step=30, label_visibility="collapsed")

st.markdown("---")

# 双卡片布局
strategy_list = list(strategies.items())
if len(strategy_list) == 1:
    render_strategy_card(strategy_list[0][1], "s0")
else:
    col_left, col_right = st.columns(2, gap="small")
    with col_left:
        render_strategy_card(strategy_list[0][1], "s0")
    with col_right:
        render_strategy_card(strategy_list[1][1], "s1")

# 超过 2 个策略时，剩余的也并排显示
for i in range(2, len(strategy_list)):
    if i % 2 == 0:
        c_l, c_r = st.columns(2, gap="small")
    with (c_l if i % 2 == 0 else c_r):
        render_strategy_card(strategy_list[i][1], f"s{i}")

# 自动刷新
if auto_refresh:
    import time
    time.sleep(int(refresh_sec))
    st.rerun()
