# -- coding: utf-8 --
import os
import requests
import re
import sys
from datetime import datetime
from email.utils import parsedate_to_datetime

def parse_cookie_expiry(cookie_str):
    """从 Cookie 字符串中提取 expires 字段并计算剩余天数"""
    match = re.search(r'expires=([^;]+)', cookie_str, re.I)
    if not match:
        return None
    try:
        expiry_date = parsedate_to_datetime(match.group(1).strip())
        delta = expiry_date - datetime.now().astimezone()
        return delta.days
    except Exception:
        return None

def send_telegram_message(text):
    bot_token = os.getenv('TG_BOT_TOKEN')
    chat_id = os.getenv('TG_CHAT_ID')
    if not bot_token or not chat_id:
        print("未配置 Telegram 通知，跳过。")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(url, json={
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }, timeout=10)
        if resp.status_code == 200:
            print("Telegram 通知发送成功。")
        else:
            print(f"Telegram 通知失败: {resp.text}")
    except Exception as e:
        print(f"发送 Telegram 异常: {e}")

def checkin(cookie):
    """执行签到并返回 (是否成功, 消息, 获得鸡腿数)"""
    url = "https://www.nodeseek.com/api/attendance"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Cookie': cookie
    }
    try:
        resp = requests.post(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}", 0
        data = resp.json()
        success = data.get('success', False)
        msg = data.get('message', '')
        chicken = 0
        if success:
            m = re.search(r'获得(\d+)鸡腿', msg)
            if m:
                chicken = int(m.group(1))
        return success, msg, chicken
    except Exception as e:
        return False, f"请求异常: {e}", 0

def main():
    cookies_raw = os.getenv('NS_COOKIES')
    if not cookies_raw:
        print("错误: 未设置 NS_COOKIES")
        sys.exit(1)

    cookies = [c.strip() for c in cookies_raw.split('\n') if c.strip()]
    if not cookies:
        print("错误: NS_COOKIES 为空")
        sys.exit(1)

    print(f"检测到 {len(cookies)} 个账号，开始签到...")
    results = []

    for idx, cookie in enumerate(cookies, 1):
        days_left = parse_cookie_expiry(cookie)
        days_str = f"{days_left} 天" if days_left is not None else "未知"

        success, msg, chicken = checkin(cookie)
        status_icon = "✅" if success else "❌"
        # 如果成功但没提取到鸡腿数，尝试从 msg 中补救
        if success and chicken == 0:
            m = re.search(r'(\d+)', msg)
            if m:
                chicken = int(m.group(1))

        result_line = f"账号 {idx}: {status_icon} {msg} | 获得 {chicken} 鸡腿 | 剩余 {days_str}"
        results.append(result_line)
        print(result_line)

    final_msg = "<b>📅 NodeSeek 签到汇总</b>\n" + "\n".join(results)
    send_telegram_message(final_msg)

if __name__ == "__main__":
    main()
