"""
AMEVA-Crawler Configuration
Zero-dependency configuration module using Python standard library.
"""
import os

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "crawler.db")

# Telegram Bot Defaults (Empty for security - configure via GUI/DB)
DEFAULT_TELEGRAM_BOT_TOKEN = ""
DEFAULT_TELEGRAM_CHAT_ID = ""
DEFAULT_TELEGRAM_ENABLED = False

# HTTP Crawler Defaults
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 AMEVA-Crawler/1.0"
DEFAULT_TIMEOUT_SEC = 20
DEFAULT_MAX_DIFF_LINES = 30
DEFAULT_MAX_NEW_LINKS = 20
