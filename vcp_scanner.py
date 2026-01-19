import akshare as ak
import pandas as pd
import logging
import time

logger = logging.getLogger(__name__)

def check_vcp_condition(df, vcp_period=50, vol_factor=1.1, ema_period=50):
    """核心 VCP 逻辑保持不变，但增加数据长度校验"""
    if df is None or len(df) < vcp_period: return False
    
    # 快速计算
    df['ema'] = df['收盘'].ewm(span=ema_period, adjust=False).mean()
    df['tr'] = pd.concat([df['最高']-df['最低'], (df['最高']-df['收盘'].shift(1)).abs(), (df['最低']-df['收盘'].shift(1)).abs()], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    curr = df.iloc[-1]
    low_atr = df['atr'].tail(vcp_period).min()
    
    # 判定条件
    preis_ueber_ema = curr['收盘'] > curr['ema']
    vol_contraction = curr['atr'] <= (low_atr * vol_factor)
    pivot_high = df['最高'].tail(20).max()
    is_breakout = curr['收盘'] >= (pivot_high * 0.98)
    
    return preis_ueber_ema and vol_contraction and is_breakout

def get_vcp_targets():
    """优化版：减少扫描范围，增加进度反馈"""
    try:
        logger.info("🚀 获取实时行情...")
        all_stocks = ak.stock_zh_a_spot_em()
        
        # 优化1：缩小范围。只看今日上涨且成交额前 80 名的股票（这些通常是主力关注的 VCP 重点）
        rising = all_stocks[all_stocks['涨跌幅'] > 0].sort_values(by='成交额', ascending=False).head(80)
        
        qualified = []
        count = 0
        total = len(rising)
        
        logger.info(f"🔍 开始快速扫描前 {total} 只活跃上涨股...")
        
        for _, row in rising.iterrows():
            count += 1
            code = row['代码']
            symbol = f"sh{code}" if code.startswith('6') else f"sz{code}"
            
            # 优化2：每隔10只打印一次进度，让你知道程序没死掉
            if count % 10 == 0:
                logger.info(f"已扫描 {count}/{total}...")

            try:
                # 获取历史数据（tail(60) 足够计算指标）
                hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(60)
                if check_vcp_condition(hist):
                    qualified.append(symbol)
                    logger.info(f"🎯 命中形态: {row['名称']} ({code})")
            except:
                continue
                
        # 优化3：如果扫描结果太多（比如超过10个），只取前5个进行 AI 深度分析
        # 避免消耗太多 AI Token 和延长运行时间
        if len(qualified) > 5:
            logger.info(f"发现 {len(qualified)} 只股票，由于过多，仅选取前 5 只进行 AI 分析。")
            return qualified[:5]
            
        return qualified
    except Exception as e:
        logger.error(f"扫描器异常: {e}")
        return []
