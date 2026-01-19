import akshare as ak
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def check_vcp_condition(df, vcp_period=50, vol_factor=1.1, ema_period=50):
    """
    核心 VCP 逻辑：价格 > EMA50 且 ATR 处于近期低位（收缩）
    """
    if len(df) < vcp_period: return False
    
    # 计算 EMA50
    df['ema'] = df['收盘'].ewm(span=ema_period, adjust=False).mean()
    # 计算 TR 和 ATR
    df['tr'] = pd.concat([df['最高']-df['最低'], (df['最高']-df['收盘'].shift(1)).abs(), (df['最低']-df['收盘'].shift(1)).abs()], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    curr = df.iloc[-1]
    # 条件1：价格在 EMA50 之上
    preis_ueber_ema = curr['收盘'] > curr['ema']
    # 条件2：波动收缩（当前 ATR <= 50天最低 ATR * 容忍度）
    low_atr = df['atr'].tail(vcp_period).min()
    vol_contraction = curr['atr'] <= (low_atr * vol_factor)
    # 条件3：突破/临界（现价接近或超过20日高点）
    pivot_high = df['最高'].tail(20).max()
    is_breakout = curr['收盘'] >= (pivot_high * 0.98)
    
    return preis_ueber_ema and vol_contraction and is_breakout

def get_vcp_targets():
    """只在当日上涨且成交额前 300 的股票中扫描"""
    try:
        all_stocks = ak.stock_zh_a_spot_em()
        # 筛选涨幅 > 0 且按成交额排序
        rising = all_stocks[all_stocks['涨跌幅'] > 0].sort_values(by='成交额', ascending=False).head(300)
        
        qualified = []
        for _, row in rising.iterrows():
            code = row['代码']
            symbol = f"sh{code}" if code.startswith('6') else f"sz{code}"
            try:
                hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(70)
                if check_vcp_condition(hist):
                    qualified.append(symbol)
            except: continue
        return qualified
    except Exception as e:
        logger.error(f"扫描异常: {e}")
        return []
