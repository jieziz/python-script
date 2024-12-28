import logging
import time
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
    import platform
    
    # 获取当前脚本所在目录的绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 根据操作系统选择不同的配置文件
    if platform.system() == 'Windows':
        env_file = 'env.windows'
    else:  # Linux 或其他系统
        env_file = 'env.linux'
    
    # 构建配置文件的完整路径
    env_path = os.path.join(current_dir, env_file)
    
    logging.info(f"当前操作系统: {platform.system()}")
    logging.info(f"尝试加载配置文件: {env_path}")
    
    # 尝试加载配置文件
    if os.path.exists(env_path):
        logging.info(f"找到配置文件: {env_path}")
        load_dotenv(env_path, override=True)
    else:
        # 尝试加载默认的 .env 文件
        default_env = os.path.join(current_dir, '.env')
        logging.warning(f"未找到系统特定配置文件 {env_path}，尝试加载默认配置: {default_env}")
        if os.path.exists(default_env):
            load_dotenv(default_env, override=True)
        else:
            logging.error("未找到任何配置文件！")
            raise FileNotFoundError(f"配置文件不存在: {env_path} 或 {default_env}")

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
        has_quehuo = page.s_ele('text:缺货')
        pinner.pin('检查库存结束')
        page.stop_loading()
        return not bool(has_quehuo)
    except Exception as e:
        logging.warning(f"检查库存时发生错误: {e}")
        return False

def perform_purchase(page):
    """执行下单流程"""
    try:
        pinner = Pinner()
        pinner.pin('执行下单开始')
        # 点击完成配置按钮
        page('#btnCompleteProductConfig').click()
        page.wait.load_start()
        pinner.pin('加入购物车用时')

        page('#checkout').click()
        page.wait.load_start()
        pinner.pin('进入结算页面用时')

        page('#btnCompleteOrder').click()
        page.wait.load_start()
        time.sleep(30)
        pinner.pin('订单提交用时')
        logging.info("订单提交成功")
        return True
        
    except Exception as e:
        logging.error(f"下单过程中发生错误: {e}")
        return False

def check_and_handle_login(page, config):
    try:
        page.get(config['LOGIN_URL'])
        time.sleep(10)
        print(page.html)
        if page.s_ele('text:欢迎回来'):
            page.stop_loading()
            return True
        else:
            page('#inputEmail').input(config['EMAIL'])
            page('#inputPassword').input(config['PASSWORD'])
            page('#login').click()
            page.wait.ele_displayed('text:欢迎回来', timeout=10)
            return True
    except Exception as e:
        logging.error(f"登录检查过程发生错误: {e}") 
    return False      

def agree_terms(page):
    try:
        # 点击复选框
        page.ele('#agreeterms').click()
        
        # 尝试多种选择器方式找到按钮
        button = (
            page.ele('.btn-success') or  # 通过类名查找
            page.ele('@onclick=agreeContinueOrder') or  # 通过onclick属性查找
            page.ele('@value=我同意条款,继续购买')  # 通过value属性查找
        )
        
        if not button:
            logging.error("找不到同意按钮")
            return False
            
        button.click()
        time.sleep(10)
        page.wait.load_start()
        
        logging.info("已同意使用条款")
        return True
        
    except Exception as e:
        logging.error(f"同意条款时发生错误: {e}")
        return False

def monitor_stock():
    config = load_config()
    co = ChromiumOptions().auto_port()
    if config['HEADLESS_MODE']:
        co.headless()
    co.set_load_mode('none')
    co.set_pref('credentials_enable_service', False)
    co.set_argument('--hide-crash-restore-bubble')
    co.set_argument('--no-sandbox') 
    browser = Chromium(co)
    page = browser.latest_tab
    pinner = Pinner()
    pinner.pin('脚本计时开始')

    # 检查登录状态并处理
    if not check_and_handle_login(page, config):
        return
    
    page.get(config['PRODUCT_URL'])  
    time.sleep(2) 
  
    if not agree_terms(page):
        logging.error("同意条款失败")
        return
    
    if config.get('PROMO_CODE'):
        page.get(config['BASE_URL']+"/cart.php?a=view")

        if page.s_ele('#inputPromotionCode'):
            page('#inputPromotionCode').input(config['PROMO_CODE'])
            page('@name=validatepromo').click()
            page.wait.load_start()
            page.wait.ele_displayed('@name=validatepromo', timeout=10)
            pinner.pin('使用优惠码用时')

    success_count = 0
    while True:
        try:
            config = load_config()     
            page.get(config['PRODUCT_URL'])     
            if check_stock(page):
                if perform_purchase(page):
                    success_count += 1
                    logging.info(f"第 {success_count} 次下单成功！继续监控新的库存...")
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