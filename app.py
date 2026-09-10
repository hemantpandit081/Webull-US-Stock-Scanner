import streamlit as st
import pandas as pd
import time

from webull.core.client import ApiClient
from webull.data.data_client import DataClient


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="US Momentum Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .block-container {
        padding-top: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    .stock-row {
        padding: 8px 10px;
        border-bottom: 1px solid #333;
        font-size: 16px;
    }

    .repeat-box {
        color: white;
        font-weight: bold;
        margin-left: 7px;
    }

    .metric-box {
        padding: 8px;
        border-radius: 6px;
        background: #111;
        border: 1px solid #333;
    }
</style>
""", unsafe_allow_html=True)


# =========================================================
# WEBULL CONNECTION
# =========================================================

try:
    APP_KEY = st.secrets["WEBULL_APP_KEY"]
    APP_SECRET = st.secrets["WEBULL_APP_SECRET"]
except Exception:
    st.error("❌ Webull API keys are missing.")
    st.stop()


@st.cache_resource
def create_webull():

    api_client = ApiClient(
        APP_KEY,
        APP_SECRET,
        "au"
    )

    api_client.add_endpoint(
        "au",
        "api.webull.com.au"
    )

    return DataClient(api_client)


try:
    data_client = create_webull()
except Exception as e:
    st.error("❌ Webull connection failed")
    st.code(str(e))
    st.stop()


# =========================================================
# SESSION STATE
# =========================================================

if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = "AAPL"

if "seen_stocks" not in st.session_state:
    st.session_state.seen_stocks = set()

if "repeat_stocks" not in st.session_state:
    st.session_state.repeat_stocks = set()

if "last_scan" not in st.session_state:
    st.session_state.last_scan = []

if "scan_count" not in st.session_state:
    st.session_state.scan_count = 0


# =========================================================
# HEADER
# =========================================================

top1, top2, top3 = st.columns([5, 1, 1])

with top1:
    st.title("📈 US Momentum Scanner")

with top2:
    if st.button("🔄 Scan", use_container_width=True):
        st.session_state.scan_now = True

with top3:
    st.caption("Webull Live")


# =========================================================
# FILTERS
# =========================================================

with st.expander("⚙️ Filters", expanded=False):

    min_price = st.number_input(
        "Minimum Price",
        min_value=0.10,
        value=1.00,
        step=0.50
    )

    max_price = st.number_input(
        "Maximum Price",
        min_value=1.00,
        value=1000.00,
        step=10.00
    )

    min_change = st.number_input(
        "Minimum % Change",
        value=2.0,
        step=0.5
    )

    min_volume = st.number_input(
        "Minimum Volume",
        value=100000,
        step=100000
    )

    max_stocks = st.slider(
        "Stocks to display",
        10,
        50,
        25
    )


# =========================================================
# GET SNAPSHOT
# =========================================================

def get_snapshot(symbol):

    try:

        result = data_client.market_data.get_snapshot(
            symbol,
            "US_STOCK"
        )

        if result.status_code != 200:
            return None

        data = result.json()

        if isinstance(data, list):

            if len(data) == 0:
                return None

            data = data[0]

        return data

    except Exception:
        return None


# =========================================================
# GET CANDIDATES
# =========================================================

def get_candidates():

    """
    First prototype uses a liquid US-stock universe.

    We will replace this with the full Webull screener/universe
    once the scanner interface is confirmed.
    """

    symbols = [
        "AAPL", "NVDA", "TSLA", "AMD", "AMZN",
        "META", "MSFT", "GOOGL", "GOOG", "NFLX",
        "PLTR", "SOFI", "MARA", "RIOT", "COIN",
        "HOOD", "RIVN", "LCID", "NIO", "SMCI",
        "MU", "AVGO", "ARM", "INTC", "QCOM",
        "TQQQ", "SPY", "QQQ", "IWM", "UBER",
        "SHOP", "SNOW", "CRWD", "PANW", "ORCL",
        "BA", "JPM", "BAC", "XOM", "CVX",
        "DIS", "PYPL", "SQ", "DKNG", "SOXL"
    ]

    return symbols


# =========================================================
# SCAN
# =========================================================

def run_scan():

    candidates = get_candidates()

    results = []

    progress = st.progress(0)

    total = len(candidates)

    for i, symbol in enumerate(candidates):

        data = get_snapshot(symbol)

        if data:

            try:

                price = float(data.get("price", 0))
                change_ratio = float(
                    data.get("change_ratio", 0)
                )
                volume = int(
                    float(data.get("volume", 0))
                )

                change_percent = change_ratio * 100

                if price < min_price:
                    continue

                if price > max_price:
                    continue

                if change_percent < min_change:
                    continue

                if volume < min_volume:
                    continue

                # -----------------------------------------
                # REPEAT STOCK
                # -----------------------------------------

                if symbol in st.session_state.seen_stocks:

                    st.session_state.repeat_stocks.add(symbol)

                else:

                    st.session_state.seen_stocks.add(symbol)

                repeated = (
                    symbol in st.session_state.repeat_stocks
                )

                results.append({
                    "symbol": symbol,
                    "price": price,
                    "change": change_percent,
                    "volume": volume,
                    "repeat": repeated
                })

            except Exception:
                pass

        progress.progress(
            int((i + 1) / total * 100)
        )

    progress.empty()

    # Sort by percentage change
    results = sorted(
        results,
        key=lambda x: x["change"],
        reverse=True
    )

    return results[:max_stocks]


# =========================================================
# RUN FIRST SCAN
# =========================================================

if "scan_now" not in st.session_state:

    st.session_state.scan_now = True


if st.session_state.scan_now:

    with st.spinner("Scanning US stocks..."):

        st.session_state.last_scan = run_scan()

        st.session_state.scan_count += 1

        st.session_state.scan_now = False


stocks = st.session_state.last_scan


# =========================================================
# MAIN LAYOUT
# =========================================================

left, right = st.columns([0.35, 0.65])


# =========================================================
# LEFT - STOCK LIST
# =========================================================

with left:

    st.subheader("Momentum Stocks")

    if not stocks:

        st.warning(
            "No stocks matched the current filters."
        )

    else:

        for stock in stocks:

            symbol = stock["symbol"]

            repeat_box = " ■" if stock["repeat"] else ""

            label = f"{symbol}{repeat_box}"

            if st.button(
                label,
                key=f"stock_{symbol}",
                use_container_width=True
            ):

                st.session_state.selected_stock = symbol

                st.rerun()

            st.caption(
                f"${stock['price']:.2f}   "
                f"{stock['change']:+.2f}%   "
                f"Vol {stock['volume']:,}"
            )


# =========================================================
# RIGHT - TRADINGVIEW
# =========================================================

with right:

    symbol = st.session_state.selected_stock

    st.subheader(f"{symbol}")

    tradingview_url = (
        f"https://www.tradingview.com/widgetembed/"
        f"?symbol=NASDAQ:{symbol}"
        f"&interval=5"
        f"&theme=dark"
        f"&style=1"
        f"&locale=en"
        f"&hide_top_toolbar=0"
        f"&hide_legend=0"
        f"&saveimage=0"
        f"&studies=[]"
    )

    st.components.v1.iframe(
        tradingview_url,
        height=700,
        scrolling=False
    )


# =========================================================
# FOOTER
# =========================================================

st.caption(
    f"Scan #{st.session_state.scan_count} • "
    f"Webull OpenAPI • "
    f"Repeat stock = ■"
)
