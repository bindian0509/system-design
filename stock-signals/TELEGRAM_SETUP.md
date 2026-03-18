# Telegram Bot Setup Guide

## Prerequisites

- A Telegram account
- Your Stock Signal Platform backend running

## Step 1: Create a Bot via BotFather

1. Open Telegram and search for **@BotFather** (the official bot for creating bots).
2. Send the command:
   ```
   /newbot
   ```
3. When prompted for a **display name**, enter:
   ```
   Stock Signals Bot
   ```
4. When prompted for a **username**, enter something unique ending in `bot`:
   ```
   yourname_stock_signals_bot
   ```
5. BotFather responds with a message containing your **bot token**:
   ```
   Use this token to access the HTTP API:
   7123456789:AAHfiqkse_aGWQHpGeqAMFrK_4RVm-example
   ```
   Save this token — you'll need it in Step 3.

## Step 2: Get Your Chat ID

### Option A: Personal alerts (DM from bot to you)

1. Search for **@userinfobot** on Telegram.
2. Send it any message.
3. It replies with your account details. Copy the **Id** field (a number like `987654321`).

### Option B: Group alerts (bot posts to a group)

1. Create a new Telegram group (e.g. "Stock Alerts").
2. Add your bot to the group (search for its username from Step 1).
3. Send any message in the group.
4. Open this URL in a browser (replace `YOUR_BOT_TOKEN` with your actual token):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
5. In the JSON response, find `"chat":{"id":-100XXXXXXXXXX}`. That negative number is your group chat ID.

### Option C: Channel alerts (bot posts to a channel)

1. Create a Telegram channel.
2. Add your bot as an **administrator** of the channel (Settings → Administrators → Add Admin).
3. The chat ID is `@your_channel_username` or the numeric ID from the `getUpdates` API.

## Step 3: Configure the Platform

Navigate to the backend directory and create a `.env` file (or edit the existing one):

```bash
cd stock-signals/backend
cp .env.example .env
```

Edit `.env` and fill in your token and chat ID:

```env
TELEGRAM_BOT_TOKEN=7123456789:AAHfiqkse_aGWQHpGeqAMFrK_4RVm-example
TELEGRAM_CHAT_ID=987654321
```

For group chats, the chat ID will be negative:

```env
TELEGRAM_CHAT_ID=-1001234567890
```

## Step 4: Restart the Backend

The server reads `.env` on startup, so restart it to pick up the new values:

```bash
# Kill the existing server
kill $(lsof -ti:8000) 2>/dev/null

# Start fresh
cd stock-signals/backend
source venv/bin/activate
uvicorn app.main:app --port 8000
```

## Step 5: Test the Integration

### Quick test via API

```bash
curl -X POST http://localhost:8000/api/scan/trigger
```

If any stock generates a **STRONG_BUY** or **EXIT** signal, you'll receive a message on Telegram.

### What the alerts look like

**Buy signal:**
```
🚀 POLYCAB — STRONG BUY
Score: 82.5

Composite score: 82.5 (F:75 T:65 M:50 V:85)
STRONG_BUY: Score >80, fundamental pass, and technical >50.
```

**Exit signal:**
```
📉 RADICO — EXIT
Score: 32.3

Composite score: 32.3 (F:58 T:15 M:0 V:45)
EXIT: Score <40.
```

**Weekly summary (Sundays):**
```
📊 Weekly Portfolio Summary

• Total Universe: 12
• Strong Buys: 2
• Buys: 4
• Holds: 3
• Exits: 3
```

## Alert Rules

| Signal | Emoji | When It Fires |
|--------|-------|---------------|
| STRONG_BUY | 🚀 | Composite score > 80 with fundamental pass and technical > 50 |
| EXIT | 📉 | Composite score < 40 or technical breakdown |
| BUY / HOLD | — | No Telegram alert (visible on dashboard only) |

Alerts are sent:
- **Daily at 6:30 PM IST** during the scheduled scan
- **On demand** when you trigger a manual scan via the dashboard or API

## Troubleshooting

### "Telegram bot token or chat_id not configured"

The `.env` file is missing or the values are empty. Verify:

```bash
cat stock-signals/backend/.env | grep TELEGRAM
```

Both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` must be non-empty.

### Bot created but no messages arrive

1. **Start a conversation with your bot first.** Open Telegram, find your bot by username, and press "Start". Bots cannot message you until you initiate contact.
2. **Verify the chat ID is correct.** Visit:
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
   Look for your chat ID in the response.
3. **Check server logs** for errors:
   ```bash
   # If running in foreground, errors appear in terminal
   # If running in background:
   tail -50 stock-signals/backend/server.log
   ```

### "Forbidden: bot was blocked by the user"

You blocked the bot on Telegram. Unblock it: open the bot chat → Menu → Unblock.

### Rate limiting

Telegram allows ~30 messages per second. The platform sends alerts sequentially, so this is unlikely to be an issue unless you have 100+ stocks generating signals simultaneously.

## Security Notes

- **Never commit `.env` to git.** The `.gitignore` should exclude it. If unsure:
  ```bash
  echo ".env" >> stock-signals/backend/.gitignore
  ```
- **Bot tokens are secrets.** If your token is compromised, revoke it via BotFather:
  ```
  /revoke
  ```
  Then create a new token and update `.env`.
- **Anyone with your bot token can send messages as your bot.** Keep it private.
