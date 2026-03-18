import hashlib
import streamlit as st
from garminconnect import Garmin


@st.cache_resource
def _login(email: str, password: str) -> Garmin:
    email_hash = hashlib.md5(email.encode()).hexdigest()[:8]
    tokenstore = f"/tmp/garmin_tokens_{email_hash}"
    client = Garmin(email, password)
    client.login(tokenstore)
    return client


def get_client(email: str | None = None, password: str | None = None) -> Garmin:
    email = email or st.secrets.get("GARMIN_EMAIL")
    password = password or st.secrets.get("GARMIN_PASSWORD")
    return _login(email, password)
