#!/usr/bin/env python3
"""
cTrader Web Trade Copier

Monitors a "signal" tab for new positions and mirrors them to an "execution" tab.
Supports both Buy and Sell positions for any instrument.

Requirements:
- Python 3.8+
- Chrome browser
- ChromeDriver (auto-managed by webdriver-manager)

Configuration:
- Update the config variables below
- Ensure cTrader Web is accessible
"""

import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from typing import Optional, Dict, List
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('ctrader_config.env')

# Configuration with environment variable fallbacks
CONFIG = {
    "ctrader_url": os.getenv("CTRADER_URL", "https://webtrader.ctrader.com"),
    "login_email": os.getenv("LOGIN_EMAIL", ""),
    "login_password": os.getenv("LOGIN_PASSWORD", ""),
    "polling_interval": int(os.getenv("POLLING_INTERVAL", "60")),
    "max_wait_time": int(os.getenv("MAX_WAIT_TIME", "120")),
    "headless": os.getenv("HEADLESS", "false").lower() == "true",
    "trigger_keyword": os.getenv("TRIGGER_KEYWORD", "NEW_TRADE"),
    "default_lot_size": float(os.getenv("DEFAULT_LOT_SIZE", "0.01")),
    "signal_tab_selector": os.getenv("SIGNAL_TAB_SELECTOR", "#signal-tab"),
    "execution_tab_selector": os.getenv("EXECUTION_TAB_SELECTOR", "#execution-tab"),
    "position_table_selector": os.getenv("POSITION_TABLE_SELECTOR", ".positions-table"),
    "order_button_selector": os.getenv("ORDER_BUTTON_SELECTOR", ".place-order-btn"),
}

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ctrader_copier.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CTraderCopier:
    """cTrader Web Trade Copier"""

    def __init__(self, config: Dict):
        self.config = config
        self.driver = None
        self.signal_window = None
        self.execution_window = None
        self.processed_trades = set()  # Track processed trades to avoid duplicates

    def setup_driver(self):
        """Set up Chrome WebDriver"""
        try:
            chrome_options = Options()
            if self.config["headless"]:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("Chrome WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def login_to_ctrader(self):
        """Login to cTrader Web"""
        try:
            self.driver.get(self.config["ctrader_url"])
            wait = WebDriverWait(self.driver, self.config["max_wait_time"])

            # Wait for login form and enter credentials
            email_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']")))
            email_field.send_keys(self.config["login_email"])

            password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_field.send_keys(self.config["login_password"])

            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()

            # Wait for login to complete
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".trading-interface")))
            logger.info("Successfully logged into cTrader Web")

        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise

    def setup_tabs(self):
        """Set up signal and execution tabs"""
        try:
            # Open signal tab
            self.driver.execute_script("window.open('');")
            self.signal_window = self.driver.window_handles[1]
            self.driver.switch_to.window(self.signal_window)
            self.driver.get(self.config["ctrader_url"] + "/signals")  # Adjust URL as needed

            # Open execution tab
            self.driver.execute_script("window.open('');")
            self.execution_window = self.driver.window_handles[2]
            self.driver.switch_to.window(self.execution_window)
            self.driver.get(self.config["ctrader_url"] + "/trading")  # Adjust URL as needed

            logger.info("Signal and execution tabs set up successfully")

        except Exception as e:
            logger.error(f"Failed to set up tabs: {e}")
            raise

    def monitor_signals(self) -> List[Dict]:
        """Monitor signal tab for new positions"""
        try:
            self.driver.switch_to.window(self.signal_window)
            wait = WebDriverWait(self.driver, 10)

            # Look for positions table
            positions_table = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, self.config["position_table_selector"])
            ))

            # Find rows with the trigger keyword
            new_trades = []
            rows = positions_table.find_elements(By.TAG_NAME, "tr")

            for row in rows:
                try:
                    row_text = row.text
                    if self.config["trigger_keyword"] in row_text:
                        trade_info = self._parse_trade_info(row)
                        if trade_info and trade_info["id"] not in self.processed_trades:
                            new_trades.append(trade_info)
                            self.processed_trades.add(trade_info["id"])
                except Exception as e:
                    logger.warning(f"Error parsing row: {e}")
                    continue

            return new_trades

        except Exception as e:
            logger.error(f"Error monitoring signals: {e}")
            return []

    def _parse_trade_info(self, row_element) -> Optional[Dict]:
        """Parse trade information from table row"""
        try:
            cells = row_element.find_elements(By.TAG_NAME, "td")
            if len(cells) < 4:
                return None

            # Extract trade details (adjust indices based on actual table structure)
            symbol = cells[0].text.strip()
            direction = cells[1].text.strip()  # BUY or SELL
            lot_size = float(cells[2].text.strip() or self.config["default_lot_size"])
            trade_id = f"{symbol}_{direction}_{int(time.time())}"  # Unique ID

            return {
                "id": trade_id,
                "symbol": symbol,
                "direction": direction,
                "lot_size": lot_size,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Error parsing trade info: {e}")
            return None

    def execute_trade(self, trade_info: Dict) -> bool:
        """Execute trade in execution tab"""
        try:
            self.driver.switch_to.window(self.execution_window)
            wait = WebDriverWait(self.driver, self.config["max_wait_time"])

            # Select symbol
            symbol_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".symbol-input")))
            symbol_input.clear()
            symbol_input.send_keys(trade_info["symbol"])

            # Select direction
            if trade_info["direction"].upper() == "BUY":
                buy_button = self.driver.find_element(By.CSS_SELECTOR, ".buy-button")
                buy_button.click()
            else:
                sell_button = self.driver.find_element(By.CSS_SELECTOR, ".sell-button")
                sell_button.click()

            # Set lot size
            lot_input = self.driver.find_element(By.CSS_SELECTOR, ".lot-size-input")
            lot_input.clear()
            lot_input.send_keys(str(trade_info["lot_size"]))

            # Place order
            order_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, self.config["order_button_selector"])))
            order_button.click()

            # Wait for confirmation
            time.sleep(2)  # Adjust based on cTrader's response time

            logger.info(f"Successfully executed {trade_info['direction']} order for {trade_info['symbol']} ({trade_info['lot_size']} lots)")
            return True

        except Exception as e:
            logger.error(f"Failed to execute trade: {e}")
            return False

    def run(self):
        """Main copier loop"""
        try:
            logger.info("Starting cTrader Trade Copier")
            self.setup_driver()
            self.login_to_ctrader()
            self.setup_tabs()

            logger.info(f"Starting monitoring loop with {self.config['polling_interval']}s interval")

            while True:
                try:
                    new_trades = self.monitor_signals()

                    if new_trades:
                        logger.info(f"Found {len(new_trades)} new trades")
                        for trade in new_trades:
                            success = self.execute_trade(trade)
                            if success:
                                logger.info(f"Trade executed: {trade}")
                            else:
                                logger.error(f"Failed to execute trade: {trade}")
                    else:
                        logger.debug("No new trades found")

                    time.sleep(self.config["polling_interval"])

                except KeyboardInterrupt:
                    logger.info("Received interrupt signal, shutting down...")
                    break
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    time.sleep(30)  # Wait before retrying

        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("WebDriver closed")

def main():
    """Main entry point"""
    copier = CTraderCopier(CONFIG)
    copier.run()

if __name__ == "__main__":
    main()