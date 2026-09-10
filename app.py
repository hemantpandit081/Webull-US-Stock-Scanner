import streamlit as st

from webull.core.client import ApiClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan


# ==============================
# PAGE
# ==============================

st.set_page_config(
    page_title="Webull US Stock Scanner",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Webull US Stock Scanner")

st.write("Testing Webull OpenAPI market-data connection.")


# ==============================
# GET WEBULL KEYS
# ==============================

try:
    APP_KEY = st.secrets["WEBULL_APP_KEY"]
    APP_SECRET = st.secrets["WEBULL_APP_SECRET"]

except Exception:
    st.error("❌ Webull API keys are missing.")
    st.stop()


# ==============================
# CONNECT TO WEBULL
# ==============================

try:

    api_client = ApiClient(
        APP_KEY,
        APP_SECRET,
        "us"
    )

    api_client.add_endpoint(
        "us",
        "api.webull.com"
    )

    data_client = DataClient(api_client)

    st.success("✅ Webull API connection created.")

except Exception as e:

    st.error("❌ Could not create Webull connection.")
    st.code(str(e))
    st.stop()


# ==============================
# MARKET DATA TEST
# ==============================

st.subheader("Market Data Test")

symbol = st.text_input(
    "Stock symbol",
    "AAPL"
).upper().strip()


if st.button("Test Webull Data"):

    try:

        result = data_client.market_data.get_history_bar(
            symbol,
            Category.US_STOCK.name,
            Timespan.M1.name
        )

        if result.status_code == 200:

            st.success("✅ Market data received!")

            st.json(result.json())

        else:

            st.error(
                f"Webull returned status code: {result.status_code}"
            )

            st.code(result.text)

    except Exception as e:

        st.error("❌ Market data request failed.")

        st.code(str(e))


# ==============================
# FOOTER
# ==============================

st.divider()

st.caption("Webull OpenAPI • US Stock Market Data")
