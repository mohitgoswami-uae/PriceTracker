"""
UAE Price Tracker
Checks Amazon.ae and Noon.com for a product's price and sends a Telegram
message whenever the price drops compared to the last recorded price.

Price history is stored in prices.json in the repo, and committed back
by the GitHub Actions workflow after each run.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# CONFIG: add/remove products here. Each product has a name plus one URL per
# platform you want checked.
# ---------------------------------------------------------------------------
PRODUCTS = [
    {
        "id": "koleston_6_4_flaming_copper",
        "name": "Koleston Supreme 6/4 Flaming Copper",
        "urls": {
            "amazon_ae": "https://www.amazon.ae/Wella-Koleston-Supreme-Flaming-Copper/dp/B07NVCJ2LW",
            "noon": "https://www.noon.com/uae-en/~wella/koleston-supreme-hair-color-6-4-flaming-copper/N13345795A/p/",
        },
    }
]

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "prices.json")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-AE,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Scrapers
# ---------------------------------------------------------------------------
def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def parse_price_text(text):
    """Extract a float from a price string like 'AED 39.00' or '39.00'."""
    if not text:
        return None
    match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def check_amazon_ae(url):
    """Returns (price, offer_text) for an amazon.ae product page."""
    soup = fetch(url)

    price = None
    price_whole = soup.select_one(".a-price .a-price-whole")
    if price_whole:
        price = parse_price_text(price_whole.get_text())
    if price is None:
        alt = soup.select_one("#priceblock_ourprice, #priceblock_dealprice")
        if alt:
            price = parse_price_text(alt.get_text())

    # Bank/card offer text often appears in a "Bank Offer" section
    offer_text = None
    offer_block = soup.find(string=re.compile("Bank Offer|Cashback|No Cost EMI", re.I))
    if offer_block:
        offer_text = offer_block.strip()

    return price, offer_text


def check_noon(url):
    """Returns (price, offer_text) for a noon.com product page."""
    soup = fetch(url)

    price = None
    price_el = soup.select_one('[data-qa="pdp-price"], .priceNow, .price')
    if price_el:
        price = parse_price_text(price_el.get_text())

    offer_text = None
    offer_block = soup.find(string=re.compile("cashback|instant discount|bank offer", re.I))
    if offer_block:
        offer_text = offer_block.strip()

    return price, offer_text


CHECKERS = {
    "amazon_ae": check_amazon_ae,
    "noon": check_noon,
}


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured, skipping notification. Message was:")
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
        timeout=20,
    )
    if not resp.ok:
        print(f"Telegram send failed: {resp.status_code} {resp.text}")


# ---------------------------------------------------------------------------
# History storage
# ---------------------------------------------------------------------------
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    history = load_history()
    now = datetime.now(timezone.utc).isoformat()
    any_alert = False

    for product in PRODUCTS:
        pid = product["id"]
        history.setdefault(pid, {})

        results = {}
        for platform, url in product["urls"].items():
            checker = CHECKERS.get(platform)
            if not checker:
                continue
            try:
                price, offer = checker(url)
            except Exception as e:
                print(f"[{pid}/{platform}] ERROR: {e}", file=sys.stderr)
                continue

            if price is None:
                print(f"[{pid}/{platform}] Could not find a price on the page.")
                continue

            results[platform] = {"price": price, "offer": offer, "url": url}

            prev = history[pid].get(platform, {}).get("price")
            history[pid].setdefault(platform, {})
            history[pid][platform]["price"] = price
            history[pid][platform]["offer"] = offer
            history[pid][platform]["last_checked"] = now

            if prev is not None and price < prev:
                any_alert = True
                drop = prev - price
                lines = [
                    f"\U0001F4C9 <b>Price drop:</b> {product['name']}",
                    f"Platform: {platform}",
                    f"New price: AED {price:.2f} (was AED {prev:.2f}, down AED {drop:.2f})",
                ]
                if offer:
                    lines.append(f"Offer on page: {offer}")
                lines.append(url)
                send_telegram("\n".join(lines))

        # Cross-platform lowest-price check
        if len(results) >= 2:
            lowest_platform = min(results, key=lambda p: results[p]["price"])
            lowest_price = results[lowest_platform]["price"]
            prev_lowest = history[pid].get("_lowest_platform")
            if prev_lowest != lowest_platform:
                any_alert = True
                lines = [
                    f"\U0001F3C6 <b>New lowest price:</b> {product['name']}",
                    f"{lowest_platform} is now cheapest at AED {lowest_price:.2f}",
                ]
                offer = results[lowest_platform].get("offer")
                if offer:
                    lines.append(f"Offer: {offer}")
                lines.append(results[lowest_platform]["url"])
                send_telegram("\n".join(lines))
            history[pid]["_lowest_platform"] = lowest_platform

    save_history(history)
    if not any_alert:
        print("No price drops this run.")


if __name__ == "__main__":
    main()
