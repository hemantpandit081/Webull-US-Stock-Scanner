import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    padding-top: 0.4rem !important;
    padding-bottom: 0rem !important;
    padding-left: 0.25rem !important;
    padding-right: 0.25rem !important;
    max-width: 100% !important;
}

[data-testid="stSidebar"] {
    width: 280px;
}

div[data-testid="column"] {
    padding-left: 2px !important;
    padding-right: 2px !important;
}

div.stButton > button {
    min-height: 27px !important;
    height: 27px !important;
    padding: 0px 4px !important;
    font-size: 12px !important;
}

.stock-value {
    font-size: 12px;
    padding-top: 4px;
    white-space: nowrap;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# WEBULL
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

            with open(SETTINGS_FILE, "r") as file:

                saved = json.load(file)

            result = DEFAULT_SETTINGS.copy()
            result.update(saved)

            return result

        except Exception:
            pass

    return DEFAULT_SETTINGS.copy()


def save_settings():

    try:

        with open(SETTINGS_FILE, "w") as file:

            json.dump(
                st.session_state.settings,
                file,
                indent=4
            )

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


if "volume_history" not in st.session_state:

    st.session_state.volume_history = {}


if "scan_results" not in st.session_state:

    st.session_state.scan_results = pd.DataFrame()


if "scan_count" not in st.session_state:

    st.session_state.scan_count = 0


if "last_scan_time" not in st.session_state:

    st.session_state.last_scan_time = None


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
# TRADINGVIEW EXCHANGE
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

            return symbol, None

        data = response.json()

        if isinstance(data, list):

            if not data:

                return symbol, None

            return symbol, data[0]

        return symbol, data

    except Exception:

        return symbol, None


# =========================================================
# FAST PARALLEL SNAPSHOT REQUEST
# =========================================================

def get_all_snapshots():

    snapshots = {}

    # -----------------------------------------------------
    # Request multiple stocks simultaneously
    # -----------------------------------------------------

    max_workers = min(10, len(STOCKS))

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

            try:

                symbol, data = future.result()

                if data is not None:

                    snapshots[symbol] = data

            except Exception:

                continue

    return snapshots


# =========================================================
# REPEAT VOLUME
# =========================================================

def check_repeat_volume(
    symbol,
    current_volume
):

    if current_volume <= 0:

        return False

    history = st.session_state.volume_history.get(
        symbol,
        []
    )

    # First reading
    if not history:

        st.session_state.volume_history[symbol] = [
            current_volume
        ]

        return False

    tolerance = float(
        settings["repeat_tolerance"]
    )

    lower = tolerance
    upper = 1.0 / tolerance

    repeat_found = False

    for old_volume in history:

        if old_volume <= 0:

            continue

        ratio = current_volume / old_volume

        if lower <= ratio <= upper:

            repeat_found = True
            break

    history.append(current_volume)

    if len(history) > 200:

        history = history[-200:]

    st.session_state.volume_history[symbol] = history

    return repeat_found


# =========================================================
# PROCESS ONE STOCK
# =========================================================

def process_stock(
    symbol,
    data
):

    try:

        price = float(
            data.get("price", 0) or 0
        )

        change_ratio = float(
            data.get("change_ratio", 0) or 0
        )

        change_percent = change_ratio * 100

        volume = float(
            data.get("volume", 0) or 0
        )

        dollar_volume = price * volume

        previous_volume = (
            st.session_state.previous_volumes.get(
                symbol
            )
        )

        if (
            previous_volume is not None
            and previous_volume > 0
        ):

            rvol = volume / previous_volume

        else:

            rvol = 1.0

        repeat = check_repeat_volume(
            symbol,
            volume
        )

        # Save volume for next scan
        st.session_state.previous_volumes[
            symbol
        ] = volume

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
            "Repeat": repeat
        }

    except Exception:

        return None


# =========================================================
# FAST SCANNER
# =========================================================

def scan_stocks():

    # -----------------------------------------------------
    # STEP 1
    # Get all Webull snapshots in parallel
    # -----------------------------------------------------

    snapshots = get_all_snapshots()

    results = []

    # -----------------------------------------------------
    # STEP 2
    # Process returned data
    # -----------------------------------------------------

    for symbol in STOCKS:

        data = snapshots.get(symbol)

        if data is None:

            continue

        result = process_stock(
            symbol,
            data
        )

        if result is not None:

            results.append(result)

    # -----------------------------------------------------
    # Empty result
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # DataFrame
    # -----------------------------------------------------

    df = pd.DataFrame(results)

    # -----------------------------------------------------
    # Sort
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

    return df.reset_index(drop=True)


# =========================================================
# PERFORM SCAN
# =========================================================

def perform_scan():

    start = datetime.now()

    df = scan_stocks()

    st.session_state.scan_results = df

    st.session_state.scan_count += 1

    st.session_state.last_scan_time = datetime.now(
        ZoneInfo("Australia/Adelaide")
    )

    elapsed = (
        datetime.now() - start
    ).total_seconds()

    st.session_state.last_scan_seconds = elapsed


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("## ⚙️ Filters")

    # -----------------------------------------------------
    # PRICE
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # VOLUME
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # MOMENTUM
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # REPEAT
    # -----------------------------------------------------

    st.markdown("### Repeat Volume")

    repeat_tolerance = st.slider(
        "Repeat tolerance",
        min_value=0.50,
        max_value=1.00,
        value=float(settings["repeat_tolerance"]),
        step=0.01
    )

    st.caption(
        "0.90 = approximately ±10% volume range."
    )

    # -----------------------------------------------------
    # SCANNER
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # CHART
    # -----------------------------------------------------

    st.markdown("### Chart")

    intervals = [
        "1",
        "3",
        "5",
        "15",
        "30",
        "60",
        "240",
        "D"
    ]

    current_interval = str(
        settings["chart_interval"]
    )

    if current_interval not in intervals:

        current_interval = "1"

    chart_interval = st.selectbox(
        "Interval",
        intervals,
        index=intervals.index(
            current_interval
        )
    )

    # -----------------------------------------------------
    # UPDATE
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    if st.button(
        "💾 Save settings",
        use_container_width=True
    ):

        save_settings()

        st.success("Saved")

    # -----------------------------------------------------
    # RESET
    # -----------------------------------------------------

    if st.button(
        "🗑️ Reset volume history",
        use_container_width=True
    ):

        st.session_state.previous_volumes = {}

        st.session_state.volume_history = {}

        st.session_state.scan_results = pd.DataFrame()

        st.success("Volume history reset")

        st.rerun()


# =========================================================
# HEADER
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

        st.success("🟢 MARKET OPEN")

    else:

        st.info("🔴 MARKET CLOSED")


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
def scanner():

    # -----------------------------------------------------
    # FIRST SCAN
    # -----------------------------------------------------

    if st.session_state.scan_results.empty:

        perform_scan()

    df = st.session_state.scan_results

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    s1, s2, s3, s4, s5 = st.columns(
        [1.5, 1.5, 2, 2, 3]
    )

    with s1:

        st.caption(
            f"Stocks: {len(df)}"
        )

    with s2:

        st.caption(
            f"Scan: #{st.session_state.scan_count}"
        )

    with s3:

        if st.session_state.last_scan_time:

            st.caption(
                "Last: "
                + st.session_state.last_scan_time.strftime(
                    "%H:%M:%S"
                )
            )

    with s4:

        scan_time = st.session_state.get(
            "last_scan_seconds",
            0
        )

        st.caption(
            f"Speed: {scan_time:.1f}s"
        )

    with s5:

        st.caption(
            "Auto: "
            + (
                "ON"
                if settings["auto_scan"]
                else "OFF"
            )
            + f" • {settings['refresh_seconds']} sec"
        )

    # =====================================================
    # 35 / 65
    # =====================================================

    left, right = st.columns(
        [35, 65]
    )

    # =====================================================
    # LEFT
    # =====================================================

    with left:

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

        if df.empty:

            st.info(
                "No stocks match filters."
            )

        else:

            for _, row in df.iterrows():

                symbol = row["Symbol"]

                repeat = bool(
                    row["Repeat"]
                )

                c1, c2, c3, c4, c5 = st.columns(
                    [1.5, 1.0, 1.0, 1.0, 1.3]
                )

                # SYMBOL

                with c1:

                    label = (
                        "■ " + symbol
                        if repeat
                        else symbol
                    )

                    if st.button(
                        label,
                        key="symbol_" + symbol,
                        use_container_width=True
                    ):

                        st.session_state.selected_symbol = symbol

                        st.rerun()

                # PRICE

                with c2:

                    st.markdown(
                        f"""
                        <div class="stock-value">
                            {row["Price"]:.2f}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                # CHANGE

                with c3:

                    st.markdown(
                        f"""
                        <div class="stock-value">
                            {row["Change"]:.2f}%
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                # RVOL

                with c4:

                    st.markdown(
                        f"""
                        <div class="stock-value">
                            {row["RVOL"]:.2f}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                # DOLLAR VOLUME

                with c5:

                    dollar = float(
                        row["Dollar"]
                    )

                    if dollar >= 1_000_000_000:

                        text = (
                            f"${dollar / 1_000_000_000:.2f}B"
                        )

                    elif dollar >= 1_000_000:

                        text = (
                            f"${dollar / 1_000_000:.2f}M"
                        )

                    elif dollar >= 1_000:

                        text = (
                            f"${dollar / 1_000:.1f}K"
                        )

                    else:

                        text = (
                            f"${dollar:.0f}"
                        )

                    st.markdown(
                        f"""
                        <div class="stock-value">
                            {text}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    # =====================================================
    # RIGHT CHART
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
            height=600
        )


# =========================================================
# RUN
# =========================================================

scanner()


# =========================================================
# FOOTER
# =========================================================

st.caption(
    "Webull US Momentum Scanner • Fast parallel snapshot scanning"
)
