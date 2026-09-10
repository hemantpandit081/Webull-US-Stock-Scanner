import streamlit as st
from webull.core.client import ApiClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan

# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="Webull US Stock Scanner",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Webull US Stock Scanner")

st.write("Testing Webull OpenAPI market-data connection.")

# =========================================================
# WEBULL SETTINGS
# =========================================================

try:
    APP_KEY = st.secrets["WEBULL_APP_KEY"]
    APP_SECRET = st.secrets["WEBULL_APP_SECRET"]

except Exception:
    st.error("Webull API keys have not been added yet.")
    st.info(
        "Next we will add your Webull App Key and App Secret "
        "securely through Streamlit Secrets."
    )
    st.stop()

# =========================================================
# CONNECT TO WEBULL
# =========================================================

try:

    api_client = ApiClient(
        APP_KEY,
        APP_SECRET,
        "au"
    )

    # Webull Australia API endpoint
    api_client.add_endpoint(
        "au",
        "https://openapi.webull.com.au"
    )

    data_client = DataClient(api_client)

    st.success("✅ Webull API connection created.")

except Exception as e:

    st.error("❌ Could not create Webull connection.")
    st.code(str(e))
    st.stop()

# =========================================================
# TEST MARKET DATA
# =========================================================

st.subheader("Market Data Test")

symbol = st.text_input(
    "Enter stock symbol",
    value="AAPL"
).upper().strip()

if st.button("Test Webull Data"):

    try:

        result = data_client.market_data.get_history_bar(
            symbol,
            Category.US_STOCK.name,
            Timespan.M1.name
        )

        st.write("Webull response:")

        if result.status_code == 200:

            st.success("✅ Market data received!")

            data = result.json()

            st.json(data)

        else:

            st.error(
                f"Webull returned status code: {result.status_code}"
            )

            st.write(result.text)

    except Exception as e:

        st.error("❌ Market data request failed.")
        st.code(str(e))

# =========================================================
# INFORMATION
# =========================================================

st.divider()

st.caption(
    "Webull OpenAPI • US Stocks • Market Data"
)
