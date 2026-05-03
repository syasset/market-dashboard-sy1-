import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import feedparser
import urllib.parse
from datetime import datetime
import pytz # ✅ 추가

st.set_page_config(layout="wide")

# =========================
# 📊 섹터 매핑 설정
# =========================
SECTOR_MAP = {
    "Tech": {
        "themes": ["AI", "반도체", "클라우드", "소프트웨어", "데이터센터", "로봇"],
        "anchors": {"NASDAQ": 0.6, "S&P500": 0.3, "KOSDAQ": 0.1}
    },
    "Energy": {
        "themes": ["에너지", "정유", "LNG", "원유", "WTI", "천연가스"],
        "anchors": {"WTI": 0.5, "Natural Gas": 0.3, "S&P500": 0.2}
    },
    "GreenEnergy": {
        "themes": ["태양광", "풍력", "수소", "원자력", "2차전지"],
        "anchors": {"NASDAQ": 0.3, "KOSPI": 0.3, "KOSDAQ": 0.3, "S&P500": 0.1}
    },
    "Crypto": {
        "themes": ["비트코인", "블록체인", "핀테크"],
        "anchors": {"Bitcoin": 0.8, "NASDAQ": 0.2}
    },
    "Defensive": {
        "themes": ["금", "채권", "리츠", "유틸리티"],
        "anchors": {"Gold": 0.7, "S&P500": 0.2, "KOSPI": 0.1}
    },
    "Industrial": {
        "themes": ["자동차", "전기차", "조선", "철강", "방산", "우주항공", "드론", "건설", "화학"],
        "anchors": {"S&P500": 0.4, "KOSPI": 0.4, "WTI": 0.1, "Natural Gas": 0.1}
    },
    "Healthcare": {
        "themes": ["헬스케어", "제약", "바이오"],
        "anchors": {"NASDAQ": 0.4, "S&P500": 0.4, "KOSPI": 0.2}
    },
    "Consumer": {
        "themes": ["항공", "여행", "카지노", "엔터", "미디어", "게임", "유통", "물류", "식품", "플랫폼", "교육"],
        "anchors": {"S&P500": 0.4, "KOSPI": 0.3, "KOSDAQ": 0.2, "NASDAQ": 0.1}
    },
    "KoreaSpecial": {
        "themes": ["KOSPI대형주", "스마트팜"],
        "anchors": {"KOSPI": 0.7, "KOSDAQ": 0.3}
    }
}

# 전체 테마 풀 (섹터 맵에서 자동 생성)
theme_pool = []
for sector_info in SECTOR_MAP.values():
    theme_pool.extend(sector_info["themes"])

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
    "KOSDAQ": "^KQ11",
    "NASDAQ": "^IXIC",
    "S&P500": "^GSPC",
    "Gold": "GC=F",
    "WTI": "CL=F",
    "Natural Gas": "NG=F"
}

usd_assets = ["Bitcoin", "NASDAQ", "S&P500", "Gold", "WTI", "Natural Gas"]


# =========================
# 📊 데이터 로드 (개선된 버전)
# =========================
@st.cache_data(ttl=300)
def load_data():
    try:
        raw = yf.download(list(tickers.values()), start="2018-01-01", progress=False)["Close"]

        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(1)

        ticker_to_name = {v: k for k, v in tickers.items()}
        data = raw.rename(columns=ticker_to_name)

        # 🔥 순서 정렬
        order = ["NASDAQ", "S&P500", "Gold", "WTI", "Natural Gas", "Bitcoin", "KOSPI", "KOSDAQ"]
        data = data[order]

        return data.ffill().bfill()
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_fx():
    try:
        fx = yf.download("KRW=X", start="2018-01-01", progress=False)["Close"]
        return fx.squeeze().ffill().bfill()
    except Exception as e:
        st.error(f"환율 데이터 로드 오류: {e}")
        return pd.Series()


@st.cache_data(ttl=300)
def load_macro():
    macro_tickers = {
        "US10Y": "^TNX",
        "US2Y": "^IRX",
        "DXY": "DX-Y.NYB",
        "USDKRW": "KRW=X"
    }

    try:
        df = yf.download(list(macro_tickers.values()), start="2018-01-01", progress=False)["Close"]
        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel(0, axis=1)
        df.columns = list(macro_tickers.keys())
        return df.ffill().bfill()
    except Exception as e:
        st.error(f"매크로 데이터 로드 오류: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=600)  # 10분 캐시
def get_news(q, n=3):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = feedparser.parse(url)
        return [e.title for e in feed.entries[:n]]
    except Exception:
        return ["뉴스를 불러올 수 없습니다."]


# 데이터 로드
data = load_data()
fx = load_fx()
macro = load_macro()

# 빈 데이터 체크
if data.empty or fx.empty:
    st.error("데이터 로드에 실패했습니다. 잠시 후 다시 시도해주세요.")
    st.stop()

# =========================
# 💱 KRW 환산
# =========================
fx_align = fx.reindex(data.index).ffill().bfill()
data_krw = data.copy()

for col in usd_assets:
    if col in data_krw.columns:
        data_krw[col] = data[col].values * fx_align.values


# =========================
# 📊 성장률 계산 (최적화된 버전)
# =========================
def calculate_growth(df):
    growth = pd.DataFrame(index=df.index)
    for col in df.columns:
        first_valid_idx = df[col].first_valid_index()
        if first_valid_idx is not None:
            first_value = df.loc[first_valid_idx, col]
            if first_value != 0:
                growth[col] = (df[col] / first_value - 1) * 100
            else:
                growth[col] = 0
        else:
            growth[col] = 0
    return growth


growth = calculate_growth(data)

# 매크로 성장률 (개선된 버전)
if not macro.empty:
    macro_growth = calculate_growth(macro)
else:
    macro_growth = pd.DataFrame()

# =========================
# 📊 자산 차트
# =========================
st.markdown("## 🌍📊 지수, 섹터별 지표")
st.markdown(f"### 🌍📈 지수차트")
if not growth.empty:
    fig = go.Figure()

    for col in growth.columns:
        fig.add_trace(go.Scatter(
            x=growth.index,
            y=growth[col],
            customdata=data_krw[col],
            name=col,
            hovertemplate="📅 %{x|%Y-%m-%d}<br>%{fullData.name}<br>📈 %{y:.2f}%<br>💰 %{customdata:,.0f}<extra></extra>"
        ))

    fig.update_layout(template="plotly_dark", dragmode="pan", height=600)
    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

# =========================
# 🌍 매크로 차트
# =========================
st.markdown(f"### 🌍📈 매크로(거시) 경제 차트")
if not macro_growth.empty:
    fig2 = go.Figure()

    for col in macro_growth.columns:
        fig2.add_trace(go.Scatter(
            x=macro_growth.index,
            y=macro_growth[col],
            customdata=macro[col],
            name=col,
            hovertemplate="📅 %{x|%Y-%m-%d}<br>%{fullData.name}<br>📈 %{y:.2f}%<br>💰 %{customdata:.2f}<extra></extra>"
        ))

    fig2.update_layout(template="plotly_dark", dragmode="pan", height=500)
    st.plotly_chart(fig2, use_container_width=True, config={"scrollZoom": True})

# =========================
# 📅 기간별 섹터 분석 선택
# =========================
    import streamlit as st
    import yfinance as yf
    import pandas as pd
    import plotly.graph_objects as go

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
        "반도체": {"tickers": ["005930.KS", "000660.KS"], "names": ["삼성전자", "SK하이닉스"]},
        "자동차": {"tickers": ["005380.KS", "000270.KS"], "names": ["현대차", "기아"]},
        "방산": {"tickers": ["012450.KS", "272210.KS"], "names": ["한화에어로스페이스", "한화시스템"]},
        "소프트웨어": {"tickers": ["035420.KS", "035720.KS"], "names": ["NAVER", "카카오"]},
        "우주항공": {"tickers": ["047810.KS", "079550.KS"], "names": ["한국항공우주", "LIG넥스원"]},
        "휴머노이드 로봇": {"tickers": ["068270.KS"], "names": ["셀트리온(예시)"]},
        "식료품": {"tickers": ["097950.KS", "271560.KS"], "names": ["CJ제일제당", "오리온"]},
        "건설": {"tickers": ["000720.KS", "028050.KS"], "names": ["현대건설", "DL이앤씨"]}
    }

    # 📥 데이터 다운로드 및 수익률 계산
    all_tickers = [t for v in sector_map.values() for t in v["tickers"]]
    stock_list = list(set(all_tickers))

    raw = yf.download(stock_list, period=yf_period, progress=False)["Close"]
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(1)

    data_sector = raw.ffill().bfill()


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

    import pandas as pd
    import numpy as np
    import streamlit as st
    import feedparser  # pip install feedparser 필요

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
    data.index = pd.to_datetime(data.index)
    dates = data.index

    if "selected_date" not in st.session_state:
        st.session_state.selected_date = dates[-1]

    st.markdown("## 📅 기간별 AI 시장분석")

    # Timeline Slider & Dropdowns (레이아웃 통합)
    slider_value = st.select_slider("📊 Timeline", options=list(dates), value=st.session_state.selected_date,
                                    key="slider_v2")

    current = pd.to_datetime(st.session_state.selected_date)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        year = st.selectbox("Year", sorted(dates.year.unique()), index=sorted(dates.year.unique()).index(current.year))
    with col2:
        month = st.selectbox("Month", range(1, 13), index=current.month - 1)
    with col3:
        day = st.selectbox("Day", range(1, 32), index=min(current.day - 1, 30))
    with col4:
        hour = st.selectbox("Hour", range(0, 24), index=current.hour)

    # 날짜 확정 로직
    try:
        dt_input = pd.to_datetime(f"{year}-{month:02d}-{day:02d} {hour:02d}:00:00")
        dropdown_val = dates[dates.get_indexer([dt_input], method="nearest")[0]]
    except:
        dropdown_val = slider_value

    final_date = slider_value if slider_value != st.session_state.selected_date else dropdown_val

    if final_date != st.session_state.selected_date:
        st.session_state.selected_date = final_date
        st.rerun()

    # 기준 인덱스 고정 (이후 모든 계산에서 재사용)
    date_idx = dates.get_indexer([st.session_state.selected_date], method="nearest")[0]
    actual_date = dates[date_idx]

    # =========================
    # 📊 2. Selected Date Analysis (요청하신 수치 표)
    # =========================
    # 타이틀 🇰🇷
    # --- 환율 데이터 가져오는 코드 추가 ---
    try:
        # yfinance를 이용해 원/달러 환율(USDKRW=X)의 가장 최근 종가를 가져옵니다.
        # 만약 기존 코드에서 이미 환율을 다운로드하고 있다면 그 변수명을 사용하세요.
        ex_data = yf.download("USDKRW=X", period="1d", progress=False)
        exchange_rate = ex_data['Close'].iloc[-1]
    except Exception:
        # 환율 로드 실패 시 기본값 설정 (에러 방지용)
        exchange_rate = 1474.0  # 현재 대략적인 환율

    # 만약 exchange_rate가 Series 형태로 오면 숫자로 변환
    if hasattr(exchange_rate, 'values'):
        exchange_rate = float(exchange_rate.values[0])
    # ----------------------------------

    st.markdown("---")
    st.markdown(f"### 📊 🇰🇷 지수별 정리표 ({actual_date.strftime('%Y-%m-%d %H:%M')})")

    # ... 이후 기존의 usd_values 보정 코드 계속 ...

    # 1. 데이터 복사
    usd_values = data.iloc[date_idx].copy()
    krw_values = data_krw.iloc[date_idx].copy()

    # 2. 인덱스 이름을 확인하여 강제로 환율 계산 적용
    # 인덱스가 '^KS11'이든 'KOSPI'이든 글자가 포함만 되어 있으면 계산합니다.
    for label in usd_values.index:
        target_label = str(label).upper()  # 대문자로 통일해서 비교

        if "KS11" in target_label or "KOSPI" in target_label or "코스피" in target_label:
            # 코스피 보정: KRW 값(6,599)을 환율(1,474)로 나눔 -> 4.48
            usd_values[label] = krw_values[label] / exchange_rate

        elif "KQ11" in target_label or "KOSDAQ" in target_label or "코스닥" in target_label:
            # 코스닥 보정
            usd_values[label] = krw_values[label] / exchange_rate

    # 3. 데이터프레임 생성
    df_view = pd.DataFrame({
        "성장률 (%)": growth.iloc[date_idx],
        "USD 값": usd_values,
        "KRW 값": krw_values
    })

    # 4. 출력 포맷 설정
    st.dataframe(df_view.style.format({
        "성장률 (%)": "{:.2f}",
        "USD 값": "{:,.2f}",  # 이제 4.48로 표시됩니다.
        "KRW 값": "{:,.0f}"  # 6,599로 표시됩니다.
    }), use_container_width=True)


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

import requests
import feedparser
import streamlit as st
from urllib.parse import quote
import re
import html  # 특수 문자 변환(&quot; 등)을 위해 추가

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
    "미국 금리": "Federal Reserve FOMC",
    "미국": "Donald Trump Election",
    "지정학적 리스크": "Oil Middle East Tension",
    "가상자산": "Bitcoin Crypto Regulation",
    "중국": "China",
    "한국": "Korea"
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
st.markdown("---")
# actual_date 변수가 없을 경우 오늘 날짜 표시
footer_date = actual_date.strftime('%Y-%m-%d') if 'actual_date' in locals() else "N/A"
st.markdown(f"""
<div style='text-align: center; color: gray; font-size: 12px;'>
    🚀 Enhanced Financial Dashboard v2.0 | 분석 기준일: {footer_date}
</div>
""", unsafe_allow_html=True)
