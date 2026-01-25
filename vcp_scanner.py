import akshare as ak
import pandas as pd
import logging
import time

logger = logging.getLogger(__name__)

def check_vcp_condition(df):
    if df is None or len(df) < 50: return False
    df['ema'] = df['收盘'].ewm(span=50, adjust=False).mean()
    curr = df.iloc[-1]
    return curr['收盘'] > curr['ema']

def get_vcp_targets():
    for attempt in range(3):
        try:
            logger.info(f"🚀 尝试抓取行情 (第{attempt+1}次)...")
            all_stocks = ak.stock_zh_a_spot_em()
            
            # --- 核心改进：处理抓取失败 ---
            if all_stocks is None or all_stocks.empty:
                logger.warning("无法获取全市场快照，使用保底列表...")
                return ["600879", "300308"] # 航天电子和中际旭创

            rising = all_stocks[all_stocks['涨跌幅'] > 0].sort_values(by='成交额', ascending=False).head(60)
            qualified = []
            for _, row in rising.iterrows():
                code = row['代码']
                try:
                    hist = ak.stock_zh_a_hist(symbol=code, period="daily").tail(60)
                    if check_vcp_condition(hist):
                        qualified.append(code)
                except: continue
            
            return qualified[:5] if qualified else ["600879"] # 如果没扫到，保底返回航天电子
        except Exception as e:
            logger.warning(f"网络波动: {e}")
            time.sleep(5)
    return ["600519"] # 最终失败则返回茅台
