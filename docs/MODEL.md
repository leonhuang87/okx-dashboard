# Model 01 — LightGBM 预测模型

## 概述

二分类模型, 预测 ETH 价格在 1 小时内是否上涨超过 0.4%。

## 训练数据

| 项目 | 值 |
|------|------|
| 数据源 | ETH-USDT 5m K线 (OKX) |
| 训练期 | 2025 Q1 (11,854 样本) |
| 特征数 | 55 |
| 标签 | 1h-0.4% (fwd=12, threshold=0.4%) |
| 类型 | binary (1=上涨, 0=不涨) |

## 超参数

```python
params = {
    'objective': 'binary',
    'metric': 'auc',
    'num_leaves': 31,
    'learning_rate': 0.05,
    'max_depth': 6,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'min_child_samples': 50,
    'verbose': -1,
}
# early_stopping: 96 rounds
```

## 性能

| 数据集 | AUC | 说明 |
|--------|-----|------|
| 验证集 | 0.533 | 2025 Q1 后 20% |
| 样本外 | 0.518 | 2025 Q2 |

## 关键特征 (Top 10)

| 特征 | 重要性 | 说明 |
|------|--------|------|
| `cross_50_200` | 最高 | EMA50/EMA200 交叉 |
| `vol_50` | 高 | 50 周期波动率 |
| `hour` | 高 | 小时 (时间特征) |
| `adx` | 中 | 趋势强度 |
| `atr` | 中 | 真实波幅 |
| `rsi` | 中 | 相对强弱 |
| `ema_short` | 中 | 短期均线 |
| `ema_long` | 中 | 长期均线 |
| `vwap_dev` | 低 | VWAP 偏离度 |
| `vol_ratio` | 低 | 量比 |

## 完整特征列表 (55 个)

```python
# 价格特征
'close', 'open', 'high', 'low', 'vwap'

# 均线
'ema_short', 'ema_long', 'sma_20', 'sma_50'
'cross_50_200'  # EMA50/EMA200 交叉信号

# 动量
'rsi', 'rsi_14', 'macd', 'macd_signal', 'macd_hist'
'momentum', 'roc'

# 波动率
'atr', 'atr_pct', 'bb_upper', 'bb_lower', 'bb_width'
'vol_20', 'vol_50'

# 趋势
'adx', 'di_plus', 'di_minus'

# 成交量
'vol_ratio', 'vol_change', 'obv'

# VWAP
'vwap_dev', 'vwap'

# 时间
'hour', 'day_of_week', 'hour_sin', 'hour_cos'
'dow_sin', 'dow_cos'

# 滞后特征
'close_lag_1', 'close_lag_2', 'close_lag_3'
'volume_lag_1', 'volume_lag_2'

# 差分特征
'close_diff_1', 'close_diff_2', 'volume_diff_1'

# 滚动统计
'close_roll_mean_12', 'close_roll_std_12'
'volume_roll_mean_12', 'volume_roll_std_12'
```

## 文件位置

```
models/model_01/
├── lgb_model.txt    # 模型文件 (1.5MB)
├── metadata.json    # 训练元数据
└── features.txt     # 特征列表
```

## 标签设计历史

我们尝试了多种标签配置:

| 配置 | fwd | threshold | 说明 | 结果 |
|------|-----|-----------|------|------|
| 1h-0.3% | 12 | 0.3% | 1h内涨0.3% | 信号太多, 胜率低 |
| 1h-0.4% | 12 | 0.4% | 1h内涨0.4% | **最终选择** |
| 1h-0.5% | 12 | 0.5% | 1h内涨0.5% | 信号太少 |
| 2h-0.4% | 24 | 0.4% | 2h内涨0.4% | 差异不大 |

## 模型加载

```python
import lightgbm as lgb

model = lgb.Booster(model_file='models/model_01/lgb_model.txt')
with open('models/model_01/features.txt') as f:
    feat_cols = f.read().strip().split('\n')

# 预测
prob = model.predict(features)[0]  # 0~1 概率
# prob > 0.58 → 做多信号
# prob < 0.42 → 做空信号
# 0.42~0.58 → 观望
```
