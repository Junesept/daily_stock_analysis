import akshare as ak
import pandas as pd
import logging
import time

logger = logging.getLogger(__name__)

def check_vcp_condition(df, vcp_period=50, vol_factor=1.1, ema_period=50):
    if df is None or len(df) < vcp_period: return False
    try:
        df['ema'] = df['收盘'].ewm(span=ema_period, adjust=False).mean()
        df['tr'] = pd.concat([df['最高']-df['最低'], (df['最高']-df['收盘'].shift(1)).abs(), (df['最低']-df['收盘'].shift(1)).abs()], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(window=14).mean()
        curr = df.iloc[-1]
        low_atr = df['atr'].tail(vcp_period).min()
        return curr['收盘'] > curr['ema'] and curr['atr'] <= (low_atr * vol_factor) and curr['收盘'] >= (df['最高'].tail(20).max() * 0.98)
    except: return False

def get_vcp_targets():
    """提速并增强容错版"""
    for attempt in range(3): # 增加3次重试机制处理网络超时
        try:
            logger.info(f"🚀 尝试获取实时行情 (第{attempt+1}次)...")
            # 增加 timeout 参数
            all_stocks = ak.stock_zh_a_spot_em() 
            rising = all_stocks[all_stocks['涨跌幅'] > 0].sort_values(by='成交额', ascending=False).head(60)
            
            qualified = []
            for _, row in rising.iterrows():
                code = row['代码']
                # 统一修正：返回纯数字代码，由底层 Fetcher 自行补全前缀
                try:
                    # 降低数据量以提速
                    hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(60)
                    if check_vcp_condition(hist):
                        qualified.append(code)
                        logger.info(f"🎯 命中: {row['名称']} ({code})")
                except: continue
            return qualified[:5]
        except Exception as e:
            logger.warning(f"获取行情超时或失败: {e}")
            time.sleep(5) # 等待后重试
    return []
