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
from analyzer import AnalysisResult

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

    def generate_dashboard_report(self, results: List[Any], report_date=None) -> str:
        date_str = report_date or datetime.now().strftime('%Y-%m-%d')
        lines = [f"# VCP 潜力股扫描日报 ({date_str})"]
        valid_res = [r for r in results if not isinstance(r, str)]
        for r in valid_res:
            lines.append(f"### {r.get_emoji()} {r.name} | {r.sentiment_score}分")
        return "\n".join(lines)

    def save_report_to_file(self, content: str, filename: Optional[str] = None) -> str:
        reports_dir = Path(__file__).parent / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)
        filepath = reports_dir / (filename or f"report_{datetime.now().strftime('%Y%m%d')}.md")
        filepath.write_text(content, encoding='utf-8')
        return str(filepath)

    def _generate_vcp_html_body(self, results: List[Any]) -> str:
        cards_html = ""
        valid_results = [res for res in results if not isinstance(res, str)]
        for res in valid_results:
            points = res.get_sniper_points()
            cards_html += f"""
            <div style="background:#fff; border-radius:12px; border:1px solid #e0e6ed; margin-bottom:20px; padding:20px; font-family:sans-serif;">
                <h2 style="color:#1a73e8; margin-top:0;">{res.get_emoji()} {res.name} ({res.code})</h2>
                <p><strong>AI 评分:</strong> {res.sentiment_score}</p>
                <p><strong>分析摘要:</strong> {res.get_core_conclusion()}</p>
                <div style="background:#f8f9fa; border-left:4px solid #1e8e3e; padding:10px;">
                    <strong>狙击位：</strong> 买入: {points.get('ideal_buy', '待定')} | 止损: {points.get('stop_loss', 'N/A')}
                </div>
            </div>
            """
        return f"<html><body style='background:#f4f7f9; padding:20px;'>{cards_html}</body></html>"

    def send(self, results_or_content: Any) -> bool:
        """主程序 main.py 调用的统一入口"""
        if isinstance(results_or_content, list):
            # 处理股票分析列表，发送 HTML 邮件
            return self.send_to_email(results_or_content)
        elif isinstance(results_or_content, str):
            # 处理大盘复盘报告（纯文本）
            return self.send_text_email(results_or_content)
        return False

    def send_to_email(self, results: List[Any], subject: Optional[str] = None) -> bool:
        if not self.is_available(): return False
        try:
            msg = MIMEMultipart()
            msg['Subject'] = Header(subject or f"🚀 VCP 扫描报告 ({datetime.now().strftime('%m-%d')})", 'utf-8')
            msg['From'] = self._email_config['sender']
            msg['To'] = ', '.join(self._email_config['receivers'])
            msg.attach(MIMEText(self._generate_vcp_html_body(results), 'html', 'utf-8'))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self._email_config['sender'], self._email_config['password'])
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
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
            return True
        except Exception as e:
            logger.error(f"大盘报告发送失败: {e}")
            return False

def send_daily_report(results: List[Any]) -> bool:
    service = NotificationService()
    return service.send(results)
