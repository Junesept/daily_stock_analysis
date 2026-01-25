import akshare as ak
import pandas as pd
import logging
import time
import yfinance as yf

logger = logging.getLogger(__name__)

def check_vcp_condition(df):
    if df is None or len(df) < 50: return False
    df['ema'] = df['收盘'].ewm(span=50, adjust=False).mean()
    curr = df.iloc[-1]
    return curr['收盘'] > curr['ema']

def get_vcp_targets():
    # 1. 定义你关注的“种子股池”（AI硬件、半导体、航天等）
    # 确保即便全扫描失败，也会精准分析这些你最看好的标的
    seed_watchlist = ["600879", "300308", "688041", "300502", "688008"]
    for attempt in range(3):
        try:
            logger.info(f"🚀 尝试抓取行情 (第{attempt+1}次)...")
            all_stocks = ak.stock_zh_a_spot_em()
            
            # --- 核心改进：处理抓取失败 ---
            if all_stocks is None or all_stocks.empty:
                raise ValueError("快照为空")
                #logger.warning("无法获取全市场快照，使用保底列表...")
                #return ["600879", "300308"] # 航天电子和中际旭创

            rising = all_stocks[all_stocks['涨跌幅'] > 0].sort_values(by='成交额', ascending=False).head(80)
            qualified = []
            for _, row in rising.iterrows():
                code = row['代码']
                try:
                    hist = ak.stock_zh_a_hist(symbol=code, period="daily").tail(60)
                    if check_vcp_condition(hist):
                        qualified.append(code)
                except: continue

            # 如果扫到了就返回，没扫到则进入下方的种子列表检查
            if qualified:
                return qualified[:5]
            
            #return qualified[:5] if qualified else ["600879"] # 如果没扫到，保底返回航天电子
        except Exception as e:
            logger.warning(f"网络波动: {e}")
            time.sleep(5)
    #return ["600519"] # 最终失败则返回茅台
    # 2. 核心改进：全市场扫描彻底失败后的“小圈子”深度扫描
    logger.info("📍 切换至种子股池保底扫描（使用yfinance确保成功）...")
    final_backup = []
    for code in seed_watchlist:
        try:
            # 转换 Yahoo 格式
            yf_code = f"{code}.SS" if code.startswith('6') else f"{code}.SZ"
            # yfinance 在多伦多极其稳定
            df = yf.download(yf_code, period="3mo", interval="1d", progress=False)
            if not df.empty:
                # 简单列名对齐以复用逻辑
                df = df.rename(columns={'Close': '收盘'})
                if check_vcp_condition(df):
                    final_backup.append(code)
        except: continue
        
    return final_backup if final_backup else ["600519"] # 最终保底：茅台


 
