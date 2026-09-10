import streamlit as st
import inspect

from webull.core.client import ApiClient
from webull.data.data_client import DataClient


st.set_page_config(
    page_title="Webull API Test",
    page_icon="📈"
)

st.title("📈 Webull API Test")

APP_KEY = st.secrets["WEBULL_APP_KEY"]
APP_SECRET = st.secrets["WEBULL_APP_SECRET"]


try:
    api_client = ApiClient(
        APP_KEY,
        APP_SECRET,
        "au"
    )

    api_client.add_endpoint(
        "au",
        "api.webull.com.au"
    )

    data_client = DataClient(api_client)

    st.success("✅ Webull API connection created")

    st.subheader("Installed SDK methods")

    methods = [
        name
        for name in dir(data_client.market_data)
        if not name.startswith("_")
    ]

    st.write(methods)

except Exception as e:
    st.error("❌ Error")
    st.code(str(e))
