# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 通知层 (VCP 优化版)
===================================
"""

import logging
import json
import smtplib
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from enum import Enum

import requests

from config import get_config
from analyzer import AnalysisResult

logger = logging.getLogger(__name__)

# --- VCP 专属 HTML 样式表 ---
VCP_EMAIL_STYLE = """
<style>
    .vcp-container { font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; max-width: 600px; margin: 0 auto; background: #f4f7f9; padding: 10px; }
    .vcp-card { background: #ffffff; border-radius: 12px; border: 1px solid #e0e6ed; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; overflow: hidden; }
    .vcp-header { background: #1a73e8; color: #ffffff; padding: 15px; text-align: center; }
    .vcp-body { padding: 20px; }
    .score-badge { font-size: 28px; font-weight: bold; color: #ffca28; margin: 10px 0; }
    .conclusion { font-size: 16px; color: #202124; line-height: 1.5; border-left: 4px solid #1a73e8; padding-left: 15px; margin: 15px 0; }
    .battle-plan { background: #fff8f8; border: 1px solid #ffcccc; border-radius: 8px; padding: 15px; margin: 15px 0; }
    .sniper-table { width: 100%; border-collapse: collapse; }
    .sniper-table td { padding: 10px 5px; border-bottom: 1px solid #eee; font-size: 14px; }
    .label { color: #5f6368; }
    .value { font-weight: bold; text-align: right; }
    .buy-price { color: #1e8e3e; font-size: 18px; }
    .stop-loss { color: #d93025; font-size: 18px; }
    .checklist { list-style: none; padding: 0; margin: 15px 0; }
    .checklist li { padding: 8px 0; font-size: 14px; border-bottom: 1px dashed #eee; color: #3c4043; }
    .footer { text-align: center; font-size: 12px; color: #9aa0a6; padding: 20px; }
</style>
"""

class NotificationChannel(Enum):
    WECHAT = "wechat"
    FEISHU = "feishu"
    TELEGRAM = "telegram"
    EMAIL = "email"
    PUSHOVER = "pushover"
    CUSTOM = "custom"
    UNKNOWN = "unknown"

# SMTP 配置保持不变...
SMTP_CONFIGS = {
    "qq.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False},
}

class NotificationService:
    def __init__(self):
        config = get_config()
        self._email_config = {
            'sender': config.email_sender,
            'password': config.email_password,
            'receivers': config.email_receivers or ([config.email_sender] if config.email_sender else []),
        }
        self._available_channels = self._detect_all_channels()

    def _detect_all_channels(self) -> List[NotificationChannel]:
        channels = []
        # 此处简化，仅展示邮件逻辑的修改
        if self._email_config['sender'] and self._email_config['password']:
            channels.append(NotificationChannel.EMAIL)
        return channels

    def _generate_vcp_html_body(self, results: List[AnalysisResult]) -> str:
        """生成精美的 VCP 专家诊断 HTML 正文"""
        cards_html = ""
        for res in results:
            points = res.get_sniper_points()
            checklist = res.get_checklist()
            
            cards_html += f"""
            <div class="vcp-card">
                <div class="vcp-header">
                    <div style="font-size: 14px; opacity: 0.9;">{res.code}</div>
                    <div style="font-size: 22px; font-weight: bold;">{res.get_emoji()} {res.name}</div>
                    <div class="score-badge">{res.sentiment_score} 分</div>
                </div>
                <div class="vcp-body">
                    <div class="conclusion"><strong>AI 诊断：</strong>{res.get_core_conclusion()}</div>
                    
                    <div class="battle-plan">
                        <div style="font-weight: bold; color: #d93025; margin-bottom: 10px;">🎯 口袋支点作战计划</div>
                        <table class="sniper-table">
                            <tr>
                                <td class="label">理想买入价 (Pivot)</td>
                                <td class="value buy-price">{points.get('ideal_buy', '等待信号')}</td>
                            </tr>
                            <tr>
                                <td class="label">硬性止损位 (Stop)</td>
                                <td class="value stop-loss">{points.get('stop_loss', 'N/A')}</td>
                            </tr>
                            <tr>
                                <td class="label">目标获利位 (Target)</td>
                                <td class="value">{points.get('take_profit', 'N/A')}</td>
                            </tr>
                        </table>
                    </div>

                    <div style="font-weight: bold; font-size: 15px; margin-top: 20px;">✅ VCP 形态核查清单</div>
                    <ul class="checklist">
                        {"".join(f"<li>{item}</li>" for item in checklist[:5])}
                    </ul>
                </div>
            </div>
            """
        
        return f"""
        <html>
        <head>{VCP_EMAIL_STYLE}</head>
        <body>
            <div class="vcp-container">
                <h1 style="text-align:center; color:#202124;">A股 VCP 潜力股扫描日报</h1>
                <p style="text-align:center; color:#5f6368;">{datetime.now().strftime('%Y-%m-%d')} | 基于米勒维尼趋势模板筛选</p>
                {cards_html}
                <div class="footer">AI 自动生成，仅供参考。风险自担。</div>
            </div>
        </body>
        </html>
        """

    def send_to_email(self, results: List[AnalysisResult], subject: Optional[str] = None) -> bool:
        """发送经过 VCP 优化的 HTML 邮件"""
        if not self._email_config['sender']: return False
        
        sender = self._email_config['sender']
        password = self._email_config['password']
        receivers = self._email_config['receivers']
        
        try:
            date_str = datetime.now().strftime('%Y-%m-%d')
            subject = subject or f"🚀 VCP 猎手报告: 今日发现 {len(results)} 只潜力股 ({date_str})"
            
            # 调用新设计的 HTML 生成器
            html_content = self._generate_vcp_html_body(results)
            
            msg = MIMEMultipart()
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From'] = sender
            msg['To'] = ', '.join(receivers)
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # 自动识别 SMTP 逻辑保持不变...
            domain = sender.split('@')[-1].lower()
            server_info = SMTP_CONFIGS.get(domain, {"server": f"smtp.{domain}", "port": 465, "ssl": True})
            
            if server_info['ssl']:
                server = smtplib.SMTP_SSL(server_info['server'], server_info['port'], timeout=20)
            else:
                server = smtplib.SMTP(server_info['server'], server_info['port'], timeout=20)
                server.starttls()
                
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
            logger.info(f"VCP 格式邮件已成功发送至 {receivers}")
            return True
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False

    def send(self, results: List[AnalysisResult]) -> bool:
        """统一发送入口"""
        # 生成 Markdown 给微信/飞书（保持原样）
        markdown_report = self.generate_daily_report(results)
        
        # 逐个渠道推送
        success = False
        if NotificationChannel.EMAIL in self._available_channels:
            if self.send_to_email(results): success = True
            
        # 其他渠道（如微信）依然使用 markdown_report
        # self.send_to_wechat(markdown_report) 
        
        return success

    # 保留原有的 generate_daily_report 等方法...
    def generate_daily_report(self, results: List[AnalysisResult], report_date: Optional[str] = None) -> str:
        # (原代码逻辑保持不变，用于支持非邮件渠道)
        return "Markdown Content"

def send_daily_report(results: List[AnalysisResult]) -> bool:
    """快捷调用函数"""
    service = NotificationService()
    # 存一份 markdown 在本地
    report_md = service.generate_daily_report(results)
    from pathlib import Path
    (Path(__file__).parent / 'reports' / f"report_{datetime.now().strftime('%Y%m%d')}.md").write_text(report_md, encoding='utf-8')
    
    return service.send(results)
