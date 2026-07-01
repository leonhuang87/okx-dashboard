"""
Backtest engine for ETH-USDT 5m strategy using LightGBM Model 01.
"""
import sqlite3, json, os, shutil
import numpy as np
import pandas as pd
import lightgbm as lgb

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'market.db')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models', 'model_01')

# Load model once at import
_tmp_model = r'D:\software_maker\_tmp_lgb.txt'
_tmp_feat = r'D:\software_maker\_tmp_feat.txt'
shutil.copy2(os.path.join(MODEL_DIR, 'lgb_model.txt'), _tmp_model)
shutil.copy2(os.path.join(MODEL_DIR, 'features.txt'), _tmp_feat)

MODEL = lgb.Booster(model_file=_tmp_model)
with open(_tmp_feat, 'r') as f:
    FEATURES = [l.strip() for l in f.readlines() if l.strip()]


def calc_features(df):
    """Calculate all 55 features matching Model 01 training."""
    c = df['close'].copy()
    h = df['high'].copy()
    l_ = df['low'].copy()
    v = df['vol'].copy()

    # Returns
    for n in [1, 2, 3, 5, 8, 13, 21]:
        df['ret_%d' % n] = c.pct_change(n)

    # Range
    for n in [1, 2, 3, 5, 8, 13, 21]:
        df['range_%d' % n] = (h.rolling(n).max() - l_.rolling(n).min()) / c

    # EMA distance
    for n in [5, 10, 20, 50, 100, 200]:
        df['ema_d_%d' % n] = (c - c.ewm(span=n).mean()) / c

    # EMA crosses
    ema = lambda s, n: s.ewm(span=n).mean()
    e5, e10, e20, e50, e100, e200 = ema(c,5), ema(c,10), ema(c,20), ema(c,50), ema(c,100), ema(c,200)
    df['cross_5_20'] = (e5 - e20) / c
    df['cross_10_50'] = (e10 - e50) / c
    df['cross_20_100'] = (e20 - e100) / c
    df['cross_50_200'] = (e50 - e200) / c

    # RSI
    def rsi(s, n):
        d = s.diff()
        g = d.clip(lower=0).rolling(n).mean()
        lo = (-d.clip(upper=0)).rolling(n).mean()
        return 100 - 100 / (1 + g / lo)

    df['rsi_7'] = rsi(c, 7)
    df['rsi_14'] = rsi(c, 14)
    df['rsi_21'] = rsi(c, 21)

    # MACD histogram
    def mh(fast, slow):
        ef = c.ewm(span=fast).mean()
        es = c.ewm(span=slow).mean()
        ml = ef - es
        sig = ml.ewm(span=9).mean()
        return ml - sig

    for fast, slow in [(5,13), (8,17), (12,26)]:
        m = mh(fast, slow)
        df['mh_%d_%d' % (fast, slow)] = m / c
        df['mhd_%d_%d' % (fast, slow)] = m.diff() / c

    # Bollinger Bands
    bb_mid = c.rolling(20).mean()
    bb_std = c.rolling(20).std()
    bb_up = bb_mid + 2 * bb_std
    bb_lo = bb_mid - 2 * bb_std
    df['bb_pct'] = (c - bb_lo) / (bb_up - bb_lo)
    df['bb_w'] = 4 * bb_std / bb_mid
    df['bb_md'] = (c - bb_mid) / c

    # ATR
    tr = pd.concat([h - l_, (h - c.shift(1)).abs(), (l_ - c.shift(1)).abs()], axis=1).max(axis=1)
    for n in [7, 14, 21]:
        df['atr_%d' % n] = tr.rolling(n).mean() / c

    # Volume ratio
    for n in [5, 10, 20, 50]:
        df['vr_%d' % n] = v / v.rolling(n).mean()

    # Volatility
    ret1 = c.pct_change(1)
    for n in [5, 20, 50]:
        df['vol_%d' % n] = ret1.rolling(n).std()

    # VWAP deviation
    vwap = (c * v).cumsum() / v.cumsum()
    df['vwap_d'] = (c - vwap) / vwap

    # Time
    dt = pd.to_datetime(df['ts'], unit='ms')
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['hsin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hcos'] = np.cos(2 * np.pi * df['hour'] / 24)

    # Range features
    df['hlr'] = (h - l_) / c
    df['clsp'] = (c - l_) / (h - l_).replace(0, np.nan)

    # Slope
    df['slope'] = c.rolling(10).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0], raw=True
    ) / c

    # ADX
    up_m = h.diff()
    dn_m = -l_.diff()
    plus_dm = np.where((up_m > dn_m) & (up_m > 0), up_m, 0)
    minus_dm = np.where((dn_m > up_m) & (dn_m > 0), dn_m, 0)
    atr14 = tr.rolling(14).mean()
    plus_di = 100 * pd.Series(plus_dm).rolling(14).mean() / atr14
    minus_di = 100 * pd.Series(minus_dm).rolling(14).mean() / atr14
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    df['adx'] = dx.rolling(14).mean()

    return df


def run_backtest(params):
    """
    Run backtest with given parameters.
    params: dict with keys:
        start_time (str): ISO datetime start (default: 48h ago)
        end_time (str): ISO datetime end (default: now)
        conf_threshold (float): confidence threshold (default 0.58)
        tp_atr_mult (float): TP ATR multiplier (default 3.0)
        sl_atr_mult (float): SL ATR multiplier (default 2.0)
        capital (float): initial capital (default 5000)
        risk_pct (float): risk per trade as fraction (default 0.01)
        leverage (float): leverage (default 10)
        comm (float): commission per side (default 0.00036)
    """
    import datetime
    now = datetime.datetime.now()

    # Parse start/end time
    start_str = params.get('start_time')
    end_str = params.get('end_time')
    if start_str:
        try:
            start_time = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00')).replace(tzinfo=None)
        except:
            start_time = now - datetime.timedelta(hours=48)
    else:
        start_time = now - datetime.timedelta(hours=48)
    if end_str:
        try:
            end_time = datetime.datetime.fromisoformat(end_str.replace('Z', '+00:00')).replace(tzinfo=None)
        except:
            end_time = now
    else:
        end_time = now

    hours = max(1, (end_time - start_time).total_seconds() / 3600)
    conf_threshold = params.get('conf_threshold', 0.58)
    tp_atr_mult = params.get('tp_atr_mult', 3.0)
    sl_atr_mult = params.get('sl_atr_mult', 2.0)
    capital = params.get('capital', 5000.0)
    risk_pct = params.get('risk_pct', 0.01)
    leverage = params.get('leverage', 10.0)
    comm = params.get('comm', 0.00036)

    import datetime
    now = datetime.datetime.now()
    buffer_hours = 12  # extra for indicator warmup
    cutoff_ts = int((start_time - datetime.timedelta(hours=buffer_hours)).timestamp() * 1000)
    end_ts = int(end_time.timestamp() * 1000)

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        'SELECT ts, open, high, low, close, vol FROM candles '
        'WHERE inst="ETH-USDT" AND bar="5m" AND ts>=? ORDER BY ts ASC',
        conn, params=[cutoff_ts]
    )
    conn.close()

    if len(df) < 100:
        return {'error': 'Not enough data: only %d bars' % len(df)}

    df['ts'] = df['ts'].astype(int)
    for col in ['open', 'high', 'low', 'close', 'vol']:
        df[col] = df[col].astype(float)

    # Calculate features
    df = calc_features(df)
    df = df.dropna().reset_index(drop=True)

    # Trim to requested time range
    start_ts = int(start_time.timestamp() * 1000)
    df_bt = df[(df['ts'] >= start_ts) & (df['ts'] <= end_ts)].reset_index(drop=True)

    if len(df_bt) < 10:
        return {'error': 'Not enough bars after feature calc: %d' % len(df_bt)}

    # Verify features
    missing = [f for f in FEATURES if f not in df_bt.columns]
    if missing:
        return {'error': 'Missing features: %s' % str(missing)}

    # Predict
    X = df_bt[FEATURES].values
    probs = MODEL.predict(X)

    # Simulate
    equity = capital
    pos_side = None
    pos_entry = 0.0
    pos_size = 0.0
    pos_tp = 0.0
    pos_sl = 0.0
    trades = []
    equity_curve = []

    for i in range(len(df_bt)):
        row = df_bt.iloc[i]
        ts = row['ts']
        price = row['close']
        nxt_open = df_bt.iloc[i+1]['open'] if i+1 < len(df_bt) else price
        atr_val = row['atr_14']
        prob = probs[i]

        # Check TP/SL
        if pos_side is not None:
            hit_tp = (pos_side == 'LONG' and nxt_open >= pos_tp) or \
                     (pos_side == 'SHORT' and nxt_open <= pos_tp)
            hit_sl = (pos_side == 'LONG' and nxt_open <= pos_sl) or \
                     (pos_side == 'SHORT' and nxt_open >= pos_sl)

            if hit_tp or hit_sl:
                exit_price = pos_tp if hit_tp else pos_sl
                if pos_side == 'LONG':
                    pnl_pct = (exit_price - pos_entry) / pos_entry
                else:
                    pnl_pct = (pos_entry - exit_price) / pos_entry
                pnl_usd = pos_size * pnl_pct * pos_entry * leverage
                pnl_usd -= pos_size * pos_entry * leverage * comm
                equity += pnl_usd
                reason = 'TP' if hit_tp else 'SL'
                trades.append({
                    'time': datetime.datetime.fromtimestamp(ts/1000).strftime('%m-%d %H:%M'),
                    'action': 'CLOSE', 'side': pos_side,
                    'entry': round(pos_entry, 2),
                    'exit': round(exit_price, 2),
                    'pnl': round(pnl_usd, 2),
                    'reason': reason,
                    'equity': round(equity, 2)
                })
                pos_side = None

        # Entry
        if pos_side is None:
            direction = None
            if prob > conf_threshold:
                direction = 'LONG'
            elif prob < (1 - conf_threshold):
                direction = 'SHORT'

            if direction:
                pos_side = direction
                pos_entry = nxt_open
                risk_usd = equity * risk_pct
                atr_abs = atr_val * pos_entry
                pos_size = risk_usd / (sl_atr_mult * atr_abs) if sl_atr_mult * atr_abs > 0 else 0
                if direction == 'LONG':
                    pos_tp = pos_entry + tp_atr_mult * atr_abs
                    pos_sl = pos_entry - sl_atr_mult * atr_abs
                else:
                    pos_tp = pos_entry - tp_atr_mult * atr_abs
                    pos_sl = pos_entry + sl_atr_mult * atr_abs
                entry_fee = pos_size * pos_entry * leverage * comm
                equity -= entry_fee
                trades.append({
                    'time': datetime.datetime.fromtimestamp(ts/1000).strftime('%m-%d %H:%M'),
                    'action': 'OPEN', 'side': direction,
                    'price': round(pos_entry, 2),
                    'size': round(pos_size, 4),
                    'tp': round(pos_tp, 2),
                    'sl': round(pos_sl, 2),
                    'prob': round(float(prob), 3)
                })

        equity_curve.append({
            'time': datetime.datetime.fromtimestamp(ts/1000).strftime('%m-%d %H:%M'),
            'equity': round(equity, 2)
        })

    # Results
    close_trades = [t for t in trades if t['action'] == 'CLOSE']
    open_trades = [t for t in trades if t['action'] == 'OPEN']
    wins = [t for t in close_trades if t['pnl'] >= 0]
    losses = [t for t in close_trades if t['pnl'] < 0]
    total_pnl = sum(t['pnl'] for t in close_trades)

    # Open position info
    open_pos = None
    if pos_side:
        last_price = df_bt.iloc[-1]['close']
        if pos_side == 'LONG':
            unreal = (last_price - pos_entry) * pos_size * leverage
        else:
            unreal = (pos_entry - last_price) * pos_size * leverage
        open_pos = {
            'side': pos_side,
            'entry': round(pos_entry, 2),
            'size': round(pos_size, 4),
            'tp': round(pos_tp, 2),
            'sl': round(pos_sl, 2),
            'last_price': round(last_price, 2),
            'unrealized': round(unreal, 2)
        }

    # Max drawdown
    peak = capital
    max_dd = 0
    for ec in equity_curve:
        if ec['equity'] > peak:
            peak = ec['equity']
        dd = (peak - ec['equity']) / peak
        if dd > max_dd:
            max_dd = dd

    # Long/Short breakdown
    long_wins = len([t for t in close_trades if t['side'] == 'LONG' and t['pnl'] >= 0])
    long_total = len([t for t in close_trades if t['side'] == 'LONG'])
    short_wins = len([t for t in close_trades if t['side'] == 'SHORT' and t['pnl'] >= 0])
    short_total = len([t for t in close_trades if t['side'] == 'SHORT'])

    # Subsample equity curve (max 200 points)
    step = max(1, len(equity_curve) // 200)
    curve_sub = equity_curve[::step]
    if equity_curve and curve_sub[-1] != equity_curve[-1]:
        curve_sub.append(equity_curve[-1])

    return {
        'summary': {
            'total_opens': len(open_trades),
            'total_closes': len(close_trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round(len(wins) / len(close_trades) * 100, 1) if close_trades else 0,
            'total_pnl': round(total_pnl, 2),
            'final_equity': round(equity, 2),
            'return_pct': round((equity / capital - 1) * 100, 2),
            'max_drawdown': round(max_dd * 100, 2),
            'long_win_rate': round(long_wins / long_total * 100, 1) if long_total > 0 else 0,
            'long_trades': long_total,
            'short_win_rate': round(short_wins / short_total * 100, 1) if short_total > 0 else 0,
            'short_trades': short_total,
            'avg_win': round(sum(t['pnl'] for t in wins) / len(wins), 2) if wins else 0,
            'avg_loss': round(sum(t['pnl'] for t in losses) / len(losses), 2) if losses else 0,
            'profit_factor': round(
                sum(t['pnl'] for t in wins) / abs(sum(t['pnl'] for t in losses)), 2
            ) if losses and sum(t['pnl'] for t in losses) != 0 else 0,
        },
        'trades': trades,
        'equity_curve': curve_sub,
        'open_position': open_pos,
        'params': {
            'start_time': start_time.strftime('%Y-%m-%d %H:%M'),
            'end_time': end_time.strftime('%Y-%m-%d %H:%M'),
            'conf_threshold': conf_threshold,
            'tp_atr_mult': tp_atr_mult,
            'sl_atr_mult': sl_atr_mult,
            'capital': capital,
            'risk_pct': risk_pct,
            'leverage': leverage,
            'comm': comm,
        },
        'bars': len(df_bt),
        'prob_stats': {
            'min': round(float(probs.min()), 3),
            'max': round(float(probs.max()), 3),
            'mean': round(float(probs.mean()), 3),
            'signals_gt_58': int((probs > 0.58).sum()),
            'signals_lt_42': int((probs < 0.42).sum()),
        }
    }
