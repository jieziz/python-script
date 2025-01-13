import logging
import time
import threading
from DrissionPage import Chromium, ChromiumOptions
from dotenv import load_dotenv
import os
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("log.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def load_config():
    """加载配置文件"""
    load_dotenv(override=True)
    base_url = os.getenv("BASE_URL", "").rstrip('/')
    promo_codes = os.getenv("PROMO_CODES", "").split(',')
    product_urls = os.getenv("PRODUCT_URLS", "").split(',')

    if len(promo_codes) != len(product_urls):
        raise ValueError("PROMO_CODES 和 PRODUCT_URLS 的数量不一致！请检查配置。")

    return {
        'BASE_URL': base_url,
        'PROMO_CODES': promo_codes,
        'PRODUCT_URLS': product_urls,
        'HEADLESS_MODE': os.getenv("HEADLESS_MODE", "False").lower() == "true",
        'DELAY_TIME': int(os.getenv("DELAY_TIME", "5")),
        'RECHECK_INTERVAL': int(os.getenv("RECHECK_INTERVAL", "1200")),  # 默认 20 分钟
        'TG_BOT_TOKEN': os.getenv("TG_BOT_TOKEN"),
        'TG_CHAT_ID': os.getenv("TG_CHAT_ID"),
        'CLAW_URL': os.getenv("CLAW_URL")
    }

def send_tg_notification(bot_token, chat_id, message):
    """通过 Telegram 机器人发送通知"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logging.info("Telegram 通知发送成功。")
        else:
            logging.error(f"Telegram 通知发送失败，状态码: {response.status_code}，响应: {response.text}")
    except Exception as e:
        logging.error(f"发送 Telegram 通知时出错: {e}")

def monitor_promo_code(config, promo_code, product_url):
    """监控单个优惠码的有效性"""
    co = ChromiumOptions().auto_port()
    if config['HEADLESS_MODE']:
        co.headless()
    co.set_load_mode('none')
    co.set_pref('credentials_enable_service', False)
    co.set_argument('--hide-crash-restore-bubble')
    browser = Chromium(co)
    page = browser.latest_tab

    try:
        while True:
            page.get(product_url)
            if page.s_ele('#btnCompleteProductConfig'):
                page('#btnCompleteProductConfig').click()
            page.wait.load_start()

            page.get(config['BASE_URL'] + "/cart.php?a=checkout")

            if page.s_ele('#inputPromotionCode'):
                page('#inputPromotionCode').input(promo_code)
                page('@name=validatepromo').click()
                page.wait.load_start()

                if page.s_ele('text:Remove Promotion Code'):
                    logging.info(f"优惠码 {promo_code} 已生效")

                    # 发送通知
                    if promo_code == "Z3ZUF1RT5F":
                        message = (
                            f"<b>全场可用优惠码 <code>{promo_code}</code> 已生效！</b>\n\n"
                            f"立即前往下单: <a href=\"{config['CLAW_URL']}\">点击这里</a>"
                        )
                    else:
                        message = (
                            f"<b>优惠码 <code>{promo_code}</code> 已生效！</b>\n\n"
                            f"立即前往下单: <a href=\"{product_url}\">点击这里</a>"
                        )

                    send_tg_notification(config['TG_BOT_TOKEN'], config['TG_CHAT_ID'], message)

                    # 移除优惠码
                    if page.s_ele('text:Remove Promotion Code'):
                        page('text:Remove Promotion Code').click()
                        logging.info(f"已移除优惠码 {promo_code}，等待 {config['RECHECK_INTERVAL']} 秒后再次检测。")

                    # 等待配置的时间间隔再重新检测
                    time.sleep(config['RECHECK_INTERVAL'])
                else:
                    logging.info(f"优惠码 {promo_code} 暂时无效，{config['DELAY_TIME']} 秒后重试。")
            time.sleep(config['DELAY_TIME'])

    except Exception as e:
        logging.error(f"监控优惠码 {promo_code} 过程中发生错误: {e}")
    finally:
        browser.quit()

def main():
    config = load_config()
    threads = []

    for promo_code, product_url in zip(config['PROMO_CODES'], config['PRODUCT_URLS']):
        thread = threading.Thread(target=monitor_promo_code, args=(config, promo_code, product_url))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    logging.info("脚本启动。")
    try:
        main()
    except Exception as e:
        logging.critical(f"脚本运行过程中发生严重错误: {e}")
    finally:
        logging.info("脚本结束运行。")
