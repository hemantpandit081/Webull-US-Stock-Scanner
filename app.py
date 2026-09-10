import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime

from webull.core.client import ApiClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category


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
# STYLE
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background: #080b10;
        color: #e8edf5;
    }

    .main .block-container {
        padding-top: 0.6rem;
        padding-left: 0.7rem;
        padding-right: 0.7rem;
        max-width: 100%;
    }

    /* HEADER */

    .title {
        font-size: 25px;
        font-weight: 850;
        color: #ffffff;
        margin-bottom: 0;
    }

    .subtitle {
        font-size: 11px;
        color: #6e7a8c;
        margin-bottom: 8px;
    }

    /* METRICS */

    .metric {
        background: #10151d;
        border: 1px solid #202a36;
        border-radius: 6px;
        padding: 7px 10px;
        margin-bottom: 6px;
    }

    .metric-label {
        font-size: 9px;
        font-weight: 700;
        color: #697588;
        text-transform: uppercase;
    }

    .metric-value {
        font-size: 17px;
        font-weight: 850;
        color: #f4f7fb;
    }

    /* STOCK HEADER */

    .stock-header {
        background: #111720;
        border-top: 1px solid #202a36;
        border-bottom: 1px solid #202a36;
        padding: 7px 8px;
        font-size: 9px;
        font-weight: 800;
        color: #697588;
        margin-bottom: 3px;
    }

    /* BUTTON */

    div[data-testid="stButton"] {
        margin: 0 !important;
        padding: 0 !important;
    }

    div[data-testid="stButton"] > button {
        width: 100% !important;
        height: 34px !important;
        min-height: 34px !important;
        padding: 0 8px !important;
        margin: 1px 0 !important;

        background: #0d1219 !important;
        border: 1px solid #1d2733 !important;
        border-radius: 4px !important;

        color: #e9eef5 !important;

        box-shadow: none !important;
        text-align: left !important;
    }

    div[data-testid="stButton"] > button:hover {
        background: #17212d !important;
        border-color: #3b4c60 !important;
        color: #ffffff !important;
    }

    div[data-testid="stButton"] > button:focus {
        background: #142238 !important;
        border-color: #4c91ff !important;
        color: #ffffff !important;
        box-shadow: 0 0 0 1px #4c91ff !important;
    }

    div[data-testid="stButton"] > button p {
        color: #e9eef5 !important;
        font-size: 12px !important;
        font-weight: 750 !important;
    }

    /* CHART */

    .chart-box {
        background: #0b1017;
        border: 1px solid #202a36;
        border-radius: 7px;
        padding: 8px;
    }

    .chart-symbol {
        font-size: 21px;
        font-weight: 850;
        color: #ffffff;
    }

    .chart-info {
        font-size: 10px;
        color: #687588;
        margin-bottom: 5px;
    }

    /* SIDEBAR */

    section[data-testid="stSidebar"] {
        background: #0b0f15;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SESSION STATE
# ============================================================

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = None

if "scan_results" not in st.session_state:
    st.session_state.scan_results = pd.DataFrame()

if "first_seen" not in st.session_state:
    st.session_state.first_seen = {}

if "previous_symbols" not in st.session_state:
    st.session_state.previous_symbols = set()

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None


# ============================================================
# WEBULL SETTINGS
# ============================================================

APP_KEY = st.secrets.get("WEBULL_APP_KEY", "")
APP_SECRET = st.secrets.get("WEBULL_APP_SECRET", "")

# IMPORTANT:
# You are using Webull Australia.
REGION_ID = "au"


# ============================================================
# WEBULL CLIENT
# ============================================================

@st.cache_resource
def create_webull():

    if not APP_KEY:
        return None, "WEBULL_APP_KEY is missing."

    if not APP_SECRET:
        return None, "WEBULL_APP_SECRET is missing."

    try:

        api_client = ApiClient(
            APP_KEY,
            APP_SECRET,
            REGION_ID
        )

        # Current Webull SDK supports regional endpoint
        # resolution from the region ID.
        #
        # AU resolves to:
        # api.webull.com.au

        data_client = DataClient(api_client)

        return data_client, None

    except Exception as e:

        return None, str(e)


data_client, connection_error = create_webull()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## ⚙ Scanner")

    min_price = st.number_input(
        "Minimum Price",
        min_value=0.01,
        value=1.00,
        step=0.10
    )

    max_price = st.number_input(
        "Maximum Price",
        min_value=1.00,
        value=100.00,
        step=1.00
    )

    min_change = st.number_input(
        "Minimum Change %",
        min_value=-100.0,
        value=2.0,
        step=0.5
    )

    min_volume = st.number_input(
        "Minimum Volume",
        min_value=0,
        value=100000,
        step=50000
    )

    min_rvol = st.number_input(
        "Minimum RVOL",
        min_value=0.0,
        value=2.0,
        step=0.5
    )

    display_count = st.slider(
        "Stocks Displayed",
        10,
        200,
        60,
        10
    )

    refresh_seconds = st.slider(
        "Refresh",
        5,
        60,
        10,
        5
    )

    chart_interval = st.selectbox(
        "Chart",
        ["1", "5", "15", "30", "60", "D"],
        index=1
    )

    st.divider()

    scan_now = st.button(
        "🔄 SCAN NOW",
        use_container_width=True,
        type="primary"
    )

    auto_scan = st.checkbox(
        "Auto Scan",
        value=True
    )


# ============================================================
# TITLE
# ============================================================

st.markdown(
    """
    <div class="title">
        📈 US MOMENTUM SCANNER
    </div>

    <div class="subtitle">
        Webull AU OpenAPI • US Stocks • Momentum • Volume • RVOL
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# HELPERS
# ============================================================

def number(value, default=0.0):

    try:

        if value is None:
            return default

        if isinstance(value, str):

            value = (
                value
                .replace(",", "")
                .replace("$", "")
                .replace("%", "")
            )

        return float(value)

    except Exception:

        return default


def value_from(row, names, default=None):

    if not isinstance(row, dict):
        return default

    for name in names:

        if name in row:
            value = row[name]

            if value not in [None, ""]:
                return value

    return default


def response_json(response):

    try:
        return response.json()

    except Exception:
        return None


def extract_list(data):

    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    for key in [
        "data",
        "items",
        "list",
        "rows",
        "results",
        "result"
    ]:

        value = data.get(key)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):

            for subkey in [
                "data",
                "items",
                "list",
                "rows",
                "results"
            ]:

                subvalue = value.get(subkey)

                if isinstance(subvalue, list):
                    return subvalue

    return []


# ============================================================
# WEBULL SNAPSHOT
# ============================================================

def get_snapshots(symbols):

    if data_client is None:
        return []

    if not symbols:
        return []

    try:

        response = data_client.market_data.get_snapshot(
            symbols=symbols,
            category="US_STOCK",
            extend_hour_required=True,
            overnight_required=False
        )

        if hasattr(response, "status_code"):

            if response.status_code != 200:
                return []

        return extract_list(
            response_json(response)
        )

    except Exception:

        return []


# ============================================================
# WEBULL SCREENER
# ============================================================

def get_gainers(rank_type):

    if data_client is None:
        return []

    try:

        response = (
            data_client
            .market_data
            .screener
            .get_gainers_losers(
                rank_type=rank_type,
                category="US_STOCK",
                direction="DESC",
                page_index=1,
                page_size=200
            )
        )

        if hasattr(response, "status_code"):

            if response.status_code != 200:
                return []

        return extract_list(
            response_json(response)
        )

    except Exception:

        return []


def get_active(rank_type="VOLUME"):

    if data_client is None:
        return []

    try:

        response = (
            data_client
            .market_data
            .screener
            .get_most_active(
                rank_type=rank_type,
                category="US_STOCK",
                direction="DESC",
                page_index=1,
                page_size=200
            )
        )

        if hasattr(response, "status_code"):

            if response.status_code != 200:
                return []

        return extract_list(
            response_json(response)
        )

    except Exception:

        return []


# ============================================================
# MARKET DISCOVERY
# ============================================================

def discover_stocks():

    combined = {}

    # 5-minute gainers
    for row in get_gainers("MIN_5"):

        symbol = value_from(
            row,
            ["symbol", "ticker", "ticker_symbol"]
        )

        if symbol:
            combined[str(symbol).upper()] = row

    # Daily gainers
    for row in get_gainers("DAY_1"):

        symbol = value_from(
            row,
            ["symbol", "ticker", "ticker_symbol"]
        )

        if symbol:
            combined[str(symbol).upper()] = row

    # Premarket
    for row in get_gainers("PRE_MARKET"):

        symbol = value_from(
            row,
            ["symbol", "ticker", "ticker_symbol"]
        )

        if symbol:
            combined[str(symbol).upper()] = row

    # Highest volume
    for row in get_active("VOLUME"):

        symbol = value_from(
            row,
            ["symbol", "ticker", "ticker_symbol"]
        )

        if symbol:
            combined[str(symbol).upper()] = row

    # Relative volume
    for row in get_active("RELATIVE_VOLUME_10D"):

        symbol = value_from(
            row,
            ["symbol", "ticker", "ticker_symbol"]
        )

        if symbol:
            combined[str(symbol).upper()] = row

    return list(combined.keys())


# ============================================================
# NORMALISE
# ============================================================

def normalise(row):

    symbol = value_from(
        row,
        ["symbol", "ticker", "ticker_symbol"],
        ""
    )

    price = number(
        value_from(
            row,
            [
                "price",
                "last_price",
                "latest_price",
                "close"
            ]
        )
    )

    change = number(
        value_from(
            row,
            [
                "change_ratio",
                "changeRatio",
                "change_percent",
                "changePercentage"
            ]
        )
    )

    if abs(change) < 1:
        change *= 100

    volume = number(
        value_from(
            row,
            [
                "volume",
                "total_volume",
                "trade_volume"
            ]
        )
    )

    rvol = number(
        value_from(
            row,
            [
                "relative_volume",
                "relativeVolume",
                "relative_volume_10d",
                "rvol"
            ]
        )
    )

    turnover = number(
        value_from(
            row,
            [
                "turnover",
                "turnover_amount",
                "amount"
            ]
        )
    )

    if turnover <= 0 and price > 0 and volume > 0:

        turnover = price * volume

    return {
        "SYMBOL": str(symbol).upper(),
        "LTP": price,
        "%": change,
        "RVOL": rvol,
        "VOLUME": volume,
        "$VOL": turnover
    }


# ============================================================
# SCAN
# ============================================================

def run_scan():

    symbols = discover_stocks()

    if not symbols:
        return pd.DataFrame()

    # Limit the snapshot request to avoid unnecessary
    # HTTP traffic.
    symbols = symbols[:500]

    snapshot_rows = get_snapshots(
        symbols
    )

    # --------------------------------------------------------
    # Build snapshot lookup
    # --------------------------------------------------------

    snapshot_map = {}

    for row in snapshot_rows:

        symbol = value_from(
            row,
            ["symbol", "ticker", "ticker_symbol"]
        )

        if symbol:

            snapshot_map[
                str(symbol).upper()
            ] = row

    results = []

    now = datetime.now().strftime(
        "%H:%M:%S"
    )

    # --------------------------------------------------------
    # Process discovered symbols
    # --------------------------------------------------------

    for symbol in symbols:

        source = snapshot_map.get(
            symbol,
            {}
        )

        row = normalise(source)

        row["SYMBOL"] = symbol

        # ----------------------------------------------------
        # FALLBACK PRICE / DATA
        # ----------------------------------------------------

        if row["LTP"] <= 0:

            # Try screener data if snapshot
            # did not contain price.
            continue

        # ----------------------------------------------------
        # FILTERS
        # ----------------------------------------------------

        if row["LTP"] < min_price:
            continue

        if row["LTP"] > max_price:
            continue

        if row["%"] < min_change:
            continue

        if row["VOLUME"] < min_volume:
            continue

        if row["RVOL"] > 0:

            if row["RVOL"] < min_rvol:
                continue

        # ----------------------------------------------------
        # FIRST SEEN
        # ----------------------------------------------------

        if symbol not in st.session_state.first_seen:

            st.session_state.first_seen[
                symbol
            ] = now

        row["TIME"] = (
            st.session_state
            .first_seen[symbol]
        )

        # ----------------------------------------------------
        # REPEAT
        # ----------------------------------------------------

        row["REPEAT"] = (
            symbol in
            st.session_state.previous_symbols
        )

        results.append(row)

    if not results:

        return pd.DataFrame()

    df = pd.DataFrame(
        results
    )

    # Strongest momentum first
    df = df.sort_values(
        by=["%", "RVOL"],
        ascending=False
    )

    df = df.head(
        display_count
    )

    st.session_state.previous_symbols = set(
        df["SYMBOL"].tolist()
    )

    st.session_state.last_scan = (
        datetime.now()
    )

    return df


# ============================================================
# CONNECTION ERROR
# ============================================================

if connection_error:

    st.error(
        "Webull connection error: "
        + connection_error
    )

    st.info(
        "Check WEBULL_APP_KEY and "
        "WEBULL_APP_SECRET in Streamlit Secrets. "
        "This application is configured for "
        "Webull Australia (region = au)."
    )

    st.stop()


# ============================================================
# FIRST SCAN / MANUAL SCAN
# ============================================================

if scan_now or st.session_state.scan_results.empty:

    with st.spinner(
        "Scanning US market..."
    ):

        st.session_state.scan_results = (
            run_scan()
        )


df = st.session_state.scan_results


# ============================================================
# METRICS
# ============================================================

if not df.empty:

    stocks = len(df)

    repeats = int(
        df["REPEAT"].sum()
    )

    valid_rvol = df.loc[
        df["RVOL"] > 0,
        "RVOL"
    ]

    if not valid_rvol.empty:

        average_rvol = (
            valid_rvol.mean()
        )

        average_rvol_text = (
            f"{average_rvol:.1f}x"
        )

    else:

        average_rvol_text = "-"

    strongest = df.iloc[0]["SYMBOL"]

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.markdown(
            f"""
            <div class="metric">
                <div class="metric-label">
                    Stocks
                </div>
                <div class="metric-value">
                    {stocks}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c2:

        st.markdown(
            f"""
            <div class="metric">
                <div class="metric-label">
                    Repeat
                </div>
                <div class="metric-value"
                     style="color:#f4c542;">
                    ■ {repeats}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c3:

        st.markdown(
            f"""
            <div class="metric">
                <div class="metric-label">
                    Average RVOL
                </div>
                <div class="metric-value"
                     style="color:#35d07f;">
                    {average_rvol_text}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c4:

        st.markdown(
            f"""
            <div class="metric">
                <div class="metric-label">
                    Top Momentum
                </div>
                <div class="metric-value"
                     style="color:#58a6ff;">
                    {strongest}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# 35 / 65 LAYOUT
# ============================================================

left, right = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT STOCK LIST
# ============================================================

with left:

    st.markdown(
        """
        <div class="stock-header">
            TIME &nbsp;&nbsp;
            SYMBOL &nbsp;&nbsp;&nbsp;
            LTP &nbsp;&nbsp;&nbsp;
            % &nbsp;&nbsp;
            RVOL &nbsp;&nbsp;
            $VOL
        </div>
        """,
        unsafe_allow_html=True
    )

    if df.empty:

        st.warning(
            "No stocks currently match the filters."
        )

    else:

        for _, row in df.iterrows():

            symbol = row["SYMBOL"]

            repeat = bool(
                row["REPEAT"]
            )

            mark = "■ " if repeat else ""

            change = row["%"]

            if change >= 0:

                change_text = (
                    f"+{change:.1f}%"
                )

            else:

                change_text = (
                    f"{change:.1f}%"
                )

            rvol = row["RVOL"]

            if rvol > 0:

                rvol_text = (
                    f"{rvol:.1f}x"
                )

            else:

                rvol_text = "-"

            dollar_volume = row["$VOL"]

            if dollar_volume >= 1_000_000_000:

                dollar_text = (
                    f"${dollar_volume / 1_000_000_000:.1f}B"
                )

            elif dollar_volume >= 1_000_000:

                dollar_text = (
                    f"${dollar_volume / 1_000_000:.1f}M"
                )

            elif dollar_volume >= 1_000:

                dollar_text = (
                    f"${dollar_volume / 1_000:.0f}K"
                )

            else:

                dollar_text = (
                    f"${dollar_volume:.0f}"
                )

            label = (
                f"{mark}{symbol}   "
                f"${row['LTP']:.2f}   "
                f"{change_text}   "
                f"{rvol_text}   "
                f"{dollar_text}"
            )

            clicked = st.button(
                label,
                key=f"stock_{symbol}",
                use_container_width=True,
                type="secondary"
            )

            if clicked:

                st.session_state.selected_symbol = (
                    symbol
                )

                st.rerun()


# ============================================================
# RIGHT CHART
# ============================================================

with right:

    selected = (
        st.session_state.selected_symbol
    )

    if not selected and not df.empty:

        selected = df.iloc[0]["SYMBOL"]

        st.session_state.selected_symbol = (
            selected
        )

    if selected:

        st.markdown(
            f"""
            <div class="chart-box">

                <div class="chart-symbol">
                    {selected}
                </div>

                <div class="chart-info">
                    Webull • {chart_interval} minute
                    • US Stock
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )

        # ----------------------------------------------------
        # HISTORY
        # ----------------------------------------------------

        bars = []

        try:

            response = (
                data_client
                .market_data
                .get_history_bar(
                    symbol=selected,
                    category="US_STOCK",
                    timespan=chart_interval,
                    count=200,
                    extend_hour_required=True
                )
            )

            if hasattr(response, "status_code"):

                if response.status_code == 200:

                    bars = extract_list(
                        response_json(response)
                    )

            else:

                bars = extract_list(
                    response_json(response)
                )

        except Exception as e:

            st.warning(
                f"Unable to load Webull chart: {e}"
            )


        # ----------------------------------------------------
        # CHART
        # ----------------------------------------------------

        if bars:

            chart = pd.DataFrame(
                bars
            )

            rename = {}

            for column in chart.columns:

                low = str(
                    column
                ).lower()

                if low in [
                    "time",
                    "timestamp"
                ]:

                    rename[column] = "time"

                elif low == "open":

                    rename[column] = "open"

                elif low == "high":

                    rename[column] = "high"

                elif low == "low":

                    rename[column] = "low"

                elif low == "close":

                    rename[column] = "close"

                elif low == "volume":

                    rename[column] = "volume"

            chart = chart.rename(
                columns=rename
            )

            needed = [
                "open",
                "high",
                "low",
                "close"
            ]

            if all(
                col in chart.columns
                for col in needed
            ):

                import plotly.graph_objects as go

                if "time" in chart.columns:

                    chart["time"] = pd.to_datetime(
                        chart["time"],
                        errors="coerce"
                    )

                else:

                    chart["time"] = range(
                        len(chart)
                    )

                fig = go.Figure()

                fig.add_trace(
                    go.Candlestick(
                        x=chart["time"],
                        open=chart["open"],
                        high=chart["high"],
                        low=chart["low"],
                        close=chart["close"],
                        increasing_line_color="#35d07f",
                        decreasing_line_color="#ff5964",
                        increasing_fillcolor="#35d07f",
                        decreasing_fillcolor="#ff5964",
                        name=selected
                    )
                )

                fig.update_layout(
                    height=650,
                    margin=dict(
                        l=5,
                        r=10,
                        t=5,
                        b=5
                    ),
                    paper_bgcolor="#0b1017",
                    plot_bgcolor="#0b1017",
                    font=dict(
                        color="#aab4c3"
                    ),
                    xaxis=dict(
                        showgrid=True,
                        gridcolor="#19232e",
                        rangeslider=dict(
                            visible=False
                        )
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor="#19232e",
                        side="right"
                    ),
                    hovermode="x unified",
                    showlegend=False
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={
                        "displaylogo": False,
                        "scrollZoom": True,
                        "responsive": True
                    }
                )

            else:

                st.warning(
                    "Webull returned chart data, "
                    "but the OHLC fields were not found."
                )

        else:

            st.info(
                f"No chart bars returned for {selected}."
            )

    else:

        st.info(
            "Select a stock from the list."
        )


# ============================================================
# STATUS
# ============================================================

st.divider()

last_scan = st.session_state.last_scan

if last_scan:

    last_scan_text = (
        last_scan.strftime("%H:%M:%S")
    )

else:

    last_scan_text = "-"

st.markdown(
    f"""
    <div style="
        color:#657184;
        font-size:10px;
        padding-bottom:3px;
    ">
        Webull AU • US_STOCK
        &nbsp;&nbsp;|&nbsp;&nbsp;
        Last scan: {last_scan_text}
        &nbsp;&nbsp;|&nbsp;&nbsp;
        Refresh: {refresh_seconds}s
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# AUTO SCAN
# ============================================================

if auto_scan:

    time.sleep(
        refresh_seconds
    )

    st.session_state.scan_results = (
        run_scan()
    )

    st.rerun()
