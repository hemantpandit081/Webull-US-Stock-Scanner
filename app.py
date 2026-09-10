import streamlit as st
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components

from webull.core.client import ApiClient
from webull.data.data_client import DataClient


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="US Stock Momentum Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# CSS
# =========================================================

st.markdown("""
<style>

/* =====================================================
   MAIN PAGE
   ===================================================== */

.block-container {
    padding-top: 8px;
    padding-left: 12px;
    padding-right: 12px;
    padding-bottom: 0px;
}


/* =====================================================
   TITLE
   ===================================================== */

h1 {
    font-size: 23px !important;
    margin: 0 !important;
    padding: 0 !important;
}


/* =====================================================
   COLUMN SPACING
   ===================================================== */

[data-testid="stHorizontalBlock"] {
    gap: 4px;
}


/* =====================================================
   GENERAL BUTTONS
   ===================================================== */

div.stButton > button {
    min-height: 25px !important;
    height: 25px !important;
    padding: 0px 4px !important;
    font-size: 12px !important;
    line-height: 1 !important;
}


/* =====================================================
   STOCK SYMBOL LINKS
   ===================================================== */

.stock-symbol-link {
    display: block !important;
    width: 100% !important;
    height: 25px !important;
    line-height: 25px !important;

    padding: 0px 4px !important;
    margin: 0px !important;

    color: inherit !important;
    opacity: 1 !important;

    text-decoration: none !important;

    font-size: 12px !important;
    font-weight: 500 !important;

    cursor: pointer !important;

    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}


/* Hover */
.stock-symbol-link:hover {
    opacity: 1 !important;
    text-decoration: underline !important;
}


/* =====================================================
   CAPTION SPACING
   ===================================================== */

[data-testid="stCaptionContainer"] {
    margin-top: 0px !important;
    margin-bottom: 0px !important;
}


/* =====================================================
   REDUCE VERTICAL SPACING
   ===================================================== */

.element-container {
    margin-bottom: 0px !important;
}


/* =====================================================
   SIDEBAR
   ===================================================== */

section[data-testid="stSidebar"] {
    padding-top: 10px;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# SESSION STATE
# =========================================================

# Read selected symbol from URL
if "symbol" in st.query_params:

    url_symbol = str(
        st.query_params["symbol"]
    ).upper().strip()

    if url_symbol:

        st.session_state.selected_symbol = (
            url_symbol
        )


if "selected_symbol" not in st.session_state:

    st.session_state.selected_symbol = "AAPL"


if "results" not in st.session_state:

    st.session_state.results = []


if "history" not in st.session_state:

    st.session_state.history = {}


if "trigger_time" not in st.session_state:

    st.session_state.trigger_time = {}


if "scan_number" not in st.session_state:

    st.session_state.scan_number = 0


if "last_scan" not in st.session_state:

    st.session_state.last_scan = "--"


if "scan_speed" not in st.session_state:

    st.session_state.scan_speed = 0


# =========================================================
# WEBULL CONNECTION
# =========================================================

APP_KEY = st.secrets["WEBULL_APP_KEY"]

APP_SECRET = st.secrets["WEBULL_APP_SECRET"]


@st.cache_resource
def connect_webull():

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


webull = connect_webull()


# =========================================================
# SIDEBAR SETTINGS
# =========================================================

st.sidebar.title(
    "⚙ Scanner Settings"
)


# ---------------------------------------------------------
# PRICE
# ---------------------------------------------------------

min_price = st.sidebar.number_input(
    "Minimum price",
    min_value=0.01,
    value=1.00,
    step=0.50
)


max_price = st.sidebar.number_input(
    "Maximum price",
    min_value=1.00,
    value=1000.00,
    step=10.00
)


# ---------------------------------------------------------
# VOLUME
# ---------------------------------------------------------

min_volume = st.sidebar.number_input(
    "Minimum volume",
    min_value=0,
    value=100000,
    step=10000
)


# ---------------------------------------------------------
# PERCENT CHANGE
# ---------------------------------------------------------

min_change = st.sidebar.number_input(
    "Minimum % change",
    value=1.0,
    step=0.5
)


# ---------------------------------------------------------
# RVOL
# ---------------------------------------------------------

min_rvol = st.sidebar.number_input(
    "Minimum RVOL",
    min_value=0.0,
    value=1.5,
    step=0.1
)


# ---------------------------------------------------------
# DOLLAR VOLUME
# ---------------------------------------------------------

min_dollar_volume = st.sidebar.number_input(
    "Minimum $ volume",
    min_value=0,
    value=1000000,
    step=100000
)


# ---------------------------------------------------------
# REPEAT VOLUME
# ---------------------------------------------------------

repeat_tolerance = st.sidebar.slider(
    "Repeat volume tolerance",
    min_value=0.50,
    max_value=0.99,
    value=0.90,
    step=0.01
)


# ---------------------------------------------------------
# SCAN SPEED
# ---------------------------------------------------------

refresh_seconds = st.sidebar.number_input(
    "Scan every",
    min_value=5,
    max_value=300,
    value=15,
    step=5
)


# ---------------------------------------------------------
# CHART INTERVAL
# ---------------------------------------------------------

chart_interval = st.sidebar.selectbox(
    "Chart interval",
    [
        "1",
        "3",
        "5",
        "15",
        "30",
        "60",
        "D"
    ],
    index=0
)


# ---------------------------------------------------------
# AUTO SCAN
# ---------------------------------------------------------

auto_scan = st.sidebar.checkbox(
    "Auto scan",
    value=True
)


# =========================================================
# TIME
# =========================================================

def ny_time():

    return datetime.now(
        ZoneInfo("America/New_York")
    )


# =========================================================
# MARKET STATUS
# =========================================================

def market_status():

    now = ny_time()


    if now.weekday() >= 5:

        return "🔴 Market Closed"


    minutes = (
        now.hour * 60
        + now.minute
    )


    if 240 <= minutes < 570:

        return "🟡 Pre-Market"


    if 570 <= minutes < 960:

        return "🟢 Market Open"


    if 960 <= minutes < 1200:

        return "🟡 After-Hours"


    return "🔴 Market Closed"


# =========================================================
# NUMBER CONVERTER
# =========================================================

def num(value):

    try:

        if value is None:

            return 0.0


        if isinstance(value, str):

            value = value.replace(
                ",",
                ""
            )

            value = value.replace(
                "%",
                ""
            )


        return float(value)


    except Exception:

        return 0.0


# =========================================================
# FIND LIST INSIDE WEBULL RESPONSE
# =========================================================

def find_list(data):

    if isinstance(data, list):

        return data


    if isinstance(data, dict):


        for key in [
            "data",
            "items",
            "list",
            "results",
            "rows"
        ]:


            if key in data:


                result = find_list(
                    data[key]
                )


                if result:

                    return result


        for value in data.values():

            result = find_list(
                value
            )


            if result:

                return result


    return []


# =========================================================
# CONVERT WEBULL STOCK
# =========================================================

def convert_stock(item):

    symbol = str(

        item.get("symbol")

        or item.get("ticker")

        or ""

    ).upper().strip()


    if not symbol:

        return None


    # -----------------------------------------------------
    # PRICE
    # -----------------------------------------------------

    price = num(

        item.get("price")

        or item.get("latest_price")

        or item.get("latestPrice")

        or item.get("close")

    )


    # -----------------------------------------------------
    # CHANGE
    # -----------------------------------------------------

    change = num(

        item.get("change_ratio")

        or item.get("changeRatio")

        or item.get("change_percent")

        or item.get("changePercent")

    )


    if abs(change) < 1:

        change *= 100


    # -----------------------------------------------------
    # VOLUME
    # -----------------------------------------------------

    volume = num(

        item.get("volume")

        or item.get("tradeVolume")

        or item.get("totalVolume")

    )


    # -----------------------------------------------------
    # RVOL
    # -----------------------------------------------------

    rvol = num(

        item.get("relative_volume_10d")

        or item.get("relativeVolume10d")

        or item.get("relative_volume")

        or item.get("rvol")

    )


    # -----------------------------------------------------
    # DOLLAR VOLUME
    # -----------------------------------------------------

    dollar_volume = (
        price * volume
    )


    return {

        "symbol": symbol,

        "price": price,

        "change": change,

        "volume": volume,

        "rvol": rvol,

        "dollar_volume":
            dollar_volume

    }


# =========================================================
# GET MARKET DATA
# =========================================================

def get_market_data():

    stocks = {}


    # =====================================================
    # 5 MINUTE GAINERS
    # =====================================================

    try:

        response = (
            webull.screener.list_gainers_losers(
                "MIN_5",
                "US_STOCK",
                "CHANGE_RATIO",
                "DESC"
            )
        )


        data = response.json()


        for item in find_list(data):

            stock = convert_stock(
                item
            )


            if stock:

                stocks[
                    stock["symbol"]
                ] = stock


    except Exception:

        pass


    # =====================================================
    # DAILY GAINERS
    # =====================================================

    try:

        response = (
            webull.screener.list_gainers_losers(
                "DAY_1",
                "US_STOCK",
                "CHANGE_RATIO",
                "DESC"
            )
        )


        data = response.json()


        for item in find_list(data):

            stock = convert_stock(
                item
            )


            if stock:

                symbol = (
                    stock["symbol"]
                )


                if symbol not in stocks:

                    stocks[
                        symbol
                    ] = stock


    except Exception:

        pass


    # =====================================================
    # HIGHEST RVOL
    # =====================================================

    try:

        response = (
            webull.screener.list_most_active(
                "US_STOCK",
                "RELATIVE_VOLUME_10D",
                "RELATIVE_VOLUME_10D",
                "DESC"
            )
        )


        data = response.json()


        for item in find_list(data):

            stock = convert_stock(
                item
            )


            if stock:

                symbol = (
                    stock["symbol"]
                )


                if symbol not in stocks:

                    stocks[
                        symbol
                    ] = stock


    except Exception:

        pass


    # =====================================================
    # HIGHEST VOLUME
    # =====================================================

    try:

        response = (
            webull.screener.list_most_active(
                "US_STOCK",
                "VOLUME",
                "VOLUME",
                "DESC"
            )
        )


        data = response.json()


        for item in find_list(data):

            stock = convert_stock(
                item
            )


            if stock:

                symbol = (
                    stock["symbol"]
                )


                if symbol not in stocks:

                    stocks[
                        symbol
                    ] = stock


    except Exception:

        pass


    return list(
        stocks.values()
    )


# =========================================================
# APPLY FILTERS
# =========================================================

def apply_filters(stocks):

    results = []


    for stock in stocks:


        if (
            stock["price"]
            < min_price
        ):

            continue


        if (
            stock["price"]
            > max_price
        ):

            continue


        if (
            stock["volume"]
            < min_volume
        ):

            continue


        if (
            stock["change"]
            < min_change
        ):

            continue


        if (
            stock["rvol"]
            < min_rvol
        ):

            continue


        if (
            stock["dollar_volume"]
            < min_dollar_volume
        ):

            continue


        results.append(
            stock
        )


    # -----------------------------------------------------
    # SORT
    # -----------------------------------------------------

    results.sort(

        key=lambda x: (

            x["rvol"],

            x["change"]

        ),

        reverse=True

    )


    return results


# =========================================================
# REPEAT VOLUME DETECTION
# =========================================================

def check_repeat(
    symbol,
    volume
):


    if (
        symbol
        not in st.session_state.history
    ):

        st.session_state.history[
            symbol
        ] = []


    previous = (
        st.session_state.history[
            symbol
        ]
    )


    repeat = False


    # -----------------------------------------------------
    # COMPARE WITH PREVIOUS VOLUMES
    # -----------------------------------------------------

    for old_volume in previous:


        if old_volume <= 0:

            continue


        ratio = (
            volume
            / old_volume
        )


        if (

            repeat_tolerance
            <= ratio

            <=
            1 / repeat_tolerance

        ):

            repeat = True

            break


    # -----------------------------------------------------
    # STORE CURRENT VOLUME
    # -----------------------------------------------------

    previous.append(
        volume
    )


    st.session_state.history[
        symbol
    ] = previous[-100:]


    return repeat


# =========================================================
# PREPARE RESULTS
# =========================================================

def prepare_results(stocks):

    output = []


    for stock in stocks:

        symbol = (
            stock["symbol"]
        )


        # -------------------------------------------------
        # FIRST APPEARANCE TIME
        # -------------------------------------------------

        if (
            symbol
            not in st.session_state.trigger_time
        ):

            st.session_state.trigger_time[
                symbol
            ] = ny_time().strftime(
                "%H:%M:%S"
            )


        # -------------------------------------------------
        # REPEAT CHECK
        # -------------------------------------------------

        repeat = check_repeat(

            symbol,

            stock["volume"]

        )


        # -------------------------------------------------
        # OUTPUT
        # -------------------------------------------------

        output.append({

            "TIME":
                st.session_state.trigger_time[
                    symbol
                ],

            "SYMBOL":
                symbol,

            "LTP":
                stock["price"],

            "%":
                stock["change"],

            "RVOL":
                stock["rvol"],

            "$VOL":
                stock["dollar_volume"],

            "REPEAT":
                repeat

        })


    return output


# =========================================================
# SCAN
# =========================================================

def scan():

    start = (
        time.perf_counter()
    )


    # -----------------------------------------------------
    # GET MARKET DATA
    # -----------------------------------------------------

    stocks = get_market_data()


    # -----------------------------------------------------
    # FILTER
    # -----------------------------------------------------

    stocks = apply_filters(
        stocks
    )


    # -----------------------------------------------------
    # PREPARE
    # -----------------------------------------------------

    results = prepare_results(
        stocks
    )


    # -----------------------------------------------------
    # SAVE RESULTS
    # -----------------------------------------------------

    st.session_state.results = (
        results
    )


    # -----------------------------------------------------
    # SCAN NUMBER
    # -----------------------------------------------------

    st.session_state.scan_number += 1


    # -----------------------------------------------------
    # LAST SCAN
    # -----------------------------------------------------

    st.session_state.last_scan = (
        ny_time().strftime(
            "%H:%M:%S"
        )
    )


    # -----------------------------------------------------
    # SCAN SPEED
    # -----------------------------------------------------

    st.session_state.scan_speed = (

        time.perf_counter()
        - start

    )


# =========================================================
# FORMAT DOLLAR VOLUME
# =========================================================

def format_volume(value):

    if (
        value
        >= 1_000_000_000
    ):

        return (
            f"${value / 1_000_000_000:.1f}B"
        )


    if (
        value
        >= 1_000_000
    ):

        return (
            f"${value / 1_000_000:.1f}M"
        )


    if (
        value
        >= 1_000
    ):

        return (
            f"${value / 1_000:.1f}K"
        )


    return (
        f"${value:.0f}"
    )


# =========================================================
# TRADINGVIEW CHART
# =========================================================

def show_chart(symbol):


    # -----------------------------------------------------
    # BASIC EXCHANGE MAP
    # -----------------------------------------------------

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
        "BABA"

    }


    if symbol in nyse_symbols:

        exchange = "NYSE"

    else:

        exchange = "NASDAQ"


    tv_symbol = (
        f"{exchange}:{symbol}"
    )


    # -----------------------------------------------------
    # TRADINGVIEW HTML
    # -----------------------------------------------------

    html = f"""

    <div style="
        width:100%;
        height:600px;
        margin:0;
        padding:0;
    ">

        <iframe

            src="
            https://www.tradingview.com/widgetembed/
            ?symbol={tv_symbol}
            &interval={chart_interval}
            &theme=dark
            &style=1
            &toolbarbg=f1f3f6
            &hidesidetoolbar=0
            &withdateranges=1
            &hideideas=1
            "

            style="
                width:100%;
                height:600px;
                border:0;
                margin:0;
                padding:0;
                display:block;
            "

            frameborder="0"

            allowtransparency="true"

            scrolling="no">

        </iframe>

    </div>

    """


    components.html(

        html,

        height=600

    )


# =========================================================
# PAGE HEADER
# =========================================================

st.title(
    "📈 US Stock Momentum Scanner"
)


st.caption(
    market_status()
)


# =========================================================
# TOP SCAN CONTROLS
# =========================================================

button_col, info_col = st.columns(
    [1, 7]
)


# ---------------------------------------------------------
# SCAN BUTTON
# ---------------------------------------------------------

with button_col:


    if st.button(

        "🔄 Scan Now",

        use_container_width=True

    ):


        scan()

        st.rerun()


# ---------------------------------------------------------
# SCAN INFORMATION
# ---------------------------------------------------------

with info_col:

    st.write(

        f"Scans: "
        f"{st.session_state.scan_number}"

        f"   | Last scan: "
        f"{st.session_state.last_scan}"

        f"   | Speed: "
        f"{st.session_state.scan_speed:.2f}s"

    )


# =========================================================
# FIRST SCAN
# =========================================================

if not st.session_state.results:

    with st.spinner(
        "Scanning US momentum stocks..."
    ):

        scan()


# =========================================================
# MAIN 35 / 65 LAYOUT
# =========================================================

left, right = st.columns(

    [35, 65],

    gap="small"

)


# =========================================================
# LEFT SCANNER
# =========================================================

with left:


    # -----------------------------------------------------
    # COLUMN WIDTHS
    # -----------------------------------------------------

    widths = [

        1.20,
        1.30,
        1.00,
        0.80,
        0.90,
        1.20

    ]


    # =====================================================
    # HEADER
    # =====================================================

    h1, h2, h3, h4, h5, h6 = st.columns(

        widths,

        gap="small"

    )


    with h1:

        st.caption(
            "TIME"
        )


    with h2:

        st.caption(
            "SYMBOL"
        )


    with h3:

        st.caption(
            "LTP"
        )


    with h4:

        st.caption(
            "%"
        )


    with h5:

        st.caption(
            "RVOL"
        )


    with h6:

        st.caption(
            "$VOL"
        )


    # =====================================================
    # STOCK ROWS
    # =====================================================

    if st.session_state.results:


        for row in st.session_state.results:


            c1, c2, c3, c4, c5, c6 = st.columns(

                widths,

                gap="small"

            )


            # =================================================
            # TIME
            # =================================================

            with c1:

                st.write(
                    row["TIME"]
                )


            # =================================================
            # SYMBOL
            # =================================================

            with c2:


                symbol = (
                    row["SYMBOL"]
                )


                # -------------------------------------------------
                # REPEAT MARKER
                # -------------------------------------------------

                if row["REPEAT"]:

                    display_symbol = (
                        "■ " + symbol
                    )

                else:

                    display_symbol = (
                        symbol
                    )


                # -------------------------------------------------
                # URL-SAFE SYMBOL
                # -------------------------------------------------

                safe_symbol = (
                    symbol
                    .replace("&", "")
                    .replace("?", "")
                    .replace("#", "")
                    .replace(" ", "")
                )


                # -------------------------------------------------
                # REAL HTML CLICKABLE LINK
                # -------------------------------------------------

                st.markdown(

                    f"""
                    <a
                        class="stock-symbol-link"
                        href="?symbol={safe_symbol}"
                        title="Open {symbol}"
                    >
                        {display_symbol}
                    </a>
                    """,

                    unsafe_allow_html=True

                )


            # =================================================
            # LTP
            # =================================================

            with c3:

                st.write(

                    f"{row['LTP']:.2f}"

                )


            # =================================================
            # %
            # =================================================

            with c4:

                st.write(

                    f"{row['%']:+.1f}%"

                )


            # =================================================
            # RVOL
            # =================================================

            with c5:

                st.write(

                    f"{row['RVOL']:.1f}x"

                )


            # =================================================
            # $VOL
            # =================================================

            with c6:

                st.write(

                    format_volume(
                        row["$VOL"]
                    )

                )


    else:

        st.info(
            "No stocks match your filters."
        )


# =========================================================
# RIGHT SIDE — TRADINGVIEW
# =========================================================

with right:

    show_chart(

        st.session_state.selected_symbol

    )


# =========================================================
# AUTO SCAN
# =========================================================

if auto_scan:


    time.sleep(
        refresh_seconds
    )


    st.rerun()
