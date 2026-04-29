import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import feedparser
import urllib.parse
from streamlit_autorefresh import st_autorefresh

# =========================
# 🔄 자동 새로고침 (5분)
# =========================
st_autorefresh(interval=300000, key="auto_refresh")  # 300,000ms = 5분

st.set_page_config(layout="wide")

# =========================
# 📌 종목 정의
# =========================
tickers = {
    "Bitcoin": "BTC-USD",
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "NASDAQ": "^IXIC",
    "S&P500": "^GSPC",
    "Gold": "GC=F",
    "Oil": "CL=F",
    "Natural Gas": "NG=F"
}

# =========================
# 📊 데이터 로딩 (5분 캐시)
# =========================
@st.cache_data(ttl=300)
def fetch_data():
    raw = yf.download(list(tickers.values()), period="1y", progress=False)["Close"]
    raw.columns = list(tickers.keys())
    raw = raw.dropna(how="all")
    return raw

data_raw = fetch_data()

# =========================
# 📊 INDEX CHART
# =========================
data_indexed = data_raw / data_raw.iloc[0] * 100

fig = go.Figure()

for col in data_indexed.columns:
    fig.add_trace(go.Scatter(
        x=data_indexed.index,
        y=data_indexed[col],
        mode="lines",
        name=col,
        hovertemplate="📅 %{x|%Y-%m-%d}<br>%{fullData.name}: %{y:.2f}<extra></extra>"
    ))

fig.update_layout(
    title="📊 Multi-Asset Dashboard (Indexed Comparison)",
    height=600,
    template="plotly_dark",
    hovermode="closest",
    dragmode="pan"
)

st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

# =========================
# 📅 날짜 선택
# =========================
selected_date = st.select_slider(
    "📅 분석 날짜 선택 (차트와 독립)",
    options=data_raw.index,
    value=data_raw.index[-1]
)

row = data_raw.loc[selected_date]
row_index = data_indexed.loc[selected_date]
returns_on_day = data_raw.pct_change().loc[selected_date]

# =========================
# 💱 환율 기준
# =========================
USD_TO_KRW = 1350

def to_krw(asset, value):
    if asset in ["KOSPI", "KOSDAQ"]:
        return value
    return value * USD_TO_KRW

# =========================
# 📌 Selected Date
# =========================
st.markdown("---")
st.markdown(f"## 📌 Selected Date: {selected_date.date()}")

st.markdown("### 💱 Currency Guide")
st.markdown("""
- 🇺🇸 USD: Bitcoin, NASDAQ, S&P500, Gold, Oil, Natural Gas  
- 🇰🇷 KRW: KOSPI, KOSDAQ  
""")

table = pd.DataFrame({
    "Asset": row.index,
    "Index (Base=100)": row_index.values,
    "USD Price": row.values,
})

table["KRW Price"] = [
    to_krw(a, v) for a, v in zip(row.index, row.values)
]

table["Index (Base=100)"] = table["Index (Base=100)"].apply(lambda x: f"{x:.2f}")
table["USD Price"] = table["USD Price"].apply(lambda x: f"{x:,.2f}")
table["KRW Price"] = table["KRW Price"].apply(lambda x: f"{x:,.0f}")

st.dataframe(table, use_container_width=True)

# =========================
# 🧠 AI 시장 상태 분석
# =========================
st.markdown("---")
st.markdown("## 🤖 AI 시장 상태 분석")

btc = returns_on_day.get("Bitcoin", 0)
nasdaq = returns_on_day.get("NASDAQ", 0)
kospi = returns_on_day.get("KOSPI", 0)
kosdaq = returns_on_day.get("KOSDAQ", 0)
gold = returns_on_day.get("Gold", 0)

market_score = (
    nasdaq * 0.4 +
    kospi * 0.25 +
    kosdaq * 0.15 +
    btc * 0.2 -
    gold * 0.2
)

if market_score > 0.01:
    market_state = "🔥 강한 상승장 (Risk-On)"
    interpretation = "위험자산으로 자금 유입"
elif market_score > 0:
    market_state = "📈 완만한 상승장"
    interpretation = "완만한 상승 흐름"
elif market_score < -0.01:
    market_state = "⚠️ 하락장 (Risk-Off)"
    interpretation = "안전자산 선호"
else:
    market_state = "⚖️ 혼조장 (Neutral)"
    interpretation = "방향성 부족"

st.markdown(f"""
### 📊 시장 진단
- 상태: **{market_state}**
- 해석: {interpretation}

### 📌 자산 변화
- NASDAQ: {nasdaq*100:.2f}%
- KOSPI: {kospi*100:.2f}%
- KOSDAQ: {kosdaq*100:.2f}%
- Bitcoin: {btc*100:.2f}%
- Gold: {gold*100:.2f}%

👉 시장 점수: **{market_score:.4f}**
""")

# =========================
# 🤖 AI 투자 추천
# =========================
st.markdown("---")
st.markdown("## 🤖 AI 투자 추천")

if market_score > 0.01:
    recommended = [
        "AI 반도체", "NASDAQ 성장주", "2차전지", "클라우드",
        "비트코인", "로봇", "신재생에너지", "모멘텀 ETF",
        "미국 성장주", "헬스케어"
    ]
    risky = ["채권", "금", "배당주", "유틸리티", "저변동 ETF"]

elif market_score < -0.01:
    recommended = [
        "금", "미국 국채", "달러", "배당주", "필수소비재",
        "헬스케어", "현금", "에너지", "방어주", "방어 ETF"
    ]
    risky = [
        "AI 과열", "코인 레버리지", "중소형 바이오",
        "2차전지 과열", "성장주"
    ]

else:
    recommended = [
        "ETF 분산", "인덱스 투자", "배당 성장", "금+주식",
        "글로벌 ETF", "에너지", "현금", "헷지", "저변동 ETF",
        "균형 포트폴리오"
    ]
    risky = [
        "레버리지", "단일 테마", "코인", "투기주", "고PER 성장주"
    ]

st.markdown("### 📈 추천 TOP 10")
for i, r in enumerate(recommended, 1):
    st.write(f"{i}. {r}")

st.markdown("---")

st.markdown("### ⚠️ 리스크 TOP 10")
for i, r in enumerate(risky, 1):
    st.write(f"{i}. {r}")

# =========================
# 📊 변동성
# =========================
returns = data_raw.pct_change().dropna()
volatility = returns.std() * (252 ** 0.5)

vol_df = pd.DataFrame({
    "Asset": volatility.index,
    "Volatility": volatility.values
}).sort_values("Volatility", ascending=False)

st.markdown("---")
st.markdown("## 📊 Volatility Ranking")
st.dataframe(vol_df.reset_index(drop=True), use_container_width=True)

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
    "중동"
]

for k in keywords:
    news = get_news(k)
    st.markdown(f"📌 {k}")
    st.markdown("- " + " | ".join(news) if news else "뉴스 없음")
    st.markdown("---")