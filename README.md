# OKX 量化交易系统

基于 LightGBM 预测模型的 ETH 自动交易系统，含 Web UI 实时监控。

## 系统架构

```
index.html (前端)  ←→  server.py (Flask API)  ←→  engine.py (策略引擎)
    ↓                       ↓                          ↓
TradingView K线      OKX CLI 子进程调用         LightGBM 预测模型
手动交易面板         SQLite 数据库              自动开仓/平仓
策略账本面板         配置管理                   持仓自动校验
```

- **server.py** — Flask 后端，端口 5000，SSE 流式下载 + API
- **engine.py** — 策略引擎，每 60 秒预测 + 持仓校验 + 自动交易
- **index.html** — 单文件前端，5 个 Tab（账户/策略/手动/数据/配置）
- **backtest_engine.py** — 回测引擎，支持参数化回测
- **启动服务器.vbs** — 静默启动器，双击即可

## 快速启动

```bash
# 1. 安装依赖
python -m pip install flask lightgbm pandas numpy scikit-learn

# 2. 启动服务器（三种方式任选）
python -B server.py          # 控制台启动
start.bat                    # 批处理启动
双击 启动服务器.vbs           # 静默启动（自动打开浏览器）

# 3. 打开浏览器
# http://localhost:5000
```

## 功能特性

### 策略引擎
- LightGBM 二分类预测（55 特征，每 60 秒）
- 自动开仓/平仓，止盈 3×ATR，止损 2×ATR
- **持仓自动校验**：每次 tick 与 OKX 实际持仓对比，方向/数量不一致时自动同步
- 配置持久化：杠杆、资金修改后重启不丢失

### Web UI（5 个 Tab）
- **账户详情**：资产概览、TradingView K 线图、持仓表格、成交记录、系统日志
- **策略开发**：净值/收益/杠杆/可用仓位卡片、收益曲线图、历史成交
- **手动交易**：交易对搜索（500+ 币种）、现货/合约切换、市价/限价下单
- **数据管理**：K 线循环下载（SSE 流式进度条）、数据库统计
- **系统配置**：API Key 管理、策略参数、自动运行开关

### 前端亮点
- K 线缩放不重置（刷新保留可视范围）
- 价格标签左侧显示（开多/开空、止盈、止损）
- 成交方向智能显示（现货：买入/卖出；合约：开多/开空/平多/平空）
- 预测自动更新（从引擎 last_signal 读取，无需手动点击）
- 收益曲线（TradingView baselineSeries，0 轴上下双色）
- 回测净值曲线（同样风格的折线图）
- 现货持仓自动过滤零余额币种

## 数据源

- **OKX 模拟盘** — 通过 OKX CLI (Pilot 代理) 访问
- **数据库** — SQLite `data/market.db`，ETH 5m 262K+ bars (2024-01~2026-06)
- **模型** — `models/model_01/` (LightGBM 二分类，AUC 0.53)

## 文档索引

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系统架构详解 |
| [OKX_CLI.md](docs/OKX_CLI.md) | OKX CLI 命令速查 + 踩坑 |
| [MODEL.md](docs/MODEL.md) | Model 01 参数 + 特征工程 |
| [STRATEGY.md](docs/STRATEGY.md) | 策略参数 + 回测结论 |
| [LESSONS.md](docs/LESSONS.md) | 开发踩坑记录 |
| [ROADMAP.md](docs/ROADMAP.md) | 待做 + 已知问题 |
