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

    def generate_dashboard_report(self, results: List[AnalysisResult], report_date=None) -> str:
        date_str = report_date or datetime.now().strftime('%Y-%m-%d')
        lines = [f"# VCP 潜力股简报 ({date_str})"]
        for r in [res for res in results if not isinstance(res, str)]:
            lines.append(f"### {r.get_emoji()} {r.name} | {r.sentiment_score}分")
        return "\n".join(lines)

    def save_report_to_file(self, content: str, filename: Optional[str] = None) -> str:
        reports_dir = Path(__file__).parent / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)
        filepath = reports_dir / (filename or f"report_{datetime.now().strftime('%Y%m%d')}.md")
        filepath.write_text(content, encoding='utf-8')
        return str(filepath)

    def send(self, results: Any) -> bool:
        if isinstance(results, list): return self.send_to_email(results)
        return True

    def send_to_email(self, results: List[AnalysisResult]) -> bool:
        if not self.is_available(): return False
        try:
            msg = MIMEMultipart()
            msg['Subject'] = Header(f"🚀 VCP 扫描报告 ({datetime.now().strftime('%m-%d')})", 'utf-8')
            msg['From'] = self._email_config['sender']
            msg['To'] = ', '.join(self._email_config['receivers'])
            # 简化版 HTML 正文
            msg.attach(MIMEText("请查看详细报告", 'plain', 'utf-8'))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self._email_config['sender'], self._email_config['password'])
                server.send_message(msg)
            return True
        except Exception as e: return False
