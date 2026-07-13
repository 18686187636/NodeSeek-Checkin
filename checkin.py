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

def checkin(cookie, random_mode=False):
    """
    签到函数，自动处理已签到、500等异常
    返回 (success, message, chicken_count)
    """
    # 使用 Session 保持 Cookies 和自动处理重定向
    s = requests.Session()
    # 设置默认 headers
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.nodeseek.com/',
        'Origin': 'https://www.nodeseek.com',
    })

    # 解析并设置 Cookie
    for item in cookie.split(';'):
        item = item.strip()
        if '=' in item:
            name, value = item.split('=', 1)
            s.cookies.set(name, value, domain='.nodeseek.com')

    # 尝试访问签到页面，获取 CSRF Token 并检查是否已签到
    # 可能的签到页面地址（根据常见情况，可能是 /attendance 或 /user/attendance）
    check_pages = ['/attendance', '/user/attendance', '/member/attendance']
    already_checked = False
    for page in check_pages:
        try:
            resp = s.get('https://www.nodeseek.com' + page, timeout=10)
            if resp.status_code == 200:
                if '已签到' in resp.text or '今日已签' in resp.text:
                    already_checked = True
                    # 尝试提取鸡腿数（可能页面会有显示）
                    m = re.search(r'已签到.*?获得(\d+)鸡腿', resp.text)
                    chicken = int(m.group(1)) if m else 0
                    return True, "已签到（今日已打卡）", chicken
                # 获取 XSRF-TOKEN（如果有）
                for c in s.cookies:
                    if c.name == 'XSRF-TOKEN':
                        break
                break
        except:
            continue

    # 如果已签到检测失败，仍然尝试签到接口
    # 定义可能的 API 端点
    endpoints = ['/api/attendance', '/api/user/checkin', '/api/checkin']
    # 准备 CSRF Token
    xsrf_token = s.cookies.get('XSRF-TOKEN')
    if xsrf_token:
        s.headers.update({'X-XSRF-TOKEN': xsrf_token, 'X-Requested-With': 'XMLHttpRequest'})
    else:
        s.headers.update({'X-Requested-With': 'XMLHttpRequest'})

    # 数据
    data = {}
    if random_mode:
        data['random'] = 'true'   # 试试手气

    # 尝试多个端点
    for endpoint in endpoints:
        url = 'https://www.nodeseek.com' + endpoint
        print(f"尝试端点: {endpoint}")
        try:
            # 先尝试带数据的请求
            if data:
                resp = s.post(url, data=data, timeout=15)
            else:
                resp = s.post(url, timeout=15)
        except Exception as e:
            print(f"请求失败: {e}")
            continue

        # 处理 500 错误（可能已签到）
        if resp.status_code == 500:
            # 尝试读取响应文本
            try:
                err_text = resp.text
                if '已签到' in err_text or '重复' in err_text or 'repeat' in err_text.lower():
                    return True, "已签到（今日已打卡）", 0
            except:
                pass
            # 尝试不带数据重试
            try:
                resp2 = s.post(url, timeout=15)
                if resp2.status_code == 200:
                    resp = resp2
                elif resp2.status_code == 500:
                    # 再次检查
                    try:
                        if '已签到' in resp2.text:
                            return True, "已签到（今日已打卡）", 0
                    except:
                        pass
                    # 如果还是500，可能是其他问题，继续尝试下一个端点
                    continue
                else:
                    # 其他状态码，继续下一个端点
                    continue
            except:
                continue

        # 检查状态码
        if resp.status_code == 200:
            try:
                result = resp.json()
                success = result.get('success', False)
                msg = result.get('message', '')
                chicken = 0
                if success:
                    m = re.search(r'获得(\d+)鸡腿', msg)
                    if m:
                        chicken = int(m.group(1))
                return success, msg, chicken
            except:
                # 非JSON响应，可能返回了HTML，检查是否已签到
                if '已签到' in resp.text:
                    return True, "已签到（页面检测）", 0
                else:
                    return False, f"非JSON响应: {resp.text[:100]}", 0
        else:
            # 其他状态码，继续尝试
            print(f"端点 {endpoint} 返回 {resp.status_code}")

    # 所有端点都失败，尝试最后的办法：假设已签到（因为之前已签到过）
    # 如果用户今天确实已经签到，我们可以直接返回成功
    # 但为了保险，我们返回错误
    return False, "所有签到端点均失败", 0

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
            # 尝试从消息中提取数字
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
