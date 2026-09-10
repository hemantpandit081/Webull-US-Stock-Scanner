import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components

from webull.core.client import ApiClient
from webull.data.data_client import DataClient


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="US Momentum Stock Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# CSS
# =========================================================

st.markdown("""
<style>

.block-container {
    padding-top: 0.5rem;
    padding-left: 0.6rem;
    padding-right: 0.6rem;
    padding-bottom: 0rem;
}

[data-testid="stSidebar"] {
    width: 280px;
}

div[data-testid="column"] {
    padding-left: 3px;
    padding-right: 3px;
}

.stock-row {
    font-size: 12px;
}

.repeat-box {
    color: white;
    font-weight: 900;
    margin-right: 4px;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# WEBULL API
# =========================================================

try:

    APP_KEY = st.secrets["WEBULL_APP_KEY"]
    APP_SECRET = st.secrets["WEBULL_APP_SECRET"]

except Exception:

    st.error("❌ Webull API keys are missing from Streamlit Secrets.")
    st.stop()


@st.cache_resource
def create_webull_client():

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

    data_client = create_webull_client()

except Exception as e:

    st.error("❌ Webull API connection failed")
    st.code(str(e))
    st.stop()


# =========================================================
# SETTINGS
# =========================================================

SETTINGS_FILE = "scanner_settings.json"

DEFAULT_SETTINGS = {

    "min_price": 1.0,
    "max_price": 1000.0,

    "min_volume": 100000,

    "min_rvol": 1.5,

    "min_change": 1.0,

    "min_dollar_volume": 1000000,

    "repeat_tolerance": 0.90,

    "refresh_seconds": 60,

    "auto_scan": True,

    "chart_interval": "1"
}


def load_settings():

    if os.path.exists(SETTINGS_FILE):

        try:

            with open(
                SETTINGS_FILE,
                "r"
            ) as f:

                saved = json.load(f)

            result = DEFAULT_SETTINGS.copy()

            result.update(saved)

            return result

        except Exception:

            pass

    return DEFAULT_SETTINGS.copy()


settings = load_settings()


def save_settings():

    with open(
        SETTINGS_FILE,
        "w"
    ) as f:

        json.dump(
            settings,
            f,
            indent=4
        )


# =========================================================
# SESSION STATE
# =========================================================

if "selected_symbol" not in st.session_state:

    st.session_state.selected_symbol = "AAPL"


if "previous_volumes" not in st.session_state:

    st.session_state.previous_volumes = {}


if "repeat_stocks" not in st.session_state:

    st.session_state.repeat_stocks = set()


if "scan_results" not in st.session_state:

    st.session_state.scan_results = pd.DataFrame()


if "scan_count" not in st.session_state:

    st.session_state.scan_count = 0


# =========================================================
# TIME
# =========================================================

NY_TZ = ZoneInfo(
    "America/New_York"
)


def market_open():

    now = datetime.now(
        NY_TZ
    )

    if now.weekday() >= 5:

        return False

    minutes = (
        now.hour * 60
        + now.minute
    )

    return (
        570 <= minutes <= 960
    )


# =========================================================
# WEBULL SNAPSHOT
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

        if isinstance(
            data,
            list
        ):

            if len(data) == 0:

                return None

            data = data[0]

        return data

    except Exception:

        return None


# =========================================================
# WEBULL CANDIDATE STOCKS
# =========================================================

# Initial Webull scanner universe.
#
# This is intentionally kept separate from the old
# yfinance 30-stock scanner.
#
# We will expand this to the full Webull US universe
# after the basic scanner is confirmed working.

STOCKS = [

    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",

    "GOOGL",
    "GOOG",
    "TSLA",
    "AVGO",
    "AMD",

    "NFLX",
    "INTC",
    "MU",
    "QCOM",
    "AMAT",

    "ARM",
    "PLTR",
    "SMCI",
    "COIN",
    "HOOD",

    "SOFI",
    "BAC",
    "JPM",
    "WMT",
    "COST",

    "UBER",
    "SHOP",
    "PDD",
    "NIO",
    "RIVN"
]


# =========================================================
# REPEAT VOLUME
# =========================================================

def check_repeat_volume(
    symbol,
    current_volume
):

    previous = (
        st.session_state
        .previous_volumes
        .get(symbol)
    )

    repeat = False

    if previous is not None:

        if previous > 0:

            ratio = (
                current_volume
                / previous
            )

            tolerance = (
                settings[
                    "repeat_tolerance"
                ]
            )

            if ratio >= tolerance:

                repeat = True

                st.session_state.repeat_stocks.add(
                    symbol
                )

    st.session_state.previous_volumes[
        symbol
    ] = current_volume

    return (
        symbol
        in st.session_state.repeat_stocks
    )


# =========================================================
# SCANNER
# =========================================================

def scan_stocks():

    results = []

    for symbol in STOCKS:

        try:

            data = get_snapshot(
                symbol
            )

            if data is None:

                continue


            # ---------------------------------------------
            # PRICE
            # ---------------------------------------------

            price = float(
                data.get(
                    "price",
                    0
                )
            )


            # ---------------------------------------------
            # CHANGE
            # ---------------------------------------------

            change_ratio = float(
                data.get(
                    "change_ratio",
                    0
                )
            )

            change = (
                change_ratio
                * 100
            )


            # ---------------------------------------------
            # VOLUME
            # ---------------------------------------------

            volume = float(
                data.get(
                    "volume",
                    0
                )
            )


            # ---------------------------------------------
            # DOLLAR VOLUME
            # ---------------------------------------------

            dollar_volume = (
                price
                * volume
            )


            # ---------------------------------------------
            # APPROXIMATE RVOL
            # ---------------------------------------------
            #
            # Snapshot gives current cumulative volume.
            #
            # For the first Webull version we use the
            # previous scanner reading as a reference.
            #
            # We will replace this with proper historical
            # intraday RVOL once the scanner is confirmed.
            #

            previous_volume = (
                st.session_state
                .previous_volumes
                .get(symbol)
            )

            if (
                previous_volume is not None
                and previous_volume > 0
            ):

                rvol = (
                    volume
                    / previous_volume
                )

            else:

                rvol = 1.0


            # ---------------------------------------------
            # REPEAT
            # ---------------------------------------------

            repeat = check_repeat_volume(
                symbol,
                volume
            )


            # ---------------------------------------------
            # FILTERS
            # ---------------------------------------------

            if price < settings[
                "min_price"
            ]:

                continue


            if price > settings[
                "max_price"
            ]:

                continue


            if volume < settings[
                "min_volume"
            ]:

                continue


            if rvol < settings[
                "min_rvol"
            ]:

                continue


            if change < settings[
                "min_change"
            ]:

                continue


            if dollar_volume < settings[
                "min_dollar_volume"
            ]:

                continue


            # ---------------------------------------------
            # RESULT
            # ---------------------------------------------

            results.append({

                "Symbol": symbol,

                "Price": price,

                "Change": change,

                "RVOL": rvol,

                "Volume": volume,

                "Dollar": dollar_volume,

                "Repeat": repeat

            })


        except Exception:

            continue


    if not results:

        return pd.DataFrame()


    df = pd.DataFrame(
        results
    )


    # ---------------------------------------------
    # SORT
    # ---------------------------------------------

    df = df.sort_values(

        [
            "Repeat",
            "RVOL",
            "Change"
        ],

        ascending=[
            False,
            False,
            False
        ]

    )


    return df


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title("⚙️ Filters")


    settings["min_price"] = st.number_input(

        "Minimum Price",

        value=float(
            settings["min_price"]
        ),

        min_value=0.01

    )


    settings["max_price"] = st.number_input(

        "Maximum Price",

        value=float(
            settings["max_price"]
        ),

        min_value=0.01

    )


    settings["min_volume"] = st.number_input(

        "Minimum Volume",

        value=int(
            settings["min_volume"]
        ),

        step=10000,

        min_value=0

    )


    settings["min_rvol"] = st.number_input(

        "Minimum RVOL",

        value=float(
            settings["min_rvol"]
        ),

        step=0.1,

        min_value=0.0

    )


    settings["min_change"] = st.number_input(

        "Minimum % Change",

        value=float(
            settings["min_change"]
        ),

        step=0.5

    )


    settings["min_dollar_volume"] = st.number_input(

        "Minimum Dollar Volume",

        value=int(
            settings[
                "min_dollar_volume"
            ]
        ),

        step=100000,

        min_value=0

    )


    settings["repeat_tolerance"] = st.slider(

        "Repeat Volume",

        0.50,

        1.00,

        float(
            settings[
                "repeat_tolerance"
            ]
        ),

        0.01

    )


    settings["refresh_seconds"] = st.number_input(

        "Refresh Seconds",

        10,

        3600,

        int(
            settings[
                "refresh_seconds"
            ]
        ),

        10

    )


    settings["chart_interval"] = st.selectbox(

        "Chart Interval",

        [
            "1",
            "5",
            "15",
            "30",
            "60",
            "D"
        ],

        index=[
            "1",
            "5",
            "15",
            "30",
            "60",
            "D"
        ].index(
            settings[
                "chart_interval"
            ]
        )

    )


    settings["auto_scan"] = st.checkbox(

        "Auto Scan",

        value=bool(
            settings[
                "auto_scan"
            ]
        )

    )


    if st.button(
        "💾 Save Filters",
        use_container_width=True
    ):

        save_settings()

        st.success(
            "Saved"
        )


# =========================================================
# HEADER
# =========================================================

header1, header2, header3 = st.columns(
    [5, 2, 2]
)


with header1:

    st.markdown(
        "## 📈 US Momentum Stock Scanner"
    )


with header2:

    if market_open():

        st.success(
            "🟢 Market Open"
        )

    else:

        st.info(
            "⚪ Market Closed"
        )


with header3:

    if st.button(
        "🔄 Scan Now",
        use_container_width=True
    ):

        st.session_state.scan_results = (
            scan_stocks()
        )

        st.session_state.scan_count += 1


# =========================================================
# FIRST SCAN
# =========================================================

if st.session_state.scan_results.empty:

    with st.spinner(
        "Scanning Webull market data..."
    ):

        st.session_state.scan_results = (
            scan_stocks()
        )

        st.session_state.scan_count += 1


df = st.session_state.scan_results


# =========================================================
# LAYOUT
# =========================================================

left, right = st.columns(
    [35, 65],
    gap="small"
)


# =========================================================
# LEFT STOCK LIST
# =========================================================

with left:

    st.markdown(
        "### 📋 Stocks"
    )


    if df.empty:

        st.info(
            "No stocks match the filters."
        )


    else:

        # ---------------------------------------------
        # HEADER
        # ---------------------------------------------

        h1, h2, h3, h4, h5 = st.columns(
            [1.4, 1.2, 1, 1, 1.2]
        )


        h1.caption(
            "Symbol"
        )

        h2.caption(
            "LTP"
        )

        h3.caption(
            "%"
        )

        h4.caption(
            "RVOL"
        )

        h5.caption(
            "$Vol"
        )


        # ---------------------------------------------
        # STOCK ROWS
        # ---------------------------------------------

        for _, row in df.iterrows():

            symbol = row[
                "Symbol"
            ]


            c1, c2, c3, c4, c5 = st.columns(
                [1.4, 1.2, 1, 1, 1.2]
            )


            # -----------------------------------------
            # SYMBOL
            # -----------------------------------------

            with c1:

                if row["Repeat"]:

                    label = (
                        "■ "
                        + symbol
                    )

                else:

                    label = symbol


                if st.button(

                    label,

                    key=f"select_{symbol}",

                    use_container_width=True

                ):

                    st.session_state.selected_symbol = (
                        symbol
                    )

                    st.rerun()


            # -----------------------------------------
            # PRICE
            # -----------------------------------------

            with c2:

                st.caption(
                    f"${row['Price']:.2f}"
                )


            # -----------------------------------------
            # CHANGE
            # -----------------------------------------

            with c3:

                st.caption(
                    f"{row['Change']:.1f}%"
                )


            # -----------------------------------------
            # RVOL
            # -----------------------------------------

            with c4:

                st.caption(
                    f"{row['RVOL']:.1f}x"
                )


            # -----------------------------------------
            # DOLLAR VOLUME
            # -----------------------------------------

            with c5:

                dollar = row[
                    "Dollar"
                ]


                if dollar >= 1_000_000_000:

                    text = (
                        f"${dollar / 1_000_000_000:.1f}B"
                    )

                elif dollar >= 1_000_000:

                    text = (
                        f"${dollar / 1_000_000:.1f}M"
                    )

                else:

                    text = (
                        f"${dollar / 1_000:.0f}K"
                    )


                st.caption(
                    text
                )


# =========================================================
# TRADINGVIEW
# =========================================================

with right:

    symbol = (
        st.session_state.selected_symbol
    )


    interval = (
        settings["chart_interval"]
    )


    st.markdown(
        f"### 📊 {symbol}"
    )


    tradingview_url = (

        "https://www.tradingview.com/widgetembed/"

        "?frameElementId=tradingview_chart"

        f"&symbol=NASDAQ%3A{symbol}"

        f"&interval={interval}"

        # Hide LEFT TradingView drawing toolbar
        "&hide_side_toolbar=1"

        "&allow_symbol_change=1"

        "&save_image=1"

        "&hide_volume=0"

        "&theme=dark"

        "&style=1"

        "&timezone=America%2FNew_York"

        "&withdateranges=1"

        "&hide_legend=0"

        "&locale=en"

    )


    html = f"""

    <iframe

        id="tradingview_chart"

        src="{tradingview_url}"

        style="

            width:100%;

            height:700px;

            border:0;

        "

        allowtransparency="true"

        frameborder="0"

        scrolling="no">

    </iframe>

    """


    components.html(

        html,

        height=720,

        scrolling=False

    )


# =========================================================
# FOOTER
# =========================================================

st.caption(

    f"Scan #{st.session_state.scan_count}  •  "
    f"Webull OpenAPI  •  "
    f"Repeat stock = ■"

)


# =========================================================
# AUTO REFRESH
# =========================================================

if settings["auto_scan"]:

    seconds = int(
        settings["refresh_seconds"]
    )


    st.markdown(

        f"""

        <script>

        setTimeout(function() {{

            window.parent.location.reload();

        }}, {seconds * 1000});

        </script>

        """,

        unsafe_allow_html=True

    )
