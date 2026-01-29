# -*- coding: utf-8 -*-
import logging
import smtplib
from datetime import datetime
from typing import List, Dict, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from enum import Enum
from pathlib import Path
from config import get_config

logger = logging.getLogger(__name__)

class NotificationChannel(Enum):
    EMAIL = "email"
    WECHAT = "wechat"
    FEISHU = "feishu"
    TELEGRAM = "telegram"
    UNKNOWN = "unknown"

class NotificationService:
    def __init__(self):
        config = get_config()
        self._email_config = {
            'sender': config.email_sender,
            'password': config.email_password,
            'receivers': config.email_receivers or ([config.email_sender] if config.email_sender else []),
        }
        self._available_channels = [NotificationChannel.EMAIL] if self._email_config['sender'] else []

    def is_available(self) -> bool: return len(self._available_channels) > 0
    def get_available_channels(self) -> List[NotificationChannel]: return self._available_channels

    def _generate_vcp_html_body(self, results: List[Any]) -> str:
        """强化版 HTML 渲染，使用严格类型检查防止崩溃"""
        valid_results = [r for r in results if not isinstance(r, str)]
        logger.info(f"📬 正在渲染邮件卡片，有效股票数: {len(valid_results)}")
        
        cards_html = ""
        for res in valid_results:
            try:
                # 安全提取基础字段
                if isinstance(res, dict):
                    code = str(res.get('code', '未知'))
                    name = str(res.get('name', '未知'))
                    score = res.get('sentiment_score', 0)
                    advice = res.get('operation_advice', '观望')
                    summary = res.get('analysis_summary', 'AI 暂无总结')
                    emoji = '⚪'
                    points = res.get('dashboard', {}).get('battle_plan', {}).get('sniper_points', {})
                else:
                    # 处理 AnalysisResult 对象
                    code = getattr(res, 'code', '未知')
                    name = getattr(res, 'name', '未知')
                    score = getattr(res, 'sentiment_score', 0)
                    advice = getattr(res, 'operation_advice', '观望')
                    summary = getattr(res, 'analysis_summary', 'AI 暂无总结')
                    emoji = res.get_emoji() if hasattr(res, 'get_emoji') else '⚪'
                    points = res.get_sniper_points() if hasattr(res, 'get_sniper_points') else {}

                cards_html += f"""
                <div style="background:#fff; border-radius:12px; border:1px solid #e0e6ed; margin-bottom:20px; padding:20px; font-family:sans-serif;">
                    <h2 style="color:#1a73e8; margin-top:0;">{emoji} {name} ({code})</h2>
                    <div style="font-size:16px; font-weight:bold; color:#f29900; margin-bottom:10px;">
                        VCP 评分: {score} | 建议: {advice}
                    </div>
                    <p style="color:#3c4043; line-height:1.6;">{str(summary)[:300]}...</p>
                    <div style="background:#f8f9fa; border-left:4px solid #1e8e3e; padding:12px; margin-top:10px;">
                        <strong>狙击参考位：</strong> 
                        买入: <span style="color:#1e8e3e;">{points.get('ideal_buy', '等待信号')}</span> | 
                        止损: <span style="color:#d93025;">{points.get('stop_loss', '参考5日线')}</span>
                    </div>
                </div>
                """
            except Exception as e:
                logger.error(f"单条股票渲染失败: {e}")
                continue
        
        if not cards_html:
            cards_html = "<div style='padding:20px; background:#fff;'>今日扫描完成，暂无符合 VCP 形态的个股进入分析池。</div>"
            
        manual_check = """
        <div style="background:#fffbe6; border:1px solid #ffe58f; padding:15px; border-radius:8px; margin-top:20px;">
            <strong style="color:#856404;">⚠️ 关键步骤：Moomoo 筹码核查</strong>
            <p style="font-size:13px; color:#555; margin-bottom:0;">Yahoo 财经数据不含筹码，请在 Moomoo 确认<strong>获利比例是否 > 80%</strong>。</p>
        </div>
        """
        return f"<html><body style='background:#f4f7f9; padding:20px;'>{cards_html}{manual_check}</body></html>"

    def send(self, results_or_content: Any) -> bool:
        if isinstance(results_or_content, list):
            return self.send_to_email(results_or_content)
        elif isinstance(results_or_content, str):
            return self.send_text_email(results_or_content)
        return False

    def send_to_email(self, results: List[Any], subject: Optional[str] = None) -> bool:
        if not self.is_available(): return False
        try:
            msg = MIMEMultipart()
            date_tag = datetime.now().strftime('%m-%d')
            msg['Subject'] = Header(subject or f"🚀 VCP 扫描报告 ({date_tag})", 'utf-8')
            msg['From'] = self._email_config['sender']
            msg['To'] = ', '.join(self._email_config['receivers'])
            
            html_body = self._generate_vcp_html_body(results)
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self._email_config['sender'], self._email_config['password'])
                server.send_message(msg)
            logger.info("✅ VCP 扫描邮件已成功送达")
            return True
        except Exception as e:
            logger.error(f"❌ 邮件失败: {e}")
            return False

    def send_text_email(self, content: str, subject: str = "📈 A股大盘复盘简报") -> bool:
        try:
            msg = MIMEMultipart()
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From'] = self._email_config['sender']
            msg['To'] = ', '.join(self._email_config['receivers'])
            msg.attach(MIMEText(content, 'plain', 'utf-8'))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self._email_config['sender'], self._email_config['password'])
                server.send_message(msg)
            logger.info("✅ 大盘复盘邮件已成功送达")
            return True
        except Exception as e:
            logger.error(f"大盘报告失败: {e}")
            return False

    def generate_dashboard_report(self, results: List[Any], report_date=None) -> str:
        date_str = report_date or datetime.now().strftime('%Y-%m-%d')
        lines = [f"# VCP 潜力股扫描日报 ({date_str})"]
        valid_res = [r for r in results if not isinstance(r, str)]
        for r in valid_res:
            name = getattr(r, 'name', r.get('name', '未知') if isinstance(r, dict) else '未知')
            score = getattr(r, 'sentiment_score', r.get('sentiment_score', 0) if isinstance(r, dict) else 0)
            lines.append(f"### {name} | {score}分")
        return "\n".join(lines)

    def save_report_to_file(self, content: str, filename: Optional[str] = None) -> str:
        reports_dir = Path(__file__).parent / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)
        filepath = reports_dir / (filename or f"report_{datetime.now().strftime('%Y%m%d')}.md")
        filepath.write_text(content, encoding='utf-8')
        return str(filepath)

def send_daily_report(results: List[Any]) -> bool:
    return NotificationService().send(results)
