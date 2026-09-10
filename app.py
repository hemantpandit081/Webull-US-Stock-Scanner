import streamlit as st
import pandas as pd
import json
import os
import requests
import io
from datetime import datetime
from zoneinfo import ZoneInfo
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
    padding-top: 1.5rem !important;
    padding-bottom: 1rem !important;
    padding-left: 0.7rem !important;
    padding-right: 0.7rem !important;
}

[data-testid="stSidebar"] {
    width: 280px;
}

div.stButton > button {
    padding: 2px 5px !important;
    min-height: 28px !important;
    height: 28px !important;
    font-size: 12px !important;
    margin: 0 !important;
}

.stock-cell {
    font-size: 12px;
    padding-top: 3px;
    padding-bottom: 3px;
    white-space: nowrap;
}

.scanner-heading {
    font-size: 10px;
    font-weight: 600;
    color: #AAAAAA;
    padding-top: 4px;
    padding-bottom: 5px;
    border-bottom: 1px solid #555555;
    white-space: nowrap;
}

.scanner-title {
    font-size: 20px;
    font-weight: 600;
    margin-top: 5px;
    margin-bottom: 6px;
}

.chart-title {
    font-size: 20px;
    font-weight: 600;
    margin-top: 5px;
    margin-bottom: 6px;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# WEBULL SETTINGS
# =========================================================

APP_KEY = st.secrets["WEBULL_APP_KEY"]
APP_SECRET = st.secrets["WEBULL_APP_SECRET"]

REGION = "au"
WEBULL_ENDPOINT = "api.webull.com.au"


@st.cache_resource
def create_webull_client():

    client = ApiClient(
        APP_KEY,
        APP_SECRET,
        REGION
    )

    client.add_endpoint(
        REGION,
        WEBULL_ENDPOINT
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

    "chart_interval": "1",

    # Whole market scanner
    "universe_limit": 5000,

    "batch_size": 20

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

    st.session_state.settings = (
        load_settings()
    )


if "selected_symbol" not in st.session_state:

    st.session_state.selected_symbol = "AAPL"


if "previous_volumes" not in st.session_state:

    st.session_state.previous_volumes = {}


if "volume_history" not in st.session_state:

    st.session_state.volume_history = {}


if "scan_results" not in st.session_state:

    st.session_state.scan_results = (
        pd.DataFrame()
    )


if "scan_count" not in st.session_state:

    st.session_state.scan_count = 0


if "last_scan_time" not in st.session_state:

    st.session_state.last_scan_time = None


if "scan_duration" not in st.session_state:

    st.session_state.scan_duration = 0


if "trigger_times" not in st.session_state:

    st.session_state.trigger_times = {}


if "active_symbols" not in st.session_state:

    st.session_state.active_symbols = set()


if "stock_universe" not in st.session_state:

    st.session_state.stock_universe = []


if "universe_loaded" not in st.session_state:

    st.session_state.universe_loaded = False


settings = st.session_state.settings


# =========================================================
# LOAD US STOCK UNIVERSE
# =========================================================

@st.cache_data(ttl=3600)
def download_us_stock_universe():

    symbols = set()

    # -----------------------------------------------------
    # NASDAQ LISTED
    # -----------------------------------------------------

    try:

        url = (
            "https://www.nasdaqtrader.com/"
            "dynamic/SymDir/nasdaqlisted.txt"
        )

        response = requests.get(
            url,
            timeout=20
        )

        if response.status_code == 200:

            text = response.text

            df = pd.read_csv(
                io.StringIO(text),
                sep="|"
            )

            if "Symbol" in df.columns:

                for _, row in df.iterrows():

                    symbol = str(
                        row["Symbol"]
                    ).strip().upper()

                    if not symbol:
                        continue

                    if symbol == "FILE CREATION TIME":
                        continue

                    # Exclude test issues
                    test_issue = str(
                        row.get(
                            "Test Issue",
                            "N"
                        )
                    ).upper()

                    if test_issue == "Y":
                        continue

                    # Exclude ETFs
                    etf = str(
                        row.get(
                            "ETF",
                            "N"
                        )
                    ).upper()

                    if etf == "Y":
                        continue

                    if (
                        symbol.isalpha()
                        and len(symbol) <= 5
                    ):

                        symbols.add(symbol)

    except Exception:
        pass


    # -----------------------------------------------------
    # OTHER US EXCHANGE LISTED
    # -----------------------------------------------------

    try:

        url = (
            "https://www.nasdaqtrader.com/"
            "dynamic/SymDir/otherlisted.txt"
        )

        response = requests.get(
            url,
            timeout=20
        )

        if response.status_code == 200:

            text = response.text

            df = pd.read_csv(
                io.StringIO(text),
                sep="|"
            )

            if "ACT Symbol" in df.columns:

                for _, row in df.iterrows():

                    symbol = str(
                        row["ACT Symbol"]
                    ).strip().upper()

                    if not symbol:
                        continue

                    if symbol == "FILE CREATION TIME":
                        continue

                    # Exclude ETFs
                    etf = str(
                        row.get(
                            "ETF",
                            "N"
                        )
                    ).upper()

                    if etf == "Y":
                        continue

                    if (
                        symbol.isalpha()
                        and len(symbol) <= 5
                    ):

                        symbols.add(symbol)

    except Exception:
        pass


    # -----------------------------------------------------
    # SORT
    # -----------------------------------------------------

    symbols = sorted(
        list(symbols)
    )


    return symbols


# =========================================================
# LOAD UNIVERSE
# =========================================================

try:

    universe = download_us_stock_universe()

    if universe:

        st.session_state.stock_universe = (
            universe
        )

        st.session_state.universe_loaded = True

except Exception:

    pass


# =========================================================
# FALLBACK
# =========================================================

if not st.session_state.stock_universe:

    st.session_state.stock_universe = [

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

TRADINGVIEW_EXCHANGE = {

    "BAC": "NYSE",
    "JPM": "NYSE",
    "WMT": "NYSE",
    "UBER": "NYSE",
    "NIO": "NYSE",
    "RIVN": "NASDAQ"

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

    current_time = (
        now.hour * 60
        + now.minute
    )

    market_open = (
        9 * 60 + 30
    )

    market_close = (
        16 * 60
    )

    return (
        market_open
        <= current_time
        < market_close
    )


# =========================================================
# SNAPSHOT
# =========================================================

def get_snapshot(symbol):

    try:

        response = (
            data_client.market_data.get_snapshot(
                symbol,
                "US_STOCK"
            )
        )

        if response is None:
            return None

        if isinstance(
            response,
            str
        ):

            try:

                response = json.loads(
                    response
                )

            except Exception:

                return None

        return response

    except Exception:

        return None


# =========================================================
# PARSE SNAPSHOT
# =========================================================

def parse_snapshot(
    symbol,
    data
):

    try:

        if data is None:
            return None


        if isinstance(
            data,
            dict
        ):

            if "data" in data:

                data = data["data"]


            if isinstance(
                data,
                list
            ):

                if not data:
                    return None

                data = data[0]


        if not isinstance(
            data,
            dict
        ):

            return None


        # -------------------------------------------------
        # PRICE
        # -------------------------------------------------

        price = (

            data.get("close")

            or data.get(
                "latestPrice"
            )

            or data.get(
                "latest_price"
            )

            or data.get(
                "price"
            )

            or data.get(
                "lastPrice"
            )

            or 0

        )


        # -------------------------------------------------
        # CHANGE
        # -------------------------------------------------

        change_ratio = (

            data.get(
                "changeRatio"
            )

            or data.get(
                "change_ratio"
            )

            or data.get(
                "changePercent"
            )

            or 0

        )


        # -------------------------------------------------
        # VOLUME
        # -------------------------------------------------

        volume = (

            data.get(
                "volume"
            )

            or data.get(
                "tradeVolume"
            )

            or data.get(
                "totalVolume"
            )

            or 0

        )


        # -------------------------------------------------
        # CONVERT
        # -------------------------------------------------

        try:

            price = float(
                price
            )

        except Exception:

            price = 0


        try:

            volume = float(
                volume
            )

        except Exception:

            volume = 0


        try:

            change_ratio = float(
                change_ratio
            )

        except Exception:

            change_ratio = 0


        # -------------------------------------------------
        # CHANGE %
        # -------------------------------------------------

        if abs(
            change_ratio
        ) < 1:

            change_percent = (
                change_ratio * 100
            )

        else:

            change_percent = (
                change_ratio
            )


        if price <= 0:
            return None


        if volume < 0:
            volume = 0


        # -------------------------------------------------
        # DOLLAR VOLUME
        # -------------------------------------------------

        dollar_volume = (
            price * volume
        )


        return {

            "Symbol": symbol,

            "Price": price,

            "Change": change_percent,

            "Volume": volume,

            "Dollar Volume":
                dollar_volume

        }

    except Exception:

        return None


# =========================================================
# REPEAT VOLUME
# =========================================================

def check_repeat_volume(
    symbol,
    current_volume
):

    tolerance = (
        settings[
            "repeat_tolerance"
        ]
    )


    history = (
        st.session_state
        .volume_history
        .get(
            symbol,
            []
        )
    )


    if len(history) == 0:

        st.session_state.volume_history[
            symbol
        ] = [
            current_volume
        ]

        return False


    lower = tolerance

    upper = (
        1 / tolerance
    )


    repeat = False


    for old_volume in history:

        if old_volume <= 0:
            continue


        ratio = (
            current_volume
            / old_volume
        )


        if (
            lower
            <= ratio
            <= upper
        ):

            repeat = True

            break


    history.append(
        current_volume
    )


    if len(history) > 200:

        history = history[-200:]


    st.session_state.volume_history[
        symbol
    ] = history


    return repeat


# =========================================================
# TRIGGER TIME
# =========================================================

def record_trigger_time(
    symbol
):

    now = datetime.now(
        ZoneInfo(
            "America/New_York"
        )
    )


    time_string = now.strftime(
        "%H:%M:%S"
    )


    if symbol not in (
        st.session_state.active_symbols
    ):

        st.session_state.trigger_times[
            symbol
        ] = time_string


    return (
        st.session_state
        .trigger_times
        .get(
            symbol,
            time_string
        )
    )


# =========================================================
# SCAN ONE SYMBOL
# =========================================================

def scan_one_symbol(
    symbol
):

    data = get_snapshot(
        symbol
    )

    parsed = parse_snapshot(
        symbol,
        data
    )

    return parsed


# =========================================================
# SCAN STOCK UNIVERSE
# =========================================================

def scan_stocks():

    start_time = datetime.now()

    results = []

    current_active_symbols = set()


    # -----------------------------------------------------
    # UNIVERSE
    # -----------------------------------------------------

    universe = (
        st.session_state.stock_universe
    )


    universe_limit = int(
        settings[
            "universe_limit"
        ]
    )


    if universe_limit > 0:

        universe = universe[
            :universe_limit
        ]


    # -----------------------------------------------------
    # BATCH
    # -----------------------------------------------------

    batch_size = int(
        settings[
            "batch_size"
        ]
    )


    # -----------------------------------------------------
    # NOTE
    # -----------------------------------------------------
    # We keep the existing working
    # single-symbol Webull call here.
    #
    # This makes the first full-market
    # version safer.
    #
    # Once confirmed working, we can
    # replace this with Webull's official
    # multi-symbol snapshot call.
    # -----------------------------------------------------

    for start in range(
        0,
        len(universe),
        batch_size
    ):

        batch = universe[
            start:
            start + batch_size
        ]


        for symbol in batch:

            parsed = scan_one_symbol(
                symbol
            )


            if parsed is None:
                continue


            price = parsed[
                "Price"
            ]

            change_percent = parsed[
                "Change"
            ]

            volume = parsed[
                "Volume"
            ]

            dollar_volume = parsed[
                "Dollar Volume"
            ]


            # -------------------------------------------------
            # PREVIOUS VOLUME
            # -------------------------------------------------

            previous_volume = (
                st.session_state
                .previous_volumes
                .get(
                    symbol,
                    0
                )
            )


            if previous_volume > 0:

                rvol = (
                    volume
                    / previous_volume
                )

            else:

                rvol = 0


            # -------------------------------------------------
            # REPEAT VOLUME
            # -------------------------------------------------

            repeat = (
                check_repeat_volume(
                    symbol,
                    volume
                )
            )


            # -------------------------------------------------
            # SAVE CURRENT VOLUME
            # -------------------------------------------------

            st.session_state.previous_volumes[
                symbol
            ] = volume


            # =================================================
            # FILTERS
            # =================================================

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


            if change_percent < settings[
                "min_change"
            ]:

                continue


            if dollar_volume < settings[
                "min_dollar_volume"
            ]:

                continue


            # =================================================
            # PASSED
            # =================================================

            current_active_symbols.add(
                symbol
            )


            trigger_time = (
                record_trigger_time(
                    symbol
                )
            )


            results.append({

                "Time":
                    trigger_time,

                "Symbol":
                    symbol,

                "Price":
                    price,

                "Change":
                    change_percent,

                "Volume":
                    volume,

                "RVOL":
                    rvol,

                "Dollar Volume":
                    dollar_volume,

                "Repeat":
                    repeat

            })


    # =====================================================
    # REMOVE OLD ACTIVE STOCKS
    # =====================================================

    old_active_symbols = (
        st.session_state.active_symbols
    )


    disappeared = (
        old_active_symbols
        -
        current_active_symbols
    )


    for symbol in disappeared:

        if symbol in (
            st.session_state.trigger_times
        ):

            del (
                st.session_state
                .trigger_times[symbol]
            )


    st.session_state.active_symbols = (
        current_active_symbols
    )


    # =====================================================
    # DATAFRAME
    # =====================================================

    if results:

        df = pd.DataFrame(
            results
        )


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

                "Time",
                "Symbol",
                "Price",
                "Change",
                "Volume",
                "RVOL",
                "Dollar Volume",
                "Repeat"

            ]

        )


    # =====================================================
    # SAVE
    # =====================================================

    end_time = datetime.now()


    st.session_state.scan_duration = (

        end_time - start_time
    ).total_seconds()


    st.session_state.scan_results = df


    st.session_state.scan_count += 1


    st.session_state.last_scan_time = (

        datetime.now(
            ZoneInfo(
                "Australia/Adelaide"
            )
        )

    )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header(
        "Scanner Filters"
    )


    # =====================================================
    # MARKET UNIVERSE
    # =====================================================

    st.subheader(
        "US Market"
    )


    universe_count = len(
        st.session_state.stock_universe
    )


    st.caption(
        f"US stocks loaded: "
        f"{universe_count:,}"
    )


    settings[
        "universe_limit"
    ] = st.number_input(

        "Stocks to scan",

        min_value=30,

        max_value=10000,

        value=int(
            settings[
                "universe_limit"
            ]
        ),

        step=100

    )


    settings[
        "batch_size"
    ] = st.number_input(

        "Batch size",

        min_value=1,

        max_value=100,

        value=int(
            settings[
                "batch_size"
            ]
        ),

        step=1

    )


    # =====================================================
    # PRICE
    # =====================================================

    st.subheader(
        "Price"
    )


    settings[
        "min_price"
    ] = st.number_input(

        "Minimum Price",

        min_value=0.0,

        value=float(
            settings[
                "min_price"
            ]
        ),

        step=0.50

    )


    settings[
        "max_price"
    ] = st.number_input(

        "Maximum Price",

        min_value=0.0,

        value=float(
            settings[
                "max_price"
            ]
        ),

        step=1.0

    )


    # =====================================================
    # VOLUME
    # =====================================================

    st.subheader(
        "Volume"
    )


    settings[
        "min_volume"
    ] = st.number_input(

        "Minimum Volume",

        min_value=0,

        value=int(
            settings[
                "min_volume"
            ]
        ),

        step=10000

    )


    settings[
        "min_dollar_volume"
    ] = st.number_input(

        "Minimum $ Volume",

        min_value=0,

        value=int(
            settings[
                "min_dollar_volume"
            ]
        ),

        step=100000

    )


    # =====================================================
    # MOMENTUM
    # =====================================================

    st.subheader(
        "Momentum"
    )


    settings[
        "min_rvol"
    ] = st.number_input(

        "Minimum RVOL",

        min_value=0.0,

        value=float(
            settings[
                "min_rvol"
            ]
        ),

        step=0.1

    )


    settings[
        "min_change"
    ] = st.number_input(

        "Minimum Change %",

        min_value=-100.0,

        value=float(
            settings[
                "min_change"
            ]
        ),

        step=0.5

    )


    # =====================================================
    # REPEAT
    # =====================================================

    st.subheader(
        "Repeat Volume"
    )


    settings[
        "repeat_tolerance"
    ] = st.slider(

        "Repeat tolerance",

        min_value=0.50,

        max_value=0.99,

        value=float(
            settings[
                "repeat_tolerance"
            ]
        ),

        step=0.01

    )


    # =====================================================
    # SCANNER
    # =====================================================

    st.subheader(
        "Scanner"
    )


    settings[
        "refresh_seconds"
    ] = st.number_input(

        "Refresh Seconds",

        min_value=30,

        max_value=3600,

        value=int(
            settings[
                "refresh_seconds"
            ]
        ),

        step=30

    )


    settings[
        "auto_scan"
    ] = st.checkbox(

        "Automatic Scan",

        value=bool(
            settings[
                "auto_scan"
            ]
        )

    )


    # =====================================================
    # TRADINGVIEW
    # =====================================================

    st.subheader(
        "TradingView"
    )


    chart_intervals = [

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
        settings[
            "chart_interval"
        ]
    )


    if current_interval not in chart_intervals:

        current_interval = "1"


    settings[
        "chart_interval"
    ] = st.selectbox(

        "Chart Interval",

        options=chart_intervals,

        index=chart_intervals.index(
            current_interval
        )

    )


    st.divider()


    # =====================================================
    # SAVE
    # =====================================================

    if st.button(
        "💾 Save Settings",
        use_container_width=True
    ):

        save_settings(
            settings
        )

        st.success(
            "Settings saved"
        )


    # =====================================================
    # RESET
    # =====================================================

    if st.button(
        "♻️ Reset Volume History",
        use_container_width=True
    ):

        st.session_state.previous_volumes = {}

        st.session_state.volume_history = {}

        st.session_state.trigger_times = {}

        st.session_state.active_symbols = set()

        st.success(
            "Volume history reset"
        )


    # =====================================================
    # REFRESH UNIVERSE
    # =====================================================

    if st.button(
        "🔄 Refresh US Stock List",
        use_container_width=True
    ):

        download_us_stock_universe.clear()

        new_universe = (
            download_us_stock_universe()
        )

        st.session_state.stock_universe = (
            new_universe
        )

        st.success(
            f"Loaded {len(new_universe):,} stocks"
        )

        st.rerun()


# =========================================================
# MAIN HEADER
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

        scan_stocks()

        st.rerun()


# =========================================================
# MARKET INFORMATION
# =========================================================

info_col1, info_col2, info_col3, info_col4 = st.columns(
    4
)


with info_col1:

    st.caption(
        f"US stocks: "
        f"{len(st.session_state.stock_universe):,}"
    )


with info_col2:

    st.caption(
        f"Scans: "
        f"{st.session_state.scan_count}"
    )


with info_col3:

    if st.session_state.last_scan_time:

        st.caption(

            "Last scan: "
            +
            st.session_state.last_scan_time.strftime(
                "%H:%M:%S"
            )

        )


with info_col4:

    if st.session_state.scan_duration:

        st.caption(

            "Scan time: "
            f"{st.session_state.scan_duration:.1f}s"

        )


# =========================================================
# INITIAL SCAN
# =========================================================

if (

    st.session_state.scan_results.empty

    and

    st.session_state.scan_count == 0

):

    scan_stocks()


# =========================================================
# SCANNER
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
    # AUTOMATIC SCAN
    # -----------------------------------------------------

    if settings["auto_scan"]:

        scan_stocks()


    df = (
        st.session_state.scan_results
    )


    # =====================================================
    # 35 / 65
    # =====================================================

    left, right = st.columns(

        [35, 65],

        gap="small"

    )


    # =====================================================
    # LEFT
    # =====================================================

    with left:

        st.markdown(

            '<div class="scanner-title">'
            'Scanner'
            '</div>',

            unsafe_allow_html=True

        )


        # -------------------------------------------------
        # HEADER
        # -------------------------------------------------

        h1, h2, h3, h4, h5, h6 = st.columns(

            [
                1.05,
                1.35,
                1.0,
                0.8,
                0.9,
                1.15
            ]

        )


        headers = [

            ("TIME", h1),
            ("SYMBOL", h2),
            ("LTP", h3),
            ("%", h4),
            ("RVOL", h5),
            ("$VOL", h6)

        ]


        for text, column in headers:

            with column:

                st.markdown(

                    f"""
                    <div class="scanner-heading">
                        {text}
                    </div>
                    """,

                    unsafe_allow_html=True

                )


        # =================================================
        # RESULTS
        # =================================================

        if df.empty:

            st.info(
                "No stocks match the filters."
            )


        else:

            for _, row in df.iterrows():

                symbol = row[
                    "Symbol"
                ]


                repeat = row[
                    "Repeat"
                ]


                c1, c2, c3, c4, c5, c6 = st.columns(

                    [
                        1.05,
                        1.35,
                        1.0,
                        0.8,
                        0.9,
                        1.15
                    ]

                )


                # TIME

                with c1:

                    st.markdown(

                        f"""
                        <div class="stock-cell">
                            {row['Time']}
                        </div>
                        """,

                        unsafe_allow_html=True

                    )


                # SYMBOL

                with c2:

                    indicator = (
                        "■ "
                        if repeat
                        else ""
                    )


                    if st.button(

                        f"{indicator}{symbol}",

                        key=f"stock_{symbol}",

                        use_container_width=True

                    ):

                        st.session_state.selected_symbol = (
                            symbol
                        )

                        st.rerun()


                # LTP

                with c3:

                    st.markdown(

                        f"""
                        <div class="stock-cell">
                            ${row['Price']:.2f}
                        </div>
                        """,

                        unsafe_allow_html=True

                    )


                # %

                with c4:

                    st.markdown(

                        f"""
                        <div class="stock-cell">
                            {row['Change']:.1f}%
                        </div>
                        """,

                        unsafe_allow_html=True

                    )


                # RVOL

                with c5:

                    st.markdown(

                        f"""
                        <div class="stock-cell">
                            {row['RVOL']:.1f}x
                        </div>
                        """,

                        unsafe_allow_html=True

                    )


                # $VOL

                with c6:

                    dollar_volume = (
                        row[
                            "Dollar Volume"
                        ]
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


                    st.markdown(

                        f"""
                        <div class="stock-cell">
                            {text}
                        </div>
                        """,

                        unsafe_allow_html=True

                    )


    # =====================================================
    # RIGHT TRADINGVIEW
    # =====================================================

    with right:

        symbol = (
            st.session_state.selected_symbol
        )


        exchange = get_exchange(
            symbol
        )


        st.markdown(

            f"""
            <div class="chart-title">
                {symbol}
            </div>
            """,

            unsafe_allow_html=True

        )


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
# RUN
# =========================================================

scanner_area()


# =========================================================
# FOOTER
# =========================================================

st.caption(

    "Webull US Momentum Scanner • "
    "Dynamic US stock universe • "
    "Historical volume repeat detection"

)
