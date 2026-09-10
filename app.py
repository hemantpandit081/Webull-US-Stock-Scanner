import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components
from concurrent.futures import ThreadPoolExecutor, as_completed


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="US Stock Screener",
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

    /* Main page */
    .block-container {
        padding-top: 0.7rem;
        padding-bottom: 0.5rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
    }

    /* Compact buttons */
    div.stButton > button {
        height: 30px;
        padding: 0px 8px;
        font-size: 13px;
        border-radius: 4px;
    }

    /* Scanner table */
    .scanner-row {
        font-size: 13px;
        line-height: 1.2;
        padding: 2px 4px;
        margin: 1px 0px;
        border-bottom: 1px solid rgba(128,128,128,0.15);
    }

    /* Header */
    .scanner-header {
        font-size: 12px;
        font-weight: 700;
        padding: 4px;
        border-bottom: 1px solid rgba(128,128,128,0.3);
    }

    /* Small text */
    .small-text {
        font-size: 11px;
        opacity: 0.75;
    }

    /* Status */
    .status-box {
        font-size: 12px;
        padding: 3px 8px;
        border-radius: 4px;
        display: inline-block;
    }

    /* Reduce dataframe spacing */
    [data-testid="stDataFrame"] {
        font-size: 12px;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        width: 280px !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# WEBULL SETTINGS
# =========================================================

APP_KEY = os.getenv("WEBULL_APP_KEY")
APP_SECRET = os.getenv("WEBULL_APP_SECRET")


# =========================================================
# WEBULL CLIENT
# =========================================================

@st.cache_resource
def create_webull_client():

    if not APP_KEY or not APP_SECRET:
        return None

    try:

        from webullsdkcore import ApiClient
        from webullsdkquotes import DataClient

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

    except Exception as e:

        st.error(f"Webull connection error: {e}")

        return None


data_client = create_webull_client()


# =========================================================
# STOCK UNIVERSE
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
# COMPANY NAMES
# =========================================================

COMPANY_NAMES = {

    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "AMZN": "Amazon",
    "META": "Meta",
    "GOOGL": "Alphabet",
    "GOOG": "Alphabet",
    "TSLA": "Tesla",
    "AVGO": "Broadcom",
    "AMD": "AMD",
    "NFLX": "Netflix",
    "INTC": "Intel",
    "MU": "Micron",
    "QCOM": "Qualcomm",
    "AMAT": "Applied Materials",
    "ARM": "Arm",
    "PLTR": "Palantir",
    "SMCI": "Super Micro Computer",
    "COIN": "Coinbase",
    "HOOD": "Robinhood",
    "SOFI": "SoFi",
    "BAC": "Bank of America",
    "JPM": "JPMorgan",
    "WMT": "Walmart",
    "COST": "Costco",
    "UBER": "Uber",
    "SHOP": "Shopify",
    "PDD": "PDD Holdings",
    "NIO": "NIO",
    "RIVN": "Rivian"

}


# =========================================================
# TRADINGVIEW EXCHANGE
# =========================================================

TRADINGVIEW_EXCHANGE = {

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
    "SHOP": "NYSE",
    "PDD": "NASDAQ",
    "NIO": "NYSE",
    "RIVN": "NASDAQ"

}


# =========================================================
# TRADINGVIEW SYMBOL
# =========================================================

def tradingview_symbol(symbol):

    exchange = TRADINGVIEW_EXCHANGE.get(
        symbol,
        "NASDAQ"
    )

    return f"{exchange}:{symbol}"


# =========================================================
# DEFAULT SETTINGS
# =========================================================

DEFAULT_SETTINGS = {

    "min_price": 1.0,

    "max_price": 1000.0,

    "min_volume": 100000,

    "min_change": 0.0,

    "min_rvol": 0.0,

    "min_dollar_volume": 0,

    "repeat_tolerance": 0.90,

    "history_length": 30,

    "refresh_seconds": 60,

    "auto_refresh": True,

    "chart_interval": "1",

    "chart_theme": "dark",

    "show_volume": True,

    "timezone": "America/New_York"

}


# =========================================================
# SETTINGS FILE
# =========================================================

SETTINGS_FILE = "scanner_settings.json"


def load_settings():

    if os.path.exists(SETTINGS_FILE):

        try:

            with open(
                SETTINGS_FILE,
                "r"
            ) as f:

                saved = json.load(f)

            settings = DEFAULT_SETTINGS.copy()

            settings.update(saved)

            return settings

        except Exception:

            pass

    return DEFAULT_SETTINGS.copy()


def save_settings(settings):

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

    except Exception:

        pass


settings = load_settings()


# =========================================================
# SESSION STATE
# =========================================================

if "selected_symbol" not in st.session_state:

    st.session_state.selected_symbol = "NVDA"


if "volume_history" not in st.session_state:

    st.session_state.volume_history = {}


if "previous_volume" not in st.session_state:

    st.session_state.previous_volume = {}


if "repeat_symbols" not in st.session_state:

    st.session_state.repeat_symbols = set()


if "results" not in st.session_state:

    st.session_state.results = []


if "scan_number" not in st.session_state:

    st.session_state.scan_number = 0


if "last_scan" not in st.session_state:

    st.session_state.last_scan = None


# =========================================================
# MARKET TIME
# =========================================================

def market_time():

    try:

        return datetime.now(
            ZoneInfo(
                settings["timezone"]
            )
        )

    except Exception:

        return datetime.now()


def market_is_open():

    now = market_time()

    weekday = now.weekday()

    if weekday >= 5:

        return False

    current_minutes = (
        now.hour * 60
        + now.minute
    )

    open_minutes = (
        9 * 60
        + 30
    )

    close_minutes = (
        16 * 60
    )

    return (
        open_minutes
        <= current_minutes
        < close_minutes
    )


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

        return response

    except Exception:

        return None


# =========================================================
# PARALLEL SNAPSHOTS
# =========================================================

def get_all_snapshots():

    snapshots = {}

    max_workers = min(
        10,
        len(STOCKS)
    )

    with ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:

        futures = {

            executor.submit(
                get_snapshot,
                symbol
            ): symbol

            for symbol in STOCKS

        }

        for future in as_completed(futures):

            symbol = futures[future]

            try:

                snapshots[symbol] = (
                    future.result()
                )

            except Exception:

                snapshots[symbol] = None

    return snapshots


# =========================================================
# SAFE VALUE
# =========================================================

def safe_get(data, *keys):

    for key in keys:

        try:

            if isinstance(data, dict):

                value = data.get(key)

            else:

                value = getattr(
                    data,
                    key,
                    None
                )

            if value is not None:

                return value

        except Exception:

            pass

    return None


# =========================================================
# VOLUME HISTORY
# =========================================================

def add_volume(
    symbol,
    volume
):

    if symbol not in st.session_state.volume_history:

        st.session_state.volume_history[symbol] = []

    history = st.session_state.volume_history[symbol]

    history.append(volume)

    max_length = int(
        settings["history_length"]
    )

    if len(history) > max_length:

        history.pop(
            0
        )


# =========================================================
# REPEAT VOLUME DETECTION
# =========================================================

def detect_repeat(
    symbol,
    volume
):

    history = st.session_state.volume_history.get(
        symbol,
        []
    )

    # First observation
    if not history:

        add_volume(
            symbol,
            volume
        )

        return False

    tolerance = float(
        settings["repeat_tolerance"]
    )

    repeat_found = False

    for old_volume in history:

        if old_volume <= 0:
            continue

        ratio = volume / old_volume

        if (
            ratio >= tolerance
            and
            ratio <= (1 / tolerance)
        ):

            repeat_found = True
            break

    add_volume(
        symbol,
        volume
    )

    if repeat_found:

        st.session_state.repeat_symbols.add(
            symbol
        )

    return repeat_found


# =========================================================
# RVOL
# =========================================================

def calculate_rvol(
    symbol,
    current_volume
):

    previous = (
        st.session_state.previous_volume.get(
            symbol
        )
    )

    st.session_state.previous_volume[
        symbol
    ] = current_volume

    if previous is None:

        return 1.0

    if previous <= 0:

        return 1.0

    return (
        current_volume
        /
        previous
    )


# =========================================================
# NUMBER FORMAT
# =========================================================

def format_number(value):

    if value is None:

        return "-"

    try:

        value = float(value)

        if value >= 1_000_000_000:

            return f"{value / 1_000_000_000:.1f}B"

        if value >= 1_000_000:

            return f"{value / 1_000_000:.1f}M"

        if value >= 1_000:

            return f"{value / 1_000:.1f}K"

        return f"{value:.0f}"

    except Exception:

        return "-"


def format_price(value):

    if value is None:

        return "-"

    try:

        return f"${float(value):.2f}"

    except Exception:

        return "-"


def format_percent(value):

    if value is None:

        return "-"

    try:

        return f"{float(value):+.2f}%"

    except Exception:

        return "-"


# =========================================================
# PARSE SNAPSHOT
# =========================================================

def parse_snapshot(
    symbol,
    snapshot
):

    if snapshot is None:

        return None

    price = safe_get(
        snapshot,
        "lastPrice",
        "last_price",
        "price"
    )

    change = safe_get(
        snapshot,
        "changeRate",
        "change_rate",
        "changePercent",
        "change_percent"
    )

    volume = safe_get(
        snapshot,
        "volume",
        "totalVolume"
    )

    previous_close = safe_get(
        snapshot,
        "preClose",
        "pre_close",
        "previousClose",
        "previous_close"
    )

    # -----------------------------------------------------
    # Convert values
    # -----------------------------------------------------

    try:

        price = float(price)

    except Exception:

        return None

    try:

        volume = float(volume)

    except Exception:

        volume = 0

    try:

        change = float(change)

        # Some APIs return decimal change rate
        if abs(change) < 1:

            change = change * 100

    except Exception:

        change = 0


    # -----------------------------------------------------
    # Dollar volume
    # -----------------------------------------------------

    dollar_volume = (
        price * volume
    )


    # -----------------------------------------------------
    # RVOL
    # -----------------------------------------------------

    rvol = calculate_rvol(
        symbol,
        volume
    )


    # -----------------------------------------------------
    # Repeat volume
    # -----------------------------------------------------

    repeat = detect_repeat(
        symbol,
        volume
    )


    return {

        "Symbol": symbol,

        "Name": COMPANY_NAMES.get(
            symbol,
            symbol
        ),

        "Price": price,

        "Change": change,

        "Volume": volume,

        "DollarVolume": dollar_volume,

        "RVOL": rvol,

        "Repeat": repeat

    }


# =========================================================
# MARKET SCAN
# =========================================================

def scan_market():

    snapshots = get_all_snapshots()

    rows = []

    for symbol in STOCKS:

        snapshot = snapshots.get(
            symbol
        )

        result = parse_snapshot(
            symbol,
            snapshot
        )

        if result is None:

            continue

        # -------------------------------------------------
        # Filters
        # -------------------------------------------------

        if (
            result["Price"]
            <
            float(settings["min_price"])
        ):

            continue

        if (
            result["Price"]
            >
            float(settings["max_price"])
        ):

            continue

        if (
            result["Volume"]
            <
            int(settings["min_volume"])
        ):

            continue

        if (
            result["Change"]
            <
            float(settings["min_change"])
        ):

            continue

        if (
            result["RVOL"]
            <
            float(settings["min_rvol"])
        ):

            continue

        if (
            result["DollarVolume"]
            <
            float(settings["min_dollar_volume"])
        ):

            continue

        rows.append(
            result
        )


    # =====================================================
    # SORT
    # =====================================================

    rows.sort(

        key=lambda x: (

            x["Repeat"],

            x["RVOL"],

            x["Change"],

            x["DollarVolume"]

        ),

        reverse=True

    )

    return rows


# =========================================================
# PERFORM SCAN
# =========================================================

def perform_scan():

    results = scan_market()

    st.session_state.results = results

    st.session_state.scan_number += 1

    st.session_state.last_scan = datetime.now()


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header("Scanner Filters")


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


    min_change = st.number_input(
        "Minimum % change",
        value=float(
            settings["min_change"]
        ),
        step=0.5
    )


    min_rvol = st.number_input(
        "Minimum RVOL",
        min_value=0.0,
        value=float(
            settings["min_rvol"]
        ),
        step=0.1
    )


    min_dollar_volume = st.number_input(
        "Minimum dollar volume",
        min_value=0,
        value=int(
            settings["min_dollar_volume"]
        ),
        step=1_000_000
    )


    repeat_tolerance = st.slider(
        "Repeat volume tolerance",
        min_value=0.50,
        max_value=1.00,
        value=float(
            settings["repeat_tolerance"]
        ),
        step=0.01
    )


    history_length = st.number_input(
        "Volume history length",
        min_value=5,
        max_value=200,
        value=int(
            settings["history_length"]
        ),
        step=5
    )


    st.divider()

    st.subheader("Live Scanner")


    auto_refresh = st.checkbox(
        "Live scanning",
        value=bool(
            settings["auto_refresh"]
        )
    )


    # -----------------------------------------------------
    # KEEP SCAN AT 60 SECONDS
    # -----------------------------------------------------

    refresh_seconds = st.number_input(
        "Scan interval (seconds)",
        min_value=10,
        max_value=3600,
        value=60,
        step=10
    )


    st.divider()

    st.subheader("TradingView")


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
            str(
                settings["chart_interval"]
            )
        )
        if str(
            settings["chart_interval"]
        ) in [
            "1",
            "3",
            "5",
            "15",
            "30",
            "60",
            "240",
            "D"
        ]
        else 0
    )


    chart_theme = st.selectbox(
        "Chart theme",
        [
            "dark",
            "light"
        ],
        index=0
        if settings["chart_theme"] == "dark"
        else 1
    )


    show_volume = st.checkbox(
        "Show volume",
        value=bool(
            settings["show_volume"]
        )
    )


    # =====================================================
    # SAVE SETTINGS
    # =====================================================

    new_settings = {

        "min_price": min_price,

        "max_price": max_price,

        "min_volume": min_volume,

        "min_change": min_change,

        "min_rvol": min_rvol,

        "min_dollar_volume":
            min_dollar_volume,

        "repeat_tolerance":
            repeat_tolerance,

        "history_length":
            history_length,

        "refresh_seconds":
            60,

        "auto_refresh":
            auto_refresh,

        "chart_interval":
            chart_interval,

        "chart_theme":
            chart_theme,

        "show_volume":
            show_volume,

        "timezone":
            settings["timezone"]

    }


    if new_settings != settings:

        settings = new_settings

        save_settings(
            settings
        )

        st.session_state.results = []

        st.rerun()


# =========================================================
# INITIAL SCAN
# =========================================================

if not st.session_state.results:

    perform_scan()


# =========================================================
# HEADER
# =========================================================

header_left, header_middle, header_right = st.columns(
    [2, 4, 2]
)


with header_left:

    st.markdown(
        "## 📈 US Stock Screener"
    )


with header_middle:

    now = market_time()

    if market_is_open():

        st.markdown(
            f"🟢 **US Market OPEN** &nbsp; "
            f"{now.strftime('%H:%M:%S')}"
        )

    else:

        st.markdown(
            f"🔴 **US Market CLOSED** &nbsp; "
            f"{now.strftime('%H:%M:%S')}"
        )


with header_right:

    if st.button(
        "🔄 SCAN",
        use_container_width=True
    ):

        perform_scan()

        st.rerun()


st.divider()


# =========================================================
# LIVE SCANNER FRAGMENT
# =========================================================

@st.fragment(
    run_every=(
        60
        if settings["auto_refresh"]
        else None
    )
)
def live_scanner():

    # -----------------------------------------------------
    # Automatic scan
    # -----------------------------------------------------

    perform_scan()


    results = st.session_state.results


    # -----------------------------------------------------
    # Scanner status
    # -----------------------------------------------------

    col1, col2, col3 = st.columns(
        [2, 2, 4]
    )


    with col1:

        st.markdown(
            f"**Stocks:** {len(results)}"
        )


    with col2:

        st.markdown(
            f"**Scan:** {st.session_state.scan_number}"
        )


    with col3:

        if st.session_state.last_scan:

            st.markdown(
                "Last scan: "
                + st.session_state.last_scan.strftime(
                    "%H:%M:%S"
                )
            )


    st.markdown(
        "<div class='scanner-header'>"
        "Ticker &nbsp;&nbsp;&nbsp; "
        "Price &nbsp;&nbsp; "
        "Change &nbsp;&nbsp; "
        "Volume &nbsp;&nbsp; "
        "RVOL"
        "</div>",
        unsafe_allow_html=True
    )


    # -----------------------------------------------------
    # Stock list
    # -----------------------------------------------------

    for row in results:

        symbol = row["Symbol"]

        repeat_symbol = ""

        if (
            symbol
            in st.session_state.repeat_symbols
        ):

            repeat_symbol = " ■"


        col1, col2, col3, col4, col5 = st.columns(
            [1.7, 1, 1, 1.4, 1]
        )


        with col1:

            if st.button(
                f"{symbol}{repeat_symbol}",
                key=f"stock_{symbol}",
                use_container_width=True
            ):

                st.session_state.selected_symbol = symbol

                st.rerun()


        with col2:

            st.caption(
                format_price(
                    row["Price"]
                )
            )


        with col3:

            st.caption(
                format_percent(
                    row["Change"]
                )
            )


        with col4:

            st.caption(
                format_number(
                    row["Volume"]
                )
            )


        with col5:

            st.caption(
                f"{row['RVOL']:.2f}x"
            )


# =========================================================
# PAGE LAYOUT
# =========================================================

left_column, right_column = st.columns(
    [35, 65]
)


# =========================================================
# LEFT — SCANNER
# =========================================================

with left_column:

    live_scanner()


# =========================================================
# RIGHT — TRADINGVIEW
# =========================================================

with right_column:

    selected = st.session_state.selected_symbol

    tv_symbol = tradingview_symbol(
        selected
    )


    st.markdown(
        f"### {selected} — "
        f"{COMPANY_NAMES.get(selected, selected)}"
    )


    # -----------------------------------------------------
    # TradingView URL
    # -----------------------------------------------------

    volume_setting = (
        "true"
        if settings["show_volume"]
        else "false"
    )


    theme = settings["chart_theme"]

    interval = settings["chart_interval"]


    tradingview_url = (
        "https://www.tradingview.com/"
        "widgetembed/"
        f"?symbol={tv_symbol}"
        f"&interval={interval}"
        "&autosize=true"
        f"&theme={theme}"
        "&style=1"
        "&locale=en"
        "&enable_publishing=false"
        "&hide_top_toolbar=false"
        "&hide_legend=false"
        "&hide_side_toolbar=false"
        "&allow_symbol_change=false"
        "&save_image=false"
        "&withdateranges=true"
        "&hideideas=true"
        f"&volume={volume_setting}"
    )


    components.iframe(
        tradingview_url,
        height=600,
        scrolling=False
    )


# =========================================================
# FOOTER
# =========================================================

st.markdown(
    """
    <div class="small-text"
         style="text-align:center; margin-top:5px;">
        US Stock Screener • Webull Market Data •
        TradingView Chart
    </div>
    """,
    unsafe_allow_html=True
)
