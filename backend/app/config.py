from pathlib import Path
from dotenv import load_dotenv
import os


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    APP_TITLE: str = "artoliy backend"

    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))

    ADMIN_CODE: str = os.getenv("ADMIN_CODE", "")
    ADMIN_IDS_RAW: str = os.getenv("ADMIN_IDS", "")

    @property
    def admin_ids(self) -> set[int]:
        result = set()
        for item in self.ADMIN_IDS_RAW.split(","):
            item = item.strip()
            if not item:
                continue
            try:
                result.add(int(item))
            except ValueError:
                continue
        return result


settings = Settings()