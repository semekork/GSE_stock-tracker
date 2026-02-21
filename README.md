# GSE Stock Tracker

A Python-based automated stock market screener and alert bot for the **Ghana Stock Exchange (GSE)**. This tracker monitors specific stocks, logs market data to a local database, and sends batch email alerts when your configured BUY or SELL target prices are hit.

The bot is designed to be easily configurable and is structured to be deployed natively on cloud platforms like **Koyeb**.

## Features

- **Live GSE Data Integration:** Fetches accurate, real-time pricing and volume data using the `afrimarket` library.
- **Automated Email Alerts:** Sends a batched, beautifully formatted summary email using Gmail's SMTP server when any target prices are hit.
- **Anti-Spam Throttling:** Features JSON state-management (`alert_state.json`) logic to ensure you only ever receive a maximum of one email alert _per calendar day_ for a specific stock target.
- **Market Hours Intelligence:** Built-in `pytz` and `datetime` logic pauses market scanning on weekends and outside of official GSE trading hours (09:30 - 15:00 UTC).
- **SQLite Database Logging:** Automatically records historical tracking data—like `current_price`, `volume`, and percentage `price_change`—into a `market_scans.db` SQLite database upon every market scan.
- **Cloud-Native Architecture:** Includes a lightweight Flask web server running on a background thread that exposes a `/healthz` endpoint to satisfy Koyeb’s strict health check requirements on web services.

## Prerequisites

- Python 3.9+
- A Google Account with **App Passwords** enabled (to send SMTP emails). [Learn how to create an App Password here](https://support.google.com/accounts/answer/185833?hl=en).

## Local Installation

1. **Clone the repository:**

   ```bash
   git clone <your-repo-url>
   cd "GSE_stock tracker"
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory (you can copy your `.env.example`) and add your deployment credentials:

   ```env
   SENDER_EMAIL="your_email@gmail.com"
   RECEIVER_EMAIL="destination_email@gmail.com"
   APP_PASSWORD="your_16_digit_app_password"
   ```

5. **Run the Tracker:**
   ```bash
   python gse_tracker.py
   ```

## Configuring Targets

To add, remove, or modify the stocks you want to track, edit the `TARGETS` dictionary located directly inside `gse_tracker.py`:

```python
# Trading Rules
TARGETS = {
    'CAL': {'action': 'SELL', 'target': 0.94, 'condition': '>=', 'name': 'CAL Bank Limited'},
    'MTNGH': {'action': 'BUY', 'target': 5.47, 'condition': '<=', 'name': 'Scancom PLC (MTN Ghana)'},
    'GCB': {'action': 'BUY', 'target': 31.00, 'condition': '<=', 'name': 'GCB Bank PLC'},
    # Add more tuples here...
}
```

## Deployment (Koyeb)

This repository is pre-configured to deploy directly onto Koyeb's free tier.

1. Push your code to a GitHub repository.
2. Sign in to [Koyeb](https://app.koyeb.com/) and click **Create Web Service**.
3. Select **GitHub** and choose your repository.
4. **Environment Variables:** In the Koyeb deployment settings, define the following variables securely:
   - `SENDER_EMAIL`
   - `RECEIVER_EMAIL`
   - `APP_PASSWORD`
5. **Port:** Expose port `8080`.
6. Koyeb will automatically detect the custom `Procfile` (`web: python gse_tracker.py`) and bind the Flask health-check server while the stock loop runs securely in a background thread!
