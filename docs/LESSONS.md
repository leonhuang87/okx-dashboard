# 开发踩坑记录

## 🔴 严重: PowerShell 编码损坏

**起因**: 用 `Get-Content` + `Set-Content -Encoding UTF8` 编辑 index.html

**原理**: PowerShell 5.1 的 `Get-Content -Raw` 在中文 Windows 上用系统 ANSI 代码页 (GBK/CP936) 读取文件, 配合 `Set-Content -Encoding UTF8` 造成 UTF-8→GBK→UTF-8 双重编码。

**结果**: 所有中文变成乱码, 文件无法恢复 (尝试了 gb18030/gbk 逆向修复, 但多次脚本覆盖后彻底损坏)。

**教训**:
- ❌ 永远不要用 PowerShell `Get-Content`/`Set-Content` 处理 UTF-8 中文文件
- ✅ 用 `read`/`write` 工具直接读写
- ✅ 用 Python 脚本做文件替换 (`open(path, 'r', encoding='utf-8')`)
- ✅ 用 `edit` 工具精确替换

## 🔴 严重: JS emoji 语法错误

**起因**: 在 JS 模板字面量中使用 emoji (✅❌⚠️)

**结果**: 浏览器 JS 解析失败, 整个页面白屏

**具体表现**:
- `✅` 在某些编码环境下被解析为多个字节
- `[OK]` 被解析为数组语法
- 反引号模板字面量中的 emoji 导致解析器混乱

**教训**:
- ❌ 不要在 JS 中使用 emoji
- ✅ 用 Unicode 转义: `\u2705` `\u274C` `\u26A0`
- ✅ 或者用纯文本: `[OK]` `[FAIL]` `[WARN]`

## 🟡 中等: OKX CLI 认证

**问题**: `okx config set` 方式设置 API Key 有 bug, CLI 不认

**解决**: 用环境变量方式:
```python
env = os.environ.copy()
env.update({
    'OKX_API_KEY': 'xxx',
    'OKX_SECRET_KEY': 'xxx',
    'OKX_PASSPHRASE': 'xxx'
})
subprocess.run([...], env=env)
```

## 🟡 中等: OKX CLI 命令格式

**错误**: `okx trade order` (不存在)
**正确**: `okx swap place`

**错误**: `okx account fills` (不存在)
**正确**: `okx swap fills`

## 🟡 中等: 现货 sz 含义不同

**错误**: 现货卖出用 USDT 金额
**正确**: 
- 现货买入: sz = USDT 金额
- 现货卖出: sz = ETH 数量

**错误信息**: "Your order should meet or exceed the minimum order amount."

## 🟡 中等: 下单量取整

ETH-USDT-SWAP 的 lot size = 0.01, 必须取整:
```python
size = round(size_eth, 2)  # 0.01 精度
```

## 🟡 中等: stderr 误判

OKX CLI 的 verbose 信息输出到 stderr, 不是错误。server.py 中:
```python
# ✗ 错误: stderr 有内容就报错
if r.stderr: return error

# ✓ 正确: 只检查 stdout
if not r.stdout.strip(): return error
```

## 🟢 轻微: 回测 DataFrame 子集操作

```python
# ✗ 错误: SettingWithCopyWarning
df = df[df['close'] > 100]
df['new_col'] = df['close'] * 2

# ✓ 正确: 先 copy
df = df[df['close'] > 100].copy()
df['new_col'] = df['close'] * 2
```

## 🟢 轻微: Python Unicode emoji 输出

Windows Python 输出 emoji 会触发 GBK 编码错误:
```python
# ✗ 错误
print("✅ Done")

# ✓ 正确
print("[OK] Done")
# 或
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
```

## 🟢 轻微: pip shim 损坏

Windows 上 `pip` 命令的 shim 可能损坏:
```bash
# ✗ 错误
pip install xxx

# ✓ 正确
python -m pip install xxx
```

## 🟢 轻微: Node.js 检查 JS 语法

```powershell
# 方法1: 直接检查
node --check "file.js"

# 方法2: 用 new Function
node -e "try{new Function(require('fs').readFileSync('file.js','utf-8'));console.log('OK')}catch(e){console.log(e.message)}"
```

## 🟢 轻微: Gitee SSH 首次连接

```powershell
# 添加 gitee.com 到 known_hosts
ssh-keyscan -t ed25519 gitee.com >> "$env:USERPROFILE\.ssh\known_hosts"

# 或者跳过 host key 检查 (临时)
$env:GIT_SSH_COMMAND = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL'
git push -u origin main
```
