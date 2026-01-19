import pandas as pd
import akshare as ak
import os

def check_vcp_condition(df, vcp_period=50, vol_factor=1.1, ema_period=50):
    """
    根据你的 Pine Script 逻辑实现的 VCP 核心判断
    """
    if len(df) < vcp_period:
        return False
    
    # 1. 计算 EMA (均线过滤)
    df['ema'] = df['收盘'].ewm(span=ema_period, adjust=False).mean()
    
    # 2. 计算 ATR (波动率收缩)
    # 模拟 Pine ta.atr(14)
    df['tr'] = pd.concat([
        df['最高'] - df['最低'],
        (df['最高'] - df['收盘'].shift(1)).abs(),
        (df['最低'] - df['收盘'].shift(1)).abs()
    ], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    current = df.iloc[-1]
    
    # EMA 过滤：价格必须在 EMA 上方
    preis_ueber_ema = current['收盘'] > current['ema']
    
    # 波动收缩：当前 ATR 是否接近 50 天最低水平
    low_atr = df['atr'].tail(vcp_period).min()
    vol_contraction = current['atr'] <= (low_atr * vol_factor)
    
    # 突破判断：是否接近 20 日高点 (Pivot High)
    pivot_high = df['最高'].tail(20).max()
    is_breakout = current['收盘'] >= (pivot_high * 0.98) # 允许 2% 的临界区
    
    return preis_ueber_ema and vol_contraction and is_breakout

def get_vcp_targets():
    """
    只在当日上涨的股票中扫描
    """
    print("🚀 正在获取 A 股实时行情...")
    try:
        # 1. 获取所有 A 股实时快照
        all_stocks = ak.stock_zh_a_spot_em()
        # 2. 筛选涨幅 > 0 且 成交额较大的前 300 只（为了扫描速度和稳定性）
        rising_stocks = all_stocks[all_stocks['涨跌幅'] > 0].sort_values(by='成交额', ascending=False).head(300)
        
        qualified_codes = []
        print(f"🔍 正在从 {len(rising_stocks)} 只上涨股票中扫描 VCP 形态...")
        
        for _, row in rising_stocks.iterrows():
            code = row['代码']
            symbol = f"sh{code}" if code.startswith('6') else f"sz{code}"
            try:
                # 获取历史数据
                hist_df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(70)
                if check_vcp_condition(hist_df):
                    print(f"✅ 发现符合 VCP 潜力股: {row['名称']} ({code})")
                    qualified_codes.append(symbol)
            except:
                continue
        
        return qualified_codes
    except Exception as e:
        print(f"❌ 扫描过程出错: {e}")
        return []
