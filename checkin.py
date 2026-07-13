# -- coding: utf-8 --
import os
import requests
import re
import sys
import json
import base64
from datetime import datetime

def decode_jwt_payload(jwt_token):
    """解码 JWT payload"""
    try:
        parts = jwt_token.split('.')
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
        return json.loads(payload_json)
    except Exception:
        return None

def get_expiry_from_cookie(cookie_str):
    """从 pjwt 提取过期剩余天数"""
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

def get_csrf_token(cookie):
    """访问首页获取 XSRF-TOKEN（若不存在）"""
    try:
        url = "https://www.nodeseek.com/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Cookie': cookie
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            # 从返回的 cookies 中提取 XSRF-TOKEN
            for c in resp.cookies:
                if c.name == 'XSRF-TOKEN':
                    return c.value
        return None
    except Exception as e:
        print(f"获取 CSRF Token 失败: {e}")
        return None

def checkin(cookie, random_mode=False):
    """执行签到，自动获取 CSRF Token 并尝试两种提交方式"""
    # 1. 从现有 Cookie 提取 XSRF-TOKEN
    xsrf_token = None
    match = re.search(r'XSRF-TOKEN=([^;]+)', cookie)
    if match:
        xsrf_token = match.group(1)
    else:
        # 如果没有，则访问首页获取
        xsrf_token = get_csrf_token(cookie)
        if xsrf_token:
            # 将新 token 加入 cookie 字符串（便于后续重用）
            cookie = cookie + f"; XSRF-TOKEN={xsrf_token}"

    # 2. 构建请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Referer': 'https://www.nodeseek.com/',
        'Origin': 'https://www.nodeseek.com',
        'X-Requested-With': 'XMLHttpRequest',
        'Cookie': cookie
    }
    if xsrf_token:
        headers['X-XSRF-TOKEN'] = xsrf_token

    url = "https://www.nodeseek.com/api/attendance"
    data = None
    if random_mode:
        data = {'random': True}   # 试试手气

    # 3. 先尝试 JSON 方式
    try:
        if data:
            resp = requests.post(url, headers=headers, json=data, timeout=15)
        else:
            resp = requests.post(url, headers=headers, timeout=15)
    except Exception as e:
        return False, f"请求异常(JSON): {e}", 0

    # 4. 如果返回 419 或 403，尝试用 form-data 方式
    if resp.status_code in (419, 403):
        print("收到 419/403，尝试使用表单提交...")
        try:
            if data:
                # 将布尔值转为字符串
                form_data = {k: str(v).lower() if isinstance(v, bool) else v for k, v in data.items()}
                resp = requests.post(url, headers=headers, data=form_data, timeout=15)
            else:
                resp = requests.post(url, headers=headers, timeout=15)
        except Exception as e:
            return False, f"请求异常(Form): {e}", 0

    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}", 0

    try:
        result = resp.json()
    except:
        return False, f"非JSON响应: {resp.text[:100]}", 0

    success = result.get('success', False)
    msg = result.get('message', '')
    chicken = 0
    if success:
        m = re.search(r'获得(\d+)鸡腿', msg)
        if m:
            chicken = int(m.group(1))
    return success, msg, chicken

def main():
    cookies_raw = os.getenv('NS_COOKIES')
    if not cookies_raw:
        print("错误: 未设置 NS_COOKIES")
        sys.exit(1)

    random_mode = os.getenv('NS_RANDOM', 'false').strip().lower() == 'true'

    lines = [line.strip() for line in cookies_raw.split('\n') if line.strip()]
    if not lines:
        print("错误: NS_COOKIES 为空")
        sys.exit(1)

    print(f"签到模式: {'试试手气' if random_mode else '固定鸡腿'}")
    print(f"检测到 {len(lines)} 个账号，开始签到...")
    results = []

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

        days_left = get_expiry_from_cookie(cookie)
        days_str = f"{days_left} 天" if days_left is not None else "未知"

        success, msg, chicken = checkin(cookie, random_mode)
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
