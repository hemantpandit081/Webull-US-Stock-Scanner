import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime
import plotly.graph_objects as go

from webull.core.client import ApiClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="US Momentum Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    html, body, [class*="css"] {
        font-family: Arial, sans-serif;
    }

    .block-container {
        padding-top: 0.7rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 100%;
    }

    .scanner-title {
        font-size: 25px;
        font-weight: 700;
        margin-bottom: 0px;
    }

    .scanner-subtitle {
        color: #8b949e;
        font-size: 13px;
        margin-bottom: 10px;
    }

    .table-header {
        color: #8b949e;
        font-size: 11px;
        font-weight: 600;
        padding: 4px 5px;
        border-bottom: 1px solid #30363d;
    }

    div[data-testid="stButton"] > button {
        width: 100%;
        min-height: 30px !important;
        height: 30px !important;
        padding: 0px 5px !important;
        border-radius: 3px !important;
        border: 1px solid #30363d !important;
        background: #161b22 !important;
        color: #f0f6fc !important;
        font-size: 12px !important;
        text-align: left !important;
    }

    div[data-testid="stButton"] > button:hover {
        border-color: #58a6ff !important;
        color: #58a6ff !important;
        background: #1c2128 !important;
    }

    .selected-stock {
        border-left: 3px solid #58a6ff;
        padding-left: 7px;
        font-weight: 700;
    }

    .chart-title {
        font-size: 17px;
        font-weight: 700;
        margin-bottom: 2px;
    }

    .status {
        color: #8b949e;
        font-size: 12px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SETTINGS
# ============================================================

REGION_ID = "au"
CATEGORY = Category.US_STOCK.name

MIN_PRICE = 0.50
MAX_PRICE = 50.00

MIN_CHANGE = 2.0
MIN_RVOL = 2.0
MIN_VOLUME = 100_000

REFRESH_SECONDS = 15

MAX_CANDIDATES = 250


# ============================================================
# WEBULL CONNECTION
# ============================================================

APP_KEY = st.secrets.get("WEBULL_APP_KEY", "")
APP_SECRET = st.secrets.get("WEBULL_APP_SECRET", "")

if not APP_KEY or not APP_SECRET:
    st.error(
        "Webull credentials not found. "
        "Add WEBULL_APP_KEY and WEBULL_APP_SECRET to Streamlit Secrets."
    )
    st.stop()


@st.cache_resource
def get_webull_client():

    api_client = ApiClient(
        APP_KEY,
        APP_SECRET,
        REGION_ID
    )

    data_client = DataClient(api_client)

    return data_client


data_client = get_webull_client()


# ============================================================
# SESSION STATE
# ============================================================

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = None

if "scanner_rows" not in st.session_state:
    st.session_state.scanner_rows = []

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None

if "diagnostic" not in st.session_state:
    st.session_state.diagnostic = {}

if "first_seen" not in st.session_state:
    st.session_state.first_seen = {}

if "repeat_symbols" not in st.session_state:
    st.session_state.repeat_symbols = set()


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):

    try:

        if value is None:
            return default

        if isinstance(value, str):
            value = value.replace(",", "")
            value = value.replace("$", "")
            value = value.replace("%", "")
            value = value.strip()

        return float(value)

    except Exception:
        return default


def recursive_records(obj):

    """
    Try to find lists of stock-like dictionaries anywhere
    inside Webull's JSON response.
    """

    found = []

    if isinstance(obj, list):

        for item in obj:

            if isinstance(item, dict):

                found.append(item)

                nested = recursive_records(item)

                if nested:
                    found.extend(nested)

            elif isinstance(item, list):

                found.extend(recursive_records(item))

    elif isinstance(obj, dict):

        for value in obj.values():

            if isinstance(value, (list, dict)):

                found.extend(recursive_records(value))

    return found


def clean_records(response):

    """
    Converts Webull response into a flat list of dictionaries.
    """

    if response is None:
        return []

    try:
        payload = response.json()
    except Exception:
        payload = response

    records = recursive_records(payload)

    # Remove duplicates
    unique = []

    seen = set()

    for r in records:

        symbol = (
            r.get("symbol")
            or r.get("ticker")
            or r.get("stock_symbol")
            or r.get("code")
        )

        if symbol:

            symbol = str(symbol).upper()

            if symbol not in seen:

                seen.add(symbol)
                unique.append(r)

    return unique


def get_symbol(record):

    return str(
        record.get("symbol")
        or record.get("ticker")
        or record.get("stock_symbol")
        or record.get("code")
        or ""
    ).upper()


def get_price(record):

    keys = [
        "price",
        "last_price",
        "latest_price",
        "close",
        "last",
        "current_price",
        "pre_close",
    ]

    for key in keys:

        if key in record:

            value = safe_float(record.get(key))

            if value > 0:
                return value

    return 0.0


def get_change(record):

    keys = [
        "change_ratio",
        "changeRate",
        "change_rate",
        "change_percent",
        "changePercent",
        "pct_change",
        "percent_change",
    ]

    for key in keys:

        if key in record:

            value = safe_float(record.get(key))

            # Webull may return decimal ratio such as 0.051
            if abs(value) < 1:

                value *= 100

            return value

    # Sometimes only change + preclose exists

    change = safe_float(
        record.get("change")
    )

    pre_close = safe_float(
        record.get("pre_close")
        or record.get("preClose")
    )

    if pre_close:

        return change / pre_close * 100

    return 0.0


def get_volume(record):

    keys = [
        "volume",
        "vol",
        "trade_volume",
        "total_volume",
    ]

    for key in keys:

        if key in record:

            value = safe_float(record.get(key))

            if value > 0:
                return value

    return 0.0


def get_rvol(record):

    keys = [
        "relative_volume",
        "relativeVolume",
        "rvol",
        "relative_vol",
        "volume_ratio",
        "volumeRatio",
    ]

    for key in keys:

        if key in record:

            value = safe_float(record.get(key))

            if value > 0:
                return value

    return 0.0


def get_dollar_volume(record):

    keys = [
        "turnover",
        "turnover_amount",
        "turnoverAmount",
        "amount",
        "trade_amount",
        "dollar_volume",
    ]

    for key in keys:

        if key in record:

            value = safe_float(record.get(key))

            if value > 0:
                return value

    price = get_price(record)
    volume = get_volume(record)

    return price * volume


def format_money(value):

    value = safe_float(value)

    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"

    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"

    if value >= 1_000:
        return f"${value / 1_000:.1f}K"

    return f"${value:,.0f}"


# ============================================================
# WEBULL SCREENER
# ============================================================

def screener_gainers(rank_type):

    try:

        response = data_client.market_data.get_gainers_losers(
            rank_type,
            CATEGORY,
            "CHANGE_RATIO",
            "DESC",
            1,
            100,
        )

        return response

    except TypeError:

        # Fallback for SDK signature variations

        try:

            response = data_client.market_data.get_gainers_losers(
                rank_type=rank_type,
                category=CATEGORY,
                sort_by="CHANGE_RATIO",
                direction="DESC",
                page_index=1,
                page_size=100,
            )

            return response

        except Exception as e:

            return e

    except Exception as e:

        return e


def screener_active(rank_type):

    try:

        response = data_client.market_data.get_most_active(
            CATEGORY,
            rank_type,
            rank_type,
            "DESC",
            1,
            100,
        )

        return response

    except TypeError:

        try:

            response = data_client.market_data.get_most_active(
                category=CATEGORY,
                rank_type=rank_type,
                sort_by=rank_type,
                direction="DESC",
                page_index=1,
                page_size=100,
            )

            return response

        except Exception as e:

            return e

    except Exception as e:

        return e


# ============================================================
# SCAN
# ============================================================

def run_scan():

    diagnostics = {}

    all_records = []

    # --------------------------------------------------------
    # 5 MINUTE GAINERS
    # --------------------------------------------------------

    r1 = screener_gainers("MIN_5")

    if isinstance(r1, Exception):

        diagnostics["5M_GAINERS"] = f"ERROR: {r1}"

    else:

        records = clean_records(r1)

        diagnostics["5M_GAINERS"] = {
            "status": getattr(r1, "status_code", "unknown"),
            "records": len(records),
        }

        all_records.extend(records)


    # --------------------------------------------------------
    # DAILY GAINERS
    # --------------------------------------------------------

    r2 = screener_gainers("DAY_1")

    if isinstance(r2, Exception):

        diagnostics["DAY_GAINERS"] = f"ERROR: {r2}"

    else:

        records = clean_records(r2)

        diagnostics["DAY_GAINERS"] = {
            "status": getattr(r2, "status_code", "unknown"),
            "records": len(records),
        }

        all_records.extend(records)


    # --------------------------------------------------------
    # RELATIVE VOLUME
    # --------------------------------------------------------

    r3 = screener_active("RELATIVE_VOLUME_10D")

    if isinstance(r3, Exception):

        diagnostics["RVOL"] = f"ERROR: {r3}"

    else:

        records = clean_records(r3)

        diagnostics["RVOL"] = {
            "status": getattr(r3, "status_code", "unknown"),
            "records": len(records),
        }

        all_records.extend(records)


    # --------------------------------------------------------
    # MOST ACTIVE
    # --------------------------------------------------------

    r4 = screener_active("VOLUME")

    if isinstance(r4, Exception):

        diagnostics["VOLUME"] = f"ERROR: {r4}"

    else:

        records = clean_records(r4)

        diagnostics["VOLUME"] = {
            "status": getattr(r4, "status_code", "unknown"),
            "records": len(records),
        }

        all_records.extend(records)


    # --------------------------------------------------------
    # UNIQUE SYMBOLS
    # --------------------------------------------------------

    symbol_records = {}

    for record in all_records:

        symbol = get_symbol(record)

        if not symbol:
            continue

        if symbol not in symbol_records:

            symbol_records[symbol] = record

        else:

            # Merge information from different screeners
            symbol_records[symbol].update(record)


    diagnostics["UNIQUE_SYMBOLS"] = len(symbol_records)

    # --------------------------------------------------------
    # BUILD SCANNER
    # --------------------------------------------------------

    rows = []

    now = datetime.now()

    for symbol, record in symbol_records.items():

        price = get_price(record)
        change = get_change(record)
        volume = get_volume(record)
        rvol = get_rvol(record)
        dollar_volume = get_dollar_volume(record)

        # ----------------------------------------------------
        # Filters
        # ----------------------------------------------------

        if price < MIN_PRICE:
            continue

        if price > MAX_PRICE:
            continue

        if change < MIN_CHANGE:
            continue

        if volume < MIN_VOLUME:
            continue

        # RVOL may not exist in gainers response.
        # Only reject if we actually have an RVOL value.
        if rvol > 0 and rvol < MIN_RVOL:
            continue

        # ----------------------------------------------------
        # FIRST SEEN
        # ----------------------------------------------------

        if symbol not in st.session_state.first_seen:

            st.session_state.first_seen[symbol] = now.strftime(
                "%H:%M:%S"
            )

        else:

            st.session_state.repeat_symbols.add(symbol)


        rows.append(
            {
                "TIME": st.session_state.first_seen[symbol],
                "SYMBOL": symbol,
                "LTP": price,
                "%": change,
                "RVOL": rvol,
                "$VOL": dollar_volume,
            }
        )


    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    rows.sort(
        key=lambda x: (
            x["RVOL"],
            x["%"],
            x["$VOL"],
        ),
        reverse=True,
    )

    rows = rows[:MAX_CANDIDATES]

    diagnostics["MATCHING_STOCKS"] = len(rows)

    return rows, diagnostics


# ============================================================
# RUN SCANNER
# ============================================================

try:

    rows, diagnostics = run_scan()

    st.session_state.scanner_rows = rows
    st.session_state.diagnostic = diagnostics
    st.session_state.last_scan = datetime.now()

except Exception as e:

    st.session_state.scanner_rows = []

    st.session_state.diagnostic = {
        "SCAN ERROR": str(e)
    }


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="scanner-title">US MOMENTUM SCANNER</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="scanner-subtitle">'
    'Webull AU OpenAPI • US Stocks • Momentum • Volume • RVOL'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Scanner Filters")

    st.number_input(
        "Minimum price",
        value=float(MIN_PRICE),
        key="ui_min_price",
    )

    st.number_input(
        "Maximum price",
        value=float(MAX_PRICE),
        key="ui_max_price",
    )

    st.number_input(
        "Minimum % change",
        value=float(MIN_CHANGE),
        key="ui_min_change",
    )

    st.number_input(
        "Minimum volume",
        value=int(MIN_VOLUME),
        key="ui_min_volume",
    )

    st.number_input(
        "Minimum RVOL",
        value=float(MIN_RVOL),
        key="ui_min_rvol",
    )

    st.number_input(
        "Refresh seconds",
        value=int(REFRESH_SECONDS),
        min_value=5,
        max_value=120,
        key="ui_refresh",
    )

    if st.button("🔄 Scan now", use_container_width=True):

        st.rerun()


# ============================================================
# USE CURRENT FILTER VALUES
# ============================================================

MIN_PRICE = st.session_state.ui_min_price
MAX_PRICE = st.session_state.ui_max_price
MIN_CHANGE = st.session_state.ui_min_change
MIN_VOLUME = st.session_state.ui_min_volume
MIN_RVOL = st.session_state.ui_min_rvol


# ============================================================
# MAIN LAYOUT
# ============================================================

left, right = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT - STOCK LIST
# ============================================================

with left:

    st.markdown(
        """
        <div class="table-header">
        TIME &nbsp;&nbsp;&nbsp;&nbsp; SYMBOL &nbsp;&nbsp;&nbsp; LTP &nbsp;&nbsp; % &nbsp;&nbsp; RVOL &nbsp;&nbsp; $VOL
        </div>
        """,
        unsafe_allow_html=True,
    )

    rows = st.session_state.scanner_rows

    if not rows:

        st.warning(
            "No stocks currently match the filters."
        )

    else:

        for row in rows:

            symbol = row["SYMBOL"]

            repeat = (
                " ■"
                if symbol in st.session_state.repeat_symbols
                else ""
            )

            label = (
                f'{row["TIME"]}   '
                f'{symbol}{repeat}   '
                f'{row["LTP"]:.2f}   '
                f'{row["%"]:.1f}%   '
                f'{row["RVOL"]:.1f}x   '
                f'{format_money(row["$VOL"])}'
            )

            clicked = st.button(
                label,
                key=f"stock_{symbol}",
                use_container_width=True,
            )

            if clicked:

                st.session_state.selected_symbol = symbol
                st.rerun()


# ============================================================
# SELECT DEFAULT STOCK
# ============================================================

if (
    st.session_state.selected_symbol is None
    and st.session_state.scanner_rows
):

    st.session_state.selected_symbol = (
        st.session_state.scanner_rows[0]["SYMBOL"]
    )


selected = st.session_state.selected_symbol


# ============================================================
# RIGHT - CHART
# ============================================================

with right:

    if selected:

        st.markdown(
            f'<div class="chart-title">{selected}</div>',
            unsafe_allow_html=True,
        )

        if st.session_state.last_scan:

            st.markdown(
                f'<div class="status">'
                f'Last scan: '
                f'{st.session_state.last_scan.strftime("%H:%M:%S")}'
                f'</div>',
                unsafe_allow_html=True,
            )


        # ----------------------------------------------------
        # GET HISTORICAL BARS
        # ----------------------------------------------------

        try:

            response = data_client.market_data.get_bars(
                selected,
                Timespan.M5,
                CATEGORY,
                200,
                False,
            )

            if response.status_code == 200:

                data = response.json()

                # Webull can return different structures.
                bars = recursive_records(data)

                chart_rows = []

                for b in bars:

                    timestamp = (
                        b.get("time")
                        or b.get("timestamp")
                        or b.get("trade_time")
                        or b.get("start_time")
                    )

                    open_price = safe_float(
                        b.get("open")
                    )

                    high_price = safe_float(
                        b.get("high")
                    )

                    low_price = safe_float(
                        b.get("low")
                    )

                    close_price = safe_float(
                        b.get("close")
                    )

                    volume = safe_float(
                        b.get("volume")
                    )

                    if (
                        timestamp is not None
                        and open_price
                        and high_price
                        and low_price
                        and close_price
                    ):

                        chart_rows.append(
                            {
                                "time": timestamp,
                                "open": open_price,
                                "high": high_price,
                                "low": low_price,
                                "close": close_price,
                                "volume": volume,
                            }
                        )


                if chart_rows:

                    df = pd.DataFrame(chart_rows)

                    df["time"] = pd.to_datetime(
                        df["time"],
                        unit="ms",
                        errors="coerce",
                    )

                    df = df.dropna(
                        subset=["time"]
                    )

                    df = df.sort_values(
                        "time"
                    )

                    fig = go.Figure()

                    fig.add_trace(
                        go.Candlestick(
                            x=df["time"],
                            open=df["open"],
                            high=df["high"],
                            low=df["low"],
                            close=df["close"],
                            name=selected,
                        )
                    )

                    fig.update_layout(
                        height=650,
                        margin=dict(
                            l=5,
                            r=5,
                            t=10,
                            b=5,
                        ),
                        xaxis_rangeslider_visible=False,
                        template="plotly_dark",
                        showlegend=False,
                        hovermode="x unified",
                    )

                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                        config={
                            "displayModeBar": True,
                            "scrollZoom": True,
                        },
                    )

                else:

                    st.warning(
                        f"No chart bars returned for {selected}."
                    )

            else:

                st.error(
                    f"Chart API error: {response.status_code}"
                )

        except Exception as e:

            st.error(
                f"Chart error: {e}"
            )

    else:

        st.info(
            "Select a stock from the scanner."
        )


# ============================================================
# DIAGNOSTIC
# ============================================================

with st.expander(
    "🔧 Webull scanner diagnostic",
    expanded=not bool(st.session_state.scanner_rows),
):

    st.write(
        st.session_state.diagnostic
    )

    if not st.session_state.scanner_rows:

        st.markdown(
            """
            **This section is important.**

            If the scanner is empty, look here first.

            We are checking:

            - 5-minute gainers
            - Daily gainers
            - Relative volume
            - Most active volume
            - Number of unique symbols
            - Number of stocks surviving filters

            This prevents us from guessing what Webull is returning.
            """
        )


# ============================================================
# AUTO REFRESH
# ============================================================

time.sleep(
    st.session_state.ui_refresh
)

st.rerun()
