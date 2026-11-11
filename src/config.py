import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
MCP_SECRET = os.environ.get("MCP_SECRET", "")
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
PORT = int(os.environ.get("PORT", "8080"))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36")
TIMEOUT = 25.0
HOEFLICH_S = 1.5  # Pause zwischen Requests derselben Domain
