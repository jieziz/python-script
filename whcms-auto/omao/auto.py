import logging
import time
import random
from DrissionPage import Chromium, ChromiumOptions 
from dotenv import load_dotenv
import os
from TimePinner import Pinner





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
    return {
        'BASE_URL': base_url,
        'PRODUCT_URL': os.getenv("PRODUCT_URL"),
        'LOGIN_URL': os.getenv("LOGIN_URL"),
        'EMAIL': os.getenv("EMAIL"),
        'PASSWORD': os.getenv("PASSWORD"),
        'PROMO_CODE': os.getenv("PROMO_CODE", ""),
        'HEADLESS_MODE': os.getenv("HEADLESS_MODE", "False").lower() == "true",
        'DELAY_TIME': int(os.getenv("DELAY_TIME", "5"))
    }

def check_stock(page):
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


def perform_purchase(page, config):
    """执行下单流程"""
    try:
        pinner = Pinner()
        pinner.pin('执行下单开始')

        page('#inputHostname').input(f"{random.randint(100000,999999)}.com")
        page('#inputRootpw').input('EgI1Z7Ko4~I;')
        page('#inputNs1prefix').input('ns1')
        page('#inputNs2prefix').input('ns2')
        # 点击完成配置按钮
        complete_btn = page('#btnCompleteProductConfig')
        page.run_js('arguments[0].click();', complete_btn)
        page.wait.load_start()
        pinner.pin('加入购物车用时')

        checkout_btn = page('#checkout')
        page.run_js('arguments[0].click();', checkout_btn)
        page.wait.load_start()
        pinner.pin('进入结算页面用时')

        time.sleep(random.uniform(1, 3))  # 随机等待
        submit_btn = page('#btnCompleteOrder')
        page.scroll.to_see(submit_btn)
        time.sleep(random.uniform(0.5, 1.5))

        page.run_js('arguments[0].click();', submit_btn)

        # 如果直接点击失败，尝试其他方式
        if "captcha" in page.url.lower() or page.s_ele('text:Complete the captcha'):
            # 方案2：尝试使用不同的点击方式
            page.run_js('''
                document.querySelector("#btnCompleteOrder").dispatchEvent(
                    new MouseEvent("click", {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    })
                );
            ''')

        page.wait.load_start()
        time.sleep(10)
        pinner.pin('订单提交用时')
        return True
        
    except Exception as e:
        logging.error(f"下单过程中发生错误: {e}")
        return False

def check_and_handle_login(page, config):
    try:
        page.get(config['LOGIN_URL'])
       

        print(config['EMAIL'])
        print(config['PASSWORD'])
        page('#inputEmail').input(config['EMAIL'])
        page('#inputPassword').input(config['PASSWORD'])

        time.sleep(5)
        # 使用 JavaScript 点击登录按钮
        login_btn = page('#login')
        page.run_js('arguments[0].click();', login_btn)
        page.wait.load_start()
        time.sleep(5)
        
        
        return True
    except Exception as e:
        logging.error(f"登录检查过程发生错误: {e}") 
    return False      


def monitor_stock():
    config = load_config()
    co = ChromiumOptions().auto_port()
    if config['HEADLESS_MODE']:
        co.headless()
    
    co.set_load_mode('none')
    co.set_pref('credentials_enable_service', False)
    co.set_argument('--hide-crash-restore-bubble')
    
    browser = Chromium(co)
    page = browser.latest_tab
    pinner = Pinner()
    pinner.pin('脚本计时开始')

    # 检查登录状态并处理
    if not check_and_handle_login(page, config):
        return
    
    if config.get('PROMO_CODE'):
        page.get(config['BASE_URL']+"/cart.php?a=view")

        if page.s_ele('#inputPromotionCode'):
            page('#inputPromotionCode').input(config['PROMO_CODE'])
            page('@name=validatepromo').click()
            page.wait.load_start()
            page.wait.ele_displayed('@name=validatepromo', timeout=10)
            pinner.pin('使用优惠码用时')

    while True:
        try:
            config = load_config()     
            page.get(config['PRODUCT_URL'])     
            if check_stock(page):
                if perform_purchase(page, config):
                    logging.info(f"下单成功！程序即将退出...")
                    return  
                else:
                    logging.error("下单失败，继续监控...")
                    
            time.sleep(config['DELAY_TIME'])
            
        except Exception as e:
            logging.error(f"监控过程发生错误: {e}")
            time.sleep(config['DELAY_TIME'])
            continue



if __name__ == "__main__":
    logging.info("脚本启动。")
    try:
        monitor_stock()
    except Exception as e:
        logging.critical(f"脚本运行过程中发生严重错误: {e}")
    finally:
        logging.info("脚本结束运行。")