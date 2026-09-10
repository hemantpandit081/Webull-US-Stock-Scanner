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

    /* Main content spacing */
    .block-container {
        padding-top: 0.70rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0.35rem !important;
        padding-right: 0.35rem !important;
        max-width: 100% !important;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        width: 280px !important;
    }

    /* Columns */
    div[data-testid="column"] {
        padding-left: 3px !important;
        padding-right: 3px !important;
    }

    /* Stock row */
    .stock-row {
        border-bottom: 1px solid rgba(128,128,128,0.18);
        padding: 2px 3px;
        margin: 0px;
        min-height: 27px;
        line-height: 20px;
        font-size: 12px;
    }

    /* Buttons */
    div.stButton > button {
        min-height: 27px !important;
        height: 27px !important;
        padding-top: 0px !important;
        padding-bottom: 0px !important;
        padding-left: 6px !important;
        padding-right: 6px !important;
        font-size: 12px !important;
    }

    /* Remove excess spacing */
    .element-container {
        margin-bottom: 0px !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# WEBULL API
# =========================================================

APP_KEY = os.getenv("WEBULL_APP_KEY", "")
APP_SECRET = os.getenv("WEBULL_APP_SECRET", "")

client = None
data_client = None

if APP_KEY and APP_SECRET:

    try:

        client = ApiClient(
            APP_KEY,
            APP_SECRET,
            "au"
        )

        client.add_endpoint(
            "au",
            "api.webull.com.au"
        )

        data_client = DataClient(client)

    except Exception:

        client = None
        data_client = None


# =========================================================
# DEFAULT SETTINGS
# =========================================================

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

    "chart_interval": "1",

}


# =========================================================
# SETTINGS FILE
# =========================================================

SETTINGS_FILE = "scanner_settings.json"


def load_settings():

    settings = DEFAULT_SETTINGS.copy()

    try:

        if os.path.exists(SETTINGS_FILE):

            with open(
                SETTINGS_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                saved = json.load(f)

                if isinstance(saved, dict):
                    settings.update(saved)

    except Exception:

        pass

    return settings


def save_settings(settings):

    try:

        with open(
            SETTINGS_FILE,
            "w",
            encoding="utf-8"
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

if "settings" not in st.session_state:

    st.session_state.settings = load_settings()


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


if "last_scan_time" not in st.session_state:

    st.session_state.last_scan_time = None


settings = st.session_state.settings


# =========================================================
# STOCK LIST
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
    "RIVN",

]


# =========================================================
# TRADINGVIEW EXCHANGES
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
    "COST": "NASDAQ",
    "SHOP": "NASDAQ",
    "PDD": "NASDAQ",
    "RIVN": "NASDAQ",

    "BAC": "NYSE",
    "JPM": "NYSE",
    "WMT": "NYSE",
    "UBER": "NYSE",
    "NIO": "NYSE",

}


# =========================================================
# MARKET STATUS
# =========================================================

def market_is_open():

    try:

        now = datetime.now(
            ZoneInfo("America/New_York")
        )

        if now.weekday() >= 5:
            return False

        market_open = now.replace(
            hour=9,
            minute=30,
            second=0,
            microsecond=0
        )

        market_close = now.replace(
            hour=16,
            minute=0,
            second=0,
            microsecond=0
        )

        return (
            market_open
            <= now
            <= market_close
        )

    except Exception:

        return False


# =========================================================
# WEBULL SNAPSHOT
# =========================================================

def get_snapshot(symbol):

    if data_client is None:
        return None

    try:

        response = data_client.market_data.get_snapshot(
            symbol,
            "US_STOCK"
        )

        # IMPORTANT:
        # Check response status before reading JSON

        if response.status_code != 200:
            return None

        data = response.json()

        # Webull may return a list

        if isinstance(data, list):

            if not data:
                return None

            return data[0]

        return data

    except Exception:

        return None


# =========================================================
# GET VALUE FROM SNAPSHOT
# =========================================================

def get_value(
    data,
    keys,
    default=0
):

    for key in keys:

        if key in data:

            value = data[key]

            if value is not None:

                return value

    return default


# =========================================================
# REPEAT VOLUME
# =========================================================

def check_repeat_volume(
    symbol,
    current_volume
):

    try:

        current_volume = float(
            current_volume
        )

    except Exception:

        return False

    if current_volume <= 0:
        return False

    previous_volume = (
        st.session_state.previous_volumes.get(
            symbol
        )
    )

    repeat = False

    if previous_volume:

        try:

            ratio = (
                current_volume
                / float(previous_volume)
            )

            tolerance = float(
                settings["repeat_tolerance"]
            )

            if ratio >= tolerance:

                repeat = True

        except Exception:

            repeat = False


    # Save current volume

    st.session_state.previous_volumes[
        symbol
    ] = current_volume


    if repeat:

        st.session_state.repeat_stocks.add(
            symbol
        )


    return repeat


# =========================================================
# SCAN ONE STOCK
# =========================================================

def scan_single_stock(symbol):

    snapshot = get_snapshot(symbol)

    if not snapshot:
        return None

    try:

        # -------------------------------------------------
        # PRICE
        # -------------------------------------------------

        price = float(
            get_value(
                snapshot,
                [
                    "close",
                    "latestPrice",
                    "lastPrice",
                    "price"
                ],
                0
            )
        )

        if price <= 0:
            return None


        # -------------------------------------------------
        # CHANGE %
        # -------------------------------------------------

        change_ratio = float(
            get_value(
                snapshot,
                [
                    "changeRatio",
                    "changePercent",
                    "change_rate"
                ],
                0
            )
        )

        if abs(change_ratio) < 1:

            change_percent = (
                change_ratio * 100
            )

        else:

            change_percent = change_ratio


        # -------------------------------------------------
        # VOLUME
        # -------------------------------------------------

        volume = float(
            get_value(
                snapshot,
                [
                    "volume",
                    "totalVolume",
                    "vol"
                ],
                0
            )
        )

        if volume <= 0:
            return None


        # -------------------------------------------------
        # DOLLAR VOLUME
        # -------------------------------------------------

        dollar_volume = (
            price * volume
        )


        # -------------------------------------------------
        # RVOL
        # -------------------------------------------------

        previous_volume = (
            st.session_state.previous_volumes.get(
                symbol
            )
        )

        if previous_volume:

            rvol = (
                volume
                / float(previous_volume)
            )

        else:

            rvol = 0


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

        if price < settings["min_price"]:
            return None

        if price > settings["max_price"]:
            return None

        if volume < settings["min_volume"]:
            return None

        if rvol < settings["min_rvol"]:
            return None

        if change_percent < settings["min_change"]:
            return None

        if dollar_volume < settings["min_dollar_volume"]:
            return None


        return {

            "Symbol": symbol,

            "Price": price,

            "Change": change_percent,

            "RVOL": rvol,

            "Volume": volume,

            "Dollar": dollar_volume,

            "Repeat": repeat,

        }


    except Exception:

        return None


# =========================================================
# SCAN ALL STOCKS
# =========================================================

def scan_stocks():

    results = []

    for symbol in STOCKS:

        result = scan_single_stock(
            symbol
        )

        if result is not None:

            results.append(result)


    if not results:

        return pd.DataFrame(
            columns=[
                "Symbol",
                "Price",
                "Change",
                "RVOL",
                "Volume",
                "Dollar",
                "Repeat"
            ]
        )


    df = pd.DataFrame(results)


    # -----------------------------------------------------
    # SORT
    # -----------------------------------------------------

    df = df.sort_values(
        by=[
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
# PERFORM SCAN
# =========================================================

def perform_scan():

    df = scan_stocks()

    st.session_state.scan_results = df

    st.session_state.scan_count += 1

    st.session_state.last_scan_time = (
        datetime.now()
    )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("### ⚙ Scanner Filters")


    min_price = st.number_input(
        "Minimum price",
        min_value=0.0,
        value=float(
            settings["min_price"]
        ),
        step=0.50
    )


    max_price = st.number_input(
        "Maximum price",
        min_value=1.0,
        value=float(
            settings["max_price"]
        ),
        step=10.0
    )


    min_volume = st.number_input(
        "Minimum volume",
        min_value=0,
        value=int(
            settings["min_volume"]
        ),
        step=100000
    )


    min_rvol = st.number_input(
        "Minimum RVOL",
        min_value=0.0,
        value=float(
            settings["min_rvol"]
        ),
        step=0.1
    )


    min_change = st.number_input(
        "Minimum change %",
        min_value=-100.0,
        value=float(
            settings["min_change"]
        ),
        step=0.5
    )


    min_dollar_volume = st.number_input(
        "Minimum $ volume",
        min_value=0,
        value=int(
            settings["min_dollar_volume"]
        ),
        step=100000
    )


    repeat_tolerance = st.number_input(
        "Repeat volume tolerance",
        min_value=0.50,
        max_value=1.50,
        value=float(
            settings["repeat_tolerance"]
        ),
        step=0.01
    )


    refresh_seconds = st.number_input(
        "Refresh seconds",
        min_value=10,
        max_value=3600,
        value=int(
            settings["refresh_seconds"]
        ),
        step=10
    )


    auto_scan = st.checkbox(
        "Auto scan",
        value=bool(
            settings["auto_scan"]
        )
    )


    chart_intervals = [
        "1",
        "3",
        "5",
        "15",
        "30",
        "60",
        "D"
    ]


    current_interval = (
        settings["chart_interval"]
    )

    if current_interval not in chart_intervals:

        current_interval = "1"


    chart_interval = st.selectbox(
        "TradingView interval",
        chart_intervals,
        index=chart_intervals.index(
            current_interval
        )
    )


    st.markdown("---")


    # -----------------------------------------------------
    # SAVE SETTINGS
    # -----------------------------------------------------

    if st.button(
        "💾 Save Filters",
        use_container_width=True
    ):

        st.session_state.settings = {

            "min_price": min_price,

            "max_price": max_price,

            "min_volume": min_volume,

            "min_rvol": min_rvol,

            "min_change": min_change,

            "min_dollar_volume":
                min_dollar_volume,

            "repeat_tolerance":
                repeat_tolerance,

            "refresh_seconds":
                refresh_seconds,

            "auto_scan":
                auto_scan,

            "chart_interval":
                chart_interval,

        }


        settings = (
            st.session_state.settings
        )


        if save_settings(settings):

            st.success(
                "Filters saved"
            )

        else:

            st.error(
                "Could not save filters"
            )


# =========================================================
# TOP HEADER
# NO HTML DIV HERE
# =========================================================

header1, header2, header3 = st.columns(
    [6, 2, 1.5]
)


with header1:

    st.markdown(
        "### 📈 US Momentum Stock Scanner"
    )


with header2:

    if market_is_open():

        st.markdown(
            "🟢 **MARKET OPEN**"
        )

    else:

        st.markdown(
            "🔴 **MARKET CLOSED**"
        )


with header3:

    if st.button(
        "🔄 Scan Now",
        use_container_width=True
    ):

        perform_scan()

        st.rerun()


# =========================================================
# LIVE SCANNER
# =========================================================

@st.fragment(
    run_every=(
        settings["refresh_seconds"]
        if settings["auto_scan"]
        else None
    )
)
def live_scanner():

    # First scan

    if st.session_state.scan_results.empty:

        perform_scan()


    # =====================================================
    # MAIN LAYOUT
    # =====================================================

    left_col, right_col = st.columns(
        [35, 65],
        gap="small"
    )


    # =====================================================
    # LEFT STOCK LIST
    # =====================================================

    with left_col:

        st.markdown(
            "**Scanner**"
        )


        # -------------------------------------------------
        # TABLE HEADERS
        # -------------------------------------------------

        h1, h2, h3, h4, h5 = st.columns(
            [2.2, 1.5, 1.5, 1.5, 2.0]
        )


        with h1:
            st.caption("Symbol")


        with h2:
            st.caption("LTP")


        with h3:
            st.caption("%")


        with h4:
            st.caption("RVOL")


        with h5:
            st.caption("$Vol")


        df = (
            st.session_state.scan_results
        )


        # -------------------------------------------------
        # NO RESULTS
        # -------------------------------------------------

        if df.empty:

            st.info(
                "No stocks match filters."
            )


        # -------------------------------------------------
        # RESULTS
        # -------------------------------------------------

        else:

            for _, row in df.iterrows():

                symbol = row["Symbol"]


                # Repeat marker

                repeat_mark = ""

                if row["Repeat"]:

                    repeat_mark = " ■"


                c1, c2, c3, c4, c5 = st.columns(
                    [2.2, 1.5, 1.5, 1.5, 2.0]
                )


                # -----------------------------------------
                # SYMBOL
                # -----------------------------------------

                with c1:

                    if st.button(
                        f"{symbol}{repeat_mark}",
                        key=f"stock_{symbol}",
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

                    st.markdown(
                        f"""
                        <div class="stock-row">
                            {row["Price"]:.2f}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


                # -----------------------------------------
                # CHANGE
                # -----------------------------------------

                with c3:

                    st.markdown(
                        f"""
                        <div class="stock-row">
                            {row["Change"]:.2f}%
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


                # -----------------------------------------
                # RVOL
                # -----------------------------------------

                with c4:

                    st.markdown(
                        f"""
                        <div class="stock-row">
                            {row["RVOL"]:.2f}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


                # -----------------------------------------
                # DOLLAR VOLUME
                # -----------------------------------------

                with c5:

                    dollar = float(
                        row["Dollar"]
                    )


                    if dollar >= 1_000_000_000:

                        dollar_text = (
                            f"${dollar / 1_000_000_000:.2f}B"
                        )

                    elif dollar >= 1_000_000:

                        dollar_text = (
                            f"${dollar / 1_000_000:.2f}M"
                        )

                    elif dollar >= 1_000:

                        dollar_text = (
                            f"${dollar / 1_000:.0f}K"
                        )

                    else:

                        dollar_text = (
                            f"${dollar:.0f}"
                        )


                    st.markdown(
                        f"""
                        <div class="stock-row">
                            {dollar_text}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


    # =====================================================
    # RIGHT TRADINGVIEW
    # =====================================================

    with right_col:

        symbol = (
            st.session_state.selected_symbol
        )


        exchange = EXCHANGE_MAP.get(
            symbol,
            "NASDAQ"
        )


        st.markdown(
            f"**{exchange}:{symbol}**"
        )


        interval = settings[
            "chart_interval"
        ]


        tv_symbol = (
            f"{exchange}%3A{symbol}"
        )


        chart_url = (
            "https://www.tradingview.com/"
            "embed-widget/advanced-chart/"
            f"?symbol={tv_symbol}"
            f"&interval={interval}"
            "&timezone=America%2FNew_York"
            "&theme=dark"
            "&style=1"
            "&locale=en"
            "&enable_publishing=false"
            "&hide_top_toolbar=false"
            "&hide_legend=false"
            "&hide_side_toolbar=true"
            "&allow_symbol_change=false"
            "&save_image=false"
            "&withdateranges=true"
            "&hide_volume=false"
        )


        components.iframe(
            chart_url,
            height=720,
            scrolling=False
        )


# =========================================================
# START SCANNER
# =========================================================

live_scanner()


# =========================================================
# FOOTER
# =========================================================

st.caption(
    f"Scan #{st.session_state.scan_count} "
    f"• Webull OpenAPI "
    f"• Repeat stock = ■"
)
