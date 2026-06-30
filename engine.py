# -*- coding: utf-8 -*-
"""
ETH Strategy Engine
- 每5分钟自动预测 + 执行
- Model 01: LightGBM binary, conf>0.58
- 止盈: 3xATR, 止损: 2xATR
- 通过 OKX CLI 下单（模拟盘）
"""
import sqlite3, subprocess, json, time, os, threading, logging
from datetime import datetime
import numpy as np

DB_PATH = 'D:/软件制作/币交易开发/data/market.db'
MODEL_DIR = 'D:/software_maker/models/model_01'
OKX_CMD = r'C:\Users\leonh\AppData\Local\hermes\node\okx.cmd'
OKX_API_KEY = '52ca522d-3bb6-4213-800c-0341e3cafc04'
OKX_SECRET = '07FC20C9E1E065B43CE01ADAFF3CCE1D'
OKX_PASS = '.Huang870521'
LOG_PATH = 'D:/软件制作/币交易开发/data/strategy.log'

logging.basicConfig(
    filename=LOG_PATH, level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s', encoding='utf-8'
)
log = logging.getLogger('Strategy')

def get_env():
    env = os.environ.copy()
    env.update({'OKX_API_KEY': OKX_API_KEY, 'OKX_SECRET_KEY': OKX_SECRET, 'OKX_PASSPHRASE': OKX_PASS})
    return env


class StrategyEngine:
    def __init__(self):
        self.running = False
        self.thread = None
        self.config = {
            'inst': 'ETH-USDT-SWAP',
            'bar': '5m',
            'capital': 5000,
            'leverage': 10,
            'conf_threshold': 0.58,
            'tp_atr_mult': 3.0,
            'sl_atr_mult': 2.0,
            'risk_pct': 0.01,  # 1% per trade
        }
        self.position = None  # {side, entry_price, size, atr_pct, open_time, tp, sl}
        self.last_signal = None
        self.last_predict_time = None
        self.trade_log = self._load_trades()
        # Recalculate equity from trade history
        eq = 5000
        for t in self.trade_log:
            if t.get('action') == 'CLOSE':
                eq += t.get('pnl_usd', 0)
        self.equity = eq
        self._load_model()

    TRADES_PATH = 'D:/软件制作/币交易开发/data/trades.json'

    def _load_trades(self):
        try:
            if os.path.exists(self.TRADES_PATH):
                with open(self.TRADES_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return []

    def _save_trades(self):
        try:
            os.makedirs(os.path.dirname(self.TRADES_PATH), exist_ok=True)
            with open(self.TRADES_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.trade_log[-500:], f, ensure_ascii=False, indent=2)
        except:
            pass

    def _load_model(self):
        import lightgbm as lgb
        model_path = os.path.join(MODEL_DIR, 'lgb_model.txt')
        feat_path = os.path.join(MODEL_DIR, 'features.txt')
        if os.path.exists(model_path):
            self.model = lgb.Booster(model_file=model_path)
            with open(feat_path) as f:
                self.feat_cols = f.read().strip().split('\n')
            log.info(f'Model loaded: {len(self.feat_cols)} features')
        else:
            self.model = None
            log.warning('Model not found!')

    def start(self):
        if self.running:
            return
        self.running = True
        # Check existing position on OKX before starting
        self._sync_position()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        log.info('Strategy started')

    def _sync_position(self):
        """Check OKX for existing positions and sync local state"""
        try:
            env = get_env()
            cmd = [OKX_CMD, 'swap', 'positions', '--json', '--demo']
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, env=env)
            stdout = r.stdout.strip()
            if not stdout:
                log.info('No existing positions found')
                return
            positions = json.loads(stdout)
            if not isinstance(positions, list):
                positions = [positions]
            for p in positions:
                pos_amt = float(p.get('pos', 0) or 0)
                if abs(pos_amt) < 0.001:
                    continue
                side = 'LONG' if pos_amt > 0 else 'SHORT'
                entry = float(p.get('avgPx', 0) or 0)
                size = abs(pos_amt)
                inst = p.get('instId', '')
                log.info(f'Found existing position: {side} {size} {inst} @ ${entry}')
                # Load recent candles to get ATR
                conn = sqlite3.connect(DB_PATH)
                rows = conn.execute(
                    "SELECT ts,open,high,low,close,vol FROM candles WHERE inst='ETH-USDT' AND bar='5m' ORDER BY ts DESC LIMIT 30"
                ).fetchall()
                conn.close()
                if len(rows) < 20:
                    continue
                import pandas as pd
                df = pd.DataFrame(rows, columns=['ts','open','high','low','close','vol'])
                df = df.sort_values('ts').reset_index(drop=True)
                for c in ['open','high','low','close','vol']: df[c] = df[c].astype(float)
                tr = np.maximum(df['high']-df['low'],
                       np.maximum(abs(df['high']-df['close'].shift(1)),
                                  abs(df['low']-df['close'].shift(1))))
                atr = tr.rolling(14).mean().iloc[-1]
                atr_pct = atr / entry
                if side == 'LONG':
                    tp = entry * (1 + atr_pct * self.config['tp_atr_mult'])
                    sl = entry * (1 - atr_pct * self.config['sl_atr_mult'])
                else:
                    tp = entry * (1 - atr_pct * self.config['tp_atr_mult'])
                    sl = entry * (1 + atr_pct * self.config['sl_atr_mult'])
                self.position = {
                    'side': side,
                    'entry_price': entry,
                    'size_eth': size,
                    'size_usd': size * entry,
                    'atr_pct': atr_pct,
                    'tp': round(tp, 2),
                    'sl': round(sl, 2),
                    'open_time': p.get('cTime', datetime.now().isoformat()),
                    'order_id': p.get('posId', '?'),
                }
                log.info(f'Synced position: {side} {size} ETH @ ${entry} TP=${tp:.2f} SL=${sl:.2f}')
                break  # Only track one position
        except Exception as e:
            log.error(f'Position sync error: {e}')

    def stop(self):
        self.running = False
        log.info('Strategy stopped')

    def _run_loop(self):
        while self.running:
            try:
                self._tick()
            except Exception as e:
                log.error(f'Tick error: {e}')
            # Check every 60 seconds (TP/SL needs frequent checks)
            time.sleep(60)

    def _tick(self):
        if not self.model:
            return

        # 1. Load recent candles
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT ts,open,high,low,close,vol FROM candles WHERE inst='ETH-USDT' AND bar='5m' ORDER BY ts DESC LIMIT 500",
        ).fetchall()
        conn.close()
        if len(rows) < 200:
            return

        import pandas as pd
        df = pd.DataFrame(rows, columns=['ts','open','high','low','close','vol'])
        df = df.sort_values('ts').reset_index(drop=True)
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        for c in ['open','high','low','close','vol']: df[c] = df[c].astype(float)

        # 2. Compute features
        df = self._features(df)
        X = df[self.feat_cols].replace([np.inf,-np.inf], np.nan).fillna(0)
        last_row = df.iloc[-1]

        # 3. Predict
        proba = float(self.model.predict(X.iloc[[-1]])[0])
        direction = 'LONG' if proba > self.config['conf_threshold'] else (
            'SHORT' if proba < (1 - self.config['conf_threshold']) else 'HOLD')

        self.last_signal = {
            'time': datetime.now().isoformat(),
            'price': round(last_row['close'], 2),
            'direction': direction,
            'probability': round(proba, 4),
        }
        self.last_predict_time = datetime.now()

        # 4. Calculate ATR for TP/SL
        tr = np.maximum(df['high']-df['low'],
               np.maximum(abs(df['high']-df['close'].shift(1)),
                          abs(df['low']-df['close'].shift(1))))
        atr = tr.rolling(14).mean().iloc[-1]
        atr_pct = atr / last_row['close']

        # 5. Check existing position - TP/SL
        if self.position:
            self._check_exit(last_row, atr_pct)
            return

        # 6. Open position if signal
        if direction in ('LONG', 'SHORT'):
            self._open_position(direction, last_row['close'], atr_pct)

    def _open_position(self, side, price, atr_pct):
        capital = self.config['capital']
        leverage = self.config['leverage']
        risk_pct = self.config['risk_pct']

        # Position sizing: risk = capital * risk_pct, stop = atr * sl_mult
        stop_dist = atr_pct * self.config['sl_atr_mult']
        if stop_dist < 0.0001:
            return

        risk_amount = capital * risk_pct
        position_usd = risk_amount / stop_dist
        position_usd = min(position_usd, capital * 0.5)

        # Size in ETH (round to lot size = 0.01)
        size_usd = position_usd * leverage
        size_eth = size_usd / price
        size_eth = max(0.01, round(size_eth, 2))  # min 0.01, round to 2 decimals

        if side == 'LONG':
            tp = price * (1 + atr_pct * self.config['tp_atr_mult'])
            sl = price * (1 - atr_pct * self.config['sl_atr_mult'])
        else:
            tp = price * (1 - atr_pct * self.config['tp_atr_mult'])
            sl = price * (1 + atr_pct * self.config['sl_atr_mult'])

        # Place order via OKX CLI (net_mode - no posSide)
        okx_side = 'buy' if side == 'LONG' else 'sell'
        try:
            env = get_env()
            cmd = [OKX_CMD, 'swap', 'place',
                   '--instId', self.config['inst'],
                   '--side', okx_side,
                   '--ordType', 'market',
                   '--sz', str(size_eth),
                   '--tdMode', 'cross',
                   '--json', '--demo', '--verbose']
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, env=env)
            stdout = r.stdout.strip()
            if not stdout:
                log.error(f'Order failed: no output, stderr={r.stderr[:300]}')
                return
            order = json.loads(stdout)
            if isinstance(order, list): order = order[0]
            s_code = order.get('sCode', '?')
            if str(s_code) != '0':
                log.error(f'Order rejected: {order.get("sMsg", "unknown")} (code={s_code})')
                return

            order_id = order.get('ordId', '?')
            log.info(f'OPEN {side} {size_eth} ETH @ ${price:.2f} TP=${tp:.2f} SL=${sl:.2f} ordId={order_id}')
        except Exception as e:
            log.error(f'Order exception: {e}')
            return

        self.position = {
            'side': side,
            'entry_price': price,
            'size_eth': size_eth,
            'size_usd': size_usd,
            'atr_pct': atr_pct,
            'tp': round(tp, 2),
            'sl': round(sl, 2),
            'open_time': datetime.now().isoformat(),
            'order_id': order_id,
        }

        trade = {
            'time': datetime.now().isoformat(),
            'action': 'OPEN',
            'side': side,
            'price': price,
            'size': size_eth,
            'tp': round(tp, 2),
            'sl': round(sl, 2),
            'order_id': order_id,
        }
        self.trade_log.append(trade)
        self._save_trades()
        log.info(f'OPEN {side} {size_eth} ETH @ ${price:.2f} TP=${tp:.2f} SL=${sl:.2f} ordId={order_id}')

    def _check_exit(self, last_row, atr_pct):
        pos = self.position
        high = last_row['high']
        low = last_row['low']

        # Also fetch real-time ticker price
        try:
            env = get_env()
            cmd = [OKX_CMD, 'market', 'ticker', 'ETH-USDT', '--json']
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, env=env)
            if r.returncode == 0 and r.stdout.strip():
                ticker = json.loads(r.stdout)
                if isinstance(ticker, list) and len(ticker) > 0:
                    ticker = ticker[0]
                last_price = float(ticker.get('last', 0) or 0)
                if last_price > 0:
                    high = max(high, last_price)
                    low = min(low, last_price)
        except Exception:
            pass

        exit_reason = None
        exit_price = None

        if pos['side'] == 'LONG':
            if high >= pos['tp']:
                exit_reason, exit_price = 'TP', pos['tp']
            elif low <= pos['sl']:
                exit_reason, exit_price = 'SL', pos['sl']
        else:
            if low <= pos['tp']:
                exit_reason, exit_price = 'TP', pos['tp']
            elif high >= pos['sl']:
                exit_reason, exit_price = 'SL', pos['sl']

        if exit_reason:
            self._close_position(exit_reason, exit_price)

    def _close_position(self, reason, exit_price):
        pos = self.position
        if not pos:
            return

        # Close via OKX CLI (net_mode - no posSide)
        okx_side = 'sell' if pos['side'] == 'LONG' else 'buy'
        try:
            env = get_env()
            cmd = [OKX_CMD, 'swap', 'place',
                   '--instId', self.config['inst'],
                   '--side', okx_side,
                   '--ordType', 'market',
                   '--sz', str(pos['size_eth']),
                   '--tdMode', 'cross',
                   '--reduceOnly',
                   '--json', '--demo']
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, env=env)
            stdout = r.stdout.strip()
            if not stdout:
                log.error(f'Close order failed: no output, stderr={r.stderr[:300]}')
            else:
                order = json.loads(stdout)
                if isinstance(order, list): order = order[0]
                log.info(f'Close order: {order.get("ordId", "?")} sCode={order.get("sCode", "?")}')
        except Exception as e:
            log.error(f'Close exception: {e}')

        # Calculate P&L
        if pos['side'] == 'LONG':
            pnl_pct = (exit_price - pos['entry_price']) / pos['entry_price']
        else:
            pnl_pct = (pos['entry_price'] - exit_price) / pos['entry_price']

        pnl_usd = pos['size_usd'] * pnl_pct
        self.equity += pnl_usd

        trade = {
            'time': datetime.now().isoformat(),
            'action': 'CLOSE',
            'side': pos['side'],
            'entry': pos['entry_price'],
            'exit': exit_price,
            'pnl_pct': round(pnl_pct, 6),
            'pnl_usd': round(pnl_usd, 2),
            'reason': reason,
            'equity': round(self.equity, 2),
        }
        self.trade_log.append(trade)
        self._save_trades()
        log.info(f'CLOSE {pos["side"]} @ ${exit_price:.2f} ({reason}) PnL={pnl_pct:+.4%} ${pnl_usd:+.2f} Eq=${self.equity:.2f}')

        self.position = None

    def _features(self, df):
        c, h, l, v = df['close'], df['high'], df['low'], df['vol']
        for n in [1,2,3,5,8,13,21]:
            df[f'ret_{n}'] = c.pct_change(n)
            df[f'range_{n}'] = (h.rolling(n).max()-l.rolling(n).min())/c
        for n in [5,10,20,50,100,200]:
            df[f'ema_d_{n}'] = (c - c.ewm(span=n).mean()) / c
        for f,s in [(5,20),(10,50),(20,100),(50,200)]:
            df[f'cross_{f}_{s}'] = (c.ewm(span=f).mean()-c.ewm(span=s).mean())/c
        for n in [7,14,21]:
            d=c.diff(); g=d.clip(lower=0).rolling(n).mean(); lo=(-d.clip(upper=0)).rolling(n).mean()
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
        return df

    def status(self):
        return {
            'running': self.running,
            'config': self.config,
            'position': self.position,
            'last_signal': self.last_signal,
            'equity': round(self.equity, 2),
            'trade_count': len(self.trade_log),
            'trades': self.trade_log[-20:],
        }

    def update_config(self, new_config):
        for k in ['capital', 'leverage']:
            if k in new_config:
                self.config[k] = float(new_config[k])
        log.info(f'Config updated: capital={self.config["capital"]}, leverage={self.config["leverage"]}')
