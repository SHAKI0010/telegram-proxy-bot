import os
import threading
from flask import Flask
from telebot import TeleBot
import logging
import time
import requests
import random
import string
from typing import List, Dict, Optional
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ------------------------
# Telegram bot setup
# ------------------------

TOKEN = os.getenv("BOT_TOKEN", "8477116669:AAGmj-43ABL69_zxLLqetulr2T_rKxBii4A")
GROUP_LINK = os.getenv("GROUP_LINK", "https://t.me/GODSHAKI")

V2RAY_SOURCES = [
    "https://raw.githubusercontent.com/salehhamze/Sub/main/all",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/all_sub.txt",
]

PROXY_SOURCES: List[Dict[str, str]] = [
    {"url": "https://raw.githubusercontent.com/hookzof/socks5_list/master/tg/mtproto.json", "type": "json"},
    {"url": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/json/mtproto-proxies.json", "type": "json"},
    {"url": "https://raw.githubusercontent.com/ALIILAPRO/MTProtoProxy/main/mtproto.txt", "type": "text"},
    {"url": "https://raw.githubusercontent.com/MhdiTaheri/ProxyCollector/main/proxy.txt", "type": "text"},
]

MAX_MSG_LEN = 3800
V2RAY_SHOW_LIMIT = 10
PROXY_SHOW_LIMIT = 20
GRID_COLS = 10
REQUEST_TIMEOUT = 12
RETRY_TIMES = 12
CACHE_TTL = 120
PIPE = "│"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")
logger = logging.getLogger("proxybot")

bot = TeleBot(TOKEN, parse_mode="Markdown")
v2ray_cache = None
proxy_cache = None


# Utility functions
def escape_markdown(text: str) -> str:
    return ''.join('\\' + ch if ch in ['`', '*', '_'] else ch for ch in text)

def with_retry_get(url: str, timeout: int = REQUEST_TIMEOUT, retries: int = RETRY_TIMES):
    for attempt in range(retries):
        try:
            res = requests.get(url, timeout=timeout)
            if res.status_code == 200:
                return res
        except Exception as e:
            logger.warning(f"GET {url} attempt {attempt+1}/{retries} failed: {e}")
        time.sleep(0.8)
    return None

def dedupe_keep_order(items: List[str]) -> List[str]:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    btn_v2ray = f"📎 {PIPE} کانفینگ V2Ray •"
    btn_proxy = f"🛜 {PIPE} پروکسی تلگرام •"
    btn_group = f"👨‍💻 {PIPE} چنل سازنده •"
    kb.add(
        InlineKeyboardButton(btn_v2ray, callback_data="v2ray"),
        InlineKeyboardButton(btn_proxy, callback_data="proxy"),
    )
    kb.add(InlineKeyboardButton(btn_group, url=GROUP_LINK))
    return kb

def back_and_group_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"🔙 {PIPE} بازگشت •", callback_data="back"),
        InlineKeyboardButton(f"👥 {PIPE} گروه کاربردی •", url=GROUP_LINK),
    )
    return kb

# fetching and formatting proxies/v2ray configs (same logic)
def fetch_v2ray_configs_fresh() -> List[str]:
    configs = []
    for url in V2RAY_SOURCES:
        res = with_retry_get(url)
        if res:
            for line in res.text.splitlines():
                ln = line.strip()
                if ln.startswith(("vmess://", "vless://", "trojan://")):
                    configs.append(ln)
    return dedupe_keep_order(configs)

def get_v2ray_configs() -> List[str]:
    global v2ray_cache
    now = time.time()
    if v2ray_cache and (now - v2ray_cache[1] < CACHE_TTL):
        return v2ray_cache[0]
    fresh = fetch_v2ray_configs_fresh()
    v2ray_cache = (fresh, now)
    return fresh

def fetch_proxies_fresh() -> List[str]:
    links = []
    for src in PROXY_SOURCES:
        res = with_retry_get(src["url"])
        if res:
            try:
                if src["type"] == "json":
                    data = res.json()
                    for p in data if isinstance(data, list) else []:
                        srv = p.get("server") or p.get("ip")
                        prt = p.get("port")
                        sec = p.get("secret")
                        if srv and prt and sec:
                            links.append(f"tg://proxy?server={srv}&port={prt}&secret={sec}")
                else:
                    for line in res.text.splitlines():
                        if line.startswith("tg://proxy?"):
                            links.append(line)
            except Exception as e:
                logger.warning(f"Error parsing {src['url']}: {e}")
    return dedupe_keep_order(links)

def get_proxies() -> List[str]:
    global proxy_cache
    now = time.time()
    if proxy_cache and (now - proxy_cache[1] < CACHE_TTL):
        return proxy_cache[0]
    fresh = fetch_proxies_fresh()
    proxy_cache = (fresh, now)
    return fresh

def format_v2ray_list(configs: List[str]) -> str:
    body = "\n".join(f"`{i}. {escape_markdown(cfg)}`" for i, cfg in enumerate(configs[:V2RAY_SHOW_LIMIT], 1))
    return f"*لیست کانفینگ‌ها 🔻*\n\n{body}"

def format_proxy_grid_text(links: List[str]) -> str:
    rows = []
    row = []
    for i, link in enumerate(links[:PROXY_SHOW_LIMIT], 1):
        label = f"[Proxy{i}]({escape_markdown(link)})"
        row.append(label)
        if len(row) == GRID_COLS:
            rows.append("  ".join(row))
            row = []
    if row:
        rows.append("  ".join(row))
    return "*Proxy List 📗*\n\n" + "\n".join(rows)

# bot handlers
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "به ربات شاکی خوش آمدی 👇", reply_markup=main_menu_kb())

@bot.callback_query_handler(func=lambda c: True)
def handle_callback(call):
    if call.data == "v2ray":
        cfgs = get_v2ray_configs()
        bot.edit_message_text(format_v2ray_list(cfgs), call.message.chat.id, call.message.message_id, reply_markup=back_and_group_kb())
    elif call.data == "proxy":
        links = get_proxies()
        bot.edit_message_text(format_proxy_grid_text(links), call.message.chat.id, call.message.message_id, reply_markup=back_and_group_kb())
    elif call.data == "back":
        bot.edit_message_text("بازگشت به منو 👇", call.message.chat.id, call.message.message_id, reply_markup=main_menu_kb())

def run_bot():
    logger.info("Telegram bot polling started")
    bot.infinity_polling(skip_pending=True)

# ------------------------
# Flask web service (for Render)
# ------------------------

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot service is running and listening for Render port check.", 200

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask on port {port}")
    app.run(host="0.0.0.0", port=port)
