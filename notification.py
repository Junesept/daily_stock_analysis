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

# 1. 定义 main.py 需要的通知渠道枚举
class NotificationChannel(Enum):
    EMAIL = "email"
    WECHAT = "wechat"
    FEISHU = "feishu"
    TELEGRAM = "telegram"
    PUSHOVER = "pushover"
    CUSTOM = "custom"
    UNKNOWN = "unknown"

class NotificationService:
    def __init__(self):
        config = get_config()
        self._email_config = {
            'sender': config.email_sender,
            'password': config.email_password,
            'receivers': config.email_receivers or ([config.email_sender] if config.email_sender else []),
        }
        # 只要配置了发送邮箱，就激活邮件渠道
        self._available_channels = [NotificationChannel.EMAIL] if self._email_config['sender'] else []

    def is_available(self) -> bool:
        return len(self._available_channels) > 0

    def get_available_channels(self) -> List[NotificationChannel]:
        return self._available_channels

    def _generate_vcp_html_body(self, results: List[AnalysisResult]) -> str:
        """生成精美的 HTML 邮件正文"""
        cards_html = ""
        for res in results:
            points = res.get_sniper_points()
            checklist = res.get_checklist()
            cards_html += f"""
            <div style="background:#fff; border-radius:12px; border:1px solid #e0e6ed; margin-bottom:20px; overflow:hidden; font-family:sans-serif;">
                <div style="background:#1a73e8; color:#fff; padding:15px; text-align:center;">
                    <div style="font-size:22px; font-weight:bold;">{res.get_emoji()} {res.name} ({res.code})</div>
                    <div style="font-size:28px; color:#ffca28; margin-top:5px;">VCP 评分: {res.sentiment_score}</div>
                </div>
                <div style="padding:20px;">
                    <div style="border-left:4px solid #1a73e8; padding-left:15px; margin:15px 0;"><strong>AI 诊断：</strong>{res.get_core_conclusion()}</div>
                    <div style="background:#fff8f8; border:1px solid #ffcccc; border-radius:8px; padding:15px;">
                        <div style="font-weight:bold; color:#d93025; margin-bottom:10px;">🎯 VCP 狙击买卖位</div>
                        <table style="width:100%; border-collapse:collapse;">
                            <tr><td style="color:#5f6368;">买入点 (Pivot)</td><td style="text-align:right; font-weight:bold; color:#1e8e3e;">{points.get('ideal_buy', '等待信号')}</td></tr>
                            <tr><td style="color:#5f6368;">止损位 (Stop)</td><td style="text-align:right; font-weight:bold; color:#d93025;">{points.get('stop_loss', 'N/A')}</td></tr>
                        </table>
                    </div>
                </div>
            </div>
            """
        return f"<html><body style='background:#f4f7f9; padding:10px;'>{cards_html}</body></html>"

    def generate_daily_report(self, results: List[AnalysisResult], report_date=None) -> str:
        """生成 Markdown 格式报告（保底使用）"""
        date_str = report_date or datetime.now().strftime('%Y-%m-%d')
        lines = [f"# 📈 A股 VCP 扫描简报 ({date_str})", ""]
        for r in results:
            lines.append(f"### {r.get_emoji()} {r.name} ({r.code})\n- 建议: **{r.operation_advice}**\n- 评分: {r.sentiment_score}\n- 诊断: {r.get_core_conclusion()}\n")
        return "\n".join(lines)

    def generate_dashboard_report(self, results: List[AnalysisResult], report_date=None) -> str:
        """主程序 main.py 强依赖的方法"""
        return self.generate_daily_report(results, report_date)

    def save_report_to_file(self, content: str, filename: Optional[str] = None) -> str:
        """保存日报到本地 reports/ 目录"""
        reports_dir = Path(__file__).parent / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)
        filepath = reports_dir / (filename or f"report_{datetime.now().strftime('%Y%m%d')}.md")
        filepath.write_text(content, encoding='utf-8')
        return str(filepath)

    def send_to_email(self, results: List[AnalysisResult], subject: Optional[str] = None) -> bool:
        if not self.is_available(): return False
        try:
            msg = MIMEMultipart()
            date_tag = datetime.now().strftime('%m-%d')
            msg['Subject'] = Header(subject or f"🚀 VCP 潜力股扫描战报 ({date_tag})", 'utf-8')
            msg['From'] = self._email_config['sender']
            msg['To'] = ', '.join(self._email_config['receivers'])
            
            # 使用精美的 HTML 格式
            msg.attach(MIMEText(self._generate_vcp_html_body(results), 'html', 'utf-8'))
            
            # 自动识别 SMTP（以 Gmail 为例，如果是 QQ 邮箱请手动改为 smtp.qq.com）
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self._email_config['sender'], self._email_config['password'])
                server.send_message(msg)
            logger.info("✅ 邮件已成功送达")
            return True
        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")
            return False

# 2. 补全 main.py 强依赖的全局快捷函数
def send_daily_report(results: List[AnalysisResult]) -> bool:
    """快捷发送函数"""
    service = NotificationService()
    # 存一份 Markdown 副本在仓库，方便在 GitHub 网页查看
    report_md = service.generate_daily_report(results)
    service.save_report_to_file(report_md)
    
    # 执行邮件推送
    return service.send_to_email(results)

def get_notification_service() -> NotificationService:
    """获取实例的快捷函数"""
    return NotificationService()
