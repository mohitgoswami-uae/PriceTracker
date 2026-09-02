# UAE Price Tracker

Checks Amazon.ae and Noon for a product every 4 hours and sends a Telegram
message on any price drop, plus an alert when the cheapest platform changes.

## One-time setup

### 1. Create a Telegram bot
1. Open Telegram, search for **@BotFather**, start a chat.
2. Send `/newbot`, follow the prompts (choose a name and username).
3. BotFather gives you a token like `123456789:AAExampleTokenHere`. Save it.

### 2. Get your chat ID
1. Send any message (e.g. "hi") to your new bot.
2. In a browser, visit:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   (replace `<YOUR_TOKEN>` with your token)
3. Look for `"chat":{"id":123456789,...}` in the response — that number is
   your chat ID.

### 3. Create the GitHub repo
1. Go to github.com → New repository (can be private).
2. Upload all files in this folder, preserving the `.github/workflows/`
   folder structure.

### 4. Add your secrets
In the repo: **Settings → Secrets and variables → Actions → New repository
secret**. Add two secrets:
- `TELEGRAM_BOT_TOKEN` = your bot token
- `TELEGRAM_CHAT_ID` = your chat ID

### 5. Test it
Go to the **Actions** tab → "Check UAE prices" → **Run workflow** (this
uses the `workflow_dispatch` trigger). Check the run logs, and check
Telegram — on the very first run there's no "previous price" yet, so you
won't get a drop alert, but you will get a "new lowest price" alert once
both platforms return a price.

After that, it runs automatically every 4 hours.

## Adding more products or platforms
Edit the `PRODUCTS` list at the top of `check_prices.py`. Each entry needs
a unique `id`, a `name`, and a `urls` dict with `amazon_ae` and/or `noon`
keys.

## Notes and limitations
- Amazon and Noon occasionally change their page structure, which can
  break the price-selector CSS and require a small update to
  `check_prices.py`.
- Amazon/Noon may show CAPTCHAs to automated traffic from cloud IP
  ranges (like GitHub Actions runners) more often than from a home
  connection. If you start seeing "could not find a price" in the logs
  consistently, that's the likely cause — let me know and I can add
  retry logic or a scraping proxy.
- The "offer" text capture is best-effort: it looks for phrases like
  "Bank Offer" or "Cashback" on the page and reports them as-is. It does
  not yet compute the exact net price per your specific card — that's a
  good next step once we confirm the base scraping is reliable.
