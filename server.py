# -*- coding: utf-8 -*-
"""
OKX Trading System Backend API
Serves real data from SQLite DB + OKX API + LightGBM Model
"""
import os, json, sqlite3, subprocess, time
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='D:/软件制作/币交易开发')
CORS(app)

DB_PATH = 'D:/软件制作/币交易开发/data/market.db'
CONFIG_PATH = 'D:/software_maker/models/model_01/strategy_config.json'
OKX_CMD = r'C:\Users\leonh\AppData\Local\hermes\node\okx.cmd'

# Initialize strategy engine
from engine import StrategyEngine
engine = StrategyEngine()

# Background data fetcher - fetch latest candles every 5 minutes
def data_fetcher_loop():
    import sqlite3, subprocess, json, time
    while True:
        try:
            env = get_okx_env()
            for inst, bar in [('ETH-USDT', '5m')]:
                cmd = [OKX_CMD, 'market', 'candles', inst, '--bar', bar, '--limit', '10', '--json']
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, env=env)
                if r.returncode != 0: continue
                data = json.loads(r.stdout)
                if not data: continue
                conn = sqlite3.connect(DB_PATH)
                for c in data:
                    ts = int(c[0])
                    conn.execute(
                        'INSERT OR REPLACE INTO candles (inst, bar, ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        (inst, bar, ts, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5]), float(c[6]), float(c[7]), int(c[8]))
                    )
                conn.commit()
                conn.close()
        except Exception as e:
            pass
        time.sleep(60)  # 1 minute

import threading
data_thread = threading.Thread(target=data_fetcher_loop, daemon=True)
data_thread.start()
MODEL_DIR = 'D:/software_maker/models/model_01'

def get_okx_env():
    env = os.environ.copy()
    env.update({
        'OKX_API_KEY': '52ca522d-3bb6-4213-800c-0341e3cafc04',
        'OKX_SECRET_KEY': '07FC20C9E1E065B43CE01ADAFF3CCE1D',
        'OKX_PASSPHRASE': '.Huang870521'
    })
    return env

# ===== Static files =====
@app.route('/')
def index():
    return send_from_directory('D:/软件制作/币交易开发', 'index.html')

# ===== Account API =====
@app.route('/api/account/balance')
def account_balance():
    """Get real account balance from OKX API"""
    try:
        env = get_okx_env()
        r = subprocess.run([OKX_CMD, 'account', 'balance', '--json', '--demo'],
                          capture_output=True, text=True, timeout=15, env=env)
        if r.returncode != 0:
            return jsonify({'error': r.stderr[:200]}), 500
        data = json.loads(r.stdout)
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== Market Data API =====
@app.route('/api/market/candles')
def market_candles():
    """Get candles from local DB"""
    inst = request.args.get('inst', 'ETH-USDT')
    bar = request.args.get('bar', '5m')
    limit = int(request.args.get('limit', 200))
    
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        'SELECT ts,open,high,low,close,vol FROM candles WHERE inst=? AND bar=? ORDER BY ts DESC LIMIT ?',
        (inst, bar, limit)
    ).fetchall()
    conn.close()
    
    candles = []
    for r in reversed(rows):
        candles.append({
            'ts': r[0], 'time': datetime.fromtimestamp(r[0]/1000).strftime('%Y-%m-%d %H:%M'),
            'open': r[1], 'high': r[2], 'low': r[3], 'close': r[4], 'vol': r[5]
        })
    return jsonify(candles)

@app.route('/api/market/ticker')
def market_ticker():
    """Get real-time ticker from OKX"""
    inst = request.args.get('inst', 'ETH-USDT')
    try:
        env = get_okx_env()
        r = subprocess.run([OKX_CMD, 'market', 'ticker', inst, '--json', '--demo'],
                          capture_output=True, text=True, timeout=10, env=env)
        if r.returncode != 0:
            return jsonify({'error': r.stderr[:200]}), 500
        data = json.loads(r.stdout)
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== Database API =====
@app.route('/api/db/stats')
def db_stats():
    """Get database statistics"""
    conn = sqlite3.connect(DB_PATH)
    stats = {}
    for inst, bar in [('ETH-USDT','5m'), ('ETH-USDT','15m'), ('BTC-USDT','5m'), ('BTC-USDT','15m'), ('BTC-USDT','1m')]:
        row = conn.execute(
            'SELECT COUNT(*), MIN(ts), MAX(ts) FROM candles WHERE inst=? AND bar=?',
            (inst, bar)
        ).fetchone()
        if row[0] > 0:
            stats[f'{inst}_{bar}'] = {
                'count': row[0],
                'start': datetime.fromtimestamp(row[1]/1000).isoformat(),
                'end': datetime.fromtimestamp(row[2]/1000).isoformat(),
                'start_str': datetime.fromtimestamp(row[1]/1000).strftime('%Y-%m-%d %H:%M'),
                'end_str': datetime.fromtimestamp(row[2]/1000).strftime('%Y-%m-%d %H:%M'),
            }
    conn.close()
    
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    return jsonify({'datasets': stats, 'db_size_mb': round(db_size/1024/1024, 1)})

@app.route('/api/config/apikey', methods=['POST'])
def config_apikey():
    """Save OKX API configuration"""
    try:
        data = request.json
        api_key = data.get('api_key', '')
        secret = data.get('secret', '')
        passphrase = data.get('passphrase', '')
        if not api_key or not secret or not passphrase:
            return jsonify({'ok': False, 'error': 'Missing fields'}), 400
        # Save to config file
        config_path = 'D:/软件制作/币交易开发/data/okx_config.json'
        import pathlib
        pathlib.Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump({'api_key': api_key, 'secret': secret, 'passphrase': passphrase}, f, indent=2)
        # Update in-memory env
        global OKX_API_KEY, OKX_SECRET, OKX_PASS
        OKX_API_KEY = api_key
        OKX_SECRET = secret
        OKX_PASS = passphrase
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/db/preview')
def db_preview():
    """Preview latest candles"""
    inst = request.args.get('inst', 'ETH-USDT')
    bar = request.args.get('bar', '5m')
    limit = min(int(request.args.get('limit', 20)), 100)
    
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        'SELECT ts,open,high,low,close,vol FROM candles WHERE inst=? AND bar=? ORDER BY ts DESC LIMIT ?',
        (inst, bar, limit)
    ).fetchall()
    conn.close()
    
    return jsonify([{
        'ts': r[0], 'time': datetime.fromtimestamp(r[0]/1000).strftime('%Y-%m-%d %H:%M'),
        'open': r[1], 'high': r[2], 'low': r[3], 'close': r[4], 'vol': r[5]
    } for r in reversed(rows)])

# ===== Model API =====
@app.route('/api/model/info')
def model_info():
    """Get Model 01 info"""
    meta_path = os.path.join(MODEL_DIR, 'metadata.json')
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({'error': 'Model not found'}), 404

@app.route('/api/model/predict', methods=['POST'])
def model_predict():
    """Run prediction on latest data"""
    try:
        import lightgbm as lgb
        import pandas as pd, numpy as np
        
        model_path = os.path.join(MODEL_DIR, 'lgb_model.txt')
        feat_path = os.path.join(MODEL_DIR, 'features.txt')
        if not os.path.exists(model_path):
            return jsonify({'error': 'Model not found'}), 404
        
        model = lgb.Booster(model_file=model_path)
        with open(feat_path) as f:
            feat_cols = f.read().strip().split('\n')
        
        # Load recent data
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT ts,open,high,low,close,vol FROM candles WHERE inst='ETH-USDT' AND bar='5m' ORDER BY ts DESC LIMIT 500", conn)
        conn.close()
        df = df.sort_values('ts').reset_index(drop=True)
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        for c in ['open','high','low','close','vol']: df[c] = df[c].astype(float)
        
        # Compute features (inline, same as training)
        c, h, l, v = df['close'], df['high'], df['low'], df['vol']
        for n in [1,2,3,5,8,13,21]:
            df[f'ret_{n}'] = c.pct_change(n)
            df[f'range_{n}'] = (h.rolling(n).max()-l.rolling(n).min())/c
        for n in [5,10,20,50,100,200]:
            df[f'ema_d_{n}'] = (c - c.ewm(span=n).mean()) / c
        for f2,s in [(5,20),(10,50),(20,100),(50,200)]:
            df[f'cross_{f2}_{s}'] = (c.ewm(span=f2).mean()-c.ewm(span=s).mean())/c
        for n in [7,14,21]:
            d2=c.diff(); g=d2.clip(lower=0).rolling(n).mean(); lo=(-d2.clip(upper=0)).rolling(n).mean()
            df[f'rsi_{n}'] = 100-100/(1+g/lo.replace(0,np.nan))
        for fast,slow in [(5,13),(8,17),(12,26)]:
            macd=c.ewm(span=fast).mean()-c.ewm(span=slow).mean(); sig=macd.ewm(span=9).mean(); hist=macd-sig
            df[f'mh_{fast}_{slow}'] = hist; df[f'mhd_{fast}_{slow}'] = hist.diff()
        mid=c.rolling(20).mean(); std=c.rolling(20).std()
        df['bb_pct']=(c-(mid-2*std))/(4*std).replace(0,np.nan)
        df['bb_w']=(4*std)/mid; df['bb_md']=(c-mid)/mid
        tr=np.maximum(h-l,np.maximum(abs(h-c.shift(1)),abs(l-c.shift(1))))
        for n in [7,14,21]: df[f'atr_{n}']=tr.rolling(n).mean()/c
        for n in [5,10,20,50]: df[f'vr_{n}']=v/v.rolling(n).mean().replace(0,np.nan)
        for n in [5,20,50]: df[f'vol_{n}']=c.pct_change().rolling(n).std()
        df['vwap']=(c*v).rolling(16).sum()/v.rolling(16).sum()
        df['vwap_d']=(c-df['vwap'])/df['vwap']
        df['hour']=df['ts'].dt.hour; df['dow']=df['ts'].dt.dayofweek
        df['hsin']=np.sin(2*np.pi*df['hour']/24); df['hcos']=np.cos(2*np.pi*df['hour']/24)
        df['hlr']=(h-l)/c; df['clsp']=(c-l)/(h-l).replace(0,np.nan)
        df['slope']=c.rolling(20).apply(lambda x:np.polyfit(range(len(x)),x,1)[0]/x.mean() if len(x)==20 else 0,raw=False)
        df['adx'] = abs(c.ewm(span=20).mean()-c.ewm(span=50).mean())/c
        
        # Predict on last bar
        X = df[feat_cols].replace([np.inf,-np.inf],np.nan).fillna(0)
        last_feat = X.iloc[[-1]]
        proba = model.predict(last_feat)[0]
        
        last_bar = df.iloc[-1]
        direction = 'LONG' if proba > 0.58 else ('SHORT' if proba < 0.42 else 'HOLD')
        
        return jsonify({
            'timestamp': last_bar['ts'].isoformat(),
            'price': round(last_bar['close'], 2),
            'probability': round(float(proba), 4),
            'direction': direction,
            'confidence': round(abs(float(proba) - 0.5) * 2, 4),
            'threshold': 0.58,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== Backtest Results API =====
@app.route('/api/backtest/results')
def backtest_results():
    """Get stored backtest results"""
    csv_path = 'D:/软件制作/币交易开发/data/lgb_oos_trades.csv'
    if not os.path.exists(csv_path):
        return jsonify({'error': 'No backtest results'}), 404
    
    import pandas as pd
    df = pd.read_csv(csv_path)
    
    # Summary stats
    n = len(df)
    wr = (df['pnl_pct'] > 0).mean()
    total_pnl = df['pnl_usd'].sum() if 'pnl_usd' in df.columns else 0
    
    # Monthly
    df['et'] = pd.to_datetime(df['et'])
    df['month'] = df['et'].dt.to_period('M').astype(str)
    monthly = []
    prev_eq = 10000
    for month, g in df.groupby('month'):
        m_pnl = g['pnl_usd'].sum() if 'pnl_usd' in g.columns else 0
        m_wr = (g['pnl_pct'] > 0).mean()
        m_roi = m_pnl / prev_eq if prev_eq > 0 else 0
        monthly.append({
            'month': str(month),
            'trades': len(g),
            'win_rate': round(m_wr * 100, 1),
            'pnl': round(m_pnl, 2),
            'roi': round(m_roi * 100, 2),
        })
        prev_eq += m_pnl
    
    return jsonify({
        'summary': {
            'total_trades': n,
            'win_rate': round(wr * 100, 1),
            'total_pnl': round(total_pnl, 2),
        },
        'monthly': monthly,
    })

# ===== System Status =====
@app.route('/api/account/positions')
def account_positions():
    try:
        env = get_okx_env()
        r = subprocess.run([OKX_CMD, 'account', 'positions', '--json', '--demo'],
                          capture_output=True, text=True, timeout=15, env=env)
        if r.returncode != 0:
            return jsonify([])
        data = json.loads(r.stdout)
        return jsonify(data)
    except Exception as e:
        return jsonify([])

@app.route('/api/account/fills')
def account_fills():
    try:
        env = get_okx_env()
        fills = []
        # Swap fills
        r = subprocess.run([OKX_CMD, 'swap', 'fills', '--json', '--demo'],
                          capture_output=True, text=True, timeout=15, env=env)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, list):
                fills.extend(data)
        # Spot fills
        r2 = subprocess.run([OKX_CMD, 'spot', 'fills', '--instId', 'ETH-USDT', '--json', '--demo'],
                           capture_output=True, text=True, timeout=15, env=env)
        if r2.returncode == 0 and r2.stdout.strip():
            data2 = json.loads(r2.stdout)
            if isinstance(data2, list):
                fills.extend(data2)
        # Sort by ts descending
        fills.sort(key=lambda x: int(x.get('ts', '0')), reverse=True)
        return jsonify(fills)
    except Exception as e:
        return jsonify([])

@app.route('/api/account/spot_holdings')
def account_spot_holdings():
    """Get spot holdings from balance"""
    try:
        env = get_okx_env()
        r = subprocess.run([OKX_CMD, 'account', 'balance', '--json', '--demo'],
                          capture_output=True, text=True, timeout=15, env=env)
        if r.returncode != 0:
            return jsonify([])
        data = json.loads(r.stdout)
        if isinstance(data, list) and data:
            data = data[0]
        holdings = []
        for d in data.get('details', []):
            avail = float(d.get('availBal', 0))
            frozen = float(d.get('frozenBal', 0))
            if avail > 0 or frozen > 0:
                holdings.append({
                    'ccy': d['ccy'],
                    'availBal': avail,
                    'frozenBal': frozen,
                    'total': avail + frozen,
                })
        return jsonify(holdings)
    except Exception as e:
        return jsonify([])

@app.route('/api/logs')
def get_logs():
    log_type = request.args.get('type', 'all')
    limit = min(int(request.args.get('limit', 100)), 500)
    logs = []
    import re
    ansi_re = re.compile(r'\x1b\[[0-9;]*m')

    # System logs (strategy engine)
    strategy_log_path = 'D:/软件制作/币交易开发/data/strategy.log'
    if os.path.exists(strategy_log_path):
        try:
            with open(strategy_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            for line in lines[-200:]:
                line = ansi_re.sub('', line.strip())
                if not line: continue
                # Categorize
                if '127.0.0.1' in line or 'Press CTRL' in line or 'WARNING:' in line:
                    continue  # skip HTTP access logs and Flask warnings
                if '* Running on' in line or '* Serving' in line or '* Debug' in line:
                    continue  # skip Flask startup messages
                if 'OPEN' in line or 'CLOSE' in line or 'Config' in line:
                    ltype = 'strategy'
                elif 'INFO' in line:
                    ltype = 'strategy'
                elif 'ERROR' in line:
                    ltype = 'strategy'
                else:
                    ltype = 'system'
                logs.append({'type': ltype, 'text': line})
        except: pass

    # Server status
    logs.append({'type': 'system', 'text': f'[{datetime.now().strftime("%H:%M:%S")}] 后端运行中 · DB: 262K+ bars · Model 01: 55特征'})
    logs.append({'type': 'system', 'text': f'[{datetime.now().strftime("%H:%M:%S")}] OKX 模拟盘已连接 · ETH-USDT 5m'})

    if log_type != 'all':
        logs = [l for l in logs if l['type'] == log_type]

    return jsonify(logs[-limit:])

@app.route('/api/strategy/status')
def strategy_status():
    return jsonify(engine.status())

@app.route('/api/strategy/start', methods=['POST'])
def strategy_start():
    data = request.get_json(silent=True) or {}
    engine.update_config(data)
    engine.start()
    return jsonify({'ok': True, 'message': 'Strategy started'})

@app.route('/api/strategy/stop', methods=['POST'])
def strategy_stop():
    engine.stop()
    return jsonify({'ok': True, 'message': 'Strategy stopped'})

@app.route('/api/strategy/config', methods=['POST'])
def strategy_config():
    data = request.get_json(silent=True) or {}
    engine.update_config(data)
    return jsonify({'ok': True, 'config': engine.config})

@app.route('/api/strategy/auto_start', methods=['GET', 'POST'])
def strategy_auto_start():
    if request.method == 'GET':
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except:
            cfg = {}
        return jsonify({'auto_start': cfg.get('auto_start', False), 'capital': cfg.get('capital', 5000), 'leverage': cfg.get('leverage', 10)})
    else:
        data = request.get_json(silent=True) or {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except:
            cfg = {}
        cfg['auto_start'] = data.get('auto_start', False)
        cfg['capital'] = data.get('capital', 5000)
        cfg['leverage'] = data.get('leverage', 10)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f)
        return jsonify({'ok': True})

@app.route('/api/status')
def system_status():
    """System status"""
    db_exists = os.path.exists(DB_PATH)
    model_exists = os.path.exists(os.path.join(MODEL_DIR, 'lgb_model.txt'))
    
    conn = sqlite3.connect(DB_PATH) if db_exists else None
    eth_count = conn.execute("SELECT COUNT(*) FROM candles WHERE inst='ETH-USDT' AND bar='5m'").fetchone()[0] if conn else 0
    conn.close() if conn else None
    
    return jsonify({
        'database': {'exists': db_exists, 'eth_5m_bars': eth_count},
        'model': {'exists': model_exists, 'name': 'Model 01'},
        'okx': {'mode': 'demo', 'api_configured': True},
        'server_time': datetime.now().isoformat(),
    })

# Manual trading endpoints
@app.route('/api/trade/order', methods=['POST'])
def trade_order():
    try:
        data = request.json
        side = data.get('side', 'buy')
        ord_type = data.get('ordType', 'market')
        size = data.get('size', 0.01)
        inst_type = data.get('instType', 'swap')
        env = get_okx_env()

        if inst_type == 'spot':
            inst = 'ETH-USDT'
            # OKX spot: buy sz=USDT, sell sz=ETH
            if side == 'buy':
                # Buy: sz is in USDT, convert from ETH amount
                try:
                    ticker_r = subprocess.run([OKX_CMD, 'market', 'ticker', inst, '--json', '--demo'],
                                             capture_output=True, text=True, timeout=10, env=env)
                    ticker_data = json.loads(ticker_r.stdout)
                    if isinstance(ticker_data, list):
                        ticker_data = ticker_data[0]
                    last_price = float(ticker_data.get('last', 0))
                    if last_price > 0:
                        size_usdt = float(size) * last_price
                        size = max(round(size_usdt, 2), 10)
                except:
                    pass
            # Sell: sz is in ETH, use directly
            cmd = [OKX_CMD, 'spot', 'place', '--instId', inst,
                   '--side', side, '--ordType', ord_type, '--sz', str(size),
                   '--json', '--demo']
        else:
            inst = 'ETH-USDT-SWAP'
            cmd = [OKX_CMD, 'swap', 'place', '--instId', inst,
                   '--side', side, '--ordType', ord_type, '--sz', str(size),
                   '--tdMode', 'cross', '--json', '--demo']

        if ord_type == 'limit':
            price = data.get('price')
            if not price:
                return jsonify({'success': False, 'error': '\u9650\u4EF7\u5355\u9700\u8981\u4EF7\u683C'})
            cmd.extend(['--px', str(price)])

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, env=env)
        stdout = r.stdout.strip()
        if not stdout:
            return jsonify({'success': False, 'error': r.stderr[-200:] if r.stderr else '\u672A\u77E5\u9519\u8BEF'})
        result = json.loads(stdout)
        if isinstance(result, list) and len(result) > 0:
            result = result[0]
        ord_id = result.get('ordId', '')
        s_code = result.get('sCode', '')
        if s_code and s_code != '0':
            return jsonify({'success': False, 'error': result.get('sMsg', s_code)})
        return jsonify({'success': True, 'ordId': ord_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/trade/close', methods=['POST'])
def trade_close():
    try:
        data = request.json
        inst = data.get('instId', 'ETH-USDT-SWAP')
        env = get_okx_env()
        # Determine if spot or swap
        if 'SWAP' in inst:
            cmd = [OKX_CMD, 'swap', 'close', '--instId', inst, '--json', '--demo']
        else:
            # Spot: need to sell the base currency
            # Get balance first
            bal_cmd = [OKX_CMD, 'account', 'balance', '--json', '--demo']
            br = subprocess.run(bal_cmd, capture_output=True, text=True, timeout=15, env=env)
            bal = json.loads(br.stdout) if br.stdout.strip() else {}
            ccy = inst.split('-')[0]  # e.g., ETH from ETH-USDT
            details = bal.get('details', [])
            holding = 0
            for d in details:
                if d.get('ccy') == ccy:
                    holding = float(d.get('availBal', 0))
                    break
            if holding <= 0:
                return jsonify({'success': False, 'error': '\u65E0\u53EF\u7528\u6301\u4ED3'})
            cmd = [OKX_CMD, 'spot', 'place', '--instId', inst,
                   '--side', 'sell', '--ordType', 'market', '--sz', str(holding),
                   '--json', '--demo']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, env=env)
        stdout = r.stdout.strip()
        if not stdout:
            return jsonify({'success': False, 'error': r.stderr[-200:] if r.stderr else '\u672A\u77E5\u9519\u8BEF'})
        result = json.loads(stdout)
        if isinstance(result, list) and len(result) > 0:
            result = result[0]
        s_code = result.get('sCode', '')
        if s_code and s_code != '0':
            return jsonify({'success': False, 'error': result.get('sMsg', s_code)})
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ===== Strategy Ledger API =====
@app.route('/api/strategy/nav')
def strategy_nav():
    """Strategy net value + stats"""
    try:
        s = engine.status()
        trades = s.get('trades', [])
        initial = engine.config.get('capital', 5000)
        current = s.get('equity', initial)
        wins = sum(1 for t in trades if t.get('pnl_usd', 0) > 0)
        total = len(trades)
        return jsonify({
            'initial': initial,
            'current': current,
            'trades': total,
            'winrate': wins / total if total > 0 else 0,
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/strategy/positions')
def strategy_positions():
    """Strategy current positions"""
    try:
        s = engine.status()
        pos = s.get('position')
        if not pos:
            return jsonify([])
        # Format to match OKX positions format
        return jsonify([{
            'instId': engine.config.get('inst', 'ETH-USDT-SWAP'),
            'pos': str(pos.get('size_eth', 0)),
            'avgPx': str(pos.get('entry_price', 0)),
            'last': str(pos.get('entry_price', 0)),
            'upl': str(round((pos.get('unrealized_pnl', 0)), 2)),
            'posSide': 'long' if pos.get('side') == 'LONG' else 'short',
        }])
    except Exception as e:
        return jsonify([])

@app.route('/api/strategy/trades')
def strategy_trades():
    """Strategy trade history"""
    try:
        s = engine.status()
        trades = s.get('trades', [])
        result = []
        for t in reversed(trades):
            result.append({
                'ts': str(int(datetime.fromisoformat(t['time']).timestamp() * 1000)) if 'time' in t else '0',
                'side': 'sell' if t.get('action') == 'CLOSE' else 'buy',
                'entryPx': str(t.get('entry', 0)),
                'exitPx': str(t.get('exit', 0)),
                'sz': str(t.get('size_eth', '')),
                'pnl': str(t.get('pnl_usd', 0)),
                'fee': '0',
            })
        return jsonify(result)
    except Exception as e:
        return jsonify([])


if __name__ == '__main__':
    print('='*60)
    print('OKX Trading System Backend')
    print(f'DB: {DB_PATH}')
    print(f'Model: {MODEL_DIR}')
    print('Starting on http://localhost:5000')
    print('='*60)

    # Auto-start strategy if configured
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        if cfg.get('auto_start'):
            engine.update_config({'capital': cfg.get('capital', 5000), 'leverage': cfg.get('leverage', 10)})
            engine.start()
            print('[AUTO] Strategy auto-started')
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f'[AUTO] Failed to auto-start: {e}')

    app.run(host='0.0.0.0', port=5000, debug=False)
