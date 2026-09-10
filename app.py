```python
import streamlit as st
import pandas as pd
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components

from webull.core.client import ApiClient
from webull.data.data_client import DataClient


# =========================================================
# PAGE CONFIGURATION
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

st.markdown(
    """
    <style>

    /* -----------------------------------------------------
       MAIN PAGE
    ----------------------------------------------------- */

    .block-container {
        padding-top: 0.35rem;
        padding-left: 0.45rem;
        padding-right: 0.45rem;
        padding-bottom: 0rem;
        max-width: 100%;
    }


    /* -----------------------------------------------------
       SIDEBAR
    ----------------------------------------------------- */

    [data-testid="stSidebar"] {
        width: 285px;
    }


    /* -----------------------------------------------------
       COLUMNS
    ----------------------------------------------------- */

    div[data-testid="column"] {
        padding-left: 3px;
        padding-right: 3px;
    }


    /* -----------------------------------------------------
       STOCK BUTTONS
    ----------------------------------------------------- */

    .stButton > button {
        min-height: 30px;
        height: 30px;
        padding: 0px 5px;
        font-size: 12px;
        border-radius: 4px;
    }


    /* -----------------------------------------------------
       STOCK LIST TEXT
    ----------------------------------------------------- */

    .stock-value {
        font-size: 11px;
        line-height: 30px;
        white-space: nowrap;
    }


    .repeat-symbol {
        font-weight: 900;
        margin-right: 3px;
    }


    /* -----------------------------------------------------
       SMALL HEADERS
    ----------------------------------------------------- */

    .small-header {
        font-size: 10px;
        font-weight: 700;
        opacity: 0.65;
    }


    /* -----------------------------------------------------
       CHART
    ----------------------------------------------------- */

    .chart-container {
        width: 100%;
        height: 720px;
        overflow: hidden;
    }


    /* -----------------------------------------------------
       FOOTER
    ----------------------------------------------------- */

    .scanner-footer {
        font-size: 10px;
        opacity: 0.55;
        padding-top: 4px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# WEBULL API
# =========================================================

try:

    APP_KEY = st.secrets["WEBULL_APP_KEY"]
    APP_SECRET = st.secrets["WEBULL_APP_SECRET"]

except Exception:

    st.error(
        "❌ Webull API keys are missing from Streamlit Secrets."
    )

    st.info(
        "Add WEBULL_APP_KEY and WEBULL_APP_SECRET "
        "to Streamlit Secrets."
    )

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

    st.error(
        "❌ Webull API connection failed."
    )

    st.code(
        str(e)
    )

    st.stop()


# =========================================================
# SETTINGS FILE
# =========================================================

SETTINGS_FILE = "scanner_settings.json"


DEFAULT_SETTINGS = {

    # -------------------------
    # Scanner
    # -------------------------

    "min_price": 1.0,

    "max_price": 1000.0,

    "min_volume": 100000,

    "min_rvol": 1.5,

    "min_change": 1.0,

    "min_dollar_volume": 1000000,

    # -------------------------
    # Repeat volume
    # -------------------------

    "repeat_tolerance": 0.90,

    "repeat_history": 20,

    # -------------------------
    # Refresh
    # -------------------------

    "refresh_seconds": 60,

    "auto_scan": True,

    # -------------------------
    # TradingView
    # -------------------------

    "chart_interval": "1",

    "chart_theme": "dark",

    "chart_style": "1",

    "show_volume": True,

    "hide_side_toolbar": True,

    "allow_symbol_change": True,

    # -------------------------
    # Chart template
    # -------------------------

    # Keep these in ONE place.
    #
    # These settings represent the scanner-wide
    # TradingView template.
    #
    # Every stock uses the same template.

    "chart_template": {

        "timezone": "America/New_York",

        "hide_legend": False,

        "withdateranges": True,

        "save_image": True,

        "hide_volume": False,

        "locale": "en"
    }
}


# =========================================================
# LOAD SETTINGS
# =========================================================

def load_settings():

    if not os.path.exists(
        SETTINGS_FILE
    ):

        return DEFAULT_SETTINGS.copy()


    try:

        with open(
            SETTINGS_FILE,
            "r"
        ) as f:

            saved = json.load(f)


        result = DEFAULT_SETTINGS.copy()

        result.update(
            saved
        )


        # Make sure nested template survives
        if "chart_template" not in result:

            result["chart_template"] = (
                DEFAULT_SETTINGS["chart_template"].copy()
            )


        return result


    except Exception:

        return DEFAULT_SETTINGS.copy()


settings = load_settings()


# =========================================================
# SAVE SETTINGS
# =========================================================

def save_settings():

    try:

        with open(
            SETTINGS_FILE,
            "w"
        ) as f:

            json.dump(
                settings,
                f,
                indent=4
            )

        return True

    except Exception:

        return False


# =========================================================
# SESSION STATE
# =========================================================

if "selected_symbol" not in st.session_state:

    st.session_state.selected_symbol = "AAPL"


if "previous_volumes" not in st.session_state:

    st.session_state.previous_volumes = {}


if "volume_history" not in st.session_state:

    st.session_state.volume_history = {}


if "repeat_stocks" not in st.session_state:

    st.session_state.repeat_stocks = set()


if "scan_results" not in st.session_state:

    st.session_state.scan_results = pd.DataFrame()


if "scan_count" not in st.session_state:

    st.session_state.scan_count = 0


if "last_scan_time" not in st.session_state:

    st.session_state.last_scan_time = None


# =========================================================
# US MARKET TIME
# =========================================================

NY_TZ = ZoneInfo(
    "America/New_York"
)


def market_open():

    now = datetime.now(
        NY_TZ
    )


    # Saturday / Sunday
    if now.weekday() >= 5:

        return False


    minutes = (
        now.hour * 60
        + now.minute
    )


    # Regular US session
    return (
        570 <= minutes <= 960
    )


def market_time():

    return datetime.now(
        NY_TZ
    ).strftime(
        "%H:%M:%S"
    )


# =========================================================
# WEBULL SNAPSHOT
# =========================================================

def get_snapshot(symbol):

    try:

        result = (
            data_client
            .market_data
            .get_snapshot(
                symbol,
                "US_STOCK"
            )
        )


        if result.status_code != 200:

            return None


        data = result.json()


        if isinstance(
            data,
            list
        ):

            if not data:

                return None

            data = data[0]


        return data


    except Exception:

        return None


# =========================================================
# STOCK UNIVERSE
# =========================================================
#
# TEST UNIVERSE
#
# We keep this small initially so the API connection and
# scanner can be confirmed.
#
# Later we will replace this with the full US universe.
# =========================================================

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
# EXCHANGE MAP
# =========================================================
#
# TradingView needs the correct exchange prefix.
#
# This can later be replaced by exchange information
# returned by Webull.
# =========================================================

EXCHANGE_MAP = {

    "AAPL": "NASDAQ",
    "MSFT": "NASDAQ",
    "NVDA": "NASDAQ",
    "AMZN": "NASDAQ",
    "META": "NASDAQ",

    "GOOGL": "NASDAQ",
    "GOOG": "NASDAQ",

    "TSLA": "NASDAQ",
    "AVGO": "NASDAQ",
    "AMD": "NASDAQ",

    "NFLX": "NASDAQ",
    "INTC": "NASDAQ",
    "MU": "NASDAQ",
    "QCOM": "NASDAQ",
    "AMAT": "NASDAQ",

    "ARM": "NASDAQ",
    "PLTR": "NASDAQ",
    "SMCI": "NASDAQ",
    "COIN": "NASDAQ",
    "HOOD": "NASDAQ",

    "SOFI": "NASDAQ",

    "BAC": "NYSE",
    "JPM": "NYSE",
    "WMT": "NYSE",
    "COST": "NASDAQ",

    "UBER": "NYSE",
    "SHOP": "NASDAQ",
    "PDD": "NASDAQ",
    "NIO": "NYSE",
    "RIVN": "NASDAQ"
}


def get_tradingview_symbol(symbol):

    exchange = EXCHANGE_MAP.get(
        symbol,
        "NASDAQ"
    )

    return (
        exchange
        + ":"
        + symbol
    )


# =========================================================
# VOLUME HISTORY
# =========================================================

def add_volume_history(
    symbol,
    volume
):

    if symbol not in st.session_state.volume_history:

        st.session_state.volume_history[
            symbol
        ] = []


    history = (
        st.session_state
        .volume_history[
            symbol
        ]
    )


    if volume > 0:

        history.append(
            volume
        )


    max_history = int(
        settings[
            "repeat_history"
        ]
    )


    if len(history) > max_history:

        history[:] = history[
            -max_history:
        ]


# =========================================================
# REPEAT VOLUME
# =========================================================
#
# The old version only compared the current reading with
# the immediately previous reading.
#
# This version looks through previous scanner observations.
#
# Example:
#
# 1. Current volume = 5M
# 2. Earlier observation = 5.2M
# 3. Difference is within tolerance
# 4. Stock gets ■
# =========================================================

def check_repeat_volume(
    symbol,
    current_volume
):

    if current_volume <= 0:

        return False


    history = (
        st.session_state
        .volume_history
        .get(
            symbol,
            []
        )
    )


    tolerance = float(
        settings[
            "repeat_tolerance"
        ]
    )


    repeat = False


    for old_volume in history:

        if old_volume <= 0:

            continue


        ratio = (
            current_volume
            / old_volume
        )


        # Close to previous volume.
        #
        # Example tolerance 0.90:
        #
        # 90% to 111.1% is treated as similar.
        #

        if (
            tolerance
            <= ratio
            <= (1 / tolerance)
        ):

            repeat = True

            break


    # Add CURRENT reading after comparison.
    #
    # This prevents current reading from matching itself.

    add_volume_history(
        symbol,
        current_volume
    )


    if repeat:

        st.session_state.repeat_stocks.add(
            symbol
        )


    return (
        symbol
        in st.session_state.repeat_stocks
    )


# =========================================================
# APPROXIMATE RVOL
# =========================================================
#
# Temporary scanner RVOL.
#
# The next stage will use proper historical intraday
# volume by time-of-day.
#
# We deliberately keep this separate from repeat-volume.
# =========================================================

def calculate_rvol(
    symbol,
    current_volume
):

    previous = (
        st.session_state
        .previous_volumes
        .get(
            symbol
        )
    )


    if (
        previous is None
        or previous <= 0
    ):

        rvol = 1.0


    else:

        rvol = (
            current_volume
            / previous
        )


    st.session_state.previous_volumes[
        symbol
    ] = current_volume


    return rvol


# =========================================================
# NUMBER FORMAT
# =========================================================

def format_money(
    value
):

    if value >= 1_000_000_000:

        return (
            f"${value / 1_000_000_000:.1f}B"
        )


    if value >= 1_000_000:

        return (
            f"${value / 1_000_000:.1f}M"
        )


    if value >= 1_000:

        return (
            f"${value / 1_000:.0f}K"
        )


    return (
        f"${value:.0f}"
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


            # -------------------------------------------------
            # PRICE
            # -------------------------------------------------

            price = float(
                data.get(
                    "price",
                    0
                )
                or 0
            )


            # -------------------------------------------------
            # CHANGE
            # -------------------------------------------------

            change_ratio = float(
                data.get(
                    "change_ratio",
                    0
                )
                or 0
            )


            change = (
                change_ratio
                * 100
            )


            # -------------------------------------------------
            # VOLUME
            # -------------------------------------------------

            volume = float(
                data.get(
                    "volume",
                    0
                )
                or 0
            )


            # -------------------------------------------------
            # DOLLAR VOLUME
            # -------------------------------------------------

            dollar_volume = (
                price
                * volume
            )


            # -------------------------------------------------
            # RVOL
            # -------------------------------------------------

            rvol = calculate_rvol(
                symbol,
                volume
            )


            # -------------------------------------------------
            # REPEAT
            # -------------------------------------------------

            repeat = check_repeat_volume(
                symbol,
                volume
            )


            # -------------------------------------------------
            # FILTERS
            # -------------------------------------------------

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


            # -------------------------------------------------
            # RESULT
            # -------------------------------------------------

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


    # ---------------------------------------------------------
    # SORT
    # ---------------------------------------------------------
    #
    # Repeat first
    # Then RVOL
    # Then percentage change
    #

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


    return df.reset_index(
        drop=True
    )


# =========================================================
# RUN SCAN
# =========================================================

def run_scan():

    with st.spinner(
        "Scanning Webull market data..."
    ):

        result = scan_stocks()


    st.session_state.scan_results = result

    st.session_state.scan_count += 1

    st.session_state.last_scan_time = (
        market_time()
    )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title(
        "⚙️ Scanner Filters"
    )


    st.markdown(
        "### Price"
    )


    settings["min_price"] = st.number_input(

        "Minimum Price",

        value=float(
            settings[
                "min_price"
            ]
        ),

        min_value=0.01,

        step=0.50
    )


    settings["max_price"] = st.number_input(

        "Maximum Price",

        value=float(
            settings[
                "max_price"
            ]
        ),

        min_value=0.01,

        step=5.00
    )


    st.markdown(
        "### Momentum"
    )


    settings["min_change"] = st.number_input(

        "Minimum % Change",

        value=float(
            settings[
                "min_change"
            ]
        ),

        step=0.5
    )


    settings["min_rvol"] = st.number_input(

        "Minimum RVOL",

        value=float(
            settings[
                "min_rvol"
            ]
        ),

        min_value=0.0,

        step=0.1
    )


    st.markdown(
        "### Volume"
    )


    settings["min_volume"] = st.number_input(

        "Minimum Volume",

        value=int(
            settings[
                "min_volume"
            ]
        ),

        min_value=0,

        step=100000
    )


    settings["min_dollar_volume"] = st.number_input(

        "Minimum Dollar Volume",

        value=int(
            settings[
                "min_dollar_volume"
            ]
        ),

        min_value=0,

        step=500000
    )


    settings["repeat_tolerance"] = st.slider(

        "Repeat Volume Tolerance",

        min_value=0.50,

        max_value=1.00,

        value=float(
            settings[
                "repeat_tolerance"
            ]
        ),

        step=0.01
    )


    settings["repeat_history"] = st.number_input(

        "Volume History Readings",

        value=int(
            settings[
                "repeat_history"
            ]
        ),

        min_value=2,

        max_value=100,

        step=1
    )


    st.markdown(
        "### Scanner Refresh"
    )


    settings["refresh_seconds"] = st.number_input(

        "Refresh Seconds",

        value=int(
            settings[
                "refresh_seconds"
            ]
        ),

        min_value=10,

        max_value=3600,

        step=10
    )


    settings["auto_scan"] = st.checkbox(

        "Auto Scan",

        value=bool(
            settings[
                "auto_scan"
            ]
        )
    )


    st.markdown(
        "### TradingView Template"
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


    settings["chart_theme"] = st.selectbox(

        "Chart Theme",

        [
            "dark",
            "light"
        ],

        index=[
            "dark",
            "light"
        ].index(
            settings[
                "chart_theme"
            ]
        )
    )


    settings["show_volume"] = st.checkbox(

        "Show Volume",

        value=bool(
            settings[
                "show_volume"
            ]
        )
    )


    st.caption(
        "The TradingView chart uses one global "
        "template for every stock."
    )


    st.divider()


    if st.button(
        "💾 Save Settings",
        use_container_width=True
    ):

        if save_settings():

            st.success(
                "Settings saved"
            )

        else:

            st.error(
                "Could not save settings"
            )


    if st.button(
        "🗑 Reset Settings",
        use_container_width=True
    ):

        settings.clear()

        settings.update(
            DEFAULT_SETTINGS.copy()
        )

        save_settings()

        st.rerun()


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

        run_scan()


# =========================================================
# FIRST SCAN
# =========================================================

if st.session_state.scan_results.empty:

    run_scan()


df = st.session_state.scan_results


# =========================================================
# MAIN LAYOUT
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
            "No stocks match the current filters."
        )


    else:

        # -----------------------------------------------------
        # TABLE HEADER
        # -----------------------------------------------------

        h1, h2, h3, h4, h5 = st.columns(
            [1.5, 1.2, 0.9, 1.0, 1.2]
        )


        with h1:

            st.markdown(
                '<div class="small-header">SYMBOL</div>',
                unsafe_allow_html=True
            )


        with h2:

            st.markdown(
                '<div class="small-header">LTP</div>',
                unsafe_allow_html=True
            )


        with h3:

            st.markdown(
                '<div class="small-header">%</div>',
                unsafe_allow_html=True
            )


        with h4:

            st.markdown(
                '<div class="small-header">RVOL</div>',
                unsafe_allow_html=True
            )


        with h5:

            st.markdown(
                '<div class="small-header">$VOL</div>',
                unsafe_allow_html=True
            )


        # -----------------------------------------------------
        # STOCK ROWS
        # -----------------------------------------------------

        for _, row in df.iterrows():

            symbol = row[
                "Symbol"
            ]


            c1, c2, c3, c4, c5 = st.columns(
                [1.5, 1.2, 0.9, 1.0, 1.2]
            )


            # -------------------------------------------------
            # SYMBOL
            # -------------------------------------------------

            with c1:

                if row["Repeat"]:

                    button_label = (
                        "■ "
                        + symbol
                    )

                else:

                    button_label = symbol


                if st.button(

                    button_label,

                    key=(
                        f"stock_"
                        f"{symbol}"
                    ),

                    use_container_width=True

                ):

                    st.session_state.selected_symbol = (
                        symbol
                    )

                    st.rerun()


            # -------------------------------------------------
            # PRICE
            # -------------------------------------------------

            with c2:

                st.markdown(
                    f'<div class="stock-value">'
                    f'${row["Price"]:.2f}'
                    f'</div>',
                    unsafe_allow_html=True
                )


            # -------------------------------------------------
            # CHANGE
            # -------------------------------------------------

            with c3:

                st.markdown(
                    f'<div class="stock-value">'
                    f'{row["Change"]:.1f}%'
                    f'</div>',
                    unsafe_allow_html=True
                )


            # -------------------------------------------------
            # RVOL
            # -------------------------------------------------

            with c4:

                st.markdown(
                    f'<div class="stock-value">'
                    f'{row["RVOL"]:.1f}x'
                    f'</div>',
                    unsafe_allow_html=True
                )


            # -------------------------------------------------
            # DOLLAR VOLUME
            # -------------------------------------------------

            with c5:

                st.markdown(
                    f'<div class="stock-value">'
                    f'{format_money(row["Dollar"])}'
                    f'</div>',
                    unsafe_allow_html=True
                )


# =========================================================
# RIGHT — TRADINGVIEW
# =========================================================

with right:

    symbol = (
        st.session_state.selected_symbol
    )


    interval = (
        settings[
            "chart_interval"
        ]
    )


    theme = (
        settings[
            "chart_theme"
        ]
    )


    tv_symbol = (
        get_tradingview_symbol(
            symbol
        )
    )


    st.markdown(
        f"### 📊 {symbol}"
    )


    # =====================================================
    # ONE GLOBAL TRADINGVIEW TEMPLATE
    # =====================================================
    #
    # The important design is that all chart parameters
    # come from the SAME settings object.
    #
    # Changing the stock changes ONLY the symbol.
    #
    # Everything else remains the same.
    # =====================================================

    template = (
        settings[
            "chart_template"
        ]
    )


    hide_volume = (
        "0"
        if settings[
            "show_volume"
        ]
        else "1"
    )


    tradingview_url = (

        "https://www.tradingview.com/widgetembed/"

        "?frameElementId=tradingview_chart"

        f"&symbol={tv_symbol.replace(':', '%3A')}"

        f"&interval={interval}"

        # -------------------------------------------------
        # GLOBAL TEMPLATE SETTINGS
        # -------------------------------------------------

        f"&theme={theme}"

        f"&style={settings['chart_style']}"

        f"&timezone="
        f"{template['timezone'].replace('/', '%2F')}"

        f"&withdateranges="
        f"{str(template['withdateranges']).lower()}"

        f"&hide_legend="
        f"{'1' if template['hide_legend'] else '0'}"

        f"&save_image="
        f"{'1' if template['save_image'] else '0'}"

        f"&hide_volume={hide_volume}"

        f"&hide_side_toolbar="
        f"{'1' if settings['hide_side_toolbar'] else '0'}"

        f"&allow_symbol_change="
        f"{'1' if settings['allow_symbol_change'] else '0'}"

        f"&locale={template['locale']}"

    )


    # -----------------------------------------------------
    # IMPORTANT
    # -----------------------------------------------------
    #
    # The iframe is deliberately generated from ONE
    # template.
    #
    # When symbol changes:
    #
    # NVDA -> TSLA -> AMD -> AAPL
    #
    # the template does not change.
    #
    # -----------------------------------------------------

    html = f"""

    <div class="chart-container">

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

    </div>

    """


    components.html(

        html,

        height=720,

        scrolling=False

    )


# =========================================================
# STATUS FOOTER
# =========================================================

last_scan = (
    st.session_state.last_scan_time
    if st.session_state.last_scan_time
    else "--"
)


st.markdown(

    f"""
    <div class="scanner-footer">

        Scan #{st.session_state.scan_count}
        &nbsp; • &nbsp;

        Webull OpenAPI
        &nbsp; • &nbsp;

        Last scan: {last_scan}
        &nbsp; • &nbsp;

        Selected: {symbol}
        &nbsp; • &nbsp;

        Repeat stock = ■

    </div>
    """,

    unsafe_allow_html=True
)


# =========================================================
# AUTO REFRESH
# =========================================================

if settings[
    "auto_scan"
]:

    seconds = int(
        settings[
            "refresh_seconds"
        ]
    )


    # JavaScript refreshes the Streamlit page.
    #
    # Scanner settings are loaded again from the
    # saved JSON file, so they remain persistent.

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
```
