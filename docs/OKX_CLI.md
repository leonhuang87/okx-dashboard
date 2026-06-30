# OKX CLI 命令速查

## 环境

- CLI 路径: `C:\Users\leonh\AppData\Local\hermes\node\okx.cmd`
- 版本: `@okx_ai/okx-trade-cli@1.3.9`
- 认证: 环境变量方式 (config 文件方式有 bug, 不认)
- 模拟盘: 必须加 `--demo`
- 网络: www.okx.com 被墙, 依赖 Pilot 代理 (okexweb.qqhrss.com)

## 环境变量

```powershell
$env:OKX_API_KEY = 'xxx'
$env:OKX_SECRET_KEY = 'xxx'
$env:OKX_PASSPHRASE = 'xxx'
```

## 常用命令

### 行情

```bash
# 获取 ticker
okx market ticker ETH-USDT --json --demo
# 返回: last, bidPx, askPx, high24h, low24h, vol24h, ts
# 注意: 返回值是列表, 需要取 [0]
```

### 账户

```bash
# 账户余额
okx account balance --json --demo
# 返回: [{totalEq, details: [{ccy, availBal, frozenBal}]}]
# 注意: 返回值是列表, 需要取 [0]

# 持仓
okx account positions --json --demo
# 返回: [{instId, pos, posSide, avgPx, last, upl, lever, instType}]
# posSide=net 模式: pos>0=做多, pos<0=做空
```

### 现货交易

```bash
# 买入 (sz = USDT 金额, 不是 ETH 数量!)
okx spot place --instId ETH-USDT --side buy --ordType market --sz 100 --json --demo

# 卖出 (sz = ETH 数量, 不是 USDT!)
okx spot place --instId ETH-USDT --side sell --ordType market --sz 0.5 --json --demo

# 现货没有 close 命令, 只能反向卖出
# 现货没有 spot fills 命令? 试试:
okx spot fills --instId ETH-USDT --json --demo
```

### 合约交易

```bash
# 开仓 (sz = 合约数量, ETH)
okx swap place --instId ETH-USDT-SWAP --side buy --ordType market --sz 0.1 --tdMode cross --json --demo

# 平仓
okx swap close --instId ETH-USDT-SWAP --sz 0.1 --json --demo

# 限价单
okx swap place --instId ETH-USDT-SWAP --side buy --ordType limit --sz 0.1 --px 1500 --tdMode cross --json --demo

# 成交记录
okx swap fills --json --demo
```

## ⚠️ 关键坑点

### 1. 现货买卖 sz 含义不同

| 操作 | `--sz` 含义 | 示例 |
|------|------------|------|
| 现货买入 | USDT 金额 | `--sz 100` = 买 100 USDT 的 ETH |
| 现货卖出 | ETH 数量 | `--sz 0.5` = 卖 0.5 ETH |
| 合约开仓 | ETH 数量 | `--sz 0.1` = 0.1 ETH |
| 合约平仓 | ETH 数量 | `--sz 0.1` = 平 0.1 ETH |

**server.py 中的处理:**
- 买入: `size_usdt = size_eth * last_price`, 最低 10 USDT
- 卖出: 直接用 ETH 数量

### 2. 返回值是列表

几乎所有 `--json` 命令返回的都是数组, 即使只有一条记录:
```python
data = json.loads(r.stdout)
if isinstance(data, list) and len(data) > 0:
    data = data[0]
```

### 3. stderr 输出

OKX CLI 的 verbose 信息输出到 stderr, 不是错误。判断命令是否成功:
```python
# ✗ 错误: stderr 非空不代表失败
if r.stderr: return error

# ✓ 正确: 只检查 stdout
if not r.stdout.strip(): return error
result = json.loads(r.stdout)
if result.get('sCode', '0') != '0': return error
```

### 4. 错误码

```json
{"sCode": "51020", "sMsg": "Your order should meet or exceed the minimum order amount."}
{"sCode": "0", "sMsg": "Order placed"}  // 成功
```

### 5. Pilot 代理

```bash
okx pilot status    # 检查代理状态
okx pilot start     # 启动代理
okx pilot stop      # 停止代理
```

如果 CLI 报网络错误, 先检查 Pilot 代理是否运行。

### 6. 净头寸模式

OKX 模拟盘默认 net_mode:
- `posSide=net`, `pos>0` = 做多, `pos<0` = 做空
- `swap place --side buy` = 开多 (如果已有空仓, 会减仓而不是开新仓)
- `swap place --side sell` = 开空 (如果已有多仓, 会减仓)
- 想要平仓用 `swap close`, 不用 `swap place --side` 反向

### 7. 模拟盘默认资产

新模拟盘账户默认有:
- 1 BTC
- 100 OKB
- 若干 ETH
- ~100,000 USDT
