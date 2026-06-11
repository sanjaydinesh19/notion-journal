import os
from dotenv import load_dotenv

load_dotenv()


def get(key: str, default=None) -> str:
    return os.getenv(key, default)


def require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(
            f"Required env var '{key}' is not set. Copy .env.example to .env and fill in values."
        )
    return val
