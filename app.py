import streamlit as st

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

except Exception as e:
    st.error("❌ Connection error")
    st.code(str(e))
    st.stop()


st.subheader("Live Snapshot Test")

symbol = st.text_input(
    "Stock symbol",
    "AAPL"
).upper().strip()


if st.button("Get Snapshot"):

    try:

        result = data_client.market_data.get_snapshot(
            symbol
        )

        st.write("Status:", result.status_code)

        if result.status_code == 200:
            st.success("✅ Market data received!")
            st.json(result.json())
        else:
            st.error("❌ Webull returned an error")
            st.code(result.text)

    except Exception as e:
        st.error("❌ Snapshot request failed")
        st.code(str(e))
