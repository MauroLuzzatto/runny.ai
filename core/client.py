import streamlit as st
from garminconnect import Garmin


def get_client(email: str | None = None, password: str | None = None) -> Garmin:
    """Create and authenticate a Garmin Connect client."""
    email = email or st.secrets.get("GARMIN_EMAIL")
    password = password or st.secrets.get("GARMIN_PASSWORD")
    client = Garmin(email, password)
    client.login()
    return client
