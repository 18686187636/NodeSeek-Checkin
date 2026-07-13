# -- coding: utf-8 --
import os
import requests
import re
import sys
import json
import base64
from datetime import datetime

def decode_jwt_payload(jwt_token):
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
            for c in resp.cookies:
                if c.name == 'XSRF-TOKEN':
                    return c.value
        return None
    except Exception as e:
        print(f"获取 CSRF Token 失败: {e}")
        return None

def checkin(cookie, random_mode=False):
    # 获取 XSRF-TOKEN
    xsrf_token = None
    match = re.search(r'XSRF-TOKEN=([^;]+)', cookie)
    if match:
        xsrf_token = match.group(1)
    else:
        xsrf_token = get_csrf_token(cookie)
        if xsrf_token:
            cookie = cookie + f"; XSRF-TOKEN={xsrf_token}"

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
    
    # 尝试带参数的请求（JSON或Form）
    def do_request(use_json=True, with_data=True):
        data = None
        if with_data and random_mode:
            data = {'random': True}
        try:
            if use_json:
                if data:
                    return requests.post(url, headers=headers, json=data, timeout=15)
                else:
                    return requests.post(url, headers=headers, timeout=15)
            else:
                if data:
                    form_data = {k: str(v).lower() if isinstance(v, bool) else v for k, v in data.items()}
                    return requests.post(url, headers=headers, data=form_data, timeout=15)
                else:
                    return requests.post(url, headers=headers, timeout=15)
        except Exception as e:
            return None

    # 第一次尝试：JSON + 数据
    resp = do_request(use_json=True, with_data=True)
    if resp is None:
        return False, "请求异常", 0

    # 如果返回 500，可能是因为已签到导致参数错误，尝试不带参数
    if resp.status_code == 500:
        print("收到 500，尝试不带参数重新请求...")
        resp = do_request(use_json=True, with_data=False)
        if resp is None:
            return False, "请求异常（重试）", 0

    # 如果返回 419 或 403，尝试表单提交
    if resp.status_code in (419, 403):
        print("收到 419/403，尝试使用表单提交...")
        resp = do_request(use_json=False, with_data=True)
        if resp is None:
            return False, "请求异常（表单）", 0
        # 若表单提交也500，则再试一次不带参数
        if resp.status_code == 500:
            print("表单提交也返回 500，尝试不带参数...")
            resp = do_request(use_json=False, with_data=False)
            if resp is None:
                return False, "请求异常（表单无参）", 0

    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}", 0

    try:
        result = resp.json()
    except:
        return False, f"非JSON响应: {resp.text[:100]}", 0

    success = result.get('success', False)
    msg = result.get('message', '')

    # 检查是否已签到
    already_checked = False
    if not success:
        # 检查常见已签到提示
        if re.search(r'(已签到|今日已签到|签到过了|重复签到|你已经签到)', msg):
            already_checked = True
            success = True  # 视为成功
            msg = "已签到（今日已打卡）"

    chicken = 0
    if success:
        # 尝试提取鸡腿数（可能为0）
        m = re.search(r'获得(\d+)鸡腿', msg)
        if m:
            chicken = int(m.group(1))
        else:
            # 如果消息中没有鸡腿数，但已签到，鸡腿为0
            if already_checked:
                chicken = 0

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
        # 如果成功但鸡腿为0，尝试从消息中提取数字
        if success and chicken == 0:
            numbers = re.findall(r'\d+', msg)
            if numbers:
                chicken = int(numbers[0])

        result_line = f"{display_name}: {status_icon} {msg} | 获得 {chicken} 鸡腿 | 剩余 {days_str}"
        results.append(result_line)
        print(result_line)

    final_msg = "<b>📅 NodeSeek 签到汇总</b>\n" + "\n".join(results)
    send_telegram_message(final_msg)

if __name__ == "__main__":
    main()
