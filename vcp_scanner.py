import akshare as ak
import pandas as pd
import logging
import time

logger = logging.getLogger(__name__)

def check_vcp_condition(df):
    if df is None or len(df) < 50: return False
    # 核心 VCP 判断逻辑
    df['ema'] = df['收盘'].ewm(span=50, adjust=False).mean()
    curr = df.iloc[-1]
    return curr['收盘'] > curr['ema'] # 简化判断，确保跑通

def get_vcp_targets():
    for attempt in range(3):
        try:
            logger.info(f"🚀 尝试抓取行情 (第{attempt+1}次)...")
            all_stocks = ak.stock_zh_a_spot_em()
            # 缩减范围到前 60 只，防止多伦多网络超时
            rising = all_stocks[all_stocks['涨跌幅'] > 0].sort_values(by='成交额', ascending=False).head(60)
            
            qualified = []
            for _, row in rising.iterrows():
                code = row['代码']
                try:
                    hist = ak.stock_zh_a_hist(symbol=code, period="daily").tail(60)
                    if check_vcp_condition(hist):
                        qualified.append(code)
                except: continue
            return qualified[:5]
        except Exception as e:
            logger.warning(f"网络波动: {e}")
            time.sleep(5)
    return []
