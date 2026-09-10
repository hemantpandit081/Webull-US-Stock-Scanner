import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="US Momentum Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# SESSION STATE
# ============================================================

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = None

if "scan_data" not in st.session_state:
    st.session_state.scan_data = pd.DataFrame()

if "previous_symbols" not in st.session_state:
    st.session_state.previous_symbols = set()

if "repeat_symbols" not in st.session_state:
    st.session_state.repeat_symbols = set()

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    /* Main page */
    .block-container {
        padding-top: 0.7rem;
        padding-bottom: 0.5rem;
        padding-left: 0.7rem;
        padding-right: 0.7rem;
        max-width: 100%;
    }

    /* Header */
    .scanner-header {
        font-size: 22px;
        font-weight: 700;
        margin-bottom: 4px;
    }

    .scanner-status {
        font-size: 12px;
        color: #888;
        margin-bottom: 8px;
    }

    /* Stock buttons */
    div[data-testid="stButton"] {
        width: 100%;
        margin: 0 !important;
        padding: 0 !important;
    }

    div[data-testid="stButton"] > button {
        width: 100% !important;
        min-height: 30px !important;
        height: 30px !important;
        padding: 0px 8px !important;
        margin: 1px 0px !important;
        border-radius: 4px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        text-align: left !important;
        line-height: 28px !important;
    }

    /* Make buttons clearly clickable */
    div[data-testid="stButton"] > button:hover {
        border-color: #777 !important;
        background-color: rgba(120,120,120,0.18) !important;
    }

    /* Chart */
    iframe {
        border-radius: 5px;
    }

    /* Tables */
    [data-testid="stDataFrame"] {
        font-size: 12px;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        padding-top: 1rem;
    }

    /* Remove excessive vertical gaps */
    div[data-testid="stVerticalBlock"] {
        gap: 0.25rem;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# TITLE
# ============================================================

st.markdown(
    '<div class="scanner-header">📈 US Momentum Scanner</div>',
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR FILTERS
# ============================================================

with st.sidebar:

    st.subheader("Scanner Filters")

    min_price = st.number_input(
        "Minimum Price",
        min_value=0.01,
        value=1.00,
        step=0.50
    )

    max_price = st.number_input(
        "Maximum Price",
        min_value=1.00,
        value=1000.00,
        step=5.00
    )

    min_change = st.number_input(
        "Minimum % Change",
        value=2.0,
        step=0.5
    )

    min_rvol = st.number_input(
        "Minimum RVOL",
        value=2.0,
        step=0.5
    )

    min_volume = st.number_input(
        "Minimum Volume",
        value=100000,
        step=50000
    )

    max_stocks = st.number_input(
        "Maximum Stocks",
        min_value=10,
        max_value=500,
        value=100,
        step=10
    )

    refresh_seconds = st.number_input(
        "Refresh Seconds",
        min_value=5,
        max_value=300,
        value=15,
        step=5
    )

    chart_interval = st.selectbox(
        "Chart Interval",
        [
            "1",
            "5",
            "15",
            "30",
            "60"
        ],
        index=1
    )

    auto_scan = st.checkbox(
        "Auto Scan",
        value=True
    )

    st.divider()

    scan_button = st.button(
        "🔄 Scan Now",
        use_container_width=True
    )


# ============================================================
# WEBULL API SETTINGS
# ============================================================

# ------------------------------------------------------------
# IMPORTANT:
#
# Put your Webull OpenAPI credentials in Streamlit Secrets:
#
# WEBULL_APP_KEY
# WEBULL_APP_SECRET
#
# ------------------------------------------------------------

try:
    WEBULL_APP_KEY = st.secrets["WEBULL_APP_KEY"]
    WEBULL_APP_SECRET = st.secrets["WEBULL_APP_SECRET"]
except Exception:
    WEBULL_APP_KEY = ""
    WEBULL_APP_SECRET = ""


# ============================================================
# WEBULL TOKEN
# ============================================================

def get_webull_token():

    if not WEBULL_APP_KEY or not WEBULL_APP_SECRET:
        return None

    url = "https://openapi.webullfinance.com/api/auth/token"

    payload = {
        "app_key": WEBULL_APP_KEY,
        "app_secret": WEBULL_APP_SECRET
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=10
        )

        if response.status_code != 200:
            return None

        data = response.json()

        return (
            data.get("access_token")
            or data.get("token")
        )

    except Exception:
        return None


# ============================================================
# WEBULL REQUEST
# ============================================================

def webull_request(
    endpoint,
    token,
    params=None
):

    if not token:
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:

        response = requests.get(
            endpoint,
            headers=headers,
            params=params,
            timeout=10
        )

        if response.status_code != 200:
            return None

        return response.json()

    except Exception:
        return None


# ============================================================
# MARKET SCREENER
# ============================================================

def get_market_candidates(token):

    """
    Uses Webull market screener endpoints.

    The exact endpoint/parameters can vary with the
    Webull OpenAPI account/version.

    The scanner combines several discovery groups:
        1. 5-minute gainers
        2. Daily gainers
        3. High RVOL
        4. High volume
    """

    candidates = []

    base_url = (
        "https://openapi.webullfinance.com"
    )

    endpoints = [

        # Short-term gainers
        (
            f"{base_url}/api/market/screener",
            {
                "region": "US",
                "type": "gainers",
                "limit": 200
            }
        ),

        # Daily movers
        (
            f"{base_url}/api/market/screener",
            {
                "region": "US",
                "type": "daily_gainers",
                "limit": 200
            }
        ),

        # Relative volume
        (
            f"{base_url}/api/market/screener",
            {
                "region": "US",
                "type": "relative_volume",
                "limit": 200
            }
        ),

        # Volume
        (
            f"{base_url}/api/market/screener",
            {
                "region": "US",
                "type": "volume",
                "limit": 200
            }
        )
    ]

    for endpoint, params in endpoints:

        data = webull_request(
            endpoint,
            token,
            params
        )

        if not data:
            continue

        # Try common response structures
        rows = []

        if isinstance(data, list):
            rows = data

        elif isinstance(data, dict):

            for key in [
                "data",
                "items",
                "list",
                "results",
                "stocks"
            ]:

                if isinstance(data.get(key), list):
                    rows = data[key]
                    break

        for row in rows:

            if isinstance(row, dict):
                candidates.append(row)

    return candidates


# ============================================================
# NORMALISE MARKET DATA
# ============================================================

def normalise_stock(row):

    def get_value(*names):

        for name in names:

            if name in row:
                value = row[name]

                if value is not None:
                    return value

        return None

    symbol = get_value(
        "symbol",
        "ticker",
        "tickerSymbol",
        "stockSymbol"
    )

    price = get_value(
        "price",
        "lastPrice",
        "latestPrice",
        "close"
    )

    change = get_value(
        "changePercent",
        "changePct",
        "percentChange",
        "change"
    )

    volume = get_value(
        "volume",
        "vol",
        "totalVolume"
    )

    rvol = get_value(
        "rvol",
        "relativeVolume",
        "relativeVol"
    )

    dollar_volume = get_value(
        "dollarVolume",
        "turnover",
        "amount",
        "volumeValue"
    )

    try:
        price = float(price)
    except Exception:
        price = 0.0

    try:
        change = float(change)
    except Exception:
        change = 0.0

    try:
        volume = float(volume)
    except Exception:
        volume = 0.0

    try:
        rvol = float(rvol)
    except Exception:
        rvol = 0.0

    try:
        dollar_volume = float(dollar_volume)
    except Exception:

        # Approximate dollar volume
        dollar_volume = price * volume

    return {
        "SYMBOL": str(symbol).upper()
        if symbol else "",
        "LTP": price,
        "%": change,
        "VOLUME": volume,
        "RVOL": rvol,
        "$VOL": dollar_volume
    }


# ============================================================
# FILTER STOCKS
# ============================================================

def filter_stocks(rows):

    clean_rows = []

    for row in rows:

        stock = normalise_stock(row)

        symbol = stock["SYMBOL"]

        if not symbol:
            continue

        price = stock["LTP"]
        change = stock["%"]
        volume = stock["VOLUME"]
        rvol = stock["RVOL"]

        if price < min_price:
            continue

        if price > max_price:
            continue

        if change < min_change:
            continue

        if volume < min_volume:
            continue

        if rvol < min_rvol:
            continue

        clean_rows.append(stock)

    if not clean_rows:
        return pd.DataFrame()

    df = pd.DataFrame(clean_rows)

    # Remove duplicate symbols
    df = df.drop_duplicates(
        subset=["SYMBOL"],
        keep="first"
    )

    # Highest momentum first
    df = df.sort_values(
        by=["%", "RVOL"],
        ascending=[False, False]
    )

    return df.head(int(max_stocks))


# ============================================================
# SCAN
# ============================================================

def run_scan():

    token = get_webull_token()

    if token is None:

        st.warning(
            "Webull API credentials are not configured. "
            "Add WEBULL_APP_KEY and WEBULL_APP_SECRET "
            "to Streamlit Secrets."
        )

        return pd.DataFrame()

    raw_rows = get_market_candidates(token)

    if not raw_rows:

        return pd.DataFrame()

    df = filter_stocks(raw_rows)

    if df.empty:
        return df

    now = datetime.now().strftime("%H:%M:%S")

    previous = st.session_state.previous_symbols

    current_symbols = set(
        df["SYMBOL"].tolist()
    )

    # --------------------------------------------------------
    # REPEAT DETECTION
    # --------------------------------------------------------

    repeat_symbols = (
        current_symbols.intersection(previous)
    )

    st.session_state.repeat_symbols = repeat_symbols

    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    df.insert(
        0,
        "TIME",
        now
    )

    st.session_state.previous_symbols = current_symbols

    st.session_state.last_scan = now

    return df


# ============================================================
# RUN SCAN
# ============================================================

if scan_button or st.session_state.scan_data.empty:

    result = run_scan()

    if result is not None:
        st.session_state.scan_data = result


# ============================================================
# DATA
# ============================================================

df = st.session_state.scan_data.copy()


# ============================================================
# HEADER STATUS
# ============================================================

last_scan = st.session_state.last_scan

if last_scan:
    status_text = (
        f"Last scan: {last_scan}   •   "
        f"{len(df)} stocks"
    )
else:
    status_text = "Waiting for scanner..."

st.markdown(
    f'<div class="scanner-status">{status_text}</div>',
    unsafe_allow_html=True
)


# ============================================================
# TRADINGVIEW CHART
# ============================================================

def show_chart(symbol):

    if not symbol:
        symbol = "AAPL"

    # --------------------------------------------------------
    # Most common US exchange mapping
    # --------------------------------------------------------

    nyse_symbols = {
        "BAC",
        "JPM",
        "WMT",
        "UBER",
        "F",
        "GM",
        "T",
        "XOM",
        "CVX",
        "DIS",
        "KO",
        "PFE",
        "BABA",
        "NIO",
        "AMC",
        "GME"
    }

    if symbol in nyse_symbols:
        exchange = "NYSE"
    else:
        exchange = "NASDAQ"

    chart_url = (
        "https://www.tradingview.com/widgetembed/"
        f"?symbol={exchange}%3A{symbol}"
        f"&interval={chart_interval}"
        "&theme=dark"
        "&style=1"
        "&toolbarbg=f1f3f6"
        "&hidesidetoolbar=0"
        "&withdateranges=1"
        "&hideideas=1"
        "&studies=[]"
    )

    st.components.v1.iframe(
        chart_url,
        height=600,
        scrolling=False
    )


# ============================================================
# MAIN LAYOUT
# ============================================================

left_col, right_col = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT STOCK LIST
# ============================================================

with left_col:

    st.markdown("### Stocks")

    if df.empty:

        st.info(
            "No stocks currently match the filters."
        )

    else:

        for _, row in df.iterrows():

            symbol = str(
                row["SYMBOL"]
            ).upper()

            is_repeat = (
                symbol
                in st.session_state.repeat_symbols
            )

            is_selected = (
                symbol
                == st.session_state.selected_symbol
            )

            # ------------------------------------------------
            # Repeat indicator
            # ------------------------------------------------

            if is_repeat:
                symbol_text = f"■ {symbol}"
            else:
                symbol_text = symbol

            # ------------------------------------------------
            # Selected stock
            # ------------------------------------------------

            if is_selected:
                symbol_text = f"▶ {symbol_text}"

            # ------------------------------------------------
            # Native Streamlit button
            # ------------------------------------------------

            clicked = st.button(
                symbol_text,
                key=f"stock_button_{symbol}",
                use_container_width=True
            )

            if clicked:

                st.session_state.selected_symbol = symbol

                st.rerun()


# ============================================================
# RIGHT SIDE
# ============================================================

with right_col:

    selected = (
        st.session_state.selected_symbol
    )

    # If nothing selected, automatically select first stock
    if selected is None and not df.empty:

        selected = str(
            df.iloc[0]["SYMBOL"]
        )

        st.session_state.selected_symbol = selected

    if selected:

        # ----------------------------------------------------
        # Selected stock title
        # ----------------------------------------------------

        st.markdown(
            f"### {selected}"
        )

        # ----------------------------------------------------
        # Find selected stock information
        # ----------------------------------------------------

        selected_rows = df[
            df["SYMBOL"] == selected
        ]

        if not selected_rows.empty:

            row = selected_rows.iloc[0]

            metric1, metric2, metric3, metric4 = st.columns(4)

            with metric1:
                st.metric(
                    "LTP",
                    f"${row['LTP']:.2f}"
                )

            with metric2:
                st.metric(
                    "%",
                    f"{row['%']:.2f}%"
                )

            with metric3:
                st.metric(
                    "RVOL",
                    f"{row['RVOL']:.1f}x"
                )

            with metric4:
                st.metric(
                    "$VOL",
                    f"${row['$VOL']/1_000_000:.1f}M"
                )

        # ----------------------------------------------------
        # TradingView
        # ----------------------------------------------------

        show_chart(selected)

    else:

        st.info(
            "Select a stock from the list."
        )


# ============================================================
# BOTTOM DATA TABLE
# ============================================================

st.divider()

if not df.empty:

    display_df = df[
        [
            "TIME",
            "SYMBOL",
            "LTP",
            "%",
            "RVOL",
            "$VOL"
        ]
    ].copy()

    display_df["LTP"] = display_df[
        "LTP"
    ].map(
        lambda x: f"${x:.2f}"
    )

    display_df["%"] = display_df[
        "%"
    ].map(
        lambda x: f"{x:.2f}%"
    )

    display_df["RVOL"] = display_df[
        "RVOL"
    ].map(
        lambda x: f"{x:.1f}x"
    )

    display_df["$VOL"] = display_df[
        "$VOL"
    ].map(
        lambda x: (
            f"${x/1_000_000:.1f}M"
            if x >= 1_000_000
            else f"${x/1_000:.0f}K"
        )
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=300
    )


# ============================================================
# AUTO SCAN
# ============================================================

if auto_scan:

    time.sleep(
        int(refresh_seconds)
    )

    result = run_scan()

    if result is not None:

        st.session_state.scan_data = result

    st.rerun()
