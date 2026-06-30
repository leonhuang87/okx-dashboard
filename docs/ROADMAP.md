# 待做 + 已知问题

## 高优先级

### 1. 策略模型优化

- [ ] 增加特征: 资金费率、跨币相关性(BTC/ETH)、高时间框架指标(4h/1d)
- [ ] 滚动窗口训练: 每月重训练, 适应市场变化
- [ ] 二分类 vs 回归: 尝试直接预测收益率而非涨跌
- [ ] 市况分层: 高波动/低波动/趋势/震荡分别建模
- [ ] GPU 加速: 当前用 CPU (AMD RX 6800 无 CUDA), 可考虑 ROCm 或云 GPU

### 2. 开仓价优化

- [ ] engine.py 使用 OKX 实际成交价 `avgPx` 而非 `last_row['close']`
- [ ] 滑点分析

### 3. 做空胜率优化

- [ ] 当前做空胜率 (52.9%) 低于做多 (58.1%)
- [ ] 可能需要非对称阈值: 做多 0.58, 做空 0.40

## 中优先级

### 4. 风控增强

- [ ] 最大回撤限制 (如 25% 自动停止)
- [ ] 连续亏损保护 (如连续 5 次亏损暂停)
- [ ] 单日最大亏损限制
- [ ] 异常行情检测 (闪崩/暴涨)

### 5. 多币种支持

- [ ] 当前只支持 ETH-USDT
- [ ] 扩展到 BTC, SOL 等
- [ ] 需要每个币种独立的模型

### 6. 实盘切换

- [ ] 当前只用模拟盘 (`--demo`)
- [ ] 需要实盘 API Key
- [ ] 需要更严格的风控

## 低优先级

### 7. 前端优化

- [ ] 移动端适配
- [ ] WebSocket 推送 (替代 5 秒轮询)
- [ ] 更多图表指标 (MA, BB, MACD 叠加)
- [ ] 交易历史导出 (CSV)

### 8. 运维

- [ ] 日志轮转 (strategy.log 无限增长)
- [ ] 数据库定期清理旧数据
- [ ] 服务崩溃自动重启 (systemd/supervisor)

## 已知问题

### 编码问题

- [x] ~~PowerShell 编码损坏 index.html~~ → 已重建, 用 Python 脚本替代
- [x] ~~JS emoji 语法错误~~ → 已用 Unicode 转义替换
- [x] ~~JS `.then()` 缺少关闭括号~~ → 已修复

### OKX CLI

- [x] ~~认证方式 config 不认~~ → 改用环境变量
- [x] ~~现货卖出 sz 含义错误~~ → 买入=USDT, 卖出=ETH
- [x] ~~下单量未取整~~ → round(size, 2)
- [x] ~~stderr 误判为错误~~ → 只检查 stdout

### 策略

- [ ] 跨年不可泛化: 2025 高波动 (253%) vs 2026 平稳, 固定参数失效
- [ ] 回测过拟合风险: 样本外表现显著下降
- [ ] LightGBM AUC 仅 0.52, 接近随机

### UI

- [x] ~~持仓闪烁~~ → 合并为单一 loadPositions 函数
- [x] ~~K线标记重叠~~ → 只在 loadPositions 中调用 updateChartMarkers
- [x] ~~成交记录只有合约~~ → 合并 spot fills + swap fills

## 环境信息

| 项目 | 值 |
|------|------|
| OS | Windows 10 x64 (19045) |
| CPU | AMD Ryzen 7 3700X |
| GPU | AMD RX 6800 (无 CUDA) |
| RAM | 32GB |
| Node | v22.22.3 |
| Python | python -m pip (pip shim 损坏) |
| OKX CLI | @okx_ai/okx-trade-cli@1.3.9 |
| 数据库 | SQLite market.db 59.6MB |
| K线数据 | ETH 5m 262,080 条 (2024-01~2026-06) |
