import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_SHEETS_URL = os.getenv("GOOGLE_SHEETS_URL")
GOOGLE_CREDS_PATH = os.getenv("GOOGLE_CREDS_PATH", "service_account.json")
