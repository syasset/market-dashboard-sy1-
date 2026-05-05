import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import feedparser
import urllib.parse
from datetime import datetime, timedelta
import pytz
import re
import html
from urllib.parse import quote

st.set_page_config(layout="wide", page_title="AI Financial Dashboard")

# 1. 테마주 검색 및 리스트 업데이트 함수 (가상 로직)
import requests
from bs4 import BeautifulSoup
import time    # 대기 시간용
import random


@st.cache_data(ttl=3600)
def get_political_list(keyword):
    """네이버 차단 시 2026 지방선거 국면 핵심 종목을 즉시 반환"""
    fallback = {
        "더불어민주당": {
            "tickers": ["033530.KQ", "004710.KS", "004690.KS", "035150.KS", "024060.KQ"],
            "names": ["에이텍", "한창제지", "태림포장", "신성이엔지", "경동인베스트"]
        },
        "국민의힘": {
            "tickers": ["010660.KS", "023530.KQ", "002410.KS", "032350.KS", "005250.KS"],
            "names": ["진양산업", "제주반도체", "범양건영", "우신시스템", "녹십자홀딩스"]
        }
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    try:
        url = f"https://search.naver.com/search.naver?where=nexearch&query={keyword}+관련주"
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')

        tickers, names = [], []
        items = soup.select(".list_stock_item") or soup.select(".n_item")

        for item in items[:5]:
            n = item.select_one(".name").text if item.select_one(".name") else ""
            c = re.search(r'\d{6}', str(item))
            if n and c:
                tickers.append(f"{c.group()}.KS")
                names.append(n)

        if not tickers: raise Exception("Blocked or No Data")
        return {"tickers": tickers, "names": names}
    except:
        # 차단 시 사전에 정의된 2026년 대장주 리스트 사용
        return fallback[keyword]


# --- 2. 대시보드 메인 설정 ---
st.set_page_config(layout="wide", page_title="2026 Politics Dashboard")
st.title("🗳️ 2026 정치 테마주 실시간 모니터링 (좌우 비교)")
st.caption("💡 국내 증시 휴장일 - 마지막 거래일 종가 기준으로 표시됩니다.")
st.divider()

# 데이터 준비
blue_stocks = get_political_list("더불어민주당")
red_stocks = get_political_list("국민의힘")

# --- 3. [한눈에 보기] 좌우 레이아웃 ---
col_blue, col_red = st.columns(2)

# [왼쪽: 더불어민주당 - 파란색 테마]
with col_blue:
    st.markdown("<h3 style='color: #004ea2;'>🔵 더불어민주당 테마주</h3>", unsafe_allow_html=True)
    st.markdown("<div style='background-color: #004ea2; height: 3px; margin-bottom: 20px;'></div>",
                unsafe_allow_html=True)

    for t, n in zip(blue_stocks["tickers"], blue_stocks["names"]):
        try:
            tk = yf.Ticker(t)
            # 휴장일 대응을 위해 넉넉한 10일치 데이터 사용
            hist = tk.history(period="10d")
            if hist.empty: hist = yf.Ticker(t.replace(".KS", ".KQ")).history(period="10d")

            data = hist['Close'].dropna()
            if len(data) >= 2:
                curr, prev = data.iloc[-1], data.iloc[-2]
                pct = ((curr - prev) / prev) * 100
                st.metric(label=n, value=f"{curr:,.0f}원", delta=f"{pct:.2f}%")
        except:
            continue

# [오른쪽: 국민의힘 - 빨간색 테마]
with col_red:
    st.markdown("<h3 style='color: #e61e2b;'>🔴 국민의힘 테마주</h3>", unsafe_allow_html=True)
    st.markdown("<div style='background-color: #e61e2b; height: 3px; margin-bottom: 20px;'></div>",
                unsafe_allow_html=True)

    for t, n in zip(red_stocks["tickers"], red_stocks["names"]):
        try:
            tk = yf.Ticker(t)
            hist = tk.history(period="10d")
            if hist.empty: hist = yf.Ticker(t.replace(".KS", ".KQ")).history(period="10d")

            data = hist['Close'].dropna()
            if len(data) >= 2:
                curr, prev = data.iloc[-1], data.iloc[-2]
                pct = ((curr - prev) / prev) * 100
                st.metric(label=n, value=f"{curr:,.0f}원", delta=f"{pct:.2f}%")
        except:
            continue

# =========================
# 📊 섹터 매핑 설정
# =========================
SECTOR_MAP = {
    "Tech": {"themes": ["AI", "반도체", "클라우드", "소프트웨어", "데이터센터", "로봇"], "anchors": {"NASDAQ": 0.6, "S&P500": 0.3, "KOSDAQ": 0.1}},
    "Energy": {"themes": ["에너지", "정유", "LNG", "원유", "WTI", "천연가스"], "anchors": {"WTI": 0.5, "Natural Gas": 0.3, "S&P500": 0.2}},
    "GreenEnergy": {"themes": ["태양광", "풍력", "수소", "원자력", "2차전지"], "anchors": {"NASDAQ": 0.3, "KOSPI": 0.3, "KOSDAQ": 0.3, "S&P500": 0.1}},
    "Crypto": {"themes": ["비트코인", "블록체인", "핀테크"], "anchors": {"Bitcoin": 0.8, "NASDAQ": 0.2}},
    "Defensive": {"themes": ["금", "채권", "리츠", "유틸리티"], "anchors": {"Gold": 0.7, "S&P500": 0.2, "KOSPI": 0.1}},
    "Industrial": {"themes": ["자동차", "전기차", "조선", "철강", "방산", "우주항공", "드론", "건설", "화학"], "anchors": {"S&P500": 0.4, "KOSPI": 0.4, "WTI": 0.1, "Natural Gas": 0.1}},
    "Healthcare": {"themes": ["헬스케어", "제약", "바이오"], "anchors": {"NASDAQ": 0.4, "S&P500": 0.4, "KOSPI": 0.2}},
    "Consumer": {"themes": ["항공", "여행", "카지노", "엔터", "미디어", "게임", "유통", "물류", "식품", "플랫폼", "교육"], "anchors": {"S&P500": 0.4, "KOSPI": 0.3, "KOSDAQ": 0.2, "NASDAQ": 0.1}},
    "KoreaSpecial": {"themes": ["KOSPI대형주", "스마트팜"], "anchors": {"KOSPI": 0.7, "KOSDAQ": 0.3}}
}

theme_pool = [t for s in SECTOR_MAP.values() for t in s["themes"]]
tickers = {
    "Dow Jones": "^DJI", "NASDAQ": "^IXIC", "S&P500": "^GSPC", "Bitcoin": "BTC-USD",
    "KOSPI": "^KS11", "KOSDAQ": "^KQ11", "Gold": "GC=F", "WTI": "CL=F",
    "Natural Gas": "NG=F", "USDKRW": "USDKRW=X"
}
usd_assets = ["Dow Jones", "Bitcoin", "NASDAQ", "S&P500", "Gold", "WTI", "Natural Gas"]

# =========================
# ⏱ 업데이트 시간 (한국 시간 기준)
# =========================
# 한국 시간대 설정
korea_time = datetime.now(pytz.timezone("Asia/Seoul"))

st.markdown(
    f"<div style='text-align:right'>⏱ Last Update (KST): {korea_time.strftime('%Y-%m-%d %H:%M:%S')}</div>",
    unsafe_allow_html=True
)

# =========================
# 📌 자산 정의
# =========================
tickers = {
    "Bitcoin": "BTC-USD",
    "KOSPI": "^KS11",
    "Dow Jones": "^DJI",
    "KOSDAQ": "^KQ11",
    "NASDAQ": "^IXIC",
    "S&P500": "^GSPC",
    "Gold": "GC=F",
    "WTI": "CL=F",
    "Natural Gas": "NG=F",
    "USDKRW": "USDKRW=X"
}

usd_assets = ["Dow Jones", "Bitcoin", "NASDAQ", "S&P500", "Gold", "WTI", "Natural Gas"]


# =========================
# 📊 데이터 로드 및 처리함수
# =========================
@st.cache_data(ttl=600)
def load_all_data():
    # 지수 데이터
    raw_all = yf.download(list(tickers.values()), start="2018-01-01", progress=False)
    # 종가 데이터 추출 및 가공
    raw_close = raw_all["Close"].ffill().bfill()
    if isinstance(raw_close.columns, pd.MultiIndex): raw_close = raw_close.droplevel(0, axis=1)
    ticker_to_name = {v: k for k, v in tickers.items()}
    data = raw_close.rename(columns=ticker_to_name)

    # [추가] 거래량 데이터 추출 및 가공
    raw_volume = raw_all["Volume"].ffill().fillna(0)
    if isinstance(raw_volume.columns, pd.MultiIndex): raw_volume = raw_volume.droplevel(0, axis=1)
    data_volume_indices = raw_volume.rename(columns=ticker_to_name)

    # 매크로 데이터 (기존 로직 유지)
    m_tickers = {"US10Y": "^TNX", "US2Y": "^IRX", "DXY": "DX-Y.NYB"}
    macro_raw = yf.download(list(m_tickers.values()), start="2018-01-01", progress=False)["Close"]
    macro = macro_raw.ffill().bfill()
    if isinstance(macro.columns, pd.MultiIndex): macro = macro.droplevel(0, axis=1)
    macro = macro.rename(columns={v: k for k, v in m_tickers.items()})

    return data, macro, data_volume_indices


def calculate_growth(df):
    # 벡터 연산으로 속도 최적화
    return (df / df.iloc[0] - 1) * 100


# 데이터 로딩
data, macro, data_volume_indices = load_all_data()
growth = calculate_growth(data)
macro_growth = calculate_growth(macro)

# KRW 환산 시계열 (차트용)
chart_data = data.drop(columns=["USDKRW"])
data_krw = chart_data.copy()
for col in usd_assets:
    data_krw[col] = chart_data[col] * data["USDKRW"]


# =========================
# 📊 자산 차트
# =========================
st.markdown("## 🌍📊 지수, 섹터별 지표")
st.markdown(f"### 📈 지수차트")

if not growth.empty:
    fig = go.Figure()

    custom_colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
        "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
        "#bcbd22", "#17becf"
    ]

    last_points = []

    # 1. 차트 선 그리기
    for i, col in enumerate(growth.columns):
        if col == "USDKRW":
            continue

        line_color = custom_colors[i % len(custom_colors)]

        fig.add_trace(go.Scatter(
            x=growth.index,
            y=growth[col],
            customdata=data_krw[col],
            name=col,
            mode='lines',
            # [핵심 수정] 확대 시 선 굵기 고정 설정
            line=dict(
                width=1,
                color=line_color
            ),
            # 확대해도 굵기가 변하지 않도록 하는 시각적 효과 (SVG 속성 활용)
            marker=dict(line=dict(width=0)),
            hovertemplate="📅 %{x|%Y-%m-%d}<br><b>%{fullData.name}</b><br>📈 %{y:.2f}%<br>💰 %{customdata:,.0f}<extra></extra>"
        ))

        last_points.append({
            "col": col,
            "y": growth[col].iloc[-1],
            "val": data_krw[col].iloc[-1],
            "color": line_color
        })

    # 모든 선에 대해 확대 시 굵기 변동 방지 강제 적용
    fig.update_traces(line=dict(width=1))

    # 2. 태그 로직 (기존 동일)
    last_points.sort(key=lambda x: x['y'], reverse=True)

    for i, p in enumerate(last_points):
        is_right = i % 2 == 0
        side_offset = 60 if is_right else -60
        x_anchor = "left" if is_right else "right"

        fig.add_annotation(
            x=growth.index[-1],
            y=p['y'],
            text=f"<b>{p['col']}</b><br>{p['val']:,.0f}",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1.5,
            arrowcolor=p['color'],
            ax=side_offset,
            ay=0,
            xanchor=x_anchor,
            yanchor="middle",
            font=dict(size=11, color="white"),
            bgcolor=p['color'],
            opacity=0.9,
            bordercolor="white",
            borderwidth=1,
            borderpad=4
        )

    # 3. 레이아웃 설정
    fig.update_layout(
        template="plotly_dark",
        dragmode="pan",
        height=650,
        # [핵심 수정] 확대 상태 유지 및 렌더링 최적화
        uirevision='constant',
        margin=dict(l=30, r=120, t=80, b=50),
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ),
        xaxis=dict(
            showgrid=False,
            range=[growth.index[0], growth.index[-1] + pd.Timedelta(days=10)]
        ),
        yaxis=dict(
            zeroline=True,
            zerolinecolor="rgba(255,255,255,0.2)",
            side="left"
        )
    )

    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

# =========================
# 🌍 매크로 차트
# =========================
st.markdown(f"### 📊 매크로(거시) 경제 차트")

improved_colors = [
    "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e",
    "#9467bd", "#17becf", "#e377c2", "#8c564b",
    "#4169E1", "#008080"
]

if not macro_growth.empty:
    fig2 = go.Figure()
    last_points_macro = []

    # 1. 차트 선 그리기 및 데이터 수집
    for i, col in enumerate(macro_growth.columns):
        line_color = improved_colors[i % len(improved_colors)]

        fig2.add_trace(go.Scatter(
            x=macro_growth.index,
            y=macro_growth[col],
            customdata=macro[col],
            name=col,
            mode='lines',
            # [수정] 확대 시 선 굵기 뭉침 방지를 위해 고정 픽셀 느낌으로 설정
            line=dict(
                width=1,
                color=line_color
            ),
            hovertemplate="📅 %{x|%Y-%m-%d}<br><b>%{fullData.name}</b><br>📈 %{y:.2f}%<br>💎 %{customdata:.2f}<extra></extra>"
        ))

        last_points_macro.append({
            "col": col,
            "y": macro_growth[col].iloc[-1],
            "val": macro[col].iloc[-1],
            "color": line_color
        })

    # 모든 매크로 선에 대해 선 굵기 고정 강제 적용
    fig2.update_traces(line=dict(width=1))

    # 2. Y축 정렬 및 태그 최적화
    last_points_macro.sort(key=lambda x: x['y'], reverse=True)

    for i, p in enumerate(last_points_macro):
        is_right = i % 2 == 0
        side_offset = 65 if is_right else -65
        x_anchor = "left" if is_right else "right"

        fig2.add_annotation(
            x=macro_growth.index[-1],
            y=p['y'],
            text=f"<b>{p['col']}</b><br>{p['val']:.2f}",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1.5,
            arrowcolor=p['color'],
            ax=side_offset,
            ay=0,
            xanchor=x_anchor,
            yanchor="middle",
            font=dict(size=11, color="white"),
            bgcolor=p['color'],
            opacity=0.9,
            bordercolor="white",
            borderwidth=1,
            borderpad=4
        )

    # 3. 레이아웃 설정 (확대 고정 및 너비 최적화)
    fig2.update_layout(
        template="plotly_dark",
        dragmode="pan",
        height=650,
        # [추가] 확대/축소 시 상태 유지를 위한 설정
        uirevision='constant',
        # 우측 여백을 충분히 주어 긴 지표명 태그가 잘리지 않게 함
        margin=dict(l=30, r=130, t=80, b=50),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11)
        ),
        xaxis=dict(
            showgrid=False,
            # 마지막 데이터 뒤에 15일 정도의 여유 공간을 두어 태그 배치 최적화
            range=[macro_growth.index[0], macro_growth.index[-1] + pd.Timedelta(days=15)]
        ),
        yaxis=dict(
            zeroline=True,
            zerolinecolor="rgba(255,255,255,0.2)",
            title="수익률/변화율 (%)"
        )
    )

    st.plotly_chart(fig2, use_container_width=True, config={"scrollZoom": True})

# =========================
# 📅 기간별 섹터 분석 선택
# =========================
    st.markdown(f"### 📅📈 기간별 섹터 분석")

    # 1. 기간 설정 및 데이터 준비
    period = st.selectbox(
        "기간설정",
        ["7일", "1개월", "6개월", "1년"],
        key="period_selector"
    )

    period_map = {"7일": 7, "1개월": 30, "6개월": 180, "1년": 365}
    period_days_map = {7: "1mo", 30: "3mo", 180: "1y", 365: "2y"}

    days = period_map[period]
    yf_period = period_days_map[days]

    # 📊 섹터 및 종목 매핑 (기존 유지)
    sector_map = {
        "반도체": {"tickers": ["005930.KS", "000660.KS", "NVDA", "TSM", "INTC", "AMD"],
                "names": ["삼성전자", "SK하이닉스", "엔비디아", "TSMC", "인텔", "AMD"]},
        "자동차": {"tickers": ["005380.KS", "000270.KS", "TSLA", "F"],
                "names": ["현대차", "기아", "테슬라", "포드 모터"]},
        "방산": {"tickers": ["012450.KS", "272210.KS", "003490.KS", "LMT", "PLTR"],
               "names": ["한화에어로스페이스", "한화시스템", "대한항공", "록히드마틴", "팔란티어"]},
        "소프트웨어": {"tickers": ["035420.KS", "035720.KS", "MSFT", "GOOGL", "GOOG", "META", "ORCL"],
                  "names": ["NAVER", "카카오", "마이크로소프트", "구글(알파벳 Class A)", "구글(알파벳 Class C)", "메타", "오라클"]},
        "우주항공": {"tickers": ["047810.KS", "012450.KS", "003490.KS", "079550.KS", "RKLB"],
                 "names": ["한국항공우주", "한화에어로스페이스", "대한항공", "LIG넥스원", "로켓랩"]},
        "해운/유통": {"tickers": ["042660.KS", "011200.KS", "005880.KS", "000120.KS", "AMZN", "WMT", "CPNG", "GD"],
                  "names": ["한화오션", "HMM", "대한해운", "CJ대한통운", "아마존닷컴", "월마트", "쿠팡", "제너럴 다이내믹스"]},
        "에너지": {"tickers": ["015760.KS", "298040.KS", "034020.KS", "010120.KS", "229640.KS", "267260.KS"],
                "names": ["한국전력", "효성중공업", "두산에너빌리티", "LS ELECTRIC", "LS에코에너지", "HD현대일렉트릭"]},
        "건설": {"tickers": ["000720.KS", "028050.KS", "028260.KS", "006360.KS"],
               "names": ["현대건설", "DL이앤씨", "삼성물산", "GS건설"]}
    }

    # 📥 데이터 다운로드 (종목 + 일자별 환율)
    all_tickers = [t for v in sector_map.values() for t in v["tickers"]]
    fx_ticker = "USDKRW=X"
    download_list = list(set(all_tickers + [fx_ticker]))

    raw_sector_data = yf.download(download_list, period=yf_period, progress=False)

    # 데이터 정리 (Close 기준)
    data_all = raw_sector_data["Close"].ffill().bfill()
    if isinstance(data_all.columns, pd.MultiIndex):
        data_all.columns = data_all.columns.get_level_values(1)
    data_sector = data_all.copy()

    # 일자별 환율 시리즈 추출
    fx_history = data_all[fx_ticker]
    # 주가 데이터만 분리
    data_only_stocks = data_all.drop(columns=[fx_ticker])
    pure_stock_data = data_only_stocks


    # ---------------------------------------------------------
    # [로직] 일자별 환율을 적용하여 원화 단위로 데이터 통합
    # ---------------------------------------------------------
    def get_daily_converted_data(df, fx_series):
        converted_df = df.copy()
        for ticker in df.columns:
            # 한국 종목(.KS, .KQ)이 아닌 경우에만 해당 날짜의 환율을 곱함
            is_korean = any(ex in ticker.upper() for ex in [".KS", ".KQ"])
            if not is_korean:
                # 주가(달러) * 그날의 환율(원/달러)
                converted_df[ticker] = df[ticker] * fx_series
        return converted_df


    data_sector_krw = get_daily_converted_data(data_only_stocks, fx_history)


    # ---------------------------------------------------------
    # [로직] 섹터 지수 및 수익률 계산
    # ---------------------------------------------------------
    def build_sector_index(sector_map, data_converted):
        sector_df = pd.DataFrame(index=data_converted.index)
        for sector, info in sector_map.items():
            valid = [s for s in info["tickers"] if s in data_converted.columns]
            if valid:
                # 원화로 통합된 종목들의 평균값으로 섹터 지수 생성
                sector_df[sector] = data_converted[valid].mean(axis=1)
        return sector_df


    sector_df = build_sector_index(sector_map, data_sector_krw)
    # 첫 번째 날을 100으로 잡고 수익률(지수) 추이 계산
    growth_sector = (sector_df / sector_df.iloc[0]) * 100

    # ---------------------------------------------------------
    # [시각화] 차트 출력
    # ---------------------------------------------------------
    colors = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3", "#FF6692", "#B6E880"]

    st.markdown("---")
    sectors = list(growth_sector.columns)
    for i in range(0, len(sectors), 2):
        row_cols = st.columns(2)

        for j in range(2):
            if i + j < len(sectors):
                sector_name = sectors[i + j]
                sector_color = colors[(i + j) % len(colors)]

                with row_cols[j]:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=growth_sector.index,
                        y=growth_sector[sector_name],
                        mode="lines",
                        line=dict(width=3, color=sector_color),
                        name=sector_name,
                        hovertemplate="<b>%{x|%y.%m.%d}</b><br>원화환산지수: %{y:.2f}<extra></extra>"
                    ))

                    fig.update_layout(
                        title=f"📈 {sector_name} 수익률",
                        height=320,
                        margin=dict(l=40, r=20, t=50, b=40),
                        xaxis=dict(title="날짜", tickformat="%y.%m.%d", showgrid=True),
                        yaxis=dict(title="지수(100)", showgrid=True),
                        plot_bgcolor="rgba(0,0,0,0)",
                        showlegend=False
                    )

                    st.plotly_chart(fig, use_container_width=True, key=f"chart_fx_{sector_name}")

                    with st.expander(f"🔍 {sector_name} 구성종목 확인"):
                        names = sector_map[sector_name]["names"]
                        codes = sector_map[sector_name]["tickers"]
                        for name, code in zip(names, codes):
                            st.write(f"- {name} ({code})")
                    st.markdown("<br>", unsafe_allow_html=True)


    # =========================
    # 🛠 0. 뉴스 가져오기 함수 (링크 포함)
    # =========================
    @st.cache_data(ttl=3600)
    def get_news(keyword, limit=2):
        rss_url = f"https://news.google.com/rss/search?q={keyword}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        news_results = []
        for entry in feed.entries[:limit]:
            news_results.append({
                "title": entry.title,
                "link": entry.link
            })
        return news_results


    # =========================
    # 📅 날짜 선택 및 상호 동기화 로직
    # =========================
    st.markdown("## 📅 기간별 AI 시장분석")

    if "clicked_sector" not in st.session_state:
        st.session_state.clicked_sector = None

    available_dates = data.index.unique()

    # 1. 연/월/일 드롭다운 기능 (기존 로직 유지)
    col_y, col_m, col_d = st.columns(3)

    with col_y:
        years = sorted(available_dates.year.unique(), reverse=True)
        sel_y = st.selectbox("Year", options=years, index=0)

    with col_m:
        months = sorted(available_dates[available_dates.year == sel_y].month.unique())
        default_m_idx = len(months) - 1
        sel_m = st.selectbox("Month", options=months, index=default_m_idx)

    with col_d:
        days = sorted(available_dates[(available_dates.year == sel_y) & (available_dates.month == sel_m)].day.unique())
        default_d_idx = len(days) - 1
        sel_d = st.selectbox("Day", options=days, index=default_d_idx)

    # 선택된 날짜 설정 및 실제 데이터 매칭
    target_date = available_dates[(available_dates.year == sel_y) &
                                  (available_dates.month == sel_m) &
                                  (available_dates.day == sel_d)][-1]

    # [수정] actual_valid_date와 date_idx를 여기서 명확히 정의합니다.
    actual_valid_date = data.index[data.index.get_indexer([target_date], method='pad')[0]]
    date_idx = data.index.get_loc(actual_valid_date)  # <--- NameError 해결 포인트

    # 날짜가 바뀌었을 때 섹터 상세창을 초기화하고 싶다면 아래 주석을 해제하세요.
    # if "last_date" not in st.session_state or st.session_state.last_date != actual_valid_date:
    #     st.session_state.clicked_sector = None
    #     st.session_state.last_date = actual_valid_date

    # 환율 호출
    current_fx = float(data.loc[actual_valid_date, "USDKRW"])

    # 영업일 및 업데이트 안내 설정
    is_weekend = actual_valid_date.weekday() >= 5
    update_time_info = "다음 영업일 한국시간 오전 08:00"

    if is_weekend:
        st.warning(f"📢 **{actual_valid_date.strftime('%Y-%m-%d')}**는 시장 휴장일입니다. 직전 영업일 데이터를 참조합니다.")
    else:
        st.info(f"📍 분석 시점: **{actual_valid_date.strftime('%Y-%m-%d')}** (환율: {current_fx:,.2f}원)")
    # =========================
    # 📊 지수별 정리표
    # =========================
    import streamlit as st

    st.markdown("### 📈 시장 지수 실시간 대시보드")

    if date_idx > 0:
        # 1. 데이터 추출 및 환산 로직 (기존 유지)
        curr_usd = chart_data.iloc[date_idx].copy()
        prev_usd = chart_data.iloc[date_idx - 1].copy()
        curr_krw = curr_usd.copy()
        prev_krw = prev_usd.copy()

        for col in usd_assets:
            curr_krw[col] = curr_usd[col] * current_fx
            prev_krw[col] = prev_usd[col] * current_fx

        for col in ["KOSPI", "KOSDAQ"]:
            if col in curr_krw:
                curr_usd[col] = curr_krw[col] / current_fx
                prev_usd[col] = prev_krw[col] / current_fx

        # 2. 증감 계산
        diff_amt = curr_krw - prev_krw
        diff_pct = (diff_amt / prev_krw) * 100

        # 3. 카드 레이아웃 설정 (3열 구성)
        display_order = [
            ("🇺🇸 Dow Jones", "Dow Jones"), ("🇺🇸 NASDAQ", "NASDAQ"), ("🇺🇸 S&P500", "S&P500"),
            ("🥇 Gold", "Gold"), ("₿ Bitcoin", "Bitcoin"), ("🛢️ WTI Oil", "WTI"),
            ("🔥 Natural Gas", "Natural Gas"), ("🇰🇷 KOSPI", "KOSPI"), ("🇰🇷 KOSDAQ", "KOSDAQ")
        ]

        rows = [display_order[i:i + 3] for i in range(0, len(display_order), 3)]

        for row in rows:
            cols = st.columns(3)
            for i, (label, key) in enumerate(row):
                with cols[i]:
                    with st.container(border=True):
                        # 지수 이름
                        st.caption(label)

                        # 메인 수치 (KRW)
                        val_krw = curr_krw[key]
                        st.subheader(f"{val_krw:,.0f} ₩")

                        # 서브 수치 (USD) - 작은 회색 글씨로 표기
                        val_usd = curr_usd[key]
                        st.markdown(
                            f"<p style='color: gray; font-size: 0.85rem; margin-top: -15px;'>($ {val_usd:,.2f})</p>",
                            unsafe_allow_html=True)

                        # 변동폭 (st.metric 활용)
                        pct_change = diff_pct[key]
                        st.metric(label="전일대비", value=f"{diff_amt[key]:+,.0f} ₩", delta=f"{pct_change:+.2f}%")

        # 4. 하단 환율 정보
        st.divider()
        prev_fx = float(data.loc[available_dates[date_idx - 1], "USDKRW"])
        fx_diff = current_fx - prev_fx
        fx_pct = (fx_diff / prev_fx) * 100

        with st.expander("💱 실시간 환율 정보 (USDKRW)", expanded=True):
            c1, c2, c3 = st.columns(3)
            c1.metric("현재 환율", f"{current_fx:,.2f} ₩")
            c2.metric("변동량", f"{fx_diff:+,.2f} ₩")
            c3.metric("변동률", f"{fx_pct:+.2f}%")

    else:
        st.warning("첫 번째 데이터 날짜이므로 전일 대비 증감 분석이 불가능합니다.")

# =========================
# 🧠 3. AI 분석 엔진 (속도 최적화)
# =========================
    def analyze_trend_fast(ticker_name, df, target_idx):
        # 분석에 필요한 최소한의 윈도우만 가져옴 (최대 120일)
        start_pos = max(0, target_idx - 120)
        window_data = df[ticker_name].iloc[start_pos: target_idx + 1]

        if len(window_data) < 120:
            return {"상태": "⚪ 데이터 부족", "점수": 50, "모멘텀(3M)": "0.00%"}

        curr = window_data.iloc[-1]
        m20, m60, m120 = window_data.iloc[-20:].mean(), window_data.iloc[-60:].mean(), window_data.mean()

        if m20 > m60 > m120:
            status, score = "🔥 강력 상승 (정배열)", 100
        elif curr > m60:
            status, score = "✅ 중기 상승 유지", 70
        elif m20 < m60 < m120:
            status, score = "💀 강력 하락 (역배열)", 10
        else:
            status, score = "⚖️ 변동성/혼조세", 50

        mom = (curr / window_data.iloc[0] - 1) * 100
        return {"상태": status, "점수": score, "모멘텀(3M)": f"{mom:+.2f}%"}


    def color_status(val):
        color_map = {"강력 상승": "#2ecc71", "강력 하락": "#e74c3c", "상승 유지": "#3498db"}
        for key, color in color_map.items():
            if key in val: return f'color: {color}; font-weight: bold'
        return 'color: #f1c40f; font-weight: bold'

    # =========================================================
    # 📈 [보강] 도미넌스 & 실시간 상세 리포트
    # =========================================================
    if 'sector_df' in locals() and not sector_df.empty:
        s_idx = sector_df.index.get_indexer([actual_valid_date], method='pad')[0]

        dom_list = []
        total_e = 0
        for col in sector_df.columns:
            hist = sector_df[col].iloc[max(0, s_idx - 5):s_idx + 1].dropna()
            # 에너지(시장 영향력) 계산
            e = (hist.std() * len(sector_map[col]["tickers"])) if len(hist) > 1 else 1.0
            total_e += e

            cv, pv = sector_df[col].iloc[s_idx], sector_df[col].iloc[max(0, s_idx - 1)]
            chg = ((cv / pv) - 1) * 100 if pd.notnull(pv) and pv != 0 else 0
            dom_list.append({"섹터": col, "에너지": e, "수익률": chg})

        df_dom = pd.DataFrame(dom_list)
        # 시장 차지 비율 계산
        df_dom["도미넌스(%)"] = (df_dom["에너지"] / total_e * 100).fillna(0)

        col_left, col_right = st.columns([1.1, 0.9])

        with col_left:
            st.write("### 🗺️ 섹터 도미넌스")

            # 날짜별 고유 키 생성 (클릭 트리거 보장)
            tm_key = f"tm_widget_{actual_valid_date.strftime('%Y%m%d')}"

            fig = px.treemap(df_dom, path=["섹터"], values="도미넌스(%)", color="수익률",
                             color_continuous_scale="RdYlGn", range_color=[-2, 2])
            fig.update_layout(height=450, margin=dict(t=0, l=0, r=0, b=0), template="plotly_dark")

            # 트리맵 출력 및 선택 감지
            selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=tm_key)

            if selected and "selection" in selected and selected["selection"]["points"]:
                new_label = selected["selection"]["points"][0].get("label")
                if new_label and st.session_state.get("clicked_sector") != new_label:
                    st.session_state.clicked_sector = new_label
                    st.rerun()

        with col_right:
            # [검증] data_sector가 여기서 정상적으로 잡히는지 확인됨
            last_data_date = data_sector.index[-1].date()
            is_latest_day = (actual_valid_date.date() >= last_data_date)

            target = st.session_state.get("clicked_sector")

            # 5월 4일 등 최신일 안내 (상시 노출)
            if is_latest_day:
                st.subheader("📢 데이터 업데이트 안내")
                st.warning("🔔 **현재 선택하신 날짜는 최신 데이터 업데이트 구간입니다.**")
                st.info("📅 해외 시장 확정 종가는 다음 영업일 오전 08:00 이후 반영됩니다.")
                st.markdown("---")

            # 트리맵에서 클릭된 섹터가 있을 때 상세 정보 출력
            if target:
                st.subheader(f"🚀 {target} 상세 정보")

                t_list = sector_map[target]["tickers"]
                n_list = sector_map[target]["names"]
                details = []

                # raw_sector_data에서 Volume 데이터만 미리 추출 및 정리
                try:
                    volume_df = raw_sector_data["Volume"].ffill().fillna(0)
                    # 만약 컬럼이 MultiIndex라면 레벨 정리
                    if isinstance(volume_df.columns, pd.MultiIndex):
                        volume_df.columns = volume_df.columns.get_level_values(0)
                except:
                    volume_df = pd.DataFrame()

                for t, n in zip(t_list, n_list):
                    try:
                        # 1. 가격 데이터 추출 (data_sector_krw는 이미 원화 환산 및 정리가 끝난 상태임)
                        if actual_valid_date in data_sector_krw.index:
                            display_p = data_sector_krw.loc[actual_valid_date, t]
                        else:
                            display_p = data_sector_krw[t].dropna().iloc[-1]

                        # 2. 거래량 데이터 추출 (volume_df에서 해당 티커 추출)
                        if not volume_df.empty and t in volume_df.columns:
                            if actual_valid_date in volume_df.index:
                                v = volume_df.loc[actual_valid_date, t]
                            else:
                                v = volume_df[t].dropna().iloc[-1]
                        else:
                            v = 0

                        # 3. 데이터 유효성 검사 (NaN 방지)
                        display_p = 0 if pd.isna(display_p) else display_p
                        v = 0 if pd.isna(v) else v

                        if display_p > 0:
                            # 거래대금 계산 (이미 display_p가 원화이므로 그대로 계산)
                            m_val = (display_p * v) / 1_000_000

                            details.append({
                                "종목": n,
                                "현재가": display_p,
                                "거래대금(백만)": m_val,
                                "거래량": v
                            })
                    except Exception as e:
                        continue

                if details:
                    st.dataframe(
                        pd.DataFrame(details).style.format({
                            "현재가": "{:,.0f}",
                            "거래대금(백만)": "{:,.1f}",
                            "거래량": "{:,.0f}"
                        }), use_container_width=True, hide_index=True
                    )

    # =========================
    # 📈 4. AI 분석 리포트 & 기상도
    # =========================
    st.markdown("---")
    st.markdown(f"## 🤖 AI Multi-Asset Trend Report")

    # [수정] date_idx가 정의되어 있어야 합니다. (앞선 날짜 선택 로직에서 정의됨)
    analysis_targets = ["NASDAQ", "Bitcoin", "Gold", "WTI", "KOSDAQ"]
    trend_results = []
    for t in analysis_targets:
        if t in data.columns:
            trend_results.append({"항목": t, **analyze_trend_fast(t, data, date_idx)})

    if 'sector_df' in locals():
        # [해결] actual_date -> actual_valid_date로 변경하여 NameError 방지
        s_idx = sector_df.index.get_indexer([actual_valid_date], method='nearest')[0]
        for s_name in sector_df.columns:
            res = analyze_trend_fast(s_name, sector_df, s_idx)
            res["항목"] = f"Sector: {s_name}"
            trend_results.append(res)

    report_df = pd.DataFrame(trend_results)
    col_l, col_r = st.columns([1.5, 1])

    with col_l:
        st.dataframe(report_df.style.map(color_status, subset=["상태"]).background_gradient(cmap="RdYlGn", subset=["점수"]),
                     use_container_width=True, hide_index=True)

    with col_r:
        if not report_df.empty:
            avg_s = report_df["점수"].mean()
            if avg_s > 75:
                st.success("#### AI 시장 진단\n시장이 매우 낙관적인 **강세장**입니다.")
            elif avg_s < 35:
                st.error("#### AI 시장 진단\n리스크 관리가 필요한 **약세장**입니다.")
            else:
                st.info("#### AI 시장 진단\n방향성을 탐색 중인 **박스권/혼조세**입니다.")

    # =========================
    # 🏭 5. 섹터 기상도 및 테마 분석 (최적화)
    # =========================
    st.markdown("### 🏭 Sector Weather Map")
    if 'sector_df' in locals() and not sector_df.empty:
        # [수정] actual_date -> actual_valid_date로 변수명 통일 및 안전한 인덱싱
        try:
            s_idx_list = sector_df.index.get_indexer([actual_valid_date], method='pad')
            s_idx = s_idx_list[0]

            # 인덱스 범위 초과 방지
            if s_idx < 0: s_idx = 0
            if s_idx >= len(sector_df): s_idx = len(sector_df) - 1

            p_idx = max(0, s_idx - 20)
            met_cols = st.columns(len(sector_df.columns))

            for i, col_name in enumerate(sector_df.columns):
                # 분모가 0이 되는 것을 방지하기 위한 처리
                prev_val = sector_df[col_name].iloc[p_idx]
                curr_val = sector_df[col_name].iloc[s_idx]

                ret = ((curr_val / prev_val) - 1) * 100 if prev_val != 0 else 0
                emoji = "☀️" if ret > 3 else "☁️" if ret > -1 else "🌧️"
                met_cols[i].metric(col_name, f"{ret:.1f}%", emoji)
        except Exception as e:
            st.error(f"Weather Map 생성 중 오류가 발생했습니다: {e}")

    # 테마 추천 섹션
    st.markdown("---")
    st.markdown("### 🤖 AI 섹터/테마 일관성 분석")

    # [수정] date_idx가 범위를 벗어나지 않도록 보장
    safe_date_idx = min(date_idx, len(data) - 1)
    daily_rets = data.pct_change().iloc[safe_date_idx].fillna(0)
    m_avg = daily_rets.mean()

    # 테마 데이터 연산 (가중 평균 및 필터링)
    theme_data = []
    # SECTOR_MAP과 theme_pool이 사전에 정의되어 있어야 합니다.
    for theme in theme_pool:
        for sector, info in SECTOR_MAP.items():
            if theme in info.get("themes", []):
                # [수정] info["anchors"]가 존재하는지 확인 후 진행
                anchors = info.get("anchors", {})
                ticks = [t for t in anchors.keys() if t in daily_rets.index]

                if not ticks: continue

                r_vals = daily_rets[ticks].values
                rel_r = r_vals.mean() - m_avg
                # std가 0일 경우를 대비한 처리
                std_val = r_vals.std()
                score = rel_r / (std_val + 1e-9)

                theme_data.append({
                    "테마": theme,
                    "섹터": sector,
                    "상대수익률": rel_r,
                    "점수": score
                })

    refined_df = pd.DataFrame(theme_data)
    if not refined_df.empty:
        # [수정] 최종 점수 산출 및 데이터프레임 스타일링
        refined_df["최종점수"] = (refined_df["점수"] * 0.6) + (refined_df.groupby("섹터")["점수"].transform("mean") * 0.4)

        top_10 = refined_df.nlargest(10, "최종점수")
        # 하위 10개 추출 로직 보완
        bottom_10 = refined_df[~refined_df["섹터"].isin(top_10["섹터"].unique())].nsmallest(10, "최종점수")
        if len(bottom_10) < 5:
            bottom_10 = refined_df.nsmallest(10, "최종점수")

        c1, c2 = st.columns(2)
        with c1:
            st.success("### 🟢 AI 추천 테마")
            st.dataframe(
                top_10[["섹터", "테마", "상대수익률"]].style.format({"상대수익률": "+{:.2%}"}).background_gradient(cmap="Greens"),
                use_container_width=True,
                hide_index=True
            )
        with c2:
            st.error("### 🔴 AI 유의 테마")
            st.dataframe(
                bottom_10[["섹터", "테마", "상대수익률"]].style.format({"상대수익률": "{:.2%}"}).background_gradient(cmap="Reds"),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("분석할 수 있는 테마 데이터가 부족합니다.")

# =========================================================
# 💡 [중요] 에러 해결: 대시보드에서 사용할 데이터를 먼저 정의합니다.
# =========================================================
# 1. 현재 선택된 날짜의 인덱스 확인 (앞선 코드에서 정의된 date_idx 사용)
# 2. 성장률(growth) 데이터에서 해당 날짜의 행만 추출하여 row_growth 생성
if 'growth' in locals() and 'date_idx' in locals():
    row_growth = growth.iloc[date_idx]
else:
    # 혹시라도 변수가 없을 경우를 대비한 방어 코드
    st.error("데이터(growth) 또는 날짜 인덱스가 설정되지 않았습니다.")
    st.stop()

# =========================
# 📈 4. AI Market Insight Dashboard (보완된 요약 대시보드)
# =========================
st.markdown("### 📈 AI Market Insight Dashboard")
summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)

with summary_col1:
    # report_df가 정의되어 있는지 확인 후 점수 계산
    if 'report_df' in locals() and not report_df.empty:
        avg_score = report_df["점수"].mean()
        sentiment = "매우 낙관" if avg_score > 80 else "낙관" if avg_score > 60 else "중립" if avg_score > 40 else "공포"
        st.metric("Market Sentiment", f"{sentiment}", delta=f"{avg_score:.1f} pts")
    else:
        st.metric("Market Sentiment", "분석중...", delta="0 pts")

with summary_col2:
    # 실시간 변동성 계산
    current_day_rets = data.pct_change().iloc[date_idx].fillna(0)
    m_vol = current_day_rets.std() * 100
    st.metric("Market Volatility", f"{'⚠️ 높음' if m_vol > 2 else '✅ 안정'}", delta=f"{m_vol:.2f}%")

with summary_col3:
    # row_growth 기반 최고 자산 (에러 지점 해결)
    best_asset = row_growth.idxmax()
    st.metric("Best Asset", best_asset, delta=f"{row_growth[best_asset]:.2f}%")

with summary_col4:
    # row_growth 기반 최저 자산 (에러 지점 해결)
    worst_asset = row_growth.idxmin()
    st.metric("Worst Asset", worst_asset, delta=f"{row_growth[worst_asset]:.2f}%", delta_color="inverse")
# =========================
# 📰 5. 뉴스 분석 (링크 포함)
# =========================
st.markdown("## 📰 AI 뉴스 분석")
st.markdown("### 📍 국내 뉴스")
keywords = ["금리", "국채", "환율", "유가", "부동산", "코스피"]

# get_news 함수와 feedparser가 정의되어 있어야 합니다.
news_cols = st.columns(3)
for i, keyword in enumerate(keywords):
    with news_cols[i % 3]:
        st.markdown(f"**📌 {keyword}**")
        try:
            news_list = get_news(keyword, 2)
            if news_list:
                for news in news_list:
                    # news가 딕셔너리 형태 {'title':..., 'link':...}인지 확인
                    if isinstance(news, dict):
                        st.markdown(f"- [{news['title']}]({news['link']})")
                    else:
                        st.markdown(f"- {news}")
            else:
                st.caption("관련 뉴스가 없습니다.")
        except Exception as e:
            st.caption(f"뉴스 로드 실패")
        st.markdown("---")

# =========================
# 🛠 뉴스 데이터 정제 및 번역 함수
# =========================
def clean_text(text):
    if not text: return ""
    # 1. HTML 엔티티 변환 (&quot; -> ", &amp; -> & 등)
    text = html.unescape(text)
    # 2. HTML 태그 제거 (<a ...></a>, <img> 등)
    text = re.sub(r'<[^>]+>', '', text)
    # 3. 불필요한 줄바꿈 및 공백 정리
    text = text.replace('\n', ' ').strip()
    return text


@st.cache_data(ttl=3600)
def get_global_news_ai(keyword_en, limit=2):
    # 1. RSS URL 구조 최적화
    encoded_keyword = quote(keyword_en)
    rss_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=en-US&gl=US&ceid=US:en"

    feed = feedparser.parse(rss_url)

    if not feed.entries:
        return []

    summarized_news = []
    for entry in feed.entries[:limit]:
        # 기사 제목과 설명 정제
        original_title = clean_text(entry.title)
        # 구글 뉴스 summary에는 기사 링크 등 HTML이 많이 포함되어 있어 강한 정제 필요
        raw_desc = clean_text(entry.summary) if 'summary' in entry else original_title
        # 번역 API 전송을 위해 길이 제한
        raw_desc = raw_desc[:250]

        try:
            # MyMemory API 번역 (제목)
            t_url = f"https://api.mymemory.translated.net/get?q={quote(original_title[:150])}&langpair=en|ko"
            t_res = requests.get(t_url, timeout=5).json()
            translated_title = t_res.get('responseData', {}).get('translatedText', original_title)
            translated_title = clean_text(translated_title) # 번역 결과물 정제

            # 번역 결과 필터링
            if "MYMEMORY WARNING" in translated_title or not translated_title:
                translated_title = original_title

            # MyMemory API 번역 (요약본)
            d_url = f"https://api.mymemory.translated.net/get?q={quote(raw_desc[:250])}&langpair=en|ko"
            d_res = requests.get(d_url, timeout=5).json()
            translated_summary = d_res.get('responseData', {}).get('translatedText', "요약을 불러올 수 없습니다.")
            translated_summary = clean_text(translated_summary) # 번역 결과물 정제

            if "MYMEMORY WARNING" in translated_summary:
                translated_summary = "원문을 참고해 주세요. (실시간 번역량 초과)"

            summarized_news.append({
                "title": translated_title,
                "original_title": original_title,
                "link": entry.link,
                "summary": translated_summary
            })
        except Exception:
            summarized_news.append({
                "title": original_title,
                "original_title": original_title,
                "link": entry.link,
                "summary": "내용 요약 및 번역 중 오류가 발생했습니다. 원문 링크를 확인하세요."
            })

    return summarized_news


# =========================
# 🌍 UI 레이아웃
# =========================
st.markdown("---")
st.markdown("### 🌐 글로벌 뉴스")

global_keywords = {
    "미국 금리": "(Treasuries",
    "미국": "Donald Trump Election US",
    "지정학적 리스크": "Oil Middle East Tension",
    "가상자산": "Bitcoin Crypto Regulation",
    "중국": "China US relations invasion of Taiwan",
    "한국": "Korea Debt to GDP"
}

global_cols = st.columns(2)
for i, (kr_name, en_keyword) in enumerate(global_keywords.items()):
    with global_cols[i % 2]:
        st.markdown(f" 📌 {kr_name}")
        news_data = get_global_news_ai(en_keyword, 2)

        if not news_data:
            st.caption("⚠️ 해당 키워드로 검색된 글로벌 뉴스가 없습니다.")
        else:
            for news in news_data:
                # 제목이 너무 길면 자르되 클릭 가능하게 처리
                with st.expander(f"📑 {news['title']}"):
                    st.caption(f"Original: {news['original_title']}")
                    st.info(f"**AI 번역 요약:** {news['summary']}")
                    st.markdown(f"🔗 [기사 원문 읽기]({news['link']})")
        st.markdown("---")

# =========================
# 🔚 Footer
# =========================
# actual_date를 위에서 정의한 actual_valid_date로 변경
st.markdown(f"<div style='text-align: center; color: gray; margin-top: 50px;'>🚀 v2.1 Optimized Dashboard | {actual_valid_date.strftime('%Y-%m-%d')}</div>", unsafe_allow_html=True)
