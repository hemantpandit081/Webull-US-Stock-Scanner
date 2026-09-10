import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
import streamlit.components.v1 as components

from webull.core.client import ApiClient
from webull.data.data_client import DataClient

# =========================================================
# PAGE CONFIG
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

st.markdown("""
<style>

.block-container {
    padding-top: 0.5rem;
    padding-bottom: 0rem;
    padding-left: 0.5rem;
    padding-right: 0.5rem;
}

[data-testid="stSidebar"] {
    width: 280px;
}

div.stButton > button {
    padding: 2px 6px;
    min-height: 28px;
    font-size: 13px;
}

.stock-row {
    font-size: 13px;
    padding: 3px 2px;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# WEBULL SETTINGS
# =========================================================

APP_KEY = st.secrets["WEBULL_APP_KEY"]
APP_SECRET = st.secrets["WEBULL_APP_SECRET"]

MAX_WORKERS = 10


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

            with open(
                SETTINGS_FILE,
                "r"
            ) as f:

                saved = json.load(f)

            return {
                **DEFAULT_SETTINGS,
                **saved
            }

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


# =========================================================
# SESSION STATE
# =========================================================

if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

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

if "scan_duration" not in st.session_state:
    st.session_state.scan_duration = 0


settings = st.session_state.settings


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
# TRADINGVIEW EXCHANGES
# =========================================================

TRADINGVIEW_EXCHANGE = {

    "BAC": "NYSE",
    "JPM": "NYSE",
    "WMT": "NYSE",
    "UBER": "NYSE",
    "NIO": "NYSE"

}


def get_exchange(symbol):

    return TRADINGVIEW_EXCHANGE.get(
        symbol,
        "NASDAQ"
    )


# =========================================================
# MARKET STATUS
# =========================================================

def market_is_open():

    now = datetime.now(
        ZoneInfo("America/New_York")
    )

    if now.weekday() >= 5:
        return False

    current_time = now.hour * 60 + now.minute

    market_open = 9 * 60 + 30
    market_close = 16 * 60

    return (
        market_open
        <= current_time
        < market_close
    )


# =========================================================
# GET ONE STOCK SNAPSHOT
# =========================================================

def get_snapshot(symbol):

    try:

        response = data_client.market_data.get_snapshot(
            symbol,
            "US_STOCK"
        )

        if response is None:
            return None

        if isinstance(response, str):

            try:
                response = json.loads(response)

            except Exception:
                return None

        return response

    except Exception:

        return None


# =========================================================
# PARSE SNAPSHOT
# =========================================================

def parse_snapshot(symbol, data):

    try:

        if data is None:
            return None

        # -------------------------------------------------
        # Handle common Webull response structures
        # -------------------------------------------------

        if isinstance(data, dict):

            if "data" in data:

                data = data["data"]

            if isinstance(data, list):

                if len(data) == 0:
                    return None

                data = data[0]

        if not isinstance(data, dict):
            return None


        # -------------------------------------------------
        # PRICE
        # -------------------------------------------------

        price = (
            data.get("close")
            or data.get("latestPrice")
            or data.get("latest_price")
            or data.get("price")
            or data.get("lastPrice")
            or 0
        )


        # -------------------------------------------------
        # CHANGE
        # -------------------------------------------------

        change_ratio = (
            data.get("changeRatio")
            or data.get("change_ratio")
            or data.get("changePercent")
            or 0
        )


        # -------------------------------------------------
        # VOLUME
        # -------------------------------------------------

        volume = (
            data.get("volume")
            or data.get("tradeVolume")
            or data.get("totalVolume")
            or 0
        )


        try:
            price = float(price)
        except Exception:
            price = 0

        try:
            volume = float(volume)
        except Exception:
            volume = 0

        try:
            change_ratio = float(change_ratio)
        except Exception:
            change_ratio = 0


        # Webull change ratio normally comes as decimal
        if abs(change_ratio) < 1:

            change_percent = change_ratio * 100

        else:

            change_percent = change_ratio


        if price <= 0:
            return None

        if volume < 0:
            volume = 0


        dollar_volume = price * volume


        return {

            "Symbol": symbol,

            "Price": price,

            "Change": change_percent,

            "Volume": volume,

            "Dollar Volume": dollar_volume

        }


    except Exception:

        return None


# =========================================================
# REPEAT VOLUME DETECTION
# =========================================================

def check_repeat_volume(
    symbol,
    current_volume
):

    tolerance = settings["repeat_tolerance"]

    history = st.session_state.volume_history.get(
        symbol,
        []
    )

    if len(history) == 0:

        st.session_state.volume_history[symbol] = [
            current_volume
        ]

        return False


    lower = tolerance
    upper = 1 / tolerance


    repeat = False

    for old_volume in history:

        if old_volume <= 0:
            continue

        ratio = current_volume / old_volume

        if lower <= ratio <= upper:

            repeat = True
            break


    history.append(current_volume)


    # Keep last 200 readings
    if len(history) > 200:

        history = history[-200:]


    st.session_state.volume_history[symbol] = history


    return repeat


# =========================================================
# FAST PARALLEL SCANNER
# =========================================================

def scan_stocks():

    start_time = datetime.now()


    results = []

    current_previous_volumes = (
        st.session_state.previous_volumes.copy()
    )


    # -----------------------------------------------------
    # Make Webull requests in parallel
    # -----------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
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

                data = future.result()

            except Exception:

                data = None


            parsed = parse_snapshot(
                symbol,
                data
            )


            if parsed is None:
                continue


            price = parsed["Price"]

            change_percent = parsed["Change"]

            volume = parsed["Volume"]

            dollar_volume = parsed["Dollar Volume"]


            # -------------------------------------------------
            # RVOL
            # -------------------------------------------------

            previous_volume = (
                current_previous_volumes.get(
                    symbol,
                    0
                )
            )


            if previous_volume > 0:

                rvol = (
                    volume /
                    previous_volume
                )

            else:

                rvol = 0


            # -------------------------------------------------
            # REPEAT VOLUME
            # -------------------------------------------------

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


            results.append({

                "Symbol": symbol,

                "Price": price,

                "Change": change_percent,

                "Volume": volume,

                "RVOL": rvol,

                "Dollar Volume": dollar_volume,

                "Repeat": repeat

            })


    # -----------------------------------------------------
    # DATAFRAME
    # -----------------------------------------------------

    if results:

        df = pd.DataFrame(results)

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

    else:

        df = pd.DataFrame(
            columns=[
                "Symbol",
                "Price",
                "Change",
                "Volume",
                "RVOL",
                "Dollar Volume",
                "Repeat"
            ]
        )


    # -----------------------------------------------------
    # Scan information
    # -----------------------------------------------------

    end_time = datetime.now()

    duration = (
        end_time - start_time
    ).total_seconds()


    st.session_state.scan_duration = duration

    st.session_state.scan_results = df

    st.session_state.scan_count += 1

    st.session_state.last_scan_time = (
        datetime.now(
            ZoneInfo("Australia/Adelaide")
        )
    )


# =========================================================
# PERFORM SCAN
# =========================================================

def perform_scan():

    scan_stocks()


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header("Scanner Filters")


    st.subheader("Price")

    settings["min_price"] = st.number_input(
        "Minimum Price",
        min_value=0.0,
        value=float(settings["min_price"]),
        step=0.50
    )

    settings["max_price"] = st.number_input(
        "Maximum Price",
        min_value=0.0,
        value=float(settings["max_price"]),
        step=1.0
    )


    st.subheader("Volume")

    settings["min_volume"] = st.number_input(
        "Minimum Volume",
        min_value=0,
        value=int(settings["min_volume"]),
        step=10000
    )

    settings["min_dollar_volume"] = st.number_input(
        "Minimum $ Volume",
        min_value=0,
        value=int(settings["min_dollar_volume"]),
        step=100000
    )


    st.subheader("Momentum")

    settings["min_rvol"] = st.number_input(
        "Minimum RVOL",
        min_value=0.0,
        value=float(settings["min_rvol"]),
        step=0.1
    )

    settings["min_change"] = st.number_input(
        "Minimum Change %",
        min_value=-100.0,
        value=float(settings["min_change"]),
        step=0.5
    )


    st.subheader("Repeat Volume")

    settings["repeat_tolerance"] = st.slider(
        "Repeat tolerance",
        min_value=0.50,
        max_value=0.99,
        value=float(settings["repeat_tolerance"]),
        step=0.01
    )


    st.subheader("Scanner")

    settings["refresh_seconds"] = st.number_input(
        "Refresh Seconds",
        min_value=5,
        max_value=3600,
        value=int(settings["refresh_seconds"]),
        step=5
    )

    settings["auto_scan"] = st.checkbox(
        "Automatic Scan",
        value=bool(settings["auto_scan"])
    )


    st.subheader("TradingView")

    settings["chart_interval"] = st.selectbox(
        "Chart Interval",
        options=[
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


    st.divider()


    if st.button(
        "💾 Save Settings",
        use_container_width=True
    ):

        save_settings(settings)

        st.success(
            "Settings saved"
        )


    if st.button(
        "♻️ Reset Volume History",
        use_container_width=True
    ):

        st.session_state.previous_volumes = {}

        st.session_state.volume_history = {}

        st.success(
            "Volume history reset"
        )


# =========================================================
# HEADER
# =========================================================

header_col1, header_col2, header_col3 = st.columns(
    [5, 2, 2]
)


with header_col1:

    st.title(
        "📈 US Stock Momentum Scanner"
    )


with header_col2:

    if market_is_open():

        st.success(
            "🟢 US MARKET OPEN"
        )

    else:

        st.info(
            "🔴 US MARKET CLOSED"
        )


with header_col3:

    if st.button(
        "🔍 Scan Now",
        use_container_width=True
    ):

        perform_scan()

        st.rerun()


# =========================================================
# SCAN INFORMATION
# =========================================================

info_col1, info_col2, info_col3 = st.columns(
    3
)


with info_col1:

    st.caption(
        f"Scans: {st.session_state.scan_count}"
    )


with info_col2:

    if st.session_state.last_scan_time:

        st.caption(
            "Last scan: "
            +
            st.session_state.last_scan_time.strftime(
                "%H:%M:%S"
            )
        )


with info_col3:

    if st.session_state.scan_duration:

        st.caption(
            f"Scan speed: "
            f"{st.session_state.scan_duration:.2f}s"
        )


# =========================================================
# INITIAL SCAN
# =========================================================

if (
    st.session_state.scan_results.empty
    and st.session_state.scan_count == 0
):

    perform_scan()


# =========================================================
# AUTO SCANNER
# =========================================================

@st.fragment(
    run_every=(
        settings["refresh_seconds"]
        if settings["auto_scan"]
        else None
    )
)
def scanner_area():

    # -----------------------------------------------------
    # Run automatic scan
    # -----------------------------------------------------

    if settings["auto_scan"]:

        perform_scan()


    df = st.session_state.scan_results


    # -----------------------------------------------------
    # MAIN LAYOUT
    # 35% STOCK LIST
    # 65% TRADINGVIEW
    # -----------------------------------------------------

    left, right = st.columns(
        [35, 65],
        gap="small"
    )


    # =====================================================
    # LEFT - STOCK LIST
    # =====================================================

    with left:

        st.markdown(
            "### Scanner"
        )


        if df.empty:

            st.info(
                "No stocks match the filters."
            )

        else:

            # Header
            h1, h2, h3, h4, h5 = st.columns(
                [1.5, 1.0, 0.9, 0.9, 1.2]
            )

            h1.caption("Symbol")
            h2.caption("LTP")
            h3.caption("%")
            h4.caption("RVOL")
            h5.caption("$VOL")


            for _, row in df.iterrows():

                symbol = row["Symbol"]

                repeat = row["Repeat"]


                c1, c2, c3, c4, c5 = st.columns(
                    [1.5, 1.0, 0.9, 0.9, 1.2]
                )


                with c1:

                    indicator = "■ " if repeat else ""

                    if st.button(
                        f"{indicator}{symbol}",
                        key=f"stock_{symbol}",
                        use_container_width=True
                    ):

                        st.session_state.selected_symbol = symbol


                with c2:

                    st.caption(
                        f"${row['Price']:.2f}"
                    )


                with c3:

                    st.caption(
                        f"{row['Change']:.1f}%"
                    )


                with c4:

                    st.caption(
                        f"{row['RVOL']:.1f}x"
                    )


                with c5:

                    dollar_volume = (
                        row["Dollar Volume"]
                    )

                    if dollar_volume >= 1_000_000_000:

                        text = (
                            f"${dollar_volume / 1_000_000_000:.1f}B"
                        )

                    elif dollar_volume >= 1_000_000:

                        text = (
                            f"${dollar_volume / 1_000_000:.1f}M"
                        )

                    else:

                        text = (
                            f"${dollar_volume / 1_000:.0f}K"
                        )

                    st.caption(text)


    # =====================================================
    # RIGHT - TRADINGVIEW
    # =====================================================

    with right:

        symbol = st.session_state.selected_symbol

        exchange = get_exchange(symbol)


        st.markdown(
            f"### {symbol}"
        )


        # -------------------------------------------------
        # TradingView URL
        # -------------------------------------------------

        tv_url = (
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
                src="{tv_url}"
                width="100%"
                height="600"
                frameborder="0"
                allowtransparency="true"
                scrolling="no">
            </iframe>
            """,
            height=620
        )


# =========================================================
# RUN SCANNER
# =========================================================

scanner_area()


# =========================================================
# FOOTER
# =========================================================

st.caption(
    "Webull US Momentum Scanner • "
    "Parallel API scanning • "
    "Historical volume repeat detection"
)
