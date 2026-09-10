
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import uuid
import threading
import time
from datetime import datetime

from webull.core.client import ApiClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category
from webull.data.common.subscribe_type import SubscribeType
from webull.data.data_streaming_client import DataStreamingClient


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
# SESSION STATE
# ============================================================

defaults = {
    "selected_symbol": None,
    "scan_data": pd.DataFrame(),
    "previous_symbols": set(),
    "repeat_symbols": set(),
    "last_scan": None,
    "stream_started": False,
    "stream_symbol": None,
    "live_price": {},
    "live_volume": {},
    "chart_data": {},
    "stream_error": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 0.6rem;
        padding-left: 0.7rem;
        padding-right: 0.7rem;
        padding-bottom: 0.5rem;
        max-width: 100%;
    }

    .title {
        font-size: 22px;
        font-weight: 700;
        margin-bottom: 2px;
    }

    .status {
        font-size: 12px;
        color: #888;
        margin-bottom: 5px;
    }

    div[data-testid="stButton"] {
        width: 100%;
        margin: 0 !important;
        padding: 0 !important;
    }

    div[data-testid="stButton"] > button {
        width: 100% !important;
        height: 30px !important;
        min-height: 30px !important;
        padding: 0 8px !important;
        margin: 1px 0 !important;
        border-radius: 4px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        text-align: left !important;
    }

    div[data-testid="stButton"] > button:hover {
        background-color: rgba(120,120,120,0.18) !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# TITLE
# ============================================================

st.markdown(
    '<div class="title">📈 US Momentum Scanner</div>',
    unsafe_allow_html=True
)


# ============================================================
# WEBULL SETTINGS
# ============================================================

try:
    APP_KEY = st.secrets["WEBULL_APP_KEY"]
    APP_SECRET = st.secrets["WEBULL_APP_SECRET"]

except Exception:
    APP_KEY = ""
    APP_SECRET = ""


REGION_ID = "us"


# ============================================================
# SIDEBAR
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
        "Scanner Refresh",
        min_value=5,
        max_value=300,
        value=15,
        step=5
    )

    chart_minutes = st.selectbox(
        "Chart",
        [
            "1 Minute",
            "5 Minutes",
            "15 Minutes",
            "30 Minutes",
            "1 Hour"
        ],
        index=0
    )

    if chart_minutes == "1 Minute":
        chart_timespan = "M1"
    elif chart_minutes == "5 Minutes":
        chart_timespan = "M5"
    elif chart_minutes == "15 Minutes":
        chart_timespan = "M15"
    elif chart_minutes == "30 Minutes":
        chart_timespan = "M30"
    else:
        chart_timespan = "H1"

    auto_scan = st.checkbox(
        "Auto Scan",
        value=True
    )

    scan_now = st.button(
        "🔄 Scan Now",
        use_container_width=True
    )


# ============================================================
# WEBULL CLIENT
# ============================================================

@st.cache_resource
def get_api_client():

    if not APP_KEY or not APP_SECRET:
        return None

    client = ApiClient(
        APP_KEY,
        APP_SECRET,
        REGION_ID
    )

    return client


api_client = get_api_client()


# ============================================================
# WEBULL DATA CLIENT
# ============================================================

@st.cache_resource
def get_data_client():

    client = get_api_client()

    if client is None:
        return None

    return DataClient(client)


data_client = get_data_client()


# ============================================================
# REAL-TIME STREAM STORAGE
# ============================================================

live_lock = threading.Lock()


# ============================================================
# STREAM CALLBACK
# ============================================================

def on_quotes_message(
    client,
    topic,
    quotes
):

    try:

        if not quotes:
            return

        if isinstance(quotes, list):

            records = quotes

        else:

            records = [quotes]

        for item in records:

            if not isinstance(item, dict):
                continue

            symbol = (
                item.get("symbol")
                or item.get("ticker")
            )

            if not symbol:
                continue

            symbol = str(symbol).upper()

            price = (
                item.get("price")
                or item.get("last_price")
                or item.get("lastPrice")
            )

            volume = (
                item.get("volume")
                or item.get("total_volume")
                or item.get("totalVolume")
            )

            try:
                price = float(price)
            except Exception:
                continue

            try:
                volume = float(volume)
            except Exception:
                volume = 0

            with live_lock:

                st.session_state.live_price[
                    symbol
                ] = price

                st.session_state.live_volume[
                    symbol
                ] = volume

    except Exception as e:

        st.session_state.stream_error = str(e)


# ============================================================
# STREAM CONNECT
# ============================================================

def start_stream(symbol):

    if not APP_KEY or not APP_SECRET:
        return False

    if (
        st.session_state.stream_started
        and
        st.session_state.stream_symbol == symbol
    ):
        return True

    try:

        session_id = uuid.uuid4().hex

        stream_client = DataStreamingClient(
            APP_KEY,
            APP_SECRET,
            REGION_ID,
            session_id
        )

        def connected(
            client,
            api_client,
            quotes_session_id
        ):

            try:

                sub_types = [
                    SubscribeType.QUOTE.name,
                    SubscribeType.SNAPSHOT.name,
                    SubscribeType.TICK.name
                ]

                client.subscribe(
                    [symbol],
                    Category.US_STOCK.name,
                    sub_types
                )

            except Exception as e:

                st.session_state.stream_error = str(e)

        stream_client.on_connect_success = connected

        stream_client.on_quotes_message = (
            on_quotes_message
        )

        def run():

            try:

                stream_client.connect_and_loop_forever()

            except Exception as e:

                st.session_state.stream_error = (
                    str(e)
                )

        thread = threading.Thread(
            target=run,
            daemon=True
        )

        thread.start()

        st.session_state.stream_started = True
        st.session_state.stream_symbol = symbol

        return True

    except Exception as e:

        st.session_state.stream_error = str(e)

        return False


# ============================================================
# HISTORICAL BARS
# ============================================================

def get_chart_bars(symbol):

    if data_client is None:
        return pd.DataFrame()

    try:

        response = (
            data_client.market_data.get_history_bar(
                symbol=symbol,
                timespan=chart_timespan,
                category=Category.US_STOCK.name,
                count=200,
                real_time_required=True
            )
        )

        if response.status_code != 200:
            return pd.DataFrame()

        data = response.json()

        if isinstance(data, dict):

            rows = (
                data.get("data")
                or data.get("items")
                or data.get("list")
                or data.get("bars")
                or []
            )

        elif isinstance(data, list):

            rows = data

        else:

            rows = []

        if not rows:
            return pd.DataFrame()

        result = []

        for row in rows:

            if not isinstance(row, dict):
                continue

            timestamp = (
                row.get("time")
                or row.get("timestamp")
                or row.get("trade_time")
            )

            try:

                open_price = float(
                    row.get("open")
                )

                high_price = float(
                    row.get("high")
                )

                low_price = float(
                    row.get("low")
                )

                close_price = float(
                    row.get("close")
                )

                volume = float(
                    row.get("volume", 0)
                )

            except Exception:

                continue

            result.append(
                {
                    "time": timestamp,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume
                }
            )

        df = pd.DataFrame(result)

        if df.empty:
            return df

        df["time"] = pd.to_datetime(
            df["time"],
            unit="ms",
            errors="coerce"
        )

        df = df.dropna(
            subset=["time"]
        )

        df = df.sort_values(
            "time"
        )

        return df

    except Exception as e:

        st.session_state.stream_error = str(e)

        return pd.DataFrame()


# ============================================================
# BUILD LIVE CHART
# ============================================================

def make_chart(symbol):

    if symbol not in st.session_state.chart_data:

        bars = get_chart_bars(symbol)

        st.session_state.chart_data[
            symbol
        ] = bars

    df = st.session_state.chart_data.get(
        symbol,
        pd.DataFrame()
    ).copy()

    if df.empty:

        return None

    # --------------------------------------------------------
    # Add latest live price to current candle
    # --------------------------------------------------------

    with live_lock:

        live_price = st.session_state.live_price.get(
            symbol
        )

        live_volume = st.session_state.live_volume.get(
            symbol
        )

    if live_price is not None:

        last_index = df.index[-1]

        df.loc[last_index, "close"] = (
            live_price
        )

        df.loc[last_index, "high"] = max(
            df.loc[last_index, "high"],
            live_price
        )

        df.loc[last_index, "low"] = min(
            df.loc[last_index, "low"],
            live_price
        )

    if live_volume is not None:

        df.loc[
            df.index[-1],
            "volume"
        ] = live_volume

    # --------------------------------------------------------
    # Chart
    # --------------------------------------------------------

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df["time"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=symbol
        )
    )

    fig.update_layout(

        template="plotly_dark",

        height=620,

        margin=dict(
            l=5,
            r=5,
            t=10,
            b=10
        ),

        xaxis=dict(
            rangeslider=dict(
                visible=False
            ),
            showgrid=True
        ),

        yaxis=dict(
            showgrid=True,
            fixedrange=False
        ),

        hovermode="x unified",

        dragmode="pan",

        showlegend=False
    )

    return fig


# ============================================================
# MARKET SCANNER
# ============================================================

def get_gainers():

    if data_client is None:
        return []

    try:

        response = (
            data_client.market_data
            .screener.get_gainers_losers(
                rank_type="DAY_1",
                direction="DESC"
            )
        )

        if response.status_code != 200:
            return []

        data = response.json()

        if isinstance(data, dict):

            rows = (
                data.get("data")
                or data.get("items")
                or data.get("list")
                or data.get("results")
                or []
            )

        else:

            rows = data

        return rows if isinstance(
            rows,
            list
        ) else []

    except Exception:

        return []


# ============================================================
# NORMALISE
# ============================================================

def normalise(row):

    def value(*keys):

        for key in keys:

            if key in row:

                val = row[key]

                if val is not None:
                    return val

        return None

    symbol = value(
        "symbol",
        "ticker"
    )

    price = value(
        "price",
        "last_price",
        "lastPrice"
    )

    change = value(
        "change_ratio",
        "changeRatio",
        "change_percent",
        "changePercent"
    )

    volume = value(
        "volume",
        "total_volume",
        "totalVolume"
    )

    rvol = value(
        "rvol",
        "relative_volume",
        "relativeVolume"
    )

    try:
        price = float(price)
    except Exception:
        price = 0

    try:
        change = float(change)

        # API may return decimal ratio
        if abs(change) < 1:
            change *= 100

    except Exception:
        change = 0

    try:
        volume = float(volume)
    except Exception:
        volume = 0

    try:
        rvol = float(rvol)
    except Exception:
        rvol = 0

    return {
        "SYMBOL": str(symbol).upper()
        if symbol else "",
        "LTP": price,
        "%": change,
        "VOLUME": volume,
        "RVOL": rvol,
        "$VOL": price * volume
    }


# ============================================================
# SCAN
# ============================================================

def scan_market():

    rows = get_gainers()

    if not rows:

        return pd.DataFrame()

    stocks = []

    for row in rows:

        if not isinstance(row, dict):
            continue

        stock = normalise(row)

        if not stock["SYMBOL"]:
            continue

        if stock["LTP"] < min_price:
            continue

        if stock["LTP"] > max_price:
            continue

        if stock["%"] < min_change:
            continue

        if stock["VOLUME"] < min_volume:
            continue

        if stock["RVOL"] < min_rvol:
            continue

        stocks.append(stock)

    if not stocks:

        return pd.DataFrame()

    df = pd.DataFrame(stocks)

    df = df.drop_duplicates(
        subset=["SYMBOL"]
    )

    df = df.sort_values(
        ["%", "RVOL"],
        ascending=False
    )

    df = df.head(
        int(max_stocks)
    )

    now = datetime.now().strftime(
        "%H:%M:%S"
    )

    current = set(
        df["SYMBOL"]
    )

    previous = (
        st.session_state.previous_symbols
    )

    st.session_state.repeat_symbols = (
        current.intersection(previous)
    )

    st.session_state.previous_symbols = current

    df.insert(
        0,
        "TIME",
        now
    )

    st.session_state.last_scan = now

    return df


# ============================================================
# RUN SCAN
# ============================================================

if scan_now or st.session_state.scan_data.empty:

    result = scan_market()

    if not result.empty:

        st.session_state.scan_data = result


df = st.session_state.scan_data.copy()


# ============================================================
# STATUS
# ============================================================

if st.session_state.last_scan:

    st.markdown(
        f'<div class="status">'
        f'Last scan: {st.session_state.last_scan}'
        f' &nbsp; • &nbsp; '
        f'{len(df)} stocks'
        f'</div>',
        unsafe_allow_html=True
    )


# ============================================================
# MAIN COLUMNS
# ============================================================

left, right = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# STOCK LIST
# ============================================================

with left:

    st.markdown("### Stocks")

    if df.empty:

        st.info(
            "No stocks match the current filters."
        )

    else:

        for _, row in df.iterrows():

            symbol = row["SYMBOL"]

            repeat = (
                symbol
                in st.session_state.repeat_symbols
            )

            selected = (
                symbol
                == st.session_state.selected_symbol
            )

            text = (
                f"■ {symbol}"
                if repeat
                else symbol
            )

            if selected:

                text = f"▶ {text}"

            if st.button(
                text,
                key=f"stock_{symbol}",
                use_container_width=True
            ):

                st.session_state.selected_symbol = (
                    symbol
                )

                # Reset stream for selected stock
                st.session_state.stream_symbol = None

                st.rerun()


# ============================================================
# CHART
# ============================================================

with right:

    if st.session_state.selected_symbol is None:

        if not df.empty:

            st.session_state.selected_symbol = (
                df.iloc[0]["SYMBOL"]
            )

    symbol = (
        st.session_state.selected_symbol
    )

    if symbol:

        # Start real-time Webull stream
        start_stream(symbol)

        with live_lock:

            current_price = (
                st.session_state.live_price.get(
                    symbol
                )
            )

        st.markdown(
            f"### {symbol}"
        )

        row_match = df[
            df["SYMBOL"] == symbol
        ]

        if not row_match.empty:

            row = row_match.iloc[0]

            c1, c2, c3, c4 = st.columns(4)

            price_display = (
                current_price
                if current_price is not None
                else row["LTP"]
            )

            with c1:
                st.metric(
                    "LTP",
                    f"${price_display:.2f}"
                )

            with c2:
                st.metric(
                    "%",
                    f"{row['%']:.2f}%"
                )

            with c3:
                st.metric(
                    "RVOL",
                    f"{row['RVOL']:.1f}x"
                )

            with c4:
                st.metric(
                    "$VOL",
                    (
                        f"${row['$VOL']/1_000_000:.1f}M"
                        if row["$VOL"] >= 1_000_000
                        else f"${row['$VOL']/1_000:.0f}K"
                    )
                )

        chart = make_chart(symbol)

        if chart:

            st.plotly_chart(
                chart,
                use_container_width=True,
                config={
                    "displaylogo": False,
                    "scrollZoom": True,
                    "displayModeBar": True
                }
            )

        else:

            st.warning(
                "Waiting for Webull candle data..."
            )

        if st.session_state.stream_error:

            st.caption(
                "Stream: "
                + st.session_state.stream_error
            )

    else:

        st.info(
            "Select a stock from the list."
        )


# ============================================================
# TABLE
# ============================================================

if not df.empty:

    st.divider()

    table = df[
        [
            "TIME",
            "SYMBOL",
            "LTP",
            "%",
            "RVOL",
            "$VOL"
        ]
    ].copy()

    table["LTP"] = table[
        "LTP"
    ].map(
        lambda x: f"${x:.2f}"
    )

    table["%"] = table[
        "%"
    ].map(
        lambda x: f"{x:.2f}%"
    )

    table["RVOL"] = table[
        "RVOL"
    ].map(
        lambda x: f"{x:.1f}x"
    )

    table["$VOL"] = table[
        "$VOL"
    ].map(
        lambda x:
        f"${x/1_000_000:.1f}M"
        if x >= 1_000_000
        else f"${x/1_000:.0f}K"
    )

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=280
    )


# ============================================================
# AUTO REFRESH
# ============================================================

if auto_scan:

    time.sleep(
        int(refresh_seconds)
    )

    result = scan_market()

    if not result.empty:

        st.session_state.scan_data = result

    st.rerun()
```
