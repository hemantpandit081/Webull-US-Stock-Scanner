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

    /* Keep normal Streamlit header visible */
    .block-container {
        padding-top: 0.65rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0.35rem !important;
        padding-right: 0.35rem !important;
        max-width: 100% !important;
    }

    [data-testid="stSidebar"] {
        width: 280px;
    }

    div[data-testid="column"] {
        padding-left: 3px;
        padding-right: 3px;
    }

    /* Stock rows */
    .stock-row {
        font-size: 12px;
        line-height: 1.1;
    }

    .repeat-box {
        color: white;
        font-weight: 900;
        margin-right: 4px;
    }

    /* Compact buttons */
    div.stButton > button {
        min-height: 28px;
        height: 28px;
        padding-top: 0px;
        padding-bottom: 0px;
        padding-left: 6px;
        padding-right: 6px;
        font-size: 12px;
    }

    /* Reduce vertical gaps */
    div[data-testid="stVerticalBlock"] {
        gap: 0.25rem;
    }

    /* Dataframe */
    [data-testid="stDataFrame"] {
        font-size: 12px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# WEBULL SETTINGS
# =========================================================

APP_KEY = st.secrets["WEBULL_APP_KEY"]
APP_SECRET = st.secrets["WEBULL_APP_SECRET"]


@st.cache_resource
def create_webull_client():

    client = ApiClient(
        APP_KEY,
        APP_SECRET,
        "au"
    )

    client.add_endpoint(
        "au",
        "api.webull.com.au"
    )

    return DataClient(client)


data_client = create_webull_client()


# =========================================================
# SETTINGS FILE
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
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)

            settings = DEFAULT_SETTINGS.copy()
            settings.update(saved)

            return settings

        except Exception:
            pass

    return DEFAULT_SETTINGS.copy()


def save_settings():

    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(st.session_state.settings, f, indent=4)

    except Exception:
        pass


if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

settings = st.session_state.settings


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

if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = None


# =========================================================
# US STOCK UNIVERSE
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
# TRADINGVIEW EXCHANGE MAP
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
    "NIO": "NYSE"
}


# =========================================================
# MARKET STATUS
# =========================================================

def market_is_open():

    now = datetime.now(
        ZoneInfo("America/New_York")
    )

    if now.weekday() >= 5:
        return False

    minutes = now.hour * 60 + now.minute

    return 570 <= minutes <= 960


# =========================================================
# WEBULL SNAPSHOT
# =========================================================

def get_snapshot(symbol):

    try:

        response = data_client.market_data.get_snapshot(
            symbol,
            "US_STOCK"
        )

        if response.status_code != 200:
            return None

        data = response.json()

        if isinstance(data, list):

            if not data:
                return None

            return data[0]

        return data

    except Exception:

        return None


# =========================================================
# REPEAT VOLUME
# =========================================================

def check_repeat_volume(symbol, current_volume):

    previous_volume = st.session_state.previous_volumes.get(
        symbol
    )

    is_repeat = False

    if previous_volume and previous_volume > 0:

        ratio = current_volume / previous_volume

        tolerance = settings["repeat_tolerance"]

        if ratio >= tolerance:

            is_repeat = True

    st.session_state.previous_volumes[symbol] = current_volume

    if is_repeat:

        st.session_state.repeat_stocks.add(symbol)

    return symbol in st.session_state.repeat_stocks


# =========================================================
# SCANNER
# =========================================================

def scan_stocks():

    results = []

    for symbol in STOCKS:

        data = get_snapshot(symbol)

        if not data:
            continue

        try:

            # ---------------------------------------------
            # PRICE
            # ---------------------------------------------

            price = float(
                data.get("price", 0) or 0
            )

            # ---------------------------------------------
            # CHANGE %
            # ---------------------------------------------

            change_ratio = float(
                data.get("change_ratio", 0) or 0
            )

            change_percent = change_ratio * 100

            # ---------------------------------------------
            # VOLUME
            # ---------------------------------------------

            volume = float(
                data.get("volume", 0) or 0
            )

            # ---------------------------------------------
            # DOLLAR VOLUME
            # ---------------------------------------------

            dollar_volume = price * volume

            # ---------------------------------------------
            # RVOL
            # ---------------------------------------------

            previous_volume = (
                st.session_state.previous_volumes.get(symbol)
            )

            if previous_volume and previous_volume > 0:

                rvol = volume / previous_volume

            else:

                rvol = 1.0

            # ---------------------------------------------
            # REPEAT VOLUME
            # ---------------------------------------------

            repeat = check_repeat_volume(
                symbol,
                volume
            )

            # ---------------------------------------------
            # FILTERS
            # ---------------------------------------------

            if price < settings["min_price"]:
                continue

            if price > settings["max_price"]:
                continue

            if volume < settings["min_volume"]:
                continue

            if rvol < settings["min_rvol"]:
                continue

            if change_percent < settings["min_change"]:
                continue

            if dollar_volume < settings["min_dollar_volume"]:
                continue

            results.append(
                {
                    "Symbol": symbol,
                    "Price": price,
                    "Change": change_percent,
                    "RVOL": rvol,
                    "Volume": volume,
                    "Dollar": dollar_volume,
                    "Repeat": repeat
                }
            )

        except Exception:

            continue

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

    # Repeat first
    # Then RVOL
    # Then percentage change

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

    return df.reset_index(drop=True)


# =========================================================
# PERFORM SCAN
# =========================================================

def perform_scan():

    result = scan_stocks()

    st.session_state.scan_results = result

    st.session_state.scan_count += 1

    st.session_state.last_scan_time = datetime.now(
        ZoneInfo("Australia/Adelaide")
    )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("## ⚙️ Scanner Filters")

    st.markdown("### Price")

    min_price = st.number_input(
        "Minimum price",
        min_value=0.0,
        value=float(settings["min_price"]),
        step=0.50
    )

    max_price = st.number_input(
        "Maximum price",
        min_value=0.0,
        value=float(settings["max_price"]),
        step=5.0
    )

    st.markdown("### Volume")

    min_volume = st.number_input(
        "Minimum volume",
        min_value=0,
        value=int(settings["min_volume"]),
        step=10000
    )

    min_dollar_volume = st.number_input(
        "Minimum $ volume",
        min_value=0,
        value=int(settings["min_dollar_volume"]),
        step=100000
    )

    st.markdown("### Momentum")

    min_rvol = st.number_input(
        "Minimum RVOL",
        min_value=0.0,
        value=float(settings["min_rvol"]),
        step=0.1
    )

    min_change = st.number_input(
        "Minimum change %",
        min_value=-100.0,
        value=float(settings["min_change"]),
        step=0.5
    )

    st.markdown("### Repeat Volume")

    repeat_tolerance = st.slider(
        "Repeat tolerance",
        min_value=0.50,
        max_value=1.00,
        value=float(settings["repeat_tolerance"]),
        step=0.01
    )

    st.caption(
        "0.90 = current volume must be at least 90% "
        "of the previous observed volume."
    )

    st.markdown("### Scanner")

    refresh_seconds = st.number_input(
        "Refresh seconds",
        min_value=10,
        max_value=600,
        value=int(settings["refresh_seconds"]),
        step=10
    )

    auto_scan = st.checkbox(
        "Automatic scan",
        value=bool(settings["auto_scan"])
    )

    st.markdown("### TradingView")

    chart_interval = st.selectbox(
        "Chart interval",
        [
            "1",
            "3",
            "5",
            "15",
            "30",
            "60",
            "240",
            "D"
        ],
        index=[
            "1",
            "3",
            "5",
            "15",
            "30",
            "60",
            "240",
            "D"
        ].index(
            str(settings["chart_interval"])
        )
    )

    # Save settings

    settings["min_price"] = min_price
    settings["max_price"] = max_price
    settings["min_volume"] = min_volume
    settings["min_dollar_volume"] = min_dollar_volume
    settings["min_rvol"] = min_rvol
    settings["min_change"] = min_change
    settings["repeat_tolerance"] = repeat_tolerance
    settings["refresh_seconds"] = refresh_seconds
    settings["auto_scan"] = auto_scan
    settings["chart_interval"] = chart_interval

    if st.button(
        "💾 Save settings",
        use_container_width=True
    ):

        save_settings()

        st.success("Settings saved")


# =========================================================
# TOP HEADER
# =========================================================

header1, header2, header3 = st.columns(
    [5, 2, 2]
)


with header1:

    st.markdown(
        "### 📈 US Momentum Stock Scanner"
    )


with header2:

    if market_is_open():

        st.success(
            "🟢 US MARKET OPEN",
            icon="📈"
        )

    else:

        st.info(
            "🔴 US MARKET CLOSED",
            icon="⏱️"
        )


with header3:

    if st.button(
        "🔄 Scan Now",
        use_container_width=True
    ):

        perform_scan()

        st.rerun()


# =========================================================
# SCANNER FRAGMENT
# =========================================================

@st.fragment(
    run_every=(
        int(settings["refresh_seconds"])
        if settings["auto_scan"]
        else None
    )
)
def scanner_fragment():

    # First scan

    if st.session_state.scan_results.empty:

        perform_scan()

    df = st.session_state.scan_results


    # =====================================================
    # STATUS BAR
    # =====================================================

    status1, status2, status3, status4 = st.columns(
        [2, 2, 2, 4]
    )

    with status1:

        st.caption(
            f"Stocks: {len(df)}"
        )

    with status2:

        st.caption(
            f"Scan: #{st.session_state.scan_count}"
        )

    with status3:

        if st.session_state.last_scan_time:

            st.caption(
                "Last: "
                + st.session_state.last_scan_time.strftime(
                    "%H:%M:%S"
                )
            )

    with status4:

        st.caption(
            f"Auto scan: "
            f"{'ON' if settings['auto_scan'] else 'OFF'} "
            f"• Every {settings['refresh_seconds']} sec"
        )


    # =====================================================
    # MAIN LAYOUT
    # =====================================================

    left, right = st.columns(
        [35, 65]
    )


    # =====================================================
    # LEFT — STOCK LIST
    # =====================================================

    with left:

        # Header

        h1, h2, h3, h4, h5 = st.columns(
            [1.5, 1.0, 1.0, 1.0, 1.3]
        )

        with h1:
            st.caption("SYMBOL")

        with h2:
            st.caption("LTP")

        with h3:
            st.caption("%")

        with h4:
            st.caption("RVOL")

        with h5:
            st.caption("$VOL")


        st.divider()


        # Stock rows

        if df.empty:

            st.info(
                "No stocks match the current filters."
            )

        else:

            for _, row in df.iterrows():

                symbol = row["Symbol"]

                repeat = bool(row["Repeat"])

                c1, c2, c3, c4, c5 = st.columns(
                    [1.5, 1.0, 1.0, 1.0, 1.3]
                )


                # -----------------------------------------
                # SYMBOL BUTTON
                # -----------------------------------------

                with c1:

                    if repeat:

                        button_label = (
                            "■ " + symbol
                        )

                    else:

                        button_label = symbol


                    if st.button(
                        button_label,
                        key=f"stock_{symbol}",
                        use_container_width=True
                    ):

                        st.session_state.selected_symbol = symbol

                        st.rerun()


                # -----------------------------------------
                # PRICE
                # -----------------------------------------

                with c2:

                    st.markdown(
                        f"<div class='stock-row'>"
                        f"{row['Price']:.2f}"
                        f"</div>",
                        unsafe_allow_html=True
                    )


                # -----------------------------------------
                # CHANGE
                # -----------------------------------------

                with c3:

                    st.markdown(
                        f"<div class='stock-row'>"
                        f"{row['Change']:.2f}%"
                        f"</div>",
                        unsafe_allow_html=True
                    )


                # -----------------------------------------
                # RVOL
                # -----------------------------------------

                with c4:

                    st.markdown(
                        f"<div class='stock-row'>"
                        f"{row['RVOL']:.2f}"
                        f"</div>",
                        unsafe_allow_html=True
                    )


                # -----------------------------------------
                # DOLLAR VOLUME
                # -----------------------------------------

                with c5:

                    dollar = row["Dollar"]

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
                            f"${dollar / 1_000:.1f}K"
                        )

                    else:

                        dollar_text = (
                            f"${dollar:.0f}"
                        )


                    st.markdown(
                        f"<div class='stock-row'>"
                        f"{dollar_text}"
                        f"</div>",
                        unsafe_allow_html=True
                    )


    # =====================================================
    # RIGHT — TRADINGVIEW
    # =====================================================

    with right:

        symbol = st.session_state.selected_symbol

        exchange = EXCHANGE_MAP.get(
            symbol,
            "NASDAQ"
        )


        st.markdown(
            f"#### {symbol}"
        )


        # -------------------------------------------------
        # TradingView widget
        #
        # IMPORTANT:
        # hide_side_toolbar=0
        #
        # This displays the LEFT drawing toolbar.
        # -------------------------------------------------

        tradingview_url = (
            "https://www.tradingview.com/widgetembed/"
            "?frameElementId=tradingview_chart"
            f"&symbol={exchange}%3A{symbol}"
            f"&interval={settings['chart_interval']}"
            "&hide_side_toolbar=0"
            "&allow_symbol_change=1"
            "&save_image=1"
            "&hide_volume=0"
            "&theme=dark"
            "&style=1"
            "&timezone=Australia%2FAdelaide"
            "&withdateranges=1"
            "&hideideas=1"
        )


        components.html(
            f"""
            <iframe
                src="{tradingview_url}"
                style="
                    width:100%;
                    height:600px;
                    border:none;
                "
                frameborder="0"
                allowtransparency="true"
                scrolling="no">
            </iframe>
            """,
            height=780
        )


# =========================================================
# RUN SCANNER
# =========================================================

scanner_fragment()


# =========================================================
# FOOTER
# =========================================================

st.caption(
    "US Momentum Scanner • Webull market data • "
    "TradingView chart • Automatic scanner refresh"
)
