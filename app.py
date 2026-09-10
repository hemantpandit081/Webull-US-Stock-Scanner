import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components

from webull.core.client import ApiClient
from webull.data.data_client import DataClient


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="US Momentum Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

/* ---------- GENERAL ---------- */

.block-container {
    padding-top: 0.45rem !important;
    padding-bottom: 0rem !important;
    padding-left: 0.45rem !important;
    padding-right: 0.45rem !important;
    max-width: 100% !important;
}

.main {
    background: #0b0f14;
}

div[data-testid="stVerticalBlock"] {
    gap: 0.15rem;
}

div[data-testid="column"] {
    padding-left: 3px;
    padding-right: 3px;
}


/* ---------- TOP HEADER ---------- */

.top-title {
    font-size: 22px;
    font-weight: 700;
    margin-top: 2px;
    margin-bottom: 0px;
}

.top-subtitle {
    font-size: 11px;
    opacity: 0.55;
    margin-top: -2px;
}


/* ---------- SCANNER PANEL ---------- */

.scanner-panel {
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 7px;
    overflow: hidden;
    background: rgba(255,255,255,0.015);
}

.scanner-title {
    font-size: 13px;
    font-weight: 700;
    padding: 7px 9px 5px 9px;
}

.scanner-count {
    font-size: 10px;
    opacity: 0.55;
}


/* ---------- TABLE HEADER ---------- */

.table-header {
    font-size: 9px;
    font-weight: 700;
    opacity: 0.48;
    padding-top: 4px;
    padding-bottom: 3px;
}


/* ---------- STOCK ROW ---------- */

.stock-row {
    min-height: 32px;
    border-top: 1px solid rgba(255,255,255,0.045);
}

.stock-symbol {
    font-size: 12px;
    font-weight: 700;
    line-height: 31px;
    white-space: nowrap;
}

.stock-name {
    font-size: 9px;
    opacity: 0.45;
    line-height: 31px;
    white-space: nowrap;
    overflow: hidden;
}

.stock-number {
    font-size: 11px;
    line-height: 31px;
    white-space: nowrap;
}

.stock-repeat {
    font-size: 10px;
    font-weight: 800;
    line-height: 31px;
}


/* ---------- BUTTONS ---------- */

.stButton > button {
    min-height: 29px !important;
    height: 29px !important;
    padding: 0px 5px !important;
    border-radius: 4px !important;
    font-size: 11px !important;
}


/* ---------- CHART ---------- */

.chart-title {
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 2px;
}

.chart-symbol {
    font-size: 10px;
    opacity: 0.5;
}


/* ---------- FOOTER ---------- */

.footer {
    font-size: 9px;
    opacity: 0.4;
    margin-top: 2px;
}


/* ---------- SIDEBAR ---------- */

section[data-testid="stSidebar"] {
    width: 285px !important;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# WEBULL CONNECTION
# ============================================================

try:
    APP_KEY = st.secrets["WEBULL_APP_KEY"]
    APP_SECRET = st.secrets["WEBULL_APP_SECRET"]

except Exception:
    st.error("Webull API keys are missing.")
    st.info(
        "Add WEBULL_APP_KEY and WEBULL_APP_SECRET "
        "under Streamlit → Settings → Secrets."
    )
    st.stop()


@st.cache_resource
def get_webull_client():

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


try:
    data_client = get_webull_client()

except Exception as e:
    st.error("Could not connect to Webull.")
    st.code(str(e))
    st.stop()


# ============================================================
# STOCK UNIVERSE
# ============================================================

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


# ============================================================
# COMPANY NAMES
# ============================================================

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
    "AMD": "Advanced Micro Devices",

    "NFLX": "Netflix",
    "INTC": "Intel",
    "MU": "Micron",
    "QCOM": "Qualcomm",
    "AMAT": "Applied Materials",

    "ARM": "Arm Holdings",
    "PLTR": "Palantir",
    "SMCI": "Super Micro Computer",
    "COIN": "Coinbase",
    "HOOD": "Robinhood",

    "SOFI": "SoFi Technologies",
    "BAC": "Bank of America",
    "JPM": "JPMorgan Chase",
    "WMT": "Walmart",
    "COST": "Costco",

    "UBER": "Uber",
    "SHOP": "Shopify",
    "PDD": "PDD Holdings",
    "NIO": "NIO",
    "RIVN": "Rivian"
}


# ============================================================
# TRADINGVIEW EXCHANGES
# ============================================================

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


def tradingview_symbol(symbol):

    exchange = EXCHANGE_MAP.get(
        symbol,
        "NASDAQ"
    )

    return f"{exchange}:{symbol}"


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_SETTINGS = {

    "min_price": 1.0,

    "max_price": 1000.0,

    "min_volume": 100000,

    "min_change": 1.0,

    "min_rvol": 1.5,

    "min_dollar_volume": 1000000,

    "repeat_tolerance": 0.90,

    "history_length": 20,

    "refresh_seconds": 60,

    "auto_refresh": True,

    "interval": "1",

    "theme": "dark",

    "show_volume": True,

    "timezone": "America/New_York"
}


SETTINGS_FILE = "scanner_settings.json"


def load_settings():

    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()

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

        return DEFAULT_SETTINGS.copy()


settings = load_settings()


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


# ============================================================
# SESSION STATE
# ============================================================

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "NVDA"

if "volume_history" not in st.session_state:
    st.session_state.volume_history = {}

if "previous_volume" not in st.session_state:
    st.session_state.previous_volume = {}

if "repeat_symbols" not in st.session_state:
    st.session_state.repeat_symbols = set()

if "results" not in st.session_state:
    st.session_state.results = pd.DataFrame()

if "scan_number" not in st.session_state:
    st.session_state.scan_number = 0

if "last_scan" not in st.session_state:
    st.session_state.last_scan = "--"


# ============================================================
# MARKET TIME
# ============================================================

NY = ZoneInfo(
    "America/New_York"
)


def current_ny_time():

    return datetime.now(
        NY
    )


def market_is_open():

    now = current_ny_time()

    if now.weekday() >= 5:
        return False

    minutes = (
        now.hour * 60
        + now.minute
    )

    return (
        570
        <= minutes
        <= 960
    )


# ============================================================
# WEBULL SNAPSHOT
# ============================================================

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


# ============================================================
# VOLUME HISTORY
# ============================================================

def add_volume(symbol, volume):

    if symbol not in st.session_state.volume_history:

        st.session_state.volume_history[symbol] = []


    history = (
        st.session_state.volume_history[symbol]
    )


    history.append(volume)


    maximum = int(
        settings["history_length"]
    )


    if len(history) > maximum:

        del history[
            :-maximum
        ]


# ============================================================
# REPEAT VOLUME
# ============================================================

def detect_repeat(
    symbol,
    volume
):

    history = (
        st.session_state.volume_history.get(
            symbol,
            []
        )
    )


    if volume <= 0:

        return False


    tolerance = float(
        settings["repeat_tolerance"]
    )


    for old_volume in history:

        if old_volume <= 0:
            continue


        ratio = (
            volume
            / old_volume
        )


        if (
            tolerance
            <= ratio
            <= (1 / tolerance)
        ):

            st.session_state.repeat_symbols.add(
                symbol
            )

            add_volume(
                symbol,
                volume
            )

            return True


    add_volume(
        symbol,
        volume
    )

    return False


# ============================================================
# RVOL
# ============================================================

def calculate_rvol(
    symbol,
    volume
):

    previous = (
        st.session_state.previous_volume.get(
            symbol
        )
    )


    if previous is None or previous <= 0:

        rvol = 1.0

    else:

        rvol = (
            volume
            / previous
        )


    st.session_state.previous_volume[symbol] = (
        volume
    )


    return rvol


# ============================================================
# FORMAT
# ============================================================

def money(value):

    if value >= 1_000_000_000:

        return f"${value / 1_000_000_000:.1f}B"

    if value >= 1_000_000:

        return f"${value / 1_000_000:.1f}M"

    if value >= 1_000:

        return f"${value / 1_000:.0f}K"

    return f"${value:.0f}"


def volume_text(value):

    if value >= 1_000_000_000:

        return f"{value / 1_000_000_000:.1f}B"

    if value >= 1_000_000:

        return f"{value / 1_000_000:.1f}M"

    if value >= 1_000:

        return f"{value / 1_000:.0f}K"

    return f"{value:.0f}"


# ============================================================
# SCAN
# ============================================================

def scan_market():

    rows = []


    for symbol in STOCKS:

        data = get_snapshot(
            symbol
        )


        if data is None:
            continue


        try:

            price = float(
                data.get(
                    "price",
                    0
                ) or 0
            )


            change_ratio = float(
                data.get(
                    "change_ratio",
                    0
                ) or 0
            )


            volume = float(
                data.get(
                    "volume",
                    0
                ) or 0
            )


            change = (
                change_ratio
                * 100
            )


            dollar_volume = (
                price
                * volume
            )


            rvol = calculate_rvol(
                symbol,
                volume
            )


            repeat = detect_repeat(
                symbol,
                volume
            )


            # --------------------------------------------
            # FILTER
            # --------------------------------------------

            if price < settings["min_price"]:
                continue


            if price > settings["max_price"]:
                continue


            if volume < settings["min_volume"]:
                continue


            if change < settings["min_change"]:
                continue


            if rvol < settings["min_rvol"]:
                continue


            if (
                dollar_volume
                < settings["min_dollar_volume"]
            ):
                continue


            rows.append({

                "Symbol": symbol,

                "Name": COMPANY_NAMES.get(
                    symbol,
                    symbol
                ),

                "Price": price,

                "Change": change,

                "RVOL": rvol,

                "Volume": volume,

                "DollarVolume": dollar_volume,

                "Repeat": repeat

            })


        except Exception:

            continue


    if not rows:

        return pd.DataFrame()


    df = pd.DataFrame(
        rows
    )


    df = df.sort_values(

        by=[
            "Repeat",
            "RVOL",
            "Change",
            "DollarVolume"
        ],

        ascending=[
            False,
            False,
            False,
            False
        ]
    )


    return df.reset_index(
        drop=True
    )


# ============================================================
# SCAN BUTTON
# ============================================================

def perform_scan():

    result = scan_market()

    st.session_state.results = result

    st.session_state.scan_number += 1

    st.session_state.last_scan = (
        current_ny_time().strftime(
            "%H:%M:%S"
        )
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## Scanner Settings"
    )


    st.markdown(
        "### Price"
    )


    settings["min_price"] = st.number_input(
        "Minimum price",
        min_value=0.01,
        value=float(settings["min_price"]),
        step=0.50
    )


    settings["max_price"] = st.number_input(
        "Maximum price",
        min_value=0.01,
        value=float(settings["max_price"]),
        step=5.00
    )


    st.markdown(
        "### Momentum"
    )


    settings["min_change"] = st.number_input(
        "Minimum % change",
        value=float(settings["min_change"]),
        step=0.5
    )


    settings["min_rvol"] = st.number_input(
        "Minimum RVOL",
        min_value=0.0,
        value=float(settings["min_rvol"]),
        step=0.1
    )


    st.markdown(
        "### Volume"
    )


    settings["min_volume"] = st.number_input(
        "Minimum volume",
        min_value=0,
        value=int(settings["min_volume"]),
        step=100000
    )


    settings["min_dollar_volume"] = st.number_input(
        "Minimum dollar volume",
        min_value=0,
        value=int(settings["min_dollar_volume"]),
        step=500000
    )


    settings["repeat_tolerance"] = st.slider(
        "Repeat-volume tolerance",
        min_value=0.50,
        max_value=1.00,
        value=float(settings["repeat_tolerance"]),
        step=0.01
    )


    settings["history_length"] = st.number_input(
        "Volume history",
        min_value=2,
        max_value=100,
        value=int(settings["history_length"]),
        step=1
    )


    st.markdown(
        "### Refresh"
    )


    settings["refresh_seconds"] = st.number_input(
        "Refresh seconds",
        min_value=10,
        max_value=3600,
        value=int(settings["refresh_seconds"]),
        step=10
    )


    settings["auto_refresh"] = st.checkbox(
        "Auto refresh",
        value=bool(settings["auto_refresh"])
    )


    st.markdown(
        "### TradingView"
    )


    settings["interval"] = st.selectbox(
        "Chart timeframe",
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
            settings["interval"]
        )
    )


    settings["theme"] = st.selectbox(
        "Chart theme",
        [
            "dark",
            "light"
        ],
        index=[
            "dark",
            "light"
        ].index(
            settings["theme"]
        )
    )


    settings["show_volume"] = st.checkbox(
        "Show chart volume",
        value=bool(settings["show_volume"])
    )


    st.divider()


    if st.button(
        "Save settings",
        use_container_width=True
    ):

        if save_settings():

            st.success(
                "Settings saved."
            )


    if st.button(
        "Reset settings",
        use_container_width=True
    ):

        settings.clear()

        settings.update(
            DEFAULT_SETTINGS.copy()
        )

        save_settings()

        st.rerun()


# ============================================================
# FIRST SCAN
# ============================================================

if st.session_state.results.empty:

    perform_scan()


df = st.session_state.results


# ============================================================
# TOP HEADER
# ============================================================

top1, top2, top3 = st.columns(
    [6, 2, 1.5]
)


with top1:

    st.markdown(
        '<div class="top-title">'
        'US Momentum Scanner'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="top-subtitle">'
        'Webull market data • Volume momentum • Repeat-volume tracking'
        '</div>',
        unsafe_allow_html=True
    )


with top2:

    if market_is_open():

        st.success(
            "● MARKET OPEN"
        )

    else:

        st.caption(
            "● MARKET CLOSED"
        )


with top3:

    if st.button(
        "SCAN",
        use_container_width=True
    ):

        perform_scan()

        st.rerun()


# ============================================================
# MAIN 35 / 65
# ============================================================

left, right = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT — SCANNER
# ============================================================

with left:

    st.markdown(
        '<div class="scanner-title">'
        'Momentum Stocks '
        f'<span class="scanner-count">'
        f'({len(df)})'
        f'</span>'
        '</div>',
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # TABLE HEADER
    # --------------------------------------------------------

    h1, h2, h3, h4, h5, h6 = st.columns(
        [
            1.1,
            2.5,
            1.0,
            0.8,
            0.8,
            1.0
        ]
    )


    with h1:

        st.markdown(
            '<div class="table-header">TICKER</div>',
            unsafe_allow_html=True
        )


    with h2:

        st.markdown(
            '<div class="table-header">NAME</div>',
            unsafe_allow_html=True
        )


    with h3:

        st.markdown(
            '<div class="table-header">LTP</div>',
            unsafe_allow_html=True
        )


    with h4:

        st.markdown(
            '<div class="table-header">%CHG</div>',
            unsafe_allow_html=True
        )


    with h5:

        st.markdown(
            '<div class="table-header">RVOL</div>',
            unsafe_allow_html=True
        )


    with h6:

        st.markdown(
            '<div class="table-header">$VOL</div>',
            unsafe_allow_html=True
        )


    # --------------------------------------------------------
    # STOCKS
    # --------------------------------------------------------

    if df.empty:

        st.info(
            "No stocks match the current filters."
        )


    else:

        for _, row in df.iterrows():

            symbol = row["Symbol"]


            c1, c2, c3, c4, c5, c6 = st.columns(
                [
                    1.1,
                    2.5,
                    1.0,
                    0.8,
                    0.8,
                    1.0
                ]
            )


            # ----------------------------------------------
            # TICKER
            # ----------------------------------------------

            with c1:

                if st.button(
                    symbol,
                    key=f"ticker_{symbol}",
                    use_container_width=True
                ):

                    st.session_state.selected_symbol = (
                        symbol
                    )

                    st.rerun()


            # ----------------------------------------------
            # REPEAT
            # ----------------------------------------------

            with c2:

                repeat_mark = (
                    "■ "
                    if row["Repeat"]
                    else ""
                )


                st.markdown(
                    f"""
                    <div class="stock-name">
                    {repeat_mark}{row["Name"]}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


            # ----------------------------------------------
            # PRICE
            # ----------------------------------------------

            with c3:

                st.markdown(
                    f"""
                    <div class="stock-number">
                    ${row["Price"]:.2f}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


            # ----------------------------------------------
            # CHANGE
            # ----------------------------------------------

            with c4:

                st.markdown(
                    f"""
                    <div class="stock-number">
                    {row["Change"]:.1f}%
                    </div>
                    """,
                    unsafe_allow_html=True
                )


            # ----------------------------------------------
            # RVOL
            # ----------------------------------------------

            with c5:

                st.markdown(
                    f"""
                    <div class="stock-number">
                    {row["RVOL"]:.1f}x
                    </div>
                    """,
                    unsafe_allow_html=True
                )


            # ----------------------------------------------
            # DOLLAR VOLUME
            # ----------------------------------------------

            with c6:

                st.markdown(
                    f"""
                    <div class="stock-number">
                    {money(row["DollarVolume"])}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


# ============================================================
# RIGHT — TRADINGVIEW
# ============================================================

with right:

    selected = (
        st.session_state.selected_symbol
    )


    tv_symbol = tradingview_symbol(
        selected
    )


    st.markdown(
        f"""
        <div class="chart-title">
        {selected}
        <span class="chart-symbol">
        {COMPANY_NAMES.get(selected, selected)}
        </span>
        </div>
        """,
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # GLOBAL TRADINGVIEW TEMPLATE
    # --------------------------------------------------------

    encoded_symbol = (
        tv_symbol
        .replace(":", "%3A")
    )


    timezone = (
        settings["timezone"]
        .replace("/", "%2F")
    )


    hide_volume = (
        "0"
        if settings["show_volume"]
        else "1"
    )


    chart_url = (

        "https://www.tradingview.com/widgetembed/"

        "?frameElementId=tradingview_chart"

        f"&symbol={encoded_symbol}"

        f"&interval={settings['interval']}"

        f"&theme={settings['theme']}"

        "&style=1"

        f"&timezone={timezone}"

        "&locale=en"

        "&withdateranges=true"

        "&hide_legend=false"

        "&save_image=true"

        "&hide_side_toolbar=false"

        "&allow_symbol_change=true"

        f"&hide_volume={hide_volume}"

    )


    chart_html = f"""
    <iframe
        id="tradingview_chart"
        src="{chart_url}"
        width="100%"
        height="600"
        frameborder="0"
        allowtransparency="true"
        scrolling="no"
        style="
            border:0;
            border-radius:6px;
            width:100%;
            background:#0b0f14;
        ">
    </iframe>
    """


    components.html(
        chart_html,
        height=745,
        scrolling=False
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    f"""
    <div class="footer">
        Scan #{st.session_state.scan_number}
        &nbsp; • &nbsp;
        Last scan {st.session_state.last_scan}
        &nbsp; • &nbsp;
        Selected {st.session_state.selected_symbol}
        &nbsp; • &nbsp;
        ■ = repeat volume
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# AUTO REFRESH
# ============================================================

if settings["auto_refresh"]:

    refresh_ms = (
        int(settings["refresh_seconds"])
        * 1000
    )


    components.html(
        f"""
        <script>

        setTimeout(function() {{

            window.parent.location.reload();

        }}, {refresh_ms});

        </script>
        """,
        height=0
    )
