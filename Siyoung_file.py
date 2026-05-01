import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import feedparser
import urllib.parse
from datetime import datetime

st.set_page_config(layout="wide")

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
    "Gold": "GC=F"
}

usd_assets = ["Bitcoin", "NASDAQ", "S&P500", "Gold"]

# =========================
# 📊 데이터 로드
# =========================
@st.cache_data(ttl=300)
def load_data():
    df = yf.download(list(tickers.values()), start="2018-01-01", progress=False)["Close"]
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(1)
    df.columns = list(tickers.keys())
    return df.ffill().bfill()

@st.cache_data(ttl=300)
def load_fx():
    fx = yf.download("KRW=X", start="2018-01-01", progress=False)["Close"]
    return fx.squeeze().ffill().bfill()

data = load_data()
fx = load_fx()

# =========================
# 💱 KRW 환산
# =========================
fx_align = fx.reindex(data.index).ffill().bfill()
data_krw = data.copy()

for col in usd_assets:
    data_krw[col] = data[col].values * fx_align.values

# =========================
# 📊 성장률
# =========================
growth = pd.DataFrame(index=data.index)

for col in data.columns:
    first = data[col].first_valid_index()
    if first is not None:
        growth[col] = (data[col] / data.loc[first, col] - 1) * 100

# =========================
# 📊 자산 차트
# =========================
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
macro_tickers = {
    "US10Y": "^TNX",
    "US2Y": "^IRX",
    "DXY": "DX-Y.NYB",
    "USDKRW": "KRW=X"
}

@st.cache_data(ttl=300)
def load_macro():
    df = yf.download(list(macro_tickers.values()), start="2018-01-01", progress=False)["Close"]
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(0, axis=1)
    df.columns = list(macro_tickers.keys())
    return df.ffill().bfill()

macro = load_macro()
macro_growth = (macro / macro.iloc[0] - 1) * 100

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
# 📅 날짜 선택
# =========================
# =========================
# 📅 데이터 준비
# =========================
data.index = pd.to_datetime(data.index)
dates = data.index

# =========================
# 📅 단일 state
# =========================
if "selected_date" not in st.session_state:
    st.session_state.selected_date = dates[-1]

current = pd.to_datetime(st.session_state.selected_date)

st.markdown("## 📅 Date Controller (State Sync Only)")

# =========================
# 1️⃣ slider (state 반영 + state 업데이트)
# =========================
# slider
slider_value = st.select_slider(
    "📊 Timeline",
    options=list(dates),
    value=st.session_state.selected_date
)

# 🔥 반드시 state에 반영
if slider_value != st.session_state.selected_date:
    st.session_state.selected_date = slider_value
    st.rerun()

# =========================
# 2️⃣ dropdown (state만 업데이트)
# =========================
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

dt = pd.to_datetime(f"{year}-{month:02d}-{day:02d} {hour:02d}:00:00")
idx = dates.get_indexer([dt], method="nearest")[0]
dropdown_value = dates[idx]

# =========================
# 🔄 핵심: state만 업데이트
# =========================
new_date = st.session_state.selected_date

if slider_value != new_date:
    new_date = slider_value

if dropdown_value != new_date:
    new_date = dropdown_value

if new_date != st.session_state.selected_date:
    st.session_state.selected_date = new_date
    st.rerun()

# =========================
# 📌 단일 데이터 기준값
# =========================
date = st.session_state.selected_date

# =========================
# 📊 Selected Date 분석
# =========================
st.markdown("## 📊 Selected Date Analysis")

row_usd = data.loc[date]
row_krw = data_krw.loc[date]
row_growth = growth.loc[date]

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
# 🧠 AI 시장 심리
# =========================
returns = data.pct_change().loc[date]

score = (
    returns.get("NASDAQ",0)*0.4 +
    returns.get("KOSPI",0)*0.25 +
    returns.get("KOSDAQ",0)*0.15 +
    returns.get("Bitcoin",0)*0.2 -
    returns.get("Gold",0)*0.2
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

st.markdown(f"## 🧠 Market Sentiment\n- 상태: {state}\n- Score: {score:.4f}\n👉 {comment}")

# =========================
# 🤖 테마 (AI 심리 바로 아래)
# =========================
theme_pool = [
"AI","반도체","로봇","클라우드","소프트웨어","데이터센터",
"자동차","전기차","자율주행","2차전지","건설","조선","철강","화학",
"에너지","정유","LNG","태양광","풍력","수소","원자력",
"비트코인","블록체인","핀테크",
"금","채권","리츠","유틸리티",
"헬스케어","제약","바이오",
"방산","우주항공","드론",
"항공","여행","카지노","엔터","미디어",
"식품","유통","플랫폼","게임","교육","물류","스마트팜"
]

def theme_score(t):
    base = returns.mean()
    if t in ["AI","반도체","클라우드"]:
        base += returns.get("NASDAQ",0)
    if t in ["자동차","전기차"]:
        base += returns.get("S&P500",0)
    if t in ["비트코인"]:
        base += returns.get("Bitcoin",0)
    if t in ["금","채권"]:
        base += returns.get("Gold",0)
    return base

scores = pd.Series({t: theme_score(t) for t in theme_pool})

top = scores.sort_values(ascending=False).head(10)
bottom = scores.sort_values(ascending=True).head(10)

# =========================
# 📊 테이블 구성
# =========================
df = pd.DataFrame({
    "투자 권고": top.index.values,
    "권고 수익률": top.values,
    "투자 유의": bottom.index.values,
    "유의 수익률": bottom.values
})

# 보기 좋게 퍼센트 변환
df["권고 수익률"] = df["권고 수익률"].map(lambda x: f"{x:.2%}")
df["유의 수익률"] = df["유의 수익률"].map(lambda x: f"{x:.2%}")

st.markdown("## 🤖 AI Theme Recommendation")

st.dataframe(df, use_container_width=True)

# =========================
# 📰 뉴스
# =========================
st.markdown("---")
st.markdown("## 📰 뉴스 분석")

def get_news(q, n=3):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    return [e.title for e in feed.entries[:n]]

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

for k in keywords:
    news = get_news(k)
    st.markdown(f"📌 {k}")
    st.markdown("- " + " | ".join(news) if news else "뉴스 없음")
    st.markdown("---")
