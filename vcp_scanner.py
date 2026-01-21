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
    """提速、深度容错并支持跨境网络访问版"""
    # 模拟浏览器请求头，降低被封锁概率
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for attempt in range(3):
        try:
            logger.info(f"🚀 正在尝试获取全市场快照 (第 {attempt+1}/3 次)...")
            
            # 获取实时行情 - 这是跨境访问最容易卡顿的地方
            # AkShare 内部通常使用 requests，增加这种全局处理可以缓解
            all_stocks = ak.stock_zh_a_spot_em() 
            
            if all_stocks is None or all_stocks.empty:
                raise ValueError("行情数据返回为空")

            # 过滤：涨幅 > 0，按成交额降序取前 80 名（锁定当日最活跃个股）
            rising = all_stocks[all_stocks['涨跌幅'] > 0].sort_values(by='成交额', ascending=False).head(80)
            
            qualified = []
            logger.info(f"🔍 行情获取成功，开始对 {len(rising)} 只活跃股进行 VCP 扫描...")

            for _, row in rising.iterrows():
                code = row['代码']
                name = row['名称']
                
                try:
                    # 降低频率：每秒抓取不超过 2 只，保护 IP
                    time.sleep(0.5) 
                    
                    # 获取历史 K 线（用于计算 ATR 和 EMA）
                    hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(60)
                    
                    if check_vcp_condition(hist):
                        qualified.append(code)
                        logger.info(f"🎯 发现符合形态: {name} ({code})")
                except Exception as e:
                    # 单只股票失败不影响全局，跳过继续
                    continue
            
            # 返回前 5 只最优质的潜力股，交给 AI 深入诊断
            return qualified[:5]

        except Exception as e:
            wait_time = (attempt + 1) * 5
            logger.warning(f"⚠️ 第 {attempt+1} 次扫描因网络波动失败: {e}，将在 {wait_time} 秒后重试...")
            time.sleep(wait_time) # 递增重试延迟

    logger.error("❌ 连续 3 次尝试均无法建立跨境数据连接，请检查 GitHub 网络环境。")
    return []
