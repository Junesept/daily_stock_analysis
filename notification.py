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

    def _generate_vcp_html_body(self, results: List[Any]) -> str:
        """生成 HTML 邮件正文（带防御性逻辑）"""
        valid_results = [r for r in results if hasattr(r, 'code')]
        logger.info(f"📬 正在渲染邮件正文，有效股票数: {len(valid_results)}")
        
        cards_html = ""
        for res in valid_results:
            # 即使没有 dashboard 数据，也确保能显示基础信息
            points = res.get_sniper_points() if hasattr(res, 'get_sniper_points') else {}
            summary = res.analysis_summary if res.analysis_summary else "AI 正在生成诊断..."
            
            cards_html += f"""
            <div style="background:#fff; border-radius:12px; border:1px solid #e0e6ed; margin-bottom:20px; padding:20px; font-family:sans-serif;">
                <h2 style="color:#1a73e8; margin-top:0;">{res.get_emoji()} {res.name} ({res.code})</h2>
                <div style="font-size:16px; font-weight:bold; color:#f29900; margin-bottom:10px;">
                    AI 评分: {res.sentiment_score} | 建议: {res.operation_advice}
                </div>
                <p style="color:#3c4043; line-height:1.6;">{summary}</p>
                <div style="background:#f8f9fa; border-left:4px solid #1e8e3e; padding:12px; margin-top:10px;">
                    <strong>狙击参考：</strong> 
                    买入点: <span style="color:#1e8e3e;">{points.get('ideal_buy', '等待信号')}</span> | 
                    止损位: <span style="color:#d93025;">{points.get('stop_loss', '参考5日线')}</span>
                </div>
            </div>
            """
        
        # 增加人工核对提醒（针对 Yahoo 财经缺少筹码的情况）
        manual_check = """
        <div style="background:#fffbe6; border:1px solid #ffe58f; padding:15px; border-radius:8px; margin-top:20px;">
            <strong style="color:#856404;">⚠️ 关键步骤：Moomoo 筹码核查</strong>
            <p style="font-size:13px; color:#555; margin-bottom:0;">请在客户端核实获利比例是否 > 80%，VCP 突破需筹码锁定良好。</p>
        </div>
        """
        
        if not cards_html:
            cards_html = "<p>今日扫描完成，暂无符合 VCP 形态的个股进入分析池。</p>"
            
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
            logger.info("✅ 邮件发送成功")
            return True
        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")
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
            logger.error(f"大盘报告失败: {e}")
            return False

    def generate_dashboard_report(self, results: List[Any], report_date=None) -> str:
        date_str = report_date or datetime.now().strftime('%Y-%m-%d')
        lines = [f"# VCP 潜力股扫描日报 ({date_str})"]
        valid_res = [r for r in results if hasattr(r, 'code')]
        for r in valid_res:
            lines.append(f"### {r.get_emoji()} {r.name} ({r.code}) | {r.sentiment_score}分")
        return "\n".join(lines)

    def save_report_to_file(self, content: str, filename: Optional[str] = None) -> str:
        reports_dir = Path(__file__).parent / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)
        filepath = reports_dir / (filename or f"report_{datetime.now().strftime('%Y%m%d')}.md")
        filepath.write_text(content, encoding='utf-8')
        return str(filepath)

def send_daily_report(results: List[Any]) -> bool:
    return NotificationService().send(results)
