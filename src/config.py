import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_SHEETS_URL = os.getenv("GOOGLE_SHEETS_URL")
GOOGLE_CREDS_PATH = os.getenv("GOOGLE_CREDS_PATH", "service_account.json")

# Parse GOOGLE_SERVICE_TTL_MINUTES with error handling
try:
    GOOGLE_SERVICE_TTL_MINUTES = int(os.getenv("GOOGLE_SERVICE_TTL_MINUTES", "30"))
except ValueError:
    raise ValueError(
        "GOOGLE_SERVICE_TTL_MINUTES должна быть числом. "
        f"Текущее значение: {os.getenv('GOOGLE_SERVICE_TTL_MINUTES')}"
    )
