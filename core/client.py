import os

from dotenv import load_dotenv
from garminconnect import Garmin


def get_client(email: str | None = None, password: str | None = None) -> Garmin:
    """Create and authenticate a Garmin Connect client."""
    load_dotenv()
    email = email or os.getenv("GARMIN_EMAIL")
    password = password or os.getenv("GARMIN_PASSWORD")
    client = Garmin(email, password)
    client.login()
    return client
