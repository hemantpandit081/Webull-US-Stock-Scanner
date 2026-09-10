import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit.components.v1 as components

from webull.core.client import ApiClient
from webull.data.data_client import DataClient


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="US Stock Momentum Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 0.7rem;
        padding-left: 1rem;
        padding-right: 1rem;
        padding-bottom: 0.5rem;
    }

    h1 {
        font-size: 24px !important;
        margin-bottom: 2px !important;
    }

    .market-status {
        font-size: 13px;
        color: #888;
        margin-bottom: 8px;
    }

    .scanner-header {
        background: #111827;
        color: #9ca3af;
        font-size: 11px;
        font-weight: 600;
        padding: 7px 5px;
        border-radius: 4px;
        margin-bottom: 2px;
    }

    .stock-row {
        font-size: 12px;
        padding: 1px 0;
        margin: 0;
    }

    div[data-testid="stButton"] {
        margin: 0 !important;
        padding: 0 !important;
    }

    div[data-testid="stButton"] button {
        min-height: 26px !important;
        height: 26px !important;
        padding: 0 3px !important;
        margin: 0 !important;
        border: none !important;
        background: transparent !important;
        font-size: 12px !important;
        text-align: left !important;
    }

    div[data-testid="stButton"] button:hover {
        background: #1f2937 !important;
    }

    .info-box {
        font-size: 11px;
        color: #888;
        margin-top: 2px;
        margin-bottom: 6px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SESSION STATE
# =========================================================

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "AAPL"

if "scan_history" not in st.session_state:
    st.session_state.scan_history = {}

if "trigger_times" not in st.session_state:
    st.session_state.trigger_times = {}

if "last_results" not in st.session_state:
    st.session_state.last_results = []

if "scan_count" not in st.session_state:
    st.session_state.scan_count = 0

if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = None

if "last_scan_seconds" not in st.session_state:
    st.session_state.last_scan_seconds = 0


# =========================================================
# WEBULL CLIENT
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
# SIDEBAR
# =========================================================

st.sidebar.title("⚙ Scanner Settings")

min_price = st.sidebar.number_input(
    "Minimum price",
    min_value=0.01,
    value=1.0,
    step=0.50,
)

max_price = st.sidebar.number_input(
    "Maximum price",
    min_value=1.0,
    value=1000.0,
    step=10.0,
)

min_volume = st.sidebar.number_input(
    "Minimum volume",
    min_value=0,
    value=100000,
    step=10000,
)

min_rvol = st.sidebar.number_input(
    "Minimum RVOL",
    min_value=0.0,
    value=1.5,
    step=0.1,
)

min_change = st.sidebar.number_input(
    "Minimum % change",
    min_value=-100.0,
    value=1.0,
    step=0.5,
)

min_dollar_volume = st.sidebar.number_input(
    "Minimum $ volume",
    min_value=0,
    value=1000000,
    step=100000,
)

repeat_tolerance = st.sidebar.slider(
    "Repeat volume tolerance",
    min_value=0.50,
    max_value=0.99,
    value=0.90,
    step=0.01,
)

refresh_seconds = st.sidebar.number_input(
    "Refresh seconds",
    min_value=5,
    max_value=300,
    value=15,
    step=5,
)

chart_interval = st.sidebar.selectbox(
    "Chart interval",
    [
        "1",
        "3",
        "5",
        "15",
        "30",
        "60",
        "D",
    ],
    index=0,
)

auto_scan = st.sidebar.checkbox(
    "Auto scan",
    value=True,
)

candidate_count = st.sidebar.slider(
    "Momentum candidates",
    min_value=100,
    max_value=600,
    value=500,
    step=100,
)

show_debug = st.sidebar.checkbox(
    "Show debug information",
    value=False,
)


# =========================================================
# TIME
# =========================================================

def ny_time():

    return datetime.now(
        ZoneInfo("America/New_York")
    )


def market_status():

    now = ny_time()

    weekday = now.weekday()

    if weekday >= 5:
        return "🔴 Market Closed"

    current = now.hour * 60 + now.minute

    if 4 * 60 <= current < 9 * 60 + 30:
        return "🟡 Pre-Market"

    if 9 * 60 + 30 <= current < 16 * 60:
        return "🟢 Market Open"

    if 16 * 60 <= current < 20 * 60:
        return "🟡 After-Hours"

    return "🔴 Market Closed"


# =========================================================
# SAFE NUMBER
# =========================================================

def number(value, default=0.0):

    try:

        if value is None:
            return default

        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()

        return float(value)

    except Exception:
        return default


# =========================================================
# EXTRACT RESPONSE RECORDS
# =========================================================

def extract_records(obj):

    """
    Webull responses can have slightly different
    JSON nesting depending on endpoint/version.

    Find the list of stock dictionaries automatically.
    """

    if obj is None:
        return []

    if isinstance(obj, list):

        if all(isinstance(x, dict) for x in obj):
            return obj

        result = []

        for x in obj:
            result.extend(extract_records(x))

        return result

    if isinstance(obj, dict):

        # Common keys first
        for key in [
            "data",
            "items",
            "list",
            "results",
            "rows",
            "stocks",
            "records",
        ]:

            if key in obj:

                found = extract_records(obj[key])

                if found:
                    return found

        # Search nested dictionaries
        for value in obj.values():

            found = extract_records(value)

            if found:
                return found

    return []


# =========================================================
# PARSE STOCK
# =========================================================

def parse_stock(item):

    symbol = str(
        item.get("symbol")
        or item.get("ticker")
        or ""
    ).upper().strip()

    if not symbol:
        return None

    price = number(
        item.get("price")
        or item.get("latest_price")
        or item.get("latestPrice")
        or item.get("close")
    )

    change_ratio = number(
        item.get("change_ratio")
        or item.get("changeRatio")
        or item.get("change_percent")
        or item.get("changePercent")
    )

    # Webull change_ratio is normally decimal.
    if abs(change_ratio) < 1:
        change_pct = change_ratio * 100
    else:
        change_pct = change_ratio

    volume = number(
        item.get("volume")
        or item.get("tradeVolume")
        or item.get("totalVolume")
    )

    rvol = number(
        item.get("relative_volume_10d")
        or item.get("relativeVolume10d")
        or item.get("relative_volume")
        or item.get("rvol")
    )

    dollar_volume = price * volume

    exchange = str(
        item.get("exchange_code")
        or item.get("exchange")
        or ""
    ).upper()

    name = str(
        item.get("name")
        or ""
    )

    return {
        "symbol": symbol,
        "name": name,
        "price": price,
        "change_pct": change_pct,
        "volume": volume,
        "rvol": rvol,
        "dollar_volume": dollar_volume,
        "exchange": exchange,
    }


# =========================================================
# WEBULL FAST MARKET SCREENER
# =========================================================

def get_market_candidates():

    records = []

    errors = []

    # -----------------------------------------------------
    # 1. 5-minute gainers
    # -----------------------------------------------------

    try:

        response = data_client.screener.list_gainers_losers(
            "MIN_5",
            "US_STOCK",
            "CHANGE_RATIO",
            "DESC",
        )

        payload = response.json()

        records.extend(
            extract_records(payload)
        )

    except Exception as e:

        errors.append(
            f"5-min gainers: {e}"
        )

    # -----------------------------------------------------
    # 2. Daily gainers
    # -----------------------------------------------------

    try:

        response = data_client.screener.list_gainers_losers(
            "DAY_1",
            "US_STOCK",
            "CHANGE_RATIO",
            "DESC",
        )

        payload = response.json()

        records.extend(
            extract_records(payload)
        )

    except Exception as e:

        errors.append(
            f"daily gainers: {e}"
        )

    # -----------------------------------------------------
    # 3. Highest RVOL
    # -----------------------------------------------------

    try:

        response = data_client.screener.list_most_active(
            "US_STOCK",
            "RELATIVE_VOLUME_10D",
            "RELATIVE_VOLUME_10D",
            "DESC",
        )

        payload = response.json()

        records.extend(
            extract_records(payload)
        )

    except Exception as e:

        errors.append(
            f"RVOL screener: {e}"
        )

    # -----------------------------------------------------
    # 4. Highest volume
    # -----------------------------------------------------

    try:

        response = data_client.screener.list_most_active(
            "US_STOCK",
            "VOLUME",
            "VOLUME",
            "DESC",
        )

        payload = response.json()

        records.extend(
            extract_records(payload)
        )

    except Exception as e:

        errors.append(
            f"volume screener: {e}"
        )

    # -----------------------------------------------------
    # Convert + remove duplicates
    # -----------------------------------------------------

    parsed = {}

    for item in records:

        stock = parse_stock(item)

        if stock is None:
            continue

        symbol = stock["symbol"]

        if symbol not in parsed:

            parsed[symbol] = stock

        else:

            # Keep the version with the highest RVOL/change
            old = parsed[symbol]

            if (
                stock["rvol"] > old["rvol"]
                or stock["change_pct"] > old["change_pct"]
            ):
                parsed[symbol] = stock

    candidates = list(parsed.values())

    # -----------------------------------------------------
    # Fast local filtering
    # -----------------------------------------------------

    filtered = []

    for stock in candidates:

        if stock["price"] < min_price:
            continue

        if stock["price"] > max_price:
            continue

        if stock["volume"] < min_volume:
            continue

        if stock["change_pct"] < min_change:
            continue

        if stock["rvol"] < min_rvol:
            continue

        if stock["dollar_volume"] < min_dollar_volume:
            continue

        filtered.append(stock)

    # Highest momentum first
    filtered.sort(
        key=lambda x: (
            x["rvol"],
            x["change_pct"],
            x["dollar_volume"],
        ),
        reverse=True,
    )

    filtered = filtered[:candidate_count]

    return filtered, errors


# =========================================================
# REPEAT VOLUME
# =========================================================

def check_repeat_volume(
    symbol,
    volume,
    tolerance,
):

    history = st.session_state.scan_history

    if symbol not in history:

        history[symbol] = []

    previous = history[symbol]

    repeat = False

    if volume > 0:

        for old_volume in previous:

            if old_volume <= 0:
                continue

            ratio = volume / old_volume

            if (
                tolerance
                <= ratio
                <= (1 / tolerance)
            ):

                repeat = True
                break

    previous.append(volume)

    # Keep only last 200 observations
    history[symbol] = previous[-200:]

    return repeat


# =========================================================
# TRIGGER TIME
# =========================================================

def update_trigger_time(
    symbol,
    active,
):

    trigger_times = st.session_state.trigger_times

    if active:

        if symbol not in trigger_times:

            trigger_times[symbol] = (
                ny_time().strftime("%H:%M:%S")
            )

        return trigger_times[symbol]

    return trigger_times.get(symbol, "")


# =========================================================
# PROCESS RESULTS
# =========================================================

def process_results(candidates):

    results = []

    current_symbols = set()

    for stock in candidates:

        symbol = stock["symbol"]

        current_symbols.add(symbol)

        repeat = check_repeat_volume(
            symbol,
            stock["volume"],
            repeat_tolerance,
        )

        time_value = update_trigger_time(
            symbol,
            True,
        )

        results.append(
            {
                "TIME": time_value,
                "SYMBOL": symbol,
                "LTP": stock["price"],
                "%": stock["change_pct"],
                "RVOL": stock["rvol"],
                "$VOL": stock["dollar_volume"],
                "REPEAT": repeat,
                "EXCHANGE": stock["exchange"],
                "NAME": stock["name"],
            }
        )

    return results


# =========================================================
# RUN SCAN
# =========================================================

def run_scan():

    start = time.perf_counter()

    candidates, errors = get_market_candidates()

    results = process_results(
        candidates
    )

    elapsed = time.perf_counter() - start

    st.session_state.last_results = results

    st.session_state.scan_count += 1

    st.session_state.last_scan_time = (
        ny_time().strftime("%H:%M:%S")
    )

    st.session_state.last_scan_seconds = elapsed

    return results, errors


# =========================================================
# TRADINGVIEW
# =========================================================

def tradingview_chart(symbol, interval):

    # Better exchange detection
    exchange = "NASDAQ"

    nyse_symbols = {
        "BAC",
        "JPM",
        "WMT",
        "UBER",
        "NIO",
        "BABA",
        "T",
        "F",
        "GM",
        "PFE",
        "XOM",
        "CVX",
        "DIS",
        "KO",
        "V",
        "MA",
    }

    if symbol in nyse_symbols:
        exchange = "NYSE"

    tv_symbol = f"{exchange}:{symbol}"

    html = f"""
    <div style="width:100%; height:600px;">
        <iframe
            src="https://www.tradingview.com/widgetembed/?frameElementId=tradingview_widget&symbol={tv_symbol}&interval={interval}&hidesidetoolbar=0&hidetoptoolbar=0&symboledit=1&saveimage=0&toolbarbg=f1f3f6&studies=[]&theme=dark&style=1&timezone=America%2FNew_York&withdateranges=1&hideideas=1"
            style="width:100%;height:600px;border:0;"
            allowtransparency="true"
            scrolling="no">
        </iframe>
    </div>
    """

    components.html(
        html,
        height=610,
    )


# =========================================================
# HEADER
# =========================================================

st.title("📈 US Stock Momentum Scanner")

st.markdown(
    f'<div class="market-status">{market_status()}</div>',
    unsafe_allow_html=True,
)


# =========================================================
# CONTROL ROW
# =========================================================

control1, control2, control3, control4 = st.columns(
    [1, 1, 1, 4]
)

with control1:

    if st.button(
        "🔄 Scan Now",
        use_container_width=True,
    ):

        with st.spinner("Scanning..."):

            results, errors = run_scan()

        st.rerun()


with control2:

    if st.button(
        "🧹 Clear History",
        use_container_width=True,
    ):

        st.session_state.scan_history = {}

        st.session_state.trigger_times = {}

        st.rerun()


with control3:

    st.caption(
        f"Scan #{st.session_state.scan_count}"
    )


# =========================================================
# INFO
# =========================================================

info1, info2, info3, info4 = st.columns(4)

with info1:

    st.markdown(
        f"**Last scan:** "
        f"{st.session_state.last_scan_time or '--'}"
    )

with info2:

    st.markdown(
        f"**Scan speed:** "
        f"{st.session_state.last_scan_seconds:.2f}s"
    )

with info3:

    st.markdown(
        f"**Stocks shown:** "
        f"{len(st.session_state.last_results)}"
    )

with info4:

    st.markdown(
        "**Source:** Webull"
    )


# =========================================================
# FIRST SCAN
# =========================================================

if not st.session_state.last_results:

    with st.spinner(
        "Loading US momentum stocks..."
    ):

        results, errors = run_scan()

else:

    results = st.session_state.last_results

    errors = []


# =========================================================
# DEBUG
# =========================================================

if show_debug and errors:

    st.warning(
        "\n".join(errors)
    )


# =========================================================
# MAIN LAYOUT
# =========================================================

left, right = st.columns(
    [35, 65],
    gap="small",
)


# =========================================================
# LEFT SCANNER
# =========================================================

with left:

    st.markdown(
        """
        <div class="scanner-header">
            TIME &nbsp;&nbsp;&nbsp;
            SYMBOL &nbsp;&nbsp;&nbsp;
            LTP &nbsp;&nbsp;&nbsp;
            % &nbsp;&nbsp;&nbsp;
            RVOL &nbsp;&nbsp;&nbsp;
            $VOL
        </div>
        """,
        unsafe_allow_html=True,
    )

    if results:

        # Highest RVOL / momentum first
        sorted_results = sorted(
            results,
            key=lambda x: (
                x["RVOL"],
                x["%"],
            ),
            reverse=True,
        )

        for row in sorted_results:

            symbol = row["SYMBOL"]

            repeat_marker = (
                "■ "
                if row["REPEAT"]
                else ""
            )

            c1, c2, c3, c4, c5, c6 = st.columns(
                [1.15, 1.25, 1.0, 0.85, 0.95, 1.15],
                gap="small",
            )

            with c1:

                st.markdown(
                    f'<div class="stock-row">'
                    f'{row["TIME"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with c2:

                button_label = (
                    f"{repeat_marker}{symbol}"
                )

                if st.button(
                    button_label,
                    key=f"stock_{symbol}",
                    use_container_width=True,
                ):

                    st.session_state.selected_symbol = symbol

                    st.rerun()

            with c3:

                st.markdown(
                    f'<div class="stock-row">'
                    f'{row["LTP"]:.2f}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with c4:

                st.markdown(
                    f'<div class="stock-row">'
                    f'{row["%"]:+.1f}%'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with c5:

                st.markdown(
                    f'<div class="stock-row">'
                    f'{row["RVOL"]:.1f}x'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with c6:

                dollar_volume = row["$VOL"]

                if dollar_volume >= 1_000_000_000:

                    vol_text = (
                        f"${dollar_volume / 1_000_000_000:.1f}B"
                    )

                elif dollar_volume >= 1_000_000:

                    vol_text = (
                        f"${dollar_volume / 1_000_000:.1f}M"
                    )

                elif dollar_volume >= 1_000:

                    vol_text = (
                        f"${dollar_volume / 1_000:.1f}K"
                    )

                else:

                    vol_text = (
                        f"${dollar_volume:.0f}"
                    )

                st.markdown(
                    f'<div class="stock-row">'
                    f'{vol_text}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    else:

        st.info(
            "No stocks currently match your filters."
        )


# =========================================================
# RIGHT CHART
# =========================================================

with right:

    st.markdown(
        f"### {st.session_state.selected_symbol}"
    )

    tradingview_chart(
        st.session_state.selected_symbol,
        chart_interval,
    )


# =========================================================
# AUTO REFRESH
# =========================================================

if auto_scan:

    time.sleep(
        max(5, int(refresh_seconds))
    )

    st.rerun()
