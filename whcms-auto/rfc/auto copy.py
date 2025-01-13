import logging
import time
from DrissionPage import Chromium, ChromiumOptions
from dotenv import load_dotenv
import os
from TimePinner import Pinner
from multiprocessing import Process

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
    product_urls = os.getenv("PRODUCT_URLS", "").split(',')
    promo_codes = os.getenv("PROMO_CODES", "").split(',')

    return {
        'BASE_URL': base_url,
        'PRODUCT_URLS': product_urls,
        'LOGIN_URL': os.getenv("LOGIN_URL"),
        'EMAILS': os.getenv("EMAILS", "").split(','),
        'PASSWORDS': os.getenv("PASSWORDS", "").split(','),
        'PROMO_CODES': promo_codes,
        'HEADLESS_MODE': os.getenv("HEADLESS_MODE", "False").lower() == "true",
        'DELAY_TIME': int(os.getenv("DELAY_TIME", "5")),
        'RECHECK_INTERVAL': int(os.getenv("RECHECK_INTERVAL", "10"))
    }

def check_stock(page):
    """检查商品库存"""
    try:
        pinner = Pinner()
        pinner.pin('检查库存开始')
        has_quehuo = page.s_ele('text:Out of Stock')
        pinner.pin('检查库存结束')
        page.stop_loading()
        return not bool(has_quehuo)
    except Exception as e:
        logging.warning(f"检查库存时发生错误: {e}")
        return False

def perform_purchase(page, promo_code):
    """执行下单流程"""
    try:
        pinner = Pinner()
        pinner.pin('执行下单开始')

        if promo_code:
            page.get(BASE_URL + "/cart.php?a=view")
            if page.s_ele('#inputPromotionCode'):
                page('#inputPromotionCode').input(promo_code)
                page('@name=validatepromo').click()
                page.wait.load_start()
                page.wait.ele_displayed('@name=validatepromo', timeout=10)
                pinner.pin('使用优惠码用时')

        page.ele('#btnCompleteProductConfig').click()
        page.wait.load_start()
        pinner.pin('加入购物车用时')

        page.ele('#tos-checkbox').click()
        page.ele("#checkout").click()
        page.wait.load_start()
        pinner.pin('进入结算页面用时')
        time.sleep(30)
        logging.info("订单提交成功")
        pinner.pin('订单提交用时')
        return True

    except Exception as e:
        logging.error(f"下单过程中发生错误: {e}")
        return False

def login(page, email, password, login_url):
    """登录账号"""
    try:
        page.get(login_url)
        if page.s_ele('text:My Dashboard'):
            page.stop_loading()
            return True
        else:
            page('#inputEmail').input(email)
            page('#inputPassword').input(password)
            page('#login').click()
            page.wait.ele_displayed('text:My Dashboard', timeout=10)
            return True
    except Exception as e:
        logging.error(f"登录检查过程发生错误: {e}")
    return False

def monitor_account(email, password, product_urls, promo_codes, base_url, login_url, headless_mode, delay_time):
    """监控指定账号的库存"""
    co = ChromiumOptions().auto_port()
    if headless_mode:
        co.headless()
    co.set_load_mode('none')
    co.set_pref('credentials_enable_service', False)
    co.set_argument('--hide-crash-restore-bubble')
    co.set_argument('--start-maximized')

    browser = Chromium(co)
    page = browser.latest_tab

    if not login(page, email, password, login_url):
        return

    success_count = 0
    while True:
        try:
            for product_url, promo_code in zip(product_urls, promo_codes):
                page.get(product_url)
                time.sleep(delay_time)

                if check_stock(page):
                    if perform_purchase(page, promo_code):
                        success_count += 1
                        logging.info(f"账号 {email} 第 {success_count} 次下单成功！继续监控新的库存...")
                    else:
                        logging.error(f"账号 {email} 下单失败，继续监控...")

                time.sleep(delay_time)
        except Exception as e:
            logging.error(f"账号 {email} 监控过程中发生错误: {e}")
            time.sleep(delay_time)
            continue

def main():
    config = load_config()

    processes = []
    for email, password in zip(config['EMAILS'], config['PASSWORDS']):
        p = Process(target=monitor_account, args=(
            email,
            password,
            config['PRODUCT_URLS'],
            config['PROMO_CODES'],
            config['BASE_URL'],
            config['LOGIN_URL'],
            config['HEADLESS_MODE'],
            config['DELAY_TIME']
        ))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

if __name__ == "__main__":
    logging.info("脚本启动。")
    try:
        main()
    except Exception as e:
        logging.critical(f"脚本运行过程中发生严重错误: {e}")
    finally:
        logging.info("脚本结束运行。")
