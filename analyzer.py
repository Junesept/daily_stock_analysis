# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - VCP 猎手版
===================================

职责：
1. 封装 Gemini API 调用逻辑，扮演 VCP 专家角色
2. 深度分析波动收缩 (VCP)、量能枯竭与突破质量
3. 结合技术面和消息面生成决策仪表盘
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from config import get_config

logger = logging.getLogger(__name__)

# 股票名称映射（常见股票）
STOCK_NAME_MAP = {
    '600519': '贵州茅台',
    '000001': '平安银行',
    '300750': '宁德时代',
    '002594': '比亚迪',
    '600036': '招商银行',
    '601318': '中国平安',
    '000858': '五粮液',
}

@dataclass
class AnalysisResult:
    """封装 Gemini 返回的分析结果，包含 VCP 决策仪表盘"""
    code: str
    name: str
    sentiment_score: int  
    trend_prediction: str  
    operation_advice: str  
    confidence_level: str = "中"  
    dashboard: Optional[Dict[str, Any]] = None  
    trend_analysis: str = ""  
    short_term_outlook: str = ""  
    medium_term_outlook: str = ""  
    technical_analysis: str = ""  
    ma_analysis: str = ""  
    volume_analysis: str = ""  
    pattern_analysis: str = ""  
    fundamental_analysis: str = ""  
    sector_position: str = ""  
    company_highlights: str = ""  
    news_summary: str = ""  
    market_sentiment: str = ""  
    hot_topics: str = ""  
    analysis_summary: str = ""  
    key_points: str = ""  
    risk_warning: str = ""  
    buy_reason: str = ""  
    raw_response: Optional[str] = None  
    search_performed: bool = False  
    data_sources: str = ""  
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

    def get_emoji(self) -> str:
        """根据操作建议返回对应 emoji，防止 main.py 报错"""
        emoji_map = {
            '买入': '🟢', '加仓': '🟢', '强烈买入': '💚',
            '持有': '🟡', '观望': '⚪', '减仓': '🟠',
            '卖出': '🔴', '强烈卖出': '❌',
        }
        return emoji_map.get(self.operation_advice, '🟡')

    def get_core_conclusion(self) -> str:
        if self.dashboard and 'core_conclusion' in self.dashboard:
            return self.dashboard['core_conclusion'].get('one_sentence', self.analysis_summary)
        return self.analysis_summary

    def get_sniper_points(self) -> Dict[str, str]:
        if self.dashboard and 'battle_plan' in self.dashboard:
            return self.dashboard['battle_plan'].get('sniper_points', {})
        return {}

    def get_checklist(self) -> List[str]:
        if self.dashboard and 'battle_plan' in self.dashboard:
            return self.dashboard['battle_plan'].get('action_checklist', [])
        return []

class GeminiAnalyzer:
    """
    VCP 专属 AI 分析器
    基于马克·米勒维尼 (Mark Minervini) 的趋势模板和 VCP 理论
    """
    
    # ========================================
    # VCP 专家系统提示词 v3.0
    # ========================================
    SYSTEM_PROMPT = """你是一位精通 **马克·米勒维尼 (Mark Minervini) VCP (波动收缩形态)** 的资深交易员。
你的任务是审核由扫描器筛选出的候选股，评估其是否具备高爆发力的“口袋支点”。

## 核心交易理念

### 1. 趋势模板 (Trend Template)
- 股价必须在 EMA50 或 MA20 之上运行。
- 均线必须呈现多头排列状态，斜率向上。

### 2. 波动收缩 (VCP)
- **收缩质量**：寻找价格振幅逐渐变小的结构（如从 25% -> 12% -> 5%）。
- **成交量枯竭**：在盘整结构的最后阶段，成交量必须出现显著的“干涸”迹象。
- **紧凑度**：价格行为越紧凑，突破的有效性越高。

### 3. 突破确认
- 突破关键压力位 (Pivot Point) 时，量比必须显著放大（通常 > 1.5）。
- 乖离率 (MA5) 超过 5% 时视为过热，严禁追高，建议等待缩量回踩。

## 输出格式：JSON 决策仪表盘
请严格按照以下 JSON 格式输出：
```json
{
    "sentiment_score": 0-100,
    "trend_prediction": "强烈看多/看多/震荡/看空",
    "operation_advice": "买入/加仓/持有/观望",
    "dashboard": {
        "core_conclusion": {
            "one_sentence": "VCP 结构研判结论",
            "signal_type": "🟢买入信号/🟡持有观望/🔴风险警报",
            "position_advice": { "no_position": "操作建议", "has_position": "操作建议" }
        },
        "data_perspective": {
            "trend_status": { "ma_alignment": "均线状态", "is_bullish": true },
            "vcp_metrics": { "contraction_quality": "紧凑/松散", "vol_dryup": "是/否", "bias_ma5": "数值" }
        },
        "battle_plan": {
            "sniper_points": { "ideal_buy": "买入价", "stop_loss": "止损价", "take_profit": "目标价" },
            "action_checklist": ["✅/❌ 检查项"]
        }
    },
    "analysis_summary": "100字深度总结"
}
```"""

    def __init__(self, api_key: Optional[str] = None):
        config = get_config()
        self._api_key = api_key or config.gemini_api_key
        self._model = None
        self._current_model_name = config.gemini_model
        self._use_openai = False
        self._init_model()

    def is_available(self) -> bool:
        """检查分析器是否可用（大盘分析模块需要此方法）"""
        return self._model is not None

    def _init_model(self) -> None:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(
                model_name=self._current_model_name,
                system_instruction=self.SYSTEM_PROMPT,
            )
            logger.info(f"Gemini VCP 专家模型初始化成功: {self._current_model_name}")
        except Exception as e:
            logger.error(f"模型初始化失败: {e}")

    def analyze(self, context: Dict[str, Any], news_context: Optional[str] = None) -> AnalysisResult:
        code = context.get('code', 'Unknown')
        name = context.get('stock_name', STOCK_NAME_MAP.get(code, f'股票{code}'))
        
        if not self._model:
            return self._get_error_result(code, name, "模型未就绪")

        try:
            prompt = self._format_vcp_prompt(context, name, news_context)
            
            # 调用 API
            response = self._model.generate_content(
                prompt,
                generation_config={"temperature": 0.3, "max_output_tokens": 4096}
            )
            
            return self._parse_response(response.text, code, name)
        except Exception as e:
            logger.error(f"VCP 分析 {name} 失败: {e}")
            return self._get_error_result(code, name, str(e))

    def _format_vcp_prompt(self, context: Dict[str, Any], name: str, news_context: Optional[str]) -> str:
        """构建专属于 VCP 诊断的提示词内容"""
        today = context.get('today', {})
        rt = context.get('realtime', {})
        chip = context.get('chip', {})
        trend = context.get('trend_analysis', {})
        
        return f"""
# 股票 VCP 诊断：{name} ({context.get('code')})

## 1. 价格与均线 (EMA/MA)
- 现价: {today.get('close')} | MA20: {today.get('ma20')}
- 均线排列: {context.get('ma_status')}
- 乖离率 (MA5): {trend.get('bias_ma5', 0):+.2f}%

## 2. 波动与量能 (Volatility & Volume)
- 量比: {rt.get('volume_ratio')} | 换手率: {rt.get('turnover_rate')}%
- 量能状态: {trend.get('volume_status')}
- ATR/波动表现: 扫描器已标记为“波动收缩中”

## 3. 筹码结构 (Supply)
- 获利比例: {chip.get('profit_ratio', 0):.1%}
- 90%筹码集中度: {chip.get('concentration_90', 0):.2%}
- 筹码状态: {chip.get('chip_status')}

## 4. 外部情报
{news_context if news_context else "暂无相关新闻"}

---
请基于 VCP 理论，对该股进行“口袋支点”诊断，判断其是否符合即将向上爆发的特征。
"""

    def _parse_response(self, text: str, code: str, name: str) -> AnalysisResult:
        try:
            # 简单清理 JSON
            json_str = text.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            
            data = json.loads(json_str)
            return AnalysisResult(
                code=code, name=name,
                sentiment_score=data.get('sentiment_score', 50),
                trend_prediction=data.get('trend_prediction', '震荡'),
                operation_advice=data.get('operation_advice', '观望'),
                dashboard=data.get('dashboard'),
                analysis_summary=data.get('analysis_summary', ''),
                success=True
            )
        except Exception as e:
            return self._parse_text_response(text, code, name)

    def _get_error_result(self, code: str, name: str, msg: str) -> AnalysisResult:
        return AnalysisResult(code=code, name=name, sentiment_score=50, trend_prediction='未知', 
                              operation_advice='观望', success=False, error_message=msg)

    def _parse_text_response(self, text, code, name):
        """保底文本解析"""
        return AnalysisResult(code=code, name=name, sentiment_score=50, trend_prediction='震荡',
                              operation_advice='持有', analysis_summary=text[:500], success=True)
