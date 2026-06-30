# 系统架构

## 文件关系

```
┌─────────────────────────────────────────────────────┐
│                   index.html (前端)                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐  │
│  │账户详情  │ │策略开发  │ │手动交易  │ │数据管理   │  │
│  │- 资产   │ │- 账本   │ │- 现货   │ │- K线下载  │  │
│  │- K线图  │ │- 净值   │ │- 合约   │ │- TICK下载 │  │
│  │- 持仓   │ │- 持仓   │ │- 平仓   │ │- 数据预览 │  │
│  │- 成交   │ │- 历史   │ │- 成交   │ │- DB统计   │  │
│  └────┬────┘ └────┬────┘ └────┬────┘ └─────┬────┘  │
│       └───────────┴───────────┴─────────────┘       │
│                    fetch() API 调用                    │
└────────────────────────┬────────────────────────────┘
                         │ HTTP
┌────────────────────────▼────────────────────────────┐
│                 server.py (Flask :5000)                │
│                                                       │
│  /api/account/balance    ← okx account balance        │
│  /api/account/positions  ← okx account positions      │
│  /api/account/fills      ← okx swap fills + spot fills│
│  /api/account/spot_holdings ← okx account balance     │
│  /api/market/ticker      ← okx market ticker          │
│  /api/market/candles     ← SQLite 查询                │
│  /api/strategy/status    ← engine.status()            │
│  /api/strategy/nav       ← engine 净值               │
│  /api/strategy/positions ← engine 持仓               │
│  /api/strategy/trades    ← engine 交易记录            │
│  /api/trade/order        ← okx spot/swap place        │
│  /api/trade/close        ← okx swap close             │
│  /api/config/apikey      ← 读写 OKX API 配置          │
│  /api/logs               ← strategy.log 读取          │
│                                                       │
│  后台线程: data_fetcher_loop() 每分钟拉取K线           │
│  启动时: auto_start=true 自动启动 engine               │
└────────────┬──────────────────────┬──────────────────┘
             │                      │
    ┌────────▼────────┐   ┌────────▼────────┐
    │  OKX CLI (子进程) │   │   engine.py      │
    │  okx --demo      │   │                  │
    │  swap place/close│   │  LightGBM 模型   │
    │  spot place      │   │  55 个特征       │
    │  market ticker   │   │  二分类预测       │
    │  account balance │   │  自动开仓/平仓   │
    └─────────────────┘   │  TP/SL 管理      │
                          │  trade_log 持久化 │
                          └──────────────────┘
```

## 前端 Tab 结构

### 1. 账户详情
- 概览卡片: 总资产 / 可用资金 / 持仓数量 / 最新价格
- K线图: TradingView lightweight-charts, 5m/15m 切换
- 策略面板: Model 01 启动/停止, 预测方向/概率/价格
- 合约持仓表格 + 现货持仓表格
- 成交记录表格 (现货标"现", 合约标"约")
- 系统日志 (全部/策略/系统 筛选)

### 2. 策略开发
- 策略净值 (初始资金可编辑, localStorage 持久化)
- 策略收益 (含胜率)
- 策略持仓
- 历史成交记录

### 3. 手动交易
- 现货/合约切换
- 买入/卖出, 市价/限价
- 百分比按钮 (25%/50%/75%/100%)
- 杠杆控制 (合约模式)
- 行情面板 (买一/卖一/24h高/低/量/涨跌幅)
- 持仓表格 (含平仓按钮)
- 成交记录

### 4. 数据管理
- K线数据下载 (1m/5m/15m/1H/4H/1D/TICK)
- 数据预览 + 图表
- 数据库统计

### 5. 系统配置
- API Key / Secret / Passphrase (可编辑)
- 策略参数 (开仓阈值/TP/SL/风险比例)
- 自动运行开关

## 刷新机制

所有数据统一 **5 秒** 刷新:
- K线图: `renderChart()` 更新数据, 不重建图表 (保留标记)
- 持仓: `loadPositions()` 同时更新账户详情和手动交易两个表格
- 成交: `loadFills()` 合并现货+合约成交
- 现货持仓: `loadSpotHoldings()` 从 balance API 提取
- K线标记: `updateChartMarkers()` 从策略引擎获取真实 TP/SL
- 日志: `loadLogs()` 15 秒

## 持仓刷新防闪烁

`loadPositions()` 一次 fetch 同时更新两个表格 (`#posTable` + `#tradePosTable`), 避免多个 setInterval 交替刷新导致闪烁。
