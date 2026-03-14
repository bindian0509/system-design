# Stock Signal Platform — Indian Equity Market

An investment signal platform that auto-screens Indian mid/small cap stocks using fundamental filters, then applies technical, momentum, and valuation signals to deliver actionable BUY/ACCUMULATE/EXIT alerts via a web dashboard and Telegram notifications.

## Architecture

```
Data Sources (yfinance, NSE)
    ↓
Fundamental Screener (filters ~500 stocks → ~50-100)
    ↓
Signal Engine (Technical + Momentum + Valuation scoring)
    ↓
Composite Scorer (weighted 0-100 score → STRONG_BUY/BUY/HOLD/EXIT)
    ↓
Dashboard + Telegram/Email Alerts
```

## Quick Start

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your Telegram bot token, email settings, etc.

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the Vite dev server proxies API calls to the backend.

### Trigger Your First Scan

Once the backend is running, trigger a manual scan:

```bash
curl -X POST http://localhost:8000/api/scan/trigger
```

This will:
1. Fetch the stock list (Nifty 500 or seed list)
2. Download fundamentals from Yahoo Finance
3. Run the fundamental screener to filter the universe
4. Fetch 2 years of price history for filtered stocks
5. Compute technical, momentum, and valuation scores
6. Generate composite signals (STRONG_BUY / BUY / HOLD / EXIT)
7. Send Telegram/email alerts for actionable signals

## Screener Filters

| Filter | Default Threshold |
|--------|------------------|
| Market Cap | ₹1,000 - ₹50,000 Cr |
| ROE | > 15% |
| ROCE | > 15% |
| Debt/Equity | < 1.0 |
| Promoter Holding | > 40% |
| Promoter Pledge | < 10% |
| Revenue Growth (3Y) | > 10% |
| Profit Growth (3Y) | > 12% |

All thresholds are configurable in `backend/app/config.py`.

## Signal Scoring

Each stock gets a weighted composite score (0-100):

- **Fundamental Quality** (30%): ROE, ROCE, growth rates, balance sheet strength
- **Technical Analysis** (25%): RSI, MACD, Moving Average crossovers, Bollinger Bands, volume
- **Momentum** (20%): Relative strength, 52-week range, rate of change, trend
- **Valuation** (25%): PE vs historical median, PEG ratio, earnings yield, P/B ratio

### Signal Classification

| Signal | Score | Conditions |
|--------|-------|------------|
| STRONG BUY | > 80 | Fundamental pass + Technical > 50 |
| BUY | 60–80 | — |
| HOLD | 40–60 | — |
| EXIT | < 40 | — |

## Scheduled Scans

By default, the scanner runs daily at **6:30 PM IST** (after market close). Configure in `.env`:

```
SCAN_HOUR=18
SCAN_MINUTE=30
```

## Telegram Alerts

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Get your chat ID by messaging [@userinfobot](https://t.me/userinfobot)
3. Set in `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your-bot-token
   TELEGRAM_CHAT_ID=your-chat-id
   ```

Alerts are sent for STRONG_BUY and EXIT signals.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/dashboard` | GET | Summary counts |
| `/api/signals` | GET | Latest signals (filterable) |
| `/api/signals/{symbol}` | GET | Signal history for a stock |
| `/api/stocks` | GET | All stocks (universe_only filter) |
| `/api/stocks/{symbol}` | GET | Stock detail + fundamentals + signal |
| `/api/stocks/{symbol}/prices` | GET | Price history |
| `/api/screener` | GET | Screened universe with scores |
| `/api/fundamentals/{symbol}` | GET | Fundamental data |
| `/api/alerts` | GET | Alert history |
| `/api/watchlist` | GET | Watchlist items |
| `/api/watchlist/{symbol}` | POST | Add to watchlist |
| `/api/watchlist/{symbol}` | DELETE | Remove from watchlist |
| `/api/scan/trigger` | POST | Trigger manual scan |

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy, APScheduler
- **Data**: yfinance, NSE India scraper
- **Analysis**: pandas, numpy, ta (technical analysis)
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS, Recharts
- **Alerts**: python-telegram-bot, smtplib
- **Database**: SQLite (easily swappable to PostgreSQL)

## Disclaimer

This platform is for **educational and research purposes only**. It is not financial advice. Always consult a SEBI-registered investment advisor before making investment decisions.
