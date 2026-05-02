import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import feedparser
import urllib.parse
from datetime import datetime

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
# ⏱ 업데이트 시간
# =========================
st.markdown(
    f"<div style='text-align:right'>⏱ Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>",
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
# 📅 날짜 선택 (개선된 버전)
# =========================
data.index = pd.to_datetime(data.index)
dates = data.index

# 단일 state 초기화
if "selected_date" not in st.session_state:
    st.session_state.selected_date = dates[-1]

current = pd.to_datetime(st.session_state.selected_date)

st.markdown("## 📅 Date Controller")

# 1️⃣ Slider
slider_value = st.select_slider(
    "📊 Timeline",
    options=list(dates),
    value=st.session_state.selected_date
)

# 2️⃣ Dropdown
years = sorted(dates.year.unique())
months = list(range(1, 13))
days = list(range(1, 32))
hours = list(range(0, 24))

col1, col2, col3, col4 = st.columns(4)

with col1:
    year = st.selectbox("Year", years, index=years.index(current.year))

with col2:
    month = st.selectbox("Month", months, index=current.month - 1)

with col3:
    day = st.selectbox("Day", days, index=current.day - 1)

with col4:
    hour = st.selectbox("Hour", hours, index=current.hour)

# 드롭다운에서 선택한 날짜를 가장 가까운 실제 데이터 날짜로 변환
try:
    dt = pd.to_datetime(f"{year}-{month:02d}-{day:02d} {hour:02d}:00:00")
    idx = dates.get_indexer([dt], method="nearest")[0]
    dropdown_value = dates[idx]
except (ValueError, IndexError):
    dropdown_value = st.session_state.selected_date

# 🔄 State 업데이트 (충돌 해결)
changed = False
new_date = st.session_state.selected_date

# 슬라이더 우선
if slider_value != st.session_state.selected_date:
    new_date = slider_value
    changed = True
# 드롭다운 2순위
elif dropdown_value != st.session_state.selected_date:
    new_date = dropdown_value
    changed = True

if changed:
    st.session_state.selected_date = new_date
    st.rerun()

# =========================
# 📌 안전한 날짜 접근
# =========================
selected_date = st.session_state.selected_date
date_idx = data.index.get_indexer([selected_date], method="nearest")[0]
actual_date = data.index[date_idx]

# =========================
# 📊 Selected Date 분석
# =========================
st.markdown("## 📊 Selected Date Analysis")
st.markdown(f"**선택된 날짜**: {actual_date.strftime('%Y-%m-%d %H:%M')}")

row_usd = data.iloc[date_idx]
row_krw = data_krw.iloc[date_idx]
row_growth = growth.iloc[date_idx]

df_view = pd.DataFrame({
    "성장률 (%)": row_growth,
    "USD 값": row_usd,
    "KRW 값": row_krw
})

st.dataframe(df_view.style.format({
    "성장률 (%)": "{:.2f}",
    "USD 값": "{:,.2f}",
    "KRW 값": "{:,.0f}"
}))

# =========================
# 🧠 AI 시장 심리 (개선된 버전)
# =========================
returns = data.pct_change().iloc[date_idx].fillna(0)

score = (
        returns.get("NASDAQ", 0) * 0.4 +
        returns.get("KOSPI", 0) * 0.25 +
        returns.get("KOSDAQ", 0) * 0.15 +
        returns.get("Bitcoin", 0) * 0.2 -
        returns.get("Gold", 0) * 0.2
)

if score > 0.01:
    state = "🔥 Risk-On"
    comment = "성장주 및 위험자산 선호 흐름"
elif score < -0.01:
    state = "⚠️ Risk-Off"
    comment = "안전자산 중심 방어적 흐름"
else:
    state = "⚖️ Neutral"
    comment = "방향성 없는 혼조 흐름"

st.markdown(f"## 🧠 Market Sentiment\n- **상태**: {state}\n- **Score**: {score:.4f}\n- **해석**: {comment}")

# =========================
# 🏭 섹터별 스코어 (신규 추가)
# =========================
st.markdown("## 🏭 Sector Analysis")

sector_scores = {}
for sector, info in SECTOR_MAP.items():
    score = sum(
        returns.get(ticker, 0) * weight
        for ticker, weight in info["anchors"].items()
    )
    sector_scores[sector] = score

sector_df = pd.DataFrame.from_dict(
    sector_scores, orient="index", columns=["Score"]
).sort_values("Score", ascending=False)

sector_df["Status"] = sector_df["Score"].apply(
    lambda x: "🟢 상승" if x > 0.005 else "🔴 하락" if x < -0.005 else "⚪ 보합"
)

st.dataframe(
    sector_df.style.format({"Score": "{:.4%}"}),
    use_container_width=True
)


# =========================
# 🤖 테마 추천 (개선된 버전)
# =========================
def get_theme_score_and_sector(theme, returns):
    """테마별 스코어 및 소속 섹터 반환"""
    for sector, info in SECTOR_MAP.items():
        if theme in info["themes"]:
            score = sum(
                returns.get(ticker, 0) * weight
                for ticker, weight in info["anchors"].items()
            )
            return score, sector
    # 매핑되지 않은 테마는 전체 평균
    return returns.mean(), "기타"


theme_data = []
for theme in theme_pool:
    score, sector = get_theme_score_and_sector(theme, returns)
    theme_data.append({"테마": theme, "스코어": score, "섹터": sector})

theme_df = pd.DataFrame(theme_data)

# 상위 10개, 하위 10개
top_themes = theme_df.nlargest(10, "스코어")
bottom_themes = theme_df.nsmallest(10, "스코어")

st.markdown("## 🤖 AI Theme Recommendation")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("### 🟢 투자 권고")
    st.dataframe(
        top_themes[["테마", "섹터", "스코어"]].style.format({"스코어": "{:.4%}"}),
        use_container_width=True
    )

with col_right:
    st.markdown("### 🔴 투자 유의")
    st.dataframe(
        bottom_themes[["테마", "섹터", "스코어"]].style.format({"스코어": "{:.4%}"}),
        use_container_width=True
    )

# =========================
# 📰 뉴스 (캐싱 적용)
# =========================
st.markdown("---")
st.markdown("## 📰 뉴스 분석")

keywords = [
    "미국 기준금리",
    "한국 기준금리",
    "달러",
    "유가",
    "AI 반도체",
    "비트코인",
    "중동",
    "트럼프",
    "원유"
]

news_cols = st.columns(3)
for i, keyword in enumerate(keywords):
    with news_cols[i % 3]:
        st.markdown(f"**📌 {keyword}**")
        news_list = get_news(keyword, 2)
        for news in news_list:
            st.markdown(f"- {news}")
        st.markdown("---")

# =========================
# 📊 요약 대시보드
# =========================
st.markdown("## 📊 Summary Dashboard")

summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)

with summary_col1:
    st.metric(
        "Market Sentiment",
        state.split()[1],
        delta=f"{score:.4f}"
    )

with summary_col2:
    best_asset = row_growth.idxmax()
    st.metric(
        "Best Asset",
        best_asset,
        delta=f"{row_growth[best_asset]:.2f}%"
    )

with summary_col3:
    worst_asset = row_growth.idxmin()
    st.metric(
        "Worst Asset",
        worst_asset,
        delta=f"{row_growth[worst_asset]:.2f}%"
    )

with summary_col4:
    best_sector = sector_df.index[0]
    st.metric(
        "Best Sector",
        best_sector,
        delta=f"{sector_df.loc[best_sector, 'Score']:.4%}"
    )

# =========================
# 🔚 Footer
# =========================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; fon


t-size: 12px;'>
    🚀 Enhanced Financial Dashboard v2.0 | 데이터: Yahoo Finance | 뉴스: Google News RSS
</div>
""", unsafe_allow_html=True)

