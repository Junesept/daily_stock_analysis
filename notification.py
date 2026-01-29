# -*- coding: utf-8 -*-
import logging
import smtplib
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
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

    def _generate_vcp_html_body(self, results: List[Any]) -> str:
        """渲染 HTML 股票卡片"""
        # 严格过滤，确保只处理对象或字典，不处理字符串字符
        valid_results = [r for r in results if not isinstance(r, str)]
        logger.info(f"📬 正在渲染 HTML 邮件，有效股票对象数: {len(valid_results)}")
        
        cards_html = ""
        for res in valid_results:
            try:
                # 兼容对象和字典
                code = getattr(res, 'code', res.get('code', '未知') if isinstance(res, dict) else '未知')
                name = getattr(res, 'name', res.get('name', '未知') if isinstance(res, dict) else '未知')
                score = getattr(res, 'sentiment_score', res.get('sentiment_score', 0) if isinstance(res, dict) else 0)
                summary = getattr(res, 'analysis_summary', res.get('analysis_summary', 'AI 诊断中...') if isinstance(res, dict) else 'AI 诊断中...')
                
                cards_html += f"""
                <div style="background:#fff; border:1px solid #e0e6ed; border-radius:12px; padding:20px; margin-bottom:20px; font-family:sans-serif;">
                    <h2 style="color:#1a73e8; margin:0 0 10px 0;">📈 {name} ({code})</h2>
                    <div style="font-size:16px; color:#f29900; margin-bottom:10px;">VCP 评分: <strong>{score}</strong></div>
                    <p style="color:#3c4043; line-height:1.6; font-size:14px;">{str(summary)[:400]}...</p>
                </div>
                """
            except Exception as e:
                logger.warning(f"单条渲染跳过: {e}")
                continue

        if not cards_html:
            cards_html = "<p style='color:#666;'>今日扫描池个股暂未达到 AI 深入诊断的标准，建议关注大盘趋势。</p>"

        manual_check = """
        <div style="background:#fffbe6; border:1px solid #ffe58f; padding:15px; border-radius:8px; margin-top:20px;">
            <strong style="color:#856404;">⚠️ 关键人工核对：Moomoo 筹码分布</strong>
            <p style="font-size:13px; color:#555; margin-bottom:0;">由于使用 Yahoo 稳定源，请在 Moomoo 客户端确认：<strong>获利比例是否 > 80%</strong> 且 <strong>筹码集中度 < 15%</strong>。</p>
        </div>
        """
        return f"<html><body style='background:#f4f7f9; padding:20px;'>{cards_html}{manual_check}</body></html>"

    def send_to_email(self, results_or_text: Union[List[Any], str], subject: Optional[str] = None) -> bool:
        """【核心修复】智能识别输入内容"""
        if not self.is_available(): return False
        
        try:
            msg = MIMEMultipart()
            date_tag = datetime.now().strftime('%m-%d')
            msg['Subject'] = Header(subject or f"🚀 VCP 扫描/复盘报告 ({date_tag})", 'utf-8')
            msg['From'] = self._email_config['sender']
            msg['To'] = ', '.join(self._email_config['receivers'])

            # 智能分流
            if isinstance(results_or_text, list):
                # 输入是列表 -> 发送 HTML 卡片
                html_content = self._generate_vcp_html_body(results_or_text)
                msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            else:
                # 输入是字符串 -> 发送纯文本/Markdown
                msg.attach(MIMEText(str(results_or_text), 'plain', 'utf-8'))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self._email_config['sender'], self._email_config['password'])
                server.send_message(msg)
            logger.info("✅ 邮件通知已成功送达")
            return True
        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")
            return False

    def send(self, content: Any) -> bool:
        """主入口适配器"""
        return self.send_to_email(content)

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
    return NotificationService().send_to_email(results)
