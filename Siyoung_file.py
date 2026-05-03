import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import feedparser
import urllib.parse
from datetime import datetime
import pytz
import requests
import re
import html
from urllib.parse import quote

st.set_page_config(layout="wide", page_title="AI Financial Dashboard")

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
    raw = yf.download(list(tickers.values()), start="2018-01-01", progress=False)["Close"]
    if isinstance(raw.columns, pd.MultiIndex): raw = raw.droplevel(0, axis=1)
    ticker_to_name = {v: k for k, v in tickers.items()}
    data = raw.rename(columns=ticker_to_name).ffill().bfill()

    # 매크로 데이터
    m_tickers = {"US10Y": "^TNX", "US2Y": "^IRX", "DXY": "DX-Y.NYB"}
    macro_raw = yf.download(list(m_tickers.values()), start="2018-01-01", progress=False)["Close"]
    if isinstance(macro_raw.columns, pd.MultiIndex): macro_raw = macro_raw.droplevel(0, axis=1)
    macro = macro_raw.rename(columns={v: k for k, v in m_tickers.items()}).ffill().bfill()

    return data, macro


def calculate_growth(df):
    # 벡터 연산으로 속도 최적화
    return (df / df.iloc[0] - 1) * 100


# 데이터 로딩
data, macro = load_all_data()
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
st.markdown(f"### 🌍📈 지수차트")

if not growth.empty:
    fig = go.Figure()

    # 시인성 높은 고대비 커스텀 색상 팔레트
    custom_colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
        "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
        "#bcbd22", "#17becf"
    ]

    last_points = []

    # [수정 포인트] USDKRW를 제외하고 차트를 그립니다.
    for i, col in enumerate(growth.columns):
        if col == "USDKRW":  # ✅ 환율은 선 차트에서 제외
            continue

        line_color = custom_colors[i % len(custom_colors)]

        # 차트 선 그리기
        fig.add_trace(go.Scatter(
            x=growth.index,
            y=growth[col],
            customdata=data_krw[col],  # 이제 여기서 KeyError가 발생하지 않습니다.
            name=col,
            mode='lines',
            line=dict(width=1.5, color=line_color),  # 두께 조정 포인트
            hovertemplate="📅 %{x|%Y-%m-%d}<br><b>%{fullData.name}</b><br>📈 %{y:.2f}%<br>💰 %{customdata:,.0f}<extra></extra>"
        ))

        last_points.append({
            "col": col,
            "y": growth[col].iloc[-1],
            "val": data_krw[col].iloc[-1],
            "color": line_color
        })

    # 2. Y축 정렬 및 지그재그 태그 로직
    last_points.sort(key=lambda x: x['y'], reverse=True)

    for i, p in enumerate(last_points):
        is_right = i % 2 == 0
        side_offset = 80 if is_right else -80
        x_anchor = "left" if is_right else "right"

        fig.add_annotation(
            x=growth.index[-1],
            y=p['y'],
            text=f"<b>{p['col']}</b><br>{p['val']:,.0f}",
            showarrow=True,
            arrowhead=1,
            arrowsize=0.8,  # 화살표 크기도 선 두께에 맞춰 살짝 줄임
            arrowwidth=1,
            arrowcolor=p['color'],
            ax=side_offset,
            ay=0,
            xanchor=x_anchor,
            yanchor="middle",
            font=dict(size=10, color="white"),  # 텍스트 크기 미세 조정
            bgcolor=p['color'],
            opacity=0.8,
            bordercolor="white",
            borderwidth=0.5,
            borderpad=3
        )

    # 3. 레이아웃 설정
    fig.update_layout(
        template="plotly_dark",
        dragmode="pan",
        height=650,
        margin=dict(l=90, r=90, t=80, b=50),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11)
        ),
        xaxis=dict(showgrid=False),
        yaxis=dict(zeroline=True, zerolinecolor="rgba(255,255,255,0.2)")
    )

    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

# =========================
# 🌍 매크로 차트
# =========================
st.markdown(f"### 🌍 📊 매크로(거시) 경제 차트")

improved_colors = [
    "#1f77b4",  # 진한 파랑
    "#d62728",  # 진한 빨강
    "#2ca02c",  # 숲색 (진녹색)
    "#ff7f0e",  # 짙은 주황
    "#9467bd",  # 보라
    "#17becf",  # 청록
    "#e377c2",  # 핑크 (마젠타 계열)
    "#8c564b",  # 갈색
    "#4169E1",  # 로열 블루
    "#008080"  # 틸(Teal)
]

# --- 매크로 차트 적용 예시 ---
if not macro_growth.empty:
    fig2 = go.Figure()
    last_points_macro = []

    for i, col in enumerate(macro_growth.columns):
        # 개선된 팔레트 사용
        line_color = improved_colors[i % len(improved_colors)]

        fig2.add_trace(go.Scatter(
            x=macro_growth.index,
            y=macro_growth[col],
            customdata=macro[col],
            name=col,
            mode='lines',
            line=dict(width=1.5, color=line_color),
            hovertemplate="📅 %{x|%Y-%m-%d}<br><b>%{fullData.name}</b><br>📈 %{y:.2f}%<br>💎 %{customdata:.2f}<extra></extra>"
        ))

        last_points_macro.append({
            "col": col, "y": macro_growth[col].iloc[-1],
            "val": macro[col].iloc[-1], "color": line_color
        })

    # (이후 정렬 및 지그재그 태그 로직은 이전과 동일)
    last_points_macro.sort(key=lambda x: x['y'], reverse=True)

    for i, p in enumerate(last_points_macro):
        is_right = i % 2 == 0
        side_offset = 80 if is_right else -80

        fig2.add_annotation(
            x=macro_growth.index[-1],
            y=p['y'],
            text=f"<b>{p['col']}</b><br>{p['val']:.2f}",
            showarrow=True,
            arrowcolor=p['color'],
            ax=side_offset,
            ay=0,
            xanchor="left" if is_right else "right",
            yanchor="middle",
            font=dict(size=10, color="white"),  # 흰색 글자가 잘 보이도록 배경색 대비 강화
            bgcolor=p['color'],  # 태그 배경이 이제 더 짙은 색이라 글자가 잘 보입니다
            opacity=0.9,  # 가독성을 위해 불투명도 살짝 상향
            bordercolor="white",
            borderwidth=0.5,
            borderpad=3
        )

    # 4. 레이아웃 설정
    fig2.update_layout(
        template="plotly_dark",
        dragmode="pan",
        height=600,  # 태그 가독성을 위해 높이 확보
        margin=dict(l=90, r=90, t=80, b=50),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11)
        ),
        xaxis=dict(showgrid=False),
        yaxis=dict(zeroline=True, zerolinecolor="rgba(255,255,255,0.2)")
    )

    st.plotly_chart(fig2, use_container_width=True, config={"scrollZoom": True})

# =========================
# 📅 기간별 섹터 분석 선택
# =========================
    st.markdown(f"### 📅📈 기간별 섹터 분석")

    # 1. 기간 설정 및 데이터 준비
    period = st.selectbox(
        "기간설정",
        ["7일", "1개월", "6개월", "1년"]
    )

    period_map = {"7일": 7, "1개월": 30, "6개월": 180, "1년": 365}
    period_days_map = {7: "1mo", 30: "3mo", 180: "1y", 365: "2y"}

    days = period_map[period]
    yf_period = period_days_map[days]

    # 📊 섹터 및 종목 매핑
    sector_map = {
        "반도체": {"tickers": ["005930.KS", "000660.KS", "NVDA", "TSM", "INTC", "AMD"],
        "names": ["삼성전자", "SK하이닉스", "엔비디아", "TSMC", "인텔", "AMD"]},
        "자동차": {"tickers": ["005380.KS", "000270.KS", "TSLA", "F"],
        "names": ["현대차", "기아", "테슬라", "포드 모터"]},
        "방산": {"tickers": ["012450.KS", "272210.KS", "003490.KS", "LMT","PLTR"],
        "names": ["한화에어로스페이스", "한화시스템", "대한항공", "록히드마틴", "팔란티어"]},
        "소프트웨어": {"tickers": ["035420.KS", "035720.KS", "MSFT", "GOOGL", "GOOG", "META", "ORCL"],
        "names": ["NAVER", "카카오", "마이크로소프트", "구글(알파벳 Class A)", "구글(알파벳 Class C)", "메타", "오라클"]},
        "우주항공": {"tickers": ["047810.KS", "012450.KS", "003490.KS", "079550.KS", "RKLB"],
        "names": ["한국항공우주", "한화에어로스페이스","대한항공", "LIG넥스원", "로켓랩"]},
        "해운/유통": {"tickers": ["042660.KS", "011200.KS", "005880.KS", "000120.KS", "AMZN", "WMT", "CPNG", "GD"],
        "names": ["한화오션", "HMM", "대한해운", "CJ대한통운", "아마존닷컴", "월마트", "쿠팡", "제너럴 다이내믹스"]},
        "에너지": {"tickers": ["015760.KS", "298040.KS", "034020.KS", "010120.KS", "229640.KS", "267260.KS"],
        "names": ["한국전력", "효성중공업", "두산에너빌리티", "LS ELECTRIC", "LS에코에너지", "HD현대일렉트릭"]},
        "건설": {"tickers": ["000720.KS", "028050.KS", "028260.KS", "006360.KS"],
        "names": ["현대건설", "DL이앤씨", "삼성물산", "GS건설"]}
    }

    # 📥 데이터 다운로드 및 수익률 계산
    all_tickers = [t for v in sector_map.values() for t in v["tickers"]]
    stock_list = list(set(all_tickers))

    # 📥 데이터 다운로드 부분 수정
    raw = yf.download(stock_list, period=yf_period, progress=False)["Close"]

    # MultiIndex 대응 (yfinance 버전에 따라 다름)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(1)

    # 중요: 해외 주식과 한국 주식의 시차 때문에 발생하는 NaN을 앞뒤로 꽉 채워줘야 계산이 됨
    data_sector = raw.ffill().bfill()


    # 데이터가 잘 불러와졌는지 디버깅용 (나중에 삭제)
    #st.write(data_sector.columns) # 내가 요청한 티커들이 컬럼명에 다 있는지 확인

    def build_sector_index(sector_map, data_sector):
        sector_df = pd.DataFrame(index=data_sector.index)
        for sector, info in sector_map.items():
            valid = [s for s in info["tickers"] if s in data_sector.columns]
            if valid:
                sector_df[sector] = data_sector[valid].mean(axis=1)
        return sector_df


    sector_df = build_sector_index(sector_map, data_sector)
    growth_sector = sector_df / sector_df.iloc[0] * 100

    # 🎨 차트별 고유 색상 팔레트 정의
    colors = [
        "#636EFA", "#EF553B", "#00CC96", "#AB63FA",
        "#FFA15A", "#19D3F3", "#FF6692", "#B6E880"
    ]


    # 📊 섹터별 차트 + 하단 종목 확인 (컬러 적용 버전)
    st.markdown("---")

    sectors = list(growth_sector.columns)
    for i in range(0, len(sectors), 2):
        row_cols = st.columns(2)

        for j in range(2):
            if i + j < len(sectors):
                sector_name = sectors[i + j]
                sector_color = colors[(i + j) % len(colors)]  # 섹터별 고유 색상 선택

                with row_cols[j]:
                    # 1. 개별 차트 생성
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=growth_sector.index,
                        y=growth_sector[sector_name],
                        mode="lines",
                        line=dict(width=3, color=sector_color),  # 고유 컬러 적용
                        name=sector_name,
                        hovertemplate="<b>%{x|%y.%m.%d}</b><br>수익률: %{y:.2f}%<extra></extra>"
                    ))

                    # 차트 디자인 설정
                    fig.update_layout(
                        title=f"📈 {sector_name} 수익률 추이",
                        height=320,
                        margin=dict(l=40, r=20, t=50, b=40),
                        xaxis=dict(title="날짜", tickformat="%y.%m.%d", showgrid=True),
                        yaxis=dict(title="지수(100)", showgrid=True),
                        plot_bgcolor="rgba(0,0,0,0)",  # 배경 투명하게
                        showlegend=False
                    )

                    st.plotly_chart(fig, use_container_width=True, key=f"chart_{sector_name}")

                    # 2. 차트 바로 밑에 구성종목 배치
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
    # 📅 1. 날짜 제어 및 인덱싱 (최적화)
    # =========================
    # =========================
    # 📅 날짜 선택 및 상호 동기화 로직
    # =========================
    st.markdown("## 📅 기간별 AI 시장분석")

    # 1. 데이터 인덱스 처리
    data.index = pd.to_datetime(data.index)
    available_dates = data.index.unique()

    if "selected_date" not in st.session_state:
        st.session_state.selected_date = available_dates[-1]

    # 2. 정밀 조정을 위한 드롭다운 (연/월/일/시)
    # 현재 선택된 날짜에서 각 구성 요소 추출
    curr_date = st.session_state.selected_date

    col_y, col_m, col_d, col_t = st.columns(4)

    with col_y:
        years = sorted(available_dates.year.unique(), reverse=True)
        sel_y = st.selectbox("Year", options=years, index=years.index(curr_date.year))

    with col_m:
        months = sorted(available_dates[available_dates.year == sel_y].month.unique())
        # 선택한 연도에 현재 월이 없을 경우를 대비한 처리
        default_m_idx = months.index(curr_date.month) if curr_date.month in months else 0
        sel_m = st.selectbox("Month", options=months, index=default_m_idx)

    with col_d:
        days = sorted(available_dates[(available_dates.year == sel_y) & (available_dates.month == sel_m)].day.unique())
        default_d_idx = days.index(curr_date.day) if curr_date.day in days else 0
        sel_d = st.selectbox("Day", options=days, index=default_d_idx)

    with col_t:
        times = sorted(available_dates[(available_dates.year == sel_y) & (available_dates.month == sel_m) & (
                    available_dates.day == sel_d)])
        # 시/분/초까지 있는 경우를 대비해 문자열 포맷팅
        time_options = [t.strftime("%H:%M") for t in times]
        curr_time_str = curr_date.strftime("%H:%M")
        default_t_idx = time_options.index(curr_time_str) if curr_time_str in time_options else 0
        sel_t_str = st.selectbox("Time", options=time_options, index=default_t_idx)

        # 최종 선택된 날짜 객체 생성
        dropdown_date = times[time_options.index(sel_t_str)]

    # 3. 슬라이더와 드롭다운 동기화
    # 드롭다운에서 변경이 일어나면 세션 상태 업데이트
    if dropdown_date != st.session_state.selected_date:
        st.session_state.selected_date = dropdown_date
        st.rerun()

    # 4. 시각적 보조를 위한 슬라이더 (모바일에서는 대략적인 이동 용도)
    selected_date = st.select_slider(
        "📊 슬라이더로 빠르게 이동",
        options=list(available_dates),
        value=st.session_state.selected_date,
        format_func=lambda x: x.strftime('%Y-%m-%d')
    )

    # 슬라이더 조작 시 세션 상태 업데이트
    if selected_date != st.session_state.selected_date:
        st.session_state.selected_date = selected_date
        st.rerun()

    actual_date = st.session_state.selected_date
    date_idx = data.index.get_indexer([actual_date], method="nearest")[0]

    st.info(f"📍 현재 분석 시점: **{actual_date.strftime('%Y-%m-%d %H:%M')}**")

    # =========================
    # 📊 지수별 정리표
    # =========================
    st.markdown("### 📊 지수별 정리표")

    # 1. 환율 및 기초 데이터 계산
    current_fx = float(data.loc[actual_date, "USDKRW"])
    usd_vals = chart_data.iloc[date_idx].copy()
    krw_vals = usd_vals.copy()

    # 2. 통화 환산 (USD 자산 -> KRW, KRW 자산 -> USD)
    for col in usd_assets:
        krw_vals[col] = usd_vals[col] * current_fx
    for col in ["KOSPI", "KOSDAQ"]:
        usd_vals[col] = krw_vals[col] / current_fx

    # 3. 데이터프레임 생성 및 '원하는 순서'로 정렬
    # 요청하신 순서 리스트 (데이터프레임의 인덱스명과 일치해야 함)
    custom_order = [
        "Dow Jones", "NASDAQ", "S&P500", "Gold",
        "Bitcoin", "WTI", "Natural Gas", "KOSPI", "KOSDAQ"
    ]

    df_view = pd.DataFrame({
        "성장률 (%)": growth.iloc[date_idx],
        "USD 값": usd_vals,
        "KRW 값": krw_vals
    })

    # USDKRW를 제외하고 위에서 정의한 순서대로 재배치
    df_ordered = df_view.reindex(custom_order)

    # 4. 환율(USDKRW) 행 생성 및 결합
    exchange_row = pd.DataFrame({
        "성장률 (%)": [0.0],  # 환율 자체의 성장률이 필요하다면 growth['USDKRW']를 넣을 수 있습니다.
        "USD 값": [1.0],
        "KRW 값": [current_fx]
    }, index=["USDKRW (환율)"])

    final_df = pd.concat([df_ordered, exchange_row])

    # 5. 출력 (소수점 2자리 포맷팅)
    st.dataframe(final_df.style.format("{:,.2f}"), use_container_width=True)
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


    # =========================
    # 📈 4. AI 분석 리포트 & 기상도
    # =========================
    st.markdown("---")
    st.markdown(f"## 🤖 AI Multi-Asset Trend Report")

    analysis_targets = ["NASDAQ", "Bitcoin", "Gold", "WTI", "KOSDAQ"]
    trend_results = []
    for t in analysis_targets:
        if t in data.columns:
            trend_results.append({"항목": t, **analyze_trend_fast(t, data, date_idx)})

    if 'sector_df' in locals():
        s_idx = sector_df.index.get_indexer([actual_date], method='nearest')[0]
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
    if 'sector_df' in locals():
        s_idx = sector_df.index.get_indexer([actual_date], method='nearest')[0]
        p_idx = max(0, s_idx - 20)
        met_cols = st.columns(len(sector_df.columns))
        for i, col_name in enumerate(sector_df.columns):
            ret = (sector_df[col_name].iloc[s_idx] / sector_df[col_name].iloc[p_idx] - 1) * 100
            emoji = "☀️" if ret > 3 else "☁️" if ret > -1 else "🌧️"
            met_cols[i].metric(col_name, f"{ret:.1f}%", emoji)

    # 테마 추천 섹션
    st.markdown("---")
    st.markdown("### 🤖 AI 섹터/테마 일관성 분석")
    daily_rets = data.pct_change().iloc[date_idx].fillna(0)
    m_avg = daily_rets.mean()

    # 테마 데이터 연산 (가중 평균 및 필터링)
    theme_data = []
    for theme in theme_pool:
        for sector, info in SECTOR_MAP.items():
            if theme in info["themes"]:
                ticks = [t for t in info["anchors"].keys() if t in daily_rets.index]
                if not ticks: continue
                r_vals = daily_rets[ticks].values
                rel_r = r_vals.mean() - m_avg
                theme_data.append({"테마": theme, "섹터": sector, "상대수익률": rel_r, "점수": rel_r / (r_vals.std() + 1e-9)})

    refined_df = pd.DataFrame(theme_data)
    if not refined_df.empty:
        refined_df["최종점수"] = (refined_df["점수"] * 0.6) + (refined_df.groupby("섹터")["점수"].transform("mean") * 0.4)
        top_10 = refined_df.nlargest(10, "최종점수")
        bottom_10 = refined_df[~refined_df["섹터"].isin(top_10["섹터"].unique())].nsmallest(10, "최종점수")
        if len(bottom_10) < 5: bottom_10 = refined_df.nsmallest(10, "최종점수")

        c1, c2 = st.columns(2)
        c1.success("### 🟢 AI 추천 테마")
        c1.dataframe(
            top_10[["섹터", "테마", "상대수익률"]].style.format({"상대수익률": "+{:.2%}"}).background_gradient(cmap="Greens"),
            use_container_width=True)
        c2.error("### 🔴 AI 유의 테마")
        c2.dataframe(
            bottom_10[["섹터", "테마", "상대수익률"]].style.format({"상대수익률": "{:.2%}"}).background_gradient(cmap="Reds"),
            use_container_width=True)

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
keywords = ["금리", "국채", "달러", "유가", "비트코인", "트럼프"]

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
st.markdown(f"<div style='text-align: center; color: gray; margin-top: 50px;'>🚀 v2.1 Optimized Dashboard | {actual_date.strftime('%Y-%m-%d')}</div>", unsafe_allow_html=True)
