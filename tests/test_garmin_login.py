"""Test script for Garmin Connect login."""

import os
import sys
import time

from dotenv import load_dotenv
from garminconnect import Garmin, GarminConnectConnectionError

load_dotenv()

TOKENSTORE = "/tmp/garmin_tokens"
MAX_RETRIES = 5


def test_login():
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    if not email or not password:
        print("ERROR: GARMIN_EMAIL and GARMIN_PASSWORD must be set in .env")
        sys.exit(1)

    print(f"Logging in as {email}...")

    client = Garmin(email, password)

    token_path = os.path.join(TOKENSTORE, "oauth1_token.json")
    use_tokens = os.path.exists(token_path)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if use_tokens:
                print("Found cached tokens, using token login...")
                client.login(TOKENSTORE)
            else:
                print("No cached tokens, performing full login...")
                client.login()
                os.makedirs(TOKENSTORE, exist_ok=True)
                client.garth.dump(TOKENSTORE)
                print(f"Tokens saved to {TOKENSTORE}")
            break
        except GarminConnectConnectionError as e:
            if use_tokens:
                print("Token login failed, clearing stale tokens...")
                import shutil

                shutil.rmtree(TOKENSTORE, ignore_errors=True)
                use_tokens = False
            if "429" in str(e) and attempt < MAX_RETRIES:
                wait = 10 * 2**attempt
                print(
                    f"Rate limited (429). Retrying in {wait}s... (attempt {attempt}/{MAX_RETRIES})"
                )
                time.sleep(wait)
            else:
                raise

    display_name = client.get_full_name()
    print(f"Login successful! Display name: {display_name}")


if __name__ == "__main__":
    test_login()
