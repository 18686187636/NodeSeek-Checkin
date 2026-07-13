# -- coding: utf-8 --
import os
import requests
import re
import sys
import json
import base64
from datetime import datetime

def decode_jwt_payload(jwt_token):
    """解码 JWT 的 payload 部分，返回 dict"""
    try:
        # JWT 由三部分组成，取第二部分（payload）
        parts = jwt_token.split('.')
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        # 补齐 base64 填充
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
        return json.loads(payload_json)
    except Exception:
        return None

def get_expiry_from_cookie(cookie_str):
    """
    从 Cookie 字符串中提取 pjwt，解码获取 exp 时间戳，返回剩余天数（整数）
    若无法提取则返回 None
    """
    # 提取 pjwt 值
    match = re.search(r'pjwt=([^;]+)', cookie_str)
    if not match:
        return None
    jwt_token = match.group(1)
    payload = decode_jwt_payload(jwt_token)
    if not payload:
        return None
    exp_timestamp = payload.get('exp')
    if not exp_timestamp:
        return None
    try:
        exp_dt = datetime.fromtimestamp(exp_timestamp)
        delta = exp_dt - datetime.now()
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

    lines = [line.strip() for line in cookies_raw.split('\n') if line.strip()]
    if not lines:
        print("错误: NS_COOKIES 为空")
        sys.exit(1)

    print(f"检测到 {len(lines)} 个账号，开始签到...")
    results = []

    # 解析每一行，支持 "用户名|Cookie" 或 纯Cookie
    accounts = []
    for line in lines:
        if '|' in line:
            username, cookie = line.split('|', 1)
        else:
            username = None
            cookie = line
        accounts.append((username, cookie.strip()))

    for idx, (username, cookie) in enumerate(accounts, 1):
        display_name = username if username else f"账号 {idx}"

        # 自动从 Cookie 中提取过期剩余天数
        days_left = get_expiry_from_cookie(cookie)
        days_str = f"{days_left} 天" if days_left is not None else "未知"

        success, msg, chicken = checkin(cookie)
        status_icon = "✅" if success else "❌"
        if success and chicken == 0:
            m = re.search(r'(\d+)', msg)
            if m:
                chicken = int(m.group(1))

        result_line = f"{display_name}: {status_icon} {msg} | 获得 {chicken} 鸡腿 | 剩余 {days_str}"
        results.append(result_line)
        print(result_line)

    final_msg = "<b>📅 NodeSeek 签到汇总</b>\n" + "\n".join(results)
    send_telegram_message(final_msg)

if __name__ == "__main__":
    main()
