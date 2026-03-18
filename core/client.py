import streamlit as st
from garminconnect import Garmin


@st.cache_resource
def _login(email: str, password: str) -> Garmin:
    client = Garmin(email, password)
    client.login()
    return client


def get_client(email: str | None = None, password: str | None = None) -> Garmin:
    email = email or st.secrets.get("GARMIN_EMAIL")
    password = password or st.secrets.get("GARMIN_PASSWORD")
    return _login(email, password)
