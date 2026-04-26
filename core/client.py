import os
import shutil
import time

import streamlit as st
from garminconnect import Garmin, GarminConnectConnectionError

_TOKENSTORE = "/tmp/garmin_tokens"
_MAX_RETRIES = 5


@st.cache_resource
def get_client(email: str, password: str) -> Garmin:
    client = Garmin(email, password)
    use_tokens = os.path.exists(os.path.join(_TOKENSTORE, "oauth1_token.json"))

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            if use_tokens:
                client.login(_TOKENSTORE)
            else:
                client.login()
                os.makedirs(_TOKENSTORE, exist_ok=True)
                client.garth.dump(_TOKENSTORE)
            break
        except GarminConnectConnectionError as e:
            if use_tokens:
                shutil.rmtree(_TOKENSTORE, ignore_errors=True)
                use_tokens = False
            if "429" in str(e) and attempt < _MAX_RETRIES:
                time.sleep(5 * 2**attempt)
            else:
                raise

    return client
