# OKX 量化交易系统

基于 LightGBM 预测模型的 ETH 自动交易系统，含 Web UI 实时监控。

## 系统架构

```
index.html (前端)  ←→  server.py (Flask API)  ←→  engine.py (策略引擎)
    ↓                       ↓                          ↓
TradingView K线      OKX CLI 子进程调用         LightGBM 预测模型
手动交易面板         SQLite 数据库              自动开仓/平仓
策略账本面板         配置管理                   交易记录持久化
```

- **server.py** — Flask 后端，端口 5000，提供 API + 静态文件
- **engine.py** — 策略引擎，每 60 秒预测一次，自动执行交易
- **index.html** — 单文件前端，5 个 Tab（账户/策略/手动/数据/配置）

## 快速启动

```bash
# 1. 安装依赖
python -m pip install flask lightgbm pandas numpy scikit-learn

# 2. 启动服务器（自动启动策略引擎）
python -B server.py

# 3. 打开浏览器
# http://localhost:5000
```

## 数据源

- **OKX 模拟盘** — 通过 OKX CLI (Pilot 代理) 访问
- **数据库** — SQLite `data/market.db`，ETH 5m 262K bars (2024-01~2026-06)
- **模型** — `models/model_01/` (LightGBM 二分类)

## 文档索引

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系统架构详解 |
| [OKX_CLI.md](docs/OKX_CLI.md) | OKX CLI 命令速查 + 踩坑 |
| [MODEL.md](docs/MODEL.md) | Model 01 参数 + 特征工程 |
| [STRATEGY.md](docs/STRATEGY.md) | 策略参数 + 回测结论 |
| [LESSONS.md](docs/LESSONS.md) | 开发踩坑记录 |
| [ROADMAP.md](docs/ROADMAP.md) | 待做 + 已知问题 |
