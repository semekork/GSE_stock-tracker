import os
import time
import json
import logging
import smtplib
import sqlite3
import threading
from datetime import datetime
from email.message import EmailMessage
import afrimarket
from dotenv import load_dotenv
import pytz
from flask import Flask

# Absolute Paths for PythonAnywhere
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, '.env')
LOG_PATH = os.path.join(BASE_DIR, 'tracker.log')
STATE_PATH = os.path.join(BASE_DIR, 'alert_state.json')
DB_PATH = os.path.join(BASE_DIR, 'market_scans.db')

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)

app = Flask(__name__)

@app.route('/healthz')
def healthz():
    return "OK", 200

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)

# Configuration
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
CHECK_INTERVAL_SECONDS = 60 * 60  # 60 minutes

# Trading Rules
TARGETS = {
    'CAL': {'action': 'SELL', 'target': 0.94, 'condition': '>=', 'name': 'CAL Bank Limited'},
    'MTNGH': {'action': 'BUY', 'target': 5.47, 'condition': '<=', 'name': 'Scancom PLC (MTN Ghana)'},
    'SOGEGH': {'action': 'BUY', 'target': 6.84, 'condition': '<=', 'name': 'Societe Generale Ghana PLC'},
    'GCB': {'action': 'BUY', 'target': 31.00, 'condition': '<=', 'name': 'GCB Bank PLC'},
    'EGH': {'action': 'BUY', 'target': 49.00, 'condition': '<=', 'name': 'Ecobank Ghana PLC'},
    'SCB': {'action': 'BUY', 'target': 28.50, 'condition': '<=', 'name': 'Standard Chartered Bank Ghana PLC'},
    'GOIL': {'action': 'BUY', 'target': 3.80, 'condition': '<=', 'name': 'GOIL PLC'},
    'TOTAL': {'action': 'BUY', 'target': 39.00, 'condition': '<=', 'name': 'TotalEnergies Marketing Ghana PLC'},
    'FML': {'action': 'BUY', 'target': 12.50, 'condition': '<=', 'name': 'Fan Milk PLC'},
    'BOPP': {'action': 'BUY', 'target': 65.00, 'condition': '<=', 'name': 'Benso Oil Palm Plantation'},
    'UNIL': {'action': 'BUY', 'target': 24.50, 'condition': '<=', 'name': 'Unilever Ghana PLC'}
}

# Initialize Exchange once
try:
    exchange = afrimarket.Exchange('GSE')
except Exception as e:
    logging.error(f"Failed to initialize Exchange: {e}")
    exchange = None

def is_market_open():
    """Check if current UTC time is within GSE market hours (Mon-Fri, 09:30 - 15:00 UTC)."""
    now = datetime.now(pytz.utc)
    weekday = now.weekday()
    
    # 0 is Monday, 4 is Friday
    if weekday > 4:
        return False
        
    current_time = now.time()
    start_time = datetime.strptime("09:30", "%H:%M").time()
    end_time = datetime.strptime("15:00", "%H:%M").time()
    
    return start_time <= current_time <= end_time

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                ticker TEXT,
                current_price REAL,
                volume TEXT,
                price_change TEXT
            )
        ''')
        conn.commit()
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def log_scans(scans):
    if not scans:
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.executemany('''
            INSERT INTO market_scans (timestamp, ticker, current_price, volume, price_change)
            VALUES (?, ?, ?, ?, ?)
        ''', scans)
        conn.commit()
    except Exception as e:
        logging.error(f"Failed to log scans to database: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading state: {e}")
        return {}

def save_state(state):
    try:
        with open(STATE_PATH, 'w') as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving state: {e}")

def can_send_alert(ticker):
    state = load_state()
    today_str = datetime.now(pytz.utc).strftime('%Y-%m-%d')
    last_alert = state.get(ticker, {}).get('last_alert_date')
    
    if last_alert == today_str:
        return False
    return True

def mark_alert_sent(ticker):
    state = load_state()
    today_str = datetime.now(pytz.utc).strftime('%Y-%m-%d')
    if ticker not in state:
        state[ticker] = {}
    state[ticker]['last_alert_date'] = today_str
    save_state(state)

def send_batched_email_alerts(alerts):
    if not alerts:
        return

    try:
        msg = EmailMessage()
        
        # Determine subject based on number of alerts
        if len(alerts) == 1:
            first = alerts[0]
            msg['Subject'] = f"🚨 GSE Trade Alert: {first['action']} {first['ticker']} at GHS {first['current_price']}"
        else:
            msg['Subject'] = f"🚨 GSE Trade Alerts: {len(alerts)} targets hit!"
            
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        
        content = "Trade Alerts Triggered!\n\n"
        for alert in alerts:
            content += (
                f"--- {alert['ticker']} ---\n"
                f"Action: {alert['action']}\n"
                f"Current Price: GHS {alert['current_price']}\n"
                f"Target Price: GHS {alert['target_price']}\n\n"
            )
        content += "Please review your portfolio.\n"
        
        msg.set_content(content)

        # Connect to Gmail SMTP server
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            smtp.send_message(msg)
            
        logging.info(f"Batched email alert sent for {len(alerts)} stocks!")
        
        # Mark all as sent only if email succeeds
        for alert in alerts:
            mark_alert_sent(alert['ticker'])
        
    except Exception as e:
        stock_list = ", ".join([a['ticker'] for a in alerts])
        logging.error(f"Failed to send batched email alert for {stock_list}: {e}")

def check_market():
    logging.info("--- Scanning Market ---")
    
    if not is_market_open():
        logging.info("Market is currently closed. Skipping scan.")
        return

    try:
        if not exchange:
            raise RuntimeError("Exchange not initialized.")
            
        df = exchange.get_listed_companies()
        df['Ticker'] = df['Ticker'].astype(str)
        
        batched_alerts = []
        scans_to_db = []
        now_str = datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        for ticker, rules in TARGETS.items():
            try:
                stock_row = df[df['Ticker'] == ticker]
                if stock_row.empty:
                    logging.warning(f"Could not find ticker {ticker} in market data.")
                    continue
                
                current_price_raw = stock_row.iloc[0]['Price']
                if isinstance(current_price_raw, str):
                    current_price = float(current_price_raw.replace(',', '').replace('GHS', '').strip())
                else:
                    current_price = float(current_price_raw)
                
                volume = str(stock_row.iloc[0].get('Volume', '0'))
                change = str(stock_row.iloc[0].get('Change', '0.0'))
                
                scans_to_db.append((now_str, ticker, current_price, volume, change))
                logging.info(f"{ticker}: GHS {current_price:.2f} (Target: {rules['action']} at {rules['condition']} {rules['target']})")
                
                condition_met = False
                if rules['action'] == 'SELL' and current_price >= rules['target']:
                    condition_met = True
                elif rules['action'] == 'BUY' and current_price <= rules['target']:
                    condition_met = True
                    
                if condition_met:
                    logging.info(f"ALERT: Target hit for {ticker}! Perform {rules['action']} at GHS {current_price}!")
                    if can_send_alert(ticker):
                        batched_alerts.append({
                            'ticker': ticker,
                            'current_price': current_price,
                            'action': rules['action'],
                            'target_price': rules['target']
                        })
                    else:
                        logging.info(f"Alert for {ticker} already sent today. Skipping.")
                    
            except Exception as e:
                logging.error(f"Error processing data for {ticker}: {e}")
                
        # Send batched email if there are any alerts
        if batched_alerts:
            send_batched_email_alerts(batched_alerts)
            
        # Log market scans to database
        if scans_to_db:
            log_scans(scans_to_db)
                
    except Exception as ex:
        logging.error(f"Market scan error: {ex}")

def run_tracker():
    logging.info("Starting GSE Stock Tracker loop...")
    logging.info(f"Monitoring: {', '.join(TARGETS.keys())}")
    
    # Run a quick test scan immediately
    try:
        check_market()
    except Exception as e:
        logging.critical(f"Critical error during initial scan: {e}", exc_info=True)
    
    # Continuous loop
    try:
        while True:
            logging.info(f"Sleeping for {CHECK_INTERVAL_SECONDS/60} minutes...")
            time.sleep(CHECK_INTERVAL_SECONDS)
            try:
                check_market()
            except Exception as e:
                logging.critical(f"Critical error in main loop: {e}", exc_info=True)
                # Sleep and continue so we don't crash and terminate
                
    except Exception as e:
        logging.info(f"Tracking stopped: {e}")

# Initialize once on module load
init_db()

if __name__ == "__main__":
    init_db()
    
    # Start the tracker in a background thread
    tracker_thread = threading.Thread(target=run_tracker, daemon=True)
    tracker_thread.start()

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)