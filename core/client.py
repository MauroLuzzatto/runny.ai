import hashlib
import os
import time
import streamlit as st
from garminconnect import Garmin

_COOLDOWN_SECS = 300  # 5 minutes between login attempts after a failure


@st.cache_resource
def _login(email: str, password: str) -> Garmin:
    email_hash = hashlib.md5(email.encode()).hexdigest()[:8]
    tokenstore = f"/tmp/garmin_tokens_{email_hash}"
    token_file = os.path.join(tokenstore, "oauth1_token.json")
    client = Garmin(email, password)
    if os.path.exists(token_file):
        client.login(tokenstore)
    else:
        client.login()
        os.makedirs(tokenstore, exist_ok=True)
        client.garth.dump(tokenstore)
    return client


def get_client(email: str | None = None, password: str | None = None) -> Garmin:
    email = email or st.secrets.get("GARMIN_EMAIL")
    password = password or st.secrets.get("GARMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError("Garmin credentials are missing.")

    cooldown_key = f"_garmin_retry_after_{hashlib.md5(email.encode()).hexdigest()[:8]}"
    retry_after = st.session_state.get(cooldown_key, 0)
    if time.time() < retry_after:
        remaining = int(retry_after - time.time())
        raise RuntimeError(
            f"Too many login attempts. Please wait {remaining}s before retrying."
        )

    try:
        return _login(email, password)
    except Exception:
        st.session_state[cooldown_key] = time.time() + _COOLDOWN_SECS
        raise
