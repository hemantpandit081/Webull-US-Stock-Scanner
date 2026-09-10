import streamlit as st
import pandas as pd
import numpy as np
import time
import uuid
import threading
from datetime import datetime

# ============================================================
# WEBULL
# ============================================================

from webull.core.client import ApiClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan


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
# DARK TRADING TERMINAL CSS
# ============================================================

st.markdown(
    """
    <style>

    /* =========================
       MAIN PAGE
       ========================= */

    .stApp {
        background: #080b10;
        color: #e8edf5;
    }

    .main .block-container {
        padding-top: 0.7rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
        max-width: 100%;
    }

    /* =========================
       HEADER
       ========================= */

    .scanner-title {
        font-size: 25px;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: 0.3px;
        margin-bottom: 2px;
    }

    .scanner-subtitle {
        font-size: 12px;
        color: #778191;
        margin-bottom: 10px;
    }

    /* =========================
       METRIC BAR
       ========================= */

    .metric-box {
        background: #10151d;
        border: 1px solid #1d2633;
        border-radius: 7px;
        padding: 8px 12px;
        margin-bottom: 7px;
    }

    .metric-label {
        color: #707b8d;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
    }

    .metric-value {
        color: #f3f6fa;
        font-size: 17px;
        font-weight: 800;
    }

    /* =========================
       COLUMN HEADERS
       ========================= */

    .list-header {
        background: #111720;
        border-bottom: 1px solid #26303d;
        border-top: 1px solid #1a222d;
        padding: 7px 8px;
        color: #687487;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 0.3px;
        margin-bottom: 3px;
    }

    /* =========================
       STOCK BUTTONS
       ========================= */

    div[data-testid="stButton"] {
        margin: 0 !important;
        padding: 0 !important;
    }

    div[data-testid="stButton"] > button {
        width: 100% !important;
        min-height: 34px !important;
        height: 34px !important;
        border-radius: 4px !important;
        border: 1px solid #1c2530 !important;
        background: #0d1219 !important;
        color: #dce3ec !important;
        padding: 0 8px !important;
        margin: 1px 0 !important;
        box-shadow: none !important;
        text-align: left !important;
        transition: 0.12s ease-in-out !important;
    }

    div[data-testid="stButton"] > button:hover {
        background: #17202b !important;
        border-color: #344354 !important;
        color: #ffffff !important;
    }

    div[data-testid="stButton"] > button:focus {
        background: #162131 !important;
        border-color: #4387ff !important;
        color: #ffffff !important;
        box-shadow: 0 0 0 1px #4387ff !important;
    }

    div[data-testid="stButton"] > button p {
        font-size: 13px !important;
        font-weight: 750 !important;
        color: #e7edf5 !important;
    }

    /* =========================
       SELECTED STOCK
       ========================= */

    .selected-stock {
        background: #13243a !important;
        border-left: 3px solid #4b91ff !important;
    }

    /* =========================
       COLOURED TEXT
       ========================= */

    .green {
        color: #35d07f;
        font-weight: 800;
    }

    .red {
        color: #ff5964;
        font-weight: 800;
    }

    .yellow {
        color: #f4c542;
        font-weight: 900;
    }

    .blue {
        color: #58a6ff;
        font-weight: 800;
    }

    .muted {
        color: #647083;
    }

    /* =========================
       CHART PANEL
       ========================= */

    .chart-panel {
        background: #0b1017;
        border: 1px solid #1b2530;
        border-radius: 8px;
        padding: 8px;
        min-height: 650px;
    }

    .chart-title {
        font-size: 20px;
        font-weight: 850;
        color: #ffffff;
        margin-bottom: 3px;
    }

    .chart-info {
        font-size: 11px;
        color: #6e7a8c;
        margin-bottom: 8px;
    }

    /* =========================
       SIDEBAR
       ========================= */

    section[data-testid="stSidebar"] {
        background: #0b0f15;
        border-right: 1px solid #1d2630;
    }

    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #ffffff;
    }

    /* =========================
       DATAFRAME
       ========================= */

    div[data-testid="stDataFrame"] {
        border: 1px solid #1b2530;
    }

    /* =========================
       DIVIDER
       ========================= */

    hr {
        border-color: #1b2530 !important;
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
# WEBULL CREDENTIALS
# ============================================================

APP_KEY = st.secrets.get("WEBULL_APP_KEY", "")
APP_SECRET = st.secrets.get("WEBULL_APP_SECRET", "")

REGION_ID = "us"


# ============================================================
# WEBULL CLIENT
# ============================================================

@st.cache_resource
def create_webull_client():

    if not APP_KEY or not APP_SECRET:
        return None, None

    try:
        api_client = ApiClient(
            APP_KEY,
            APP_SECRET,
            REGION_ID
        )

        data_client = DataClient(api_client)

        return api_client, data_client

    except Exception as e:
        st.error(f"Webull connection error: {e}")
        return None, None


api_client, data_client = create_webull_client()


# ============================================================
# SIDEBAR FILTERS
# ============================================================

with st.sidebar:

    st.markdown("## ⚙ Scanner Filters")

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
        value=2.0,
        step=0.5
    )

    min_rvol = st.number_input(
        "Minimum RVOL",
        min_value=0.0,
        value=2.0,
        step=0.5
    )

    min_volume = st.number_input(
        "Minimum Volume",
        min_value=0,
        value=100000,
        step=50000
    )

    max_stocks = st.slider(
        "Stocks Displayed",
        min_value=10,
        max_value=200,
        value=60,
        step=10
    )

    refresh_seconds = st.slider(
        "Scan Refresh",
        min_value=5,
        max_value=60,
        value=10,
        step=5
    )

    chart_interval = st.selectbox(
        "Chart Interval",
        [
            "1",
            "5",
            "15",
            "30",
            "60",
            "D"
        ],
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
# HEADER
# ============================================================

st.markdown(
    """
    <div class="scanner-title">
        📈 US MOMENTUM SCANNER
    </div>

    <div class="scanner-subtitle">
        Webull market data • Momentum • Relative Volume • Volume
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# WEBULL RESPONSE HELPERS
# ============================================================

def safe_json(response):

    try:
        return response.json()
    except Exception:
        return None


def extract_rows(data):

    if data is None:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        for key in [
            "data",
            "items",
            "list",
            "rows",
            "result",
            "results"
        ]:

            value = data.get(key)

            if isinstance(value, list):
                return value

            if isinstance(value, dict):

                for subkey in [
                    "items",
                    "list",
                    "rows",
                    "data"
                ]:

                    subvalue = value.get(subkey)

                    if isinstance(subvalue, list):
                        return subvalue

    return []


# ============================================================
# NUMBER CONVERSION
# ============================================================

def to_float(value, default=0.0):

    try:

        if value is None:
            return default

        if isinstance(value, str):
            value = value.replace(",", "")
            value = value.replace("$", "")
            value = value.replace("%", "")

        return float(value)

    except Exception:
        return default


def get_value(row, names, default=None):

    if not isinstance(row, dict):
        return default

    for name in names:

        if name in row and row[name] not in [None, ""]:
            return row[name]

    return default


# ============================================================
# WEBULL MARKET SCREENER
# ============================================================

def get_webull_ranked_stocks(
    rank_type,
    page_size=200
):

    if data_client is None:
        return []

    try:

        # Current Webull SDK exposes screener methods
        # through market_data.screener.

        response = data_client.market_data.screener.get_gainers_losers(
            rank_type=rank_type,
            category=Category.US_STOCK.name,
            direction="DESC",
            page_index=1,
            page_size=page_size
        )

        data = safe_json(response)

        return extract_rows(data)

    except Exception:

        return []


# ============================================================
# MARKET DISCOVERY
# ============================================================

def discover_market():

    combined = {}

    # --------------------------------------------------------
    # 1. 5 MINUTE GAINERS
    # --------------------------------------------------------

    lists = []

    lists.append(
        get_webull_ranked_stocks(
            "MIN_5",
            200
        )
    )

    # --------------------------------------------------------
    # 2. DAILY GAINERS
    # --------------------------------------------------------

    lists.append(
        get_webull_ranked_stocks(
            "DAY_1",
            200
        )
    )

    # --------------------------------------------------------
    # 3. PRE-MARKET
    # --------------------------------------------------------

    lists.append(
        get_webull_ranked_stocks(
            "PRE_MARKET",
            200
        )
    )

    # --------------------------------------------------------
    # COMBINE
    # --------------------------------------------------------

    for rows in lists:

        for row in rows:

            symbol = get_value(
                row,
                [
                    "symbol",
                    "ticker",
                    "ticker_symbol"
                ]
            )

            if not symbol:
                continue

            symbol = str(symbol).upper().strip()

            combined[symbol] = row

    return list(combined.values())


# ============================================================
# NORMALISE MARKET DATA
# ============================================================

def normalise_row(row):

    symbol = get_value(
        row,
        [
            "symbol",
            "ticker",
            "ticker_symbol"
        ],
        ""
    )

    price = to_float(
        get_value(
            row,
            [
                "price",
                "last_price",
                "latest_price",
                "close"
            ]
        )
    )

    change_ratio = to_float(
        get_value(
            row,
            [
                "change_ratio",
                "changeRatio",
                "change_percent",
                "changePercentage"
            ]
        )
    )

    # Some Webull responses return ratio such as 0.031
    # rather than 3.1.
    if abs(change_ratio) < 1:
        change_ratio *= 100

    volume = to_float(
        get_value(
            row,
            [
                "volume",
                "total_volume",
                "trade_volume"
            ]
        )
    )

    rvol = to_float(
        get_value(
            row,
            [
                "relative_volume",
                "relativeVolume",
                "rvol",
                "relative_volume_10d"
            ]
        )
    )

    turnover = to_float(
        get_value(
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
        "%": change_ratio,
        "RVOL": rvol,
        "VOLUME": volume,
        "$VOL": turnover
    }


# ============================================================
# SCAN
# ============================================================

def run_scan():

    rows = discover_market()

    results = []

    now = datetime.now().strftime("%H:%M:%S")

    for raw in rows:

        row = normalise_row(raw)

        symbol = row["SYMBOL"]

        if not symbol:
            continue

        price = row["LTP"]
        change = row["%"]
        volume = row["VOLUME"]
        rvol = row["RVOL"]

        # ----------------------------------------------------
        # FILTERS
        # ----------------------------------------------------

        if price < min_price:
            continue

        if price > max_price:
            continue

        if change < min_change:
            continue

        if volume < min_volume:
            continue

        if rvol > 0 and rvol < min_rvol:
            continue

        # ----------------------------------------------------
        # FIRST APPEARANCE TIME
        # ----------------------------------------------------

        if symbol not in st.session_state.first_seen:

            st.session_state.first_seen[symbol] = now

        row["TIME"] = st.session_state.first_seen[symbol]

        # ----------------------------------------------------
        # REPEAT INDICATOR
        # ----------------------------------------------------

        if symbol in st.session_state.previous_symbols:
            row["REPEAT"] = True
        else:
            row["REPEAT"] = False

        results.append(row)

    # --------------------------------------------------------
    # DATAFRAME
    # --------------------------------------------------------

    df = pd.DataFrame(results)

    if df.empty:
        return df

    df = df.sort_values(
        by=["%", "RVOL"],
        ascending=False
    )

    df = df.head(max_stocks)

    st.session_state.previous_symbols = set(
        df["SYMBOL"].tolist()
    )

    st.session_state.last_scan = datetime.now()

    return df


# ============================================================
# RUN INITIAL / MANUAL SCAN
# ============================================================

if scan_now or st.session_state.scan_results.empty:

    with st.spinner("Scanning US market..."):

        st.session_state.scan_results = run_scan()


df = st.session_state.scan_results


# ============================================================
# TOP METRICS
# ============================================================

if not df.empty:

    total_stocks = len(df)

    repeat_count = int(
        df["REPEAT"].sum()
    )

    strongest = df.iloc[0]["SYMBOL"]

    avg_rvol = df["RVOL"].replace(
        0,
        np.nan
    ).mean()

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-label">Stocks</div>
                <div class="metric-value">{total_stocks}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c2:

        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-label">Repeating</div>
                <div class="metric-value">
                    <span class="yellow">■ {repeat_count}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c3:

        rvol_text = (
            f"{avg_rvol:.1f}x"
            if not pd.isna(avg_rvol)
            else "-"
        )

        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-label">Average RVOL</div>
                <div class="metric-value green">
                    {rvol_text}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c4:

        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-label">Top Momentum</div>
                <div class="metric-value blue">
                    {strongest}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# MAIN 35 / 65 LAYOUT
# ============================================================

left, right = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT — STOCK LIST
# ============================================================

with left:

    st.markdown(
        """
        <div class="list-header">
            TIME &nbsp;&nbsp;&nbsp; SYMBOL &nbsp;&nbsp;&nbsp;
            LTP &nbsp;&nbsp; % &nbsp;&nbsp; RVOL &nbsp;&nbsp; $VOL
        </div>
        """,
        unsafe_allow_html=True
    )

    if df.empty:

        st.info(
            "No stocks currently match your filters."
        )

    else:

        for _, row in df.iterrows():

            symbol = row["SYMBOL"]

            selected = (
                symbol ==
                st.session_state.selected_symbol
            )

            repeat = row["REPEAT"]

            if repeat:
                repeat_mark = "■"
            else:
                repeat_mark = ""

            change = row["%"]

            if change >= 0:
                change_text = f"+{change:.1f}%"
            else:
                change_text = f"{change:.1f}%"

            rvol = row["RVOL"]

            if rvol > 0:
                rvol_text = f"{rvol:.1f}x"
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

            # ------------------------------------------------
            # BUTTON TEXT
            # ------------------------------------------------

            prefix = "■ " if repeat else ""

            label = (
                f"{prefix}{symbol}    "
                f"${row['LTP']:.2f}    "
                f"{change_text}    "
                f"{rvol_text}    "
                f"{dollar_text}"
            )

            # ------------------------------------------------
            # BUTTON
            # ------------------------------------------------

            clicked = st.button(
                label,
                key=f"stock_{symbol}",
                use_container_width=True,
                type="secondary"
            )

            if clicked:

                st.session_state.selected_symbol = symbol

                st.rerun()


# ============================================================
# RIGHT — CHART
# ============================================================

with right:

    selected = st.session_state.selected_symbol

    if not selected and not df.empty:

        selected = df.iloc[0]["SYMBOL"]

        st.session_state.selected_symbol = selected

    if selected:

        st.markdown(
            f"""
            <div class="chart-panel">

                <div class="chart-title">
                    {selected}
                </div>

                <div class="chart-info">
                    Webull market data • {chart_interval} minute chart
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )

        # ----------------------------------------------------
        # GET HISTORICAL BARS
        # ----------------------------------------------------

        chart_df = pd.DataFrame()

        if data_client is not None:

            try:

                response = (
                    data_client
                    .market_data
                    .get_history_bar(
                        symbol=selected,
                        category=Category.US_STOCK.name,
                        timespan=(
                            Timespan.M1
                            if chart_interval == "1"
                            else Timespan.M5
                            if chart_interval == "5"
                            else Timespan.M15
                            if chart_interval == "15"
                            else Timespan.M30
                            if chart_interval == "30"
                            else Timespan.H1
                            if chart_interval == "60"
                            else Timespan.D
                        ),
                        count=200,
                        extend_hour_required=True
                    )
                )

                raw = safe_json(response)

                bars = extract_rows(raw)

                if bars:

                    chart_df = pd.DataFrame(bars)

            except Exception as e:

                st.warning(
                    f"Chart data unavailable: {e}"
                )

        # ----------------------------------------------------
        # NORMALISE CHART
        # ----------------------------------------------------

        if not chart_df.empty:

            rename_map = {}

            for col in chart_df.columns:

                low = str(col).lower()

                if low in ["time", "timestamp"]:
                    rename_map[col] = "time"

                elif low in ["open"]:
                    rename_map[col] = "open"

                elif low in ["high"]:
                    rename_map[col] = "high"

                elif low in ["low"]:
                    rename_map[col] = "low"

                elif low in ["close"]:
                    rename_map[col] = "close"

                elif low in ["volume"]:
                    rename_map[col] = "volume"

            chart_df = chart_df.rename(
                columns=rename_map
            )

            required = [
                "open",
                "high",
                "low",
                "close"
            ]

            if all(
                col in chart_df.columns
                for col in required
            ):

                try:

                    import plotly.graph_objects as go

                    # ----------------------------------------
                    # TIME
                    # ----------------------------------------

                    if "time" in chart_df.columns:

                        chart_df["time"] = pd.to_datetime(
                            chart_df["time"],
                            errors="coerce"
                        )

                    else:

                        chart_df["time"] = range(
                            len(chart_df)
                        )

                    # ----------------------------------------
                    # CHART
                    # ----------------------------------------

                    fig = go.Figure()

                    fig.add_trace(
                        go.Candlestick(
                            x=chart_df["time"],
                            open=chart_df["open"],
                            high=chart_df["high"],
                            low=chart_df["low"],
                            close=chart_df["close"],
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
                            l=10,
                            r=10,
                            t=10,
                            b=10
                        ),
                        paper_bgcolor="#0b1017",
                        plot_bgcolor="#0b1017",
                        font=dict(
                            color="#aab4c3"
                        ),
                        xaxis=dict(
                            showgrid=True,
                            gridcolor="#18212c",
                            rangeslider=dict(
                                visible=False
                            )
                        ),
                        yaxis=dict(
                            showgrid=True,
                            gridcolor="#18212c",
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

                except Exception as e:

                    st.error(
                        f"Chart rendering error: {e}"
                    )

            else:

                st.info(
                    "Webull returned chart data in an unexpected format."
                )

        else:

            st.info(
                f"Waiting for Webull chart data for {selected}..."
            )

    else:

        st.info(
            "Select a stock from the scanner."
        )


# ============================================================
# FOOTER STATUS
# ============================================================

st.divider()

if st.session_state.last_scan:

    last_scan_text = (
        st.session_state.last_scan
        .strftime("%H:%M:%S")
    )

else:

    last_scan_text = "-"

st.markdown(
    f"""
    <div style="
        color:#657184;
        font-size:11px;
        padding-bottom:4px;
    ">
        Last scan: {last_scan_text}
        &nbsp;&nbsp; • &nbsp;&nbsp;
        Webull US market
        &nbsp;&nbsp; • &nbsp;&nbsp;
        Auto refresh: {refresh_seconds}s
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# AUTO SCAN
# ============================================================

if auto_scan:

    time.sleep(refresh_seconds)

    st.session_state.scan_results = run_scan()

    st.rerun()
