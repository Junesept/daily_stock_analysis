# -*- coding: utf-8 -*-
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from config import get_config

logger = logging.getLogger(__name__)

STOCK_NAME_MAP = {
    '600519': '贵州茅台', '000001': '平安银行', '000651': '格力电器',
    '300308': '中际旭创', '688008': '澜起科技', '600879': '航天电子',
    '300502': '新易盛', '688041': '海光信息', '300750': '宁德时代'
}

@dataclass
class AnalysisResult:
    code: str
    name: str
    sentiment_score: int
    trend_prediction: str
    operation_advice: str
    dashboard: Optional[Dict[str, Any]] = None
    analysis_summary: str = ""
    success: bool = True
    error_message: Optional[str] = None

    def get_emoji(self) -> str:
        emoji_map = {'买入': '🟢', '加仓': '🟢', '强烈买入': '💚', '持有': '🟡', '观望': '⚪', '减仓': '🟠', '卖出': '🔴'}
        return emoji_map.get(self.operation_advice, '⚪')

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
    SYSTEM_PROMPT = "你是一位精通 Mark Minervini VCP 理论的交易员。请根据行情数据给出买入、止损点位。"

    def __init__(self, api_key: Optional[str] = None):
        config = get_config()
        self._api_key = api_key or config.gemini_api_key
        self._model = None
        self._use_openai = False 
        self._current_model_name = config.gemini_model
        self._init_model()

    def _init_model(self):
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(model_name=self._current_model_name, system_instruction=self.SYSTEM_PROMPT)
            logger.info("Gemini VCP 专家就绪")
        except Exception as e: logger.error(f"模型初始化失败: {e}")

    def is_available(self) -> bool: return self._model is not None

    def analyze(self, context: Dict[str, Any], news_context: Optional[str] = None) -> AnalysisResult:
        code = context.get('code', 'Unknown')
        name = context.get('stock_name', STOCK_NAME_MAP.get(code, f'股票{code}'))
        try:
            prompt = f"请分析股票 {name} ({code}) 的 VCP 形态：\n{json.dumps(context, ensure_ascii=False)}"
            response = self._model.generate_content(prompt)
            # 这里 AI 会返回包含 VCP 决策的文本
            return AnalysisResult(code=code, name=name, sentiment_score=60, trend_prediction='看多', operation_advice='持有', analysis_summary=response.text[:500])
        except Exception as e:
            return AnalysisResult(code=code, name=name, sentiment_score=50, trend_prediction='未知', operation_advice='观望', success=False, error_message=str(e))
