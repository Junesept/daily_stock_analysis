import yfinance as yf
import pandas as pd
import logging
import time

logger = logging.getLogger(__name__)

# 定义 VCP 核心筛选指标 (Minervini 趋势模板简化版)
def check_vcp_condition(df):
    if df is None or len(df) < 50: return False
    # 计算指标
    close = df['Close']
    ma50 = close.rolling(window=50).mean()
    ma150 = close.rolling(window=150).mean()
    ma200 = close.rolling(window=200).mean()
    high_52week = close.tail(252).max()
    low_52week = close.tail(252).min()
    
    curr_price = close.iloc[-1]
    
    # 筛选条件:
    # 1. 价格在 50/150/200 日线之上
    # 2. 50日线 > 150日线 > 200日线 (趋势多头)
    # 3. 当前价格距离 52 周高点 25% 以内 (强势股)
    # 4. 当前价格至少比 52 周低点高 25% (摆脱底部)
    cond1 = curr_price > ma50.iloc[-1] > ma150.iloc[-1] > ma200.iloc[-1]
    cond2 = curr_price >= (high_52week * 0.75)
    cond3 = curr_price >= (low_52week * 1.25)
    
    return cond1 and cond2 and cond3

def get_vcp_targets():
    """使用 Yahoo 财经批量扫描活跃 A 股"""
    # 建议手动维护一个活跃股池 (如沪深300 + 创业板指成分股)
    # 此处为示例：你可以通过 Akshare 一次性获取代码列表，或使用静态列表
    active_pool = ["600519", "300308", "688008", "600879", "300502", "688041", "300750", "002594"] # 扩充至 300+ 
    
    # 转换格式
    yf_symbols = [f"{c}.SS" if c.startswith('6') else f"{c}.SZ" for c in active_pool]
    
    logger.info(f"🔍 正在通过 Yahoo 财经扫描 {len(yf_symbols)} 只核心活跃股...")
    
    try:
        # 批量下载最近一年的数据以计算 52 周高低点
        data = yf.download(yf_symbols, period="1y", interval="1d", group_by='ticker', progress=False)
        
        qualified = []
        for symbol in yf_symbols:
            df = data[symbol].dropna()
            if check_vcp_condition(df):
                code = symbol.split('.')[0]
                qualified.append(code)
                logger.info(f"🎯 命中 VCP 趋势: {code}")
        
        return qualified[:5] # 返回前 5 只交给 AI
    except Exception as e:
        logger.error(f"Yahoo 扫描异常: {e}")
        return ["600519"] # 保底茅台
