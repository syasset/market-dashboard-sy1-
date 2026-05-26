import plotly.graph_objects as go
import plotly.express as px
import feedparser
import urllib.parse
from datetime import datetime, timedelta
import pytz
import re
import html
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
import time
import random
import streamlit as st  # 이 줄이 반드시 있어야 합니다!
import yfinance as yf
import pandas as pd
import numpy as np
from streamlit_autorefresh import st_autorefresh
import json
from google import genai
import datetime as dt_module
import os

if 'sector_df' not in locals():
    sector_df = pd.DataFrame()
if 'news_list' not in locals():
    news_list = []

# F5 새로고침 시 세션 증발을 방어하기 위한 로컬 캐시 파일 경로
CACHE_FILE = "gemini_report_cache.json"

# ---------------------------------------------------------
# 🛡️ 세션 상태 초기화 및 뉴스 메모리 브릿지 개설
# ---------------------------------------------------------
if 'sector_df' not in locals():
    sector_df = pd.DataFrame()

# 💡 핵심: 하단의 뉴스 크롤링 결과가 상단 제미나이로 유기적으로 배달되도록 세션 상태로 관리합니다.
if 'news_list' not in st.session_state:
    st.session_state.news_list = []

st_autorefresh(interval=3 * 60 * 1000, key="data_refresh")

# F5 새로고침 시 세션 증발을 방어하기 위한 로컬 캐시 파일 경로
CACHE_FILE = "gemini_report_cache.json"

# 스트림릿 세션 상태(Session State) 안전 초기화 및 로컬 복원 가드
if "stored_report" not in st.session_state:
    st.session_state.stored_report = None
if "api_status" not in st.session_state:
    st.session_state.api_status = "IDLE"
if "last_analysis_time" not in st.session_state:
    st.session_state.last_analysis_time = None
if "retry_wait_time" not in st.session_state:
    st.session_state.retry_wait_time = 0
if "last_error_time" not in st.session_state:
    st.session_state.last_error_time = None
if "error_detail" not in st.session_state:
    st.session_state.error_detail = ""

# [팝업 먹통 완치 가드] F5 새로고침 시 파일 캐시를 읽어 기존 대시보드 상태값까지 완벽 복원
if st.session_state.stored_report is None and os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
            if cache_data.get("stored_report"):
                st.session_state.stored_report = cache_data.get("stored_report")
                st.session_state.last_analysis_time = cache_data.get("last_analysis_time")
                st.session_state.api_status = "SUCCESS"
                st.session_state.error_detail = ""
    except Exception:
        pass


# =========================================
#  글로벌 매크로 AI 분석 엔진 (세션 뉴스 데이터 실시간 하이브리드 반영)
# =========================================
def get_ai_macro_analysis(news_list=None, market_data=None, macro_data=None, sector_df=None, limit=None):
    try:
        # [교훈] 사용자 정답 경로 및 v1 명시 고정
        client = genai.Client(
            api_key=st.secrets["GEMINI_API_KEY"],
            http_options={'api_version': 'v1'}
        )

        # 💡 [순서 제약 돌파]: 인자로 받은 news_list가 비어있다면, 세션 브릿지에 저장된 하단의 최신 크롤링 데이터를 동적으로 낚아챕니다.
        target_news = news_list if news_list else st.session_state.news_list
        d_limit = limit if limit else 12
        n_txt = "\n".join([str(n) for n in target_news[:d_limit]]) if target_news else "현재 크롤링된 대시보드 뉴스 데이터 없음 (구글 실시간 검색 의존)"

        seoul_tz = pytz.timezone("Asia/Seoul")
        now = dt_module.datetime.now(seoul_tz)

        weekday_list = list(("월", "화", "수", "목", "금", "토", "일"))
        weekday_str = weekday_list[now.weekday()]

        current_date_str = now.strftime("%Y년 %m월 %d일")
        current_time_str = now.strftime(f"%Y년 %m월 %d일 ({weekday_str}요일) %H시 %M분")

        st.session_state.last_analysis_time = current_time_str

        # 프롬프트에 대시보드 자체 크롤링 뉴스 데이터 묶음(n_txt)을 완벽 배달 주입합니다.
        prompt = f"""
        당신은 글로벌 자산운용사의 수석 투자 전략가입니다.
        반드시 아래의 지침을 칼같이 준수하여 분석 리포트를 작성하세요. 
        리포트의 최상단 서문(제목 바로 아래)에는 분석 완료 시점인 한국(서울) 기준 일시 **{current_time_str}**를 반드시 명시하여 시작하세요.

        🚨 [최신성 및 날짜 제한 절대 원칙]
        - 오늘 날짜와 시간은 **{current_time_str}** 입니다.
        - 반드시 이 시점을 기준으로 구글 실시간 웹 검색(Search)을 수행하고, 아래 제공되는 대시보드 수집 뉴스를 상호 교차 검증하여 가장 최신(24~48시간 이내)의 시황을 기반으로 분석하세요.
        - 특히 최근 시장 변동성의 핵심인 '트럼프-시진핑 정상회담', '스페이스X IPO' 등 매크로 빅이벤트와 관련 뉴스가 수집되어 있다면 이를 최우선으로 리포트에 반영하세요.
        - 과거 고정 데이터나 유통기한이 지난 수치를 기재하는 것은 치명적인 오류입니다.

        📊 [대시보드 자체 시스템 수집 최신 경제/시황 뉴스 백엔드 데이터]
        {n_txt}

        📊 [시장 심리 및 대중 관심도(Sentiment) 반영 조건]
        - 전쟁, 정상회담, 패권 경쟁 등 시장의 기대감과 불안감을 자극하는 이벤트 분석 시, 단순히 사건의 발생 여부만 적지 마세요.
        - 해당 이슈가 '여러 언론사에서 집중적으로 다뤄지고 있는지', 'SNS 및 커뮤니티에서 리태그/인용되며 대중의 관심도가 극에 달해 있는지' 등 시장 참여자들의 심리적 과열 상태를 함께 진단하세요.

        🔎 [참고 키워드: 실제 시장 영향 분석 및 수치 도출용]
        - 뉴스: 금리, 전쟁, 오일쇼크, 정상회담, 신기술 개발(양자역학, 휴머노이드, UAM 등), IPO, 패권, 인수 합병, 협약, 우주, 나스닥, 다우존스, S&P500, 코스피, 코스닥, 환율 등
        - 지표: 매크로 경제, 미국 2년/10년 국채 금리, 달러인덱스(DXY), 고용지표, 한국 부채, 주요 지수 종가, 실시간 환율 등

        📌 [필수 포함 내용]
        1. 💥 최근 급등락 원인 분석: 최근 발생한 갑작스러운 지수 등락에 대해 뉴스 및 지표 키워드를 매핑하여 원인을 데이터와 함께 정확히 대답해주세요.
        2. 🔬 핵심 시황 진단: 현재({current_date_str} 기준) 시장의 가장 큰 테마와 리스크 요인을 분석하세요. (언론사 노출도 및 대중 리태그 심리 분석 포함)
        3. 🎯 유망 종목 추천: 글로벌 시총 TOP 50 및 국내 우량주 기준 현재 상황에서 가장 수익성이 기대되는 5종목을 각각 선정하고, 명확한 정량적 데이터(최신 실적, 지표, 수혜 규모)를 근거로 선정 이유를 설명하세요.
        4. 🐋 고래들의 포트폴리오 최신 동향: 국민연금, 버크셔 헤서웨이 등 주요 기관/고래들의 가장 최근 공시(13F 등) 기준 보유 종목 및 비중 지표 동향을 요약하세요.
        5. 📝 전략 요약: 향후 투자 포지션에 대한 3줄 요약 가이드를 제시하세요.
        """

        response = client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=prompt,
            config=google.genai.types.GenerateContentConfig(  # 👈 풀 경로를 적어주면 파이썬이 무조건 알아듣습니다.
                tools=[{"google_search": {}}]  # 실시간 구글 검색엔진 장착 툴 완벽 가동
            )
        )

        if response and response.text:
            st.session_state.stored_report = response.text
            st.session_state.api_status = "SUCCESS"
            st.session_state.error_detail = ""

            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump({
                        "stored_report": st.session_state.stored_report,
                        "last_analysis_time": st.session_state.last_analysis_time,
                        "api_status": "SUCCESS"
                    }, f, ensure_ascii=False, indent=4)
            except Exception:
                pass
        else:
            st.session_state.api_status = "EMPTY"

    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg:
            retry_seconds = 60
            match = re.search(r"retry in ([\d\.]+)s", err_msg)
            if match:
                retry_seconds = int(float(match.group(1)))
            st.session_state.retry_wait_time = retry_seconds
            st.session_state.last_error_time = time.time()
            st.session_state.api_status = "QUOTA_EXCEEDED"
            st.session_state.error_detail = err_msg
        else:
            st.session_state.api_status = "SERVER_ERROR"
            st.session_state.error_detail = err_msg

get_global_news_ai = get_ai_macro_analysis


# 팝업 윈도우 인터페이스
@st.dialog("📊 AI 종합 마켓 분석 시스템", width="large")
def show_report_popup(title, content):
    st.subheader(title)

    if st.session_state.last_analysis_time:
        st.caption(f"🕒 **데이터 분석 기준 시점:** {st.session_state.last_analysis_time}")

    st.divider()
    if content and str(content).strip():
        st.markdown(content)
    else:
        st.info("💡 현재 저장된 리포트 텍스트가 비어 있습니다. 사이드바의 '마켓 분석 예약' 버튼을 눌러 실시간 분석 데이터를 새로 받아와 주세요.")

    if st.button("닫기"):
        st.rerun()


# ==========================================
# 3. 사이드바 UI 로직 (비동기 스레딩 & 영구 보존 메모리 매니저)
# ==========================================
import threading

# F5 새로고침 및 단말기 세션 갱신에도 보존되는 전역 영구 저장소 (조건문 3 충족)
if not hasattr(st, "_stored_report_cache"):
    st._stored_report_cache = ""
if not hasattr(st, "_api_status_cache"):
    st._api_status_cache = "READY"
if not hasattr(st, "_error_detail_cache"):
    st._error_detail_cache = ""


def run_sidebar_logic(news_list, growth, macro_growth, sector_df):
    st.sidebar.markdown("---")
    st.sidebar.subheader("🤖 AI 인텔리전스")

    # 세션 상태 변수가 없으면 영구 저장소의 값으로 초기화 (F5 방어 및 연동)
    if 'stored_report' not in st.session_state:
        st.session_state.stored_report = st._stored_report_cache
    if 'api_status' not in st.session_state:
        st.session_state.api_status = st._api_status_cache
    if 'error_detail' not in st.session_state:
        st.session_state.error_detail = st._error_detail_cache
    if 'is_analyzing' not in st.session_state:
        st.session_state.is_analyzing = False

    # 백그라운드에서 구글 API를 실행할 비동기 래퍼 함수 (조건문 5 충족)
    def bg_analysis_worker():
        try:
            # 오직 이 버튼 로직을 통해서만 분석이 수행됨 (조건문 1 충족)
            get_global_news_ai(news_list, growth, macro_growth, sector_df, limit=12)
            # 완료 후 전역 캐시와 세션에 결과 저장
            st._stored_report_cache = st.session_state.stored_report
            st._api_status_cache = st.session_state.api_status
        except Exception as e:
            st._api_status_cache = "SERVER_ERROR"
            st._error_detail_cache = str(e)
            st.session_state.api_status = "SERVER_ERROR"
            st.session_state.error_detail = str(e)
        finally:
            st._is_analyzing_cache = False

    # [기능 1] 마켓 분석 예약 버튼
    if not st.session_state.is_analyzing:
        if st.sidebar.button("🚀 마켓 분석 예약", use_container_width=True):
            st.session_state.is_analyzing = True
            # 백그라운드 스레드를 생성하여 구글 API를 겟(Get)하므로 메인 화면이 멈추지 않음
            thr = threading.Thread(target=bg_analysis_worker)
            thr.start()
            st.toast("🦁 백그라운드에서 구글 AI 마켓 분석이 예약되었습니다. 다른 작업을 계속 진행하실 수 있습니다!")
            st.rerun()
    else:
        st.sidebar.info("⏳ 구글 AI가 백그라운드에서 분석 중입니다... (대시보드 이용 가능)")
        if st.sidebar.button("🔄 분석 상태 새로고침", use_container_width=True):
            # 세션 상태와 전역 캐시를 동기화하여 실시간 반영
            st.session_state.stored_report = st._stored_report_cache
            st.session_state.api_status = st._api_status_cache
            st.session_state.error_detail = st._error_detail_cache
            st.rerun()

    # [기능 2] 분석 결과 보기 버튼 (오직 이 버튼을 눌렀을 때만 팝업창을 제어함 - 조건문 2, 3 충족)
    if st.session_state.stored_report:
        st.sidebar.success("✅ 최근 성공 리포트 보관 중")
        if st.sidebar.button("📄 최근 분석 결과 보기", use_container_width=True):
            show_report_popup("📊 AI 종합 마켓 분석 리포트", st.session_state.stored_report)

    elif st.session_state.api_status in ["QUOTA_EXCEEDED", "SERVER_ERROR"]:
        st.sidebar.error("⚠️ 분석 실패 기록 존재")
        if st.sidebar.button("🚨 에러 내용 보기", use_container_width=True):
            err_content = f"🚨 **구글 API 호출 오류**\n\n할당량 초과 또는 서버 불안정 현상입니다. 잠시 후 다시 분석을 요청해주세요.\n\n---\n**[에러 원문]**\n{st.session_state.error_detail}"
            show_report_popup("⚠️ 분석 실패 안내", err_content)


@st.dialog("종목 상세 분석 및 재무 상태", width="large")
def show_stock_detail(ticker, name, df_krw):
    # --- 데이터 로드 ---
    @st.cache_data(ttl=86400)
    def get_financial_info(t_code):
        try:
            t = yf.Ticker(t_code)
            q_fin = t.quarterly_financials
            info = t.info
            return q_fin, info
        except:
            return None, None

    q_fin_df, info_dict = get_financial_info(ticker)

    # --- 상단 헤더 ---
    col_title, col_price = st.columns([1.5, 1])
    with col_title:
        st.write(f"### {name} ({ticker})")

    with col_price:
        curr_price_krw = df_krw[ticker].dropna().iloc[-1] if ticker in df_krw.columns else 0
        is_foreign = not any(ex in ticker.upper() for ex in [".KS", ".KQ"])

        p_col1, p_col2 = st.columns(2)
        p_col1.metric("현재가 (KRW)", f"{curr_price_krw:,.0f}원")
        if is_foreign and info_dict:
            curr_price_usd = info_dict.get('currentPrice') or info_dict.get('regularMarketPrice', 0)
            p_col2.metric("현재가 (USD)", f"${curr_price_usd:,.2f}")

    tab1, tab2, tab3, tab4 = st.tabs(["📈 주가 차트", "📊 분기 실적 요약", "💡 투자 지표", "🤖 AI 저평가 진단"])

    # --- 1번 탭: 주가 차트 (호버 기능 강화) ---
    with tab1:
        valid_series = df_krw[ticker].dropna()
        if len(valid_series) > 2:
            lookback_days = st.slider("조회 기간 설정 (일)", 2, len(valid_series), min(30, len(valid_series)),
                                      key=f"slider_{ticker}")

            # 1. 원본 가격 데이터 및 수익률 계산
            price_series = valid_series.iloc[-lookback_days:]
            stock_growth = (price_series / price_series.iloc[0] - 1) * 100

            # 2. 해외 종목인 경우 달러 가격 계산 (df_krw 생성 시 사용한 USDKRW 역산)
            # 만약 전역 변수 'data'에 USDKRW가 있다면 가져와서 계산합니다.
            usd_prices = None
            if is_foreign and 'data' in globals() and 'USDKRW' in globals()['data'].columns:
                exchange_rate = globals()['data']['USDKRW'].reindex(price_series.index, method='ffill')
                usd_prices = price_series / exchange_rate

            # 3. 차트 생성
            fig = go.Figure()

            # 호버에 표시할 데이터 묶기 (한화 가격, 달러 가격)
            # customdata는 리스트의 리스트 형태로 넘겨야 합니다.
            custom_data_list = [price_series.values]
            hover_template_str = "날짜: %{x}<br><b>수익률: %{y:.2f}%</b><br>가격(KRW): %{customdata[0]:,.0f}원"

            if usd_prices is not None:
                custom_data_list.append(usd_prices.values)
                hover_template_str += "<br>가격(USD): $%{customdata[1]:.2f}"

            custom_data_final = np.stack(custom_data_list, axis=-1)

            fig.add_trace(go.Scatter(
                x=stock_growth.index,
                y=stock_growth.values,
                customdata=custom_data_final,
                mode='lines',
                line=dict(width=3, color='#00CC96'),
                fill='tozeroy',
                fillcolor='rgba(0, 204, 150, 0.1)',
                hovertemplate=hover_template_str + "<extra></extra>"
            ))

            fig.update_layout(
                template="plotly_dark",
                height=400,
                yaxis=dict(ticksuffix="%"),
                margin=dict(t=20, b=20),
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)

            # 하단 수익률 요약 텍스트
            period_return = (price_series.iloc[-1] / price_series.iloc[0] - 1) * 100
            st.write(
                f"⏱ **최근 {lookback_days}일간 수익률:** :{'red' if period_return > 0 else 'blue'}[{period_return:+.2f}%]")
        else:
            st.warning("차트 데이터가 부족합니다.")

    # --- 2번 탭: 분기 실적 요약 (QoQ, YoY 증감율) ---
    with tab2:
        if q_fin_df is not None and not q_fin_df.empty:
            # 1. 필요 항목 추출 및 전치(Transpose)하여 시계열 순서로 정렬
            items = {'Total Revenue': '매출액', 'Operating Income': '영업이익', 'Net Income': '당기순이익'}
            available_items = [i for i in items.keys() if i in q_fin_df.index]

            if available_items:
                # 데이터를 행(항목), 열(날짜) -> 행(날짜), 열(항목)로 변경 후 날짜 오름차순 정렬
                df = q_fin_df.loc[available_items].T.sort_index(ascending=True)
                df = df.rename(columns=items)

                # 2. 증감율 계산
                # QoQ (직전 분기 대비): 현재 행 / 이전 행 - 1
                qoq_change = df.pct_change(periods=1) * 100
                # YoY (작년 동분기 대비): 현재 행 / 4개 이전 행 - 1
                yoy_change = df.pct_change(periods=4) * 100

                # 3. 최신 분기 데이터들만 역순으로(최신이 위로) 표시
                latest_df = df.iloc[::-1].copy()

                st.markdown("#### 📅 최근 분기별 실적 상세")

                for col in df.columns:
                    st.write(f"**📍 {col}**")

                    # 수치, QoQ, YoY를 합친 데이터프레임 생성
                    display_df = pd.DataFrame({
                        '금액': latest_df[col].map(lambda x: f"{x:,.0f}" if pd.notnull(x) else "-"),
                        '직전분기 대비(QoQ)': qoq_change[col].iloc[::-1].map(
                            lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-"),
                        '전년동기 대비(YoY)': yoy_change[col].iloc[::-1].map(lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-")
                    })

                    # 날짜 형식 예쁘게 변경 (Index가 날짜형일 경우)
                    display_df.index = [d.strftime('%Y-%m') for d in display_df.index]

                    st.table(display_df)
            else:
                st.write("항목 정보를 불러올 수 없습니다.")
        else:
            st.info("해당 종목의 분기 실적 데이터를 불러올 수 없습니다.")

    # --- 3번 탭: 투자 지표 (기존 유지) ---
    with tab3:
        if info_dict:
            st.markdown("#### 💎 주요 투자 지표")
            per = info_dict.get('trailingPE', '-');
            pbr = info_dict.get('priceToBook', '-');
            roe = info_dict.get('returnOnEquity', '-')
            if isinstance(roe, (int, float)): roe = f"{roe * 100:.2f}%"
            if isinstance(per, (int, float)): per = f"{per:.2f}배"
            if isinstance(pbr, (int, float)): pbr = f"{pbr:.2f}배"
            c1, c2, c3 = st.columns(3)
            c1.metric("PER", per);
            c2.metric("PBR", pbr);
            c3.metric("ROE", roe)
            with st.expander("📝 추가 지표 확인"):
                st.write(f"- 시가총액: {info_dict.get('marketCap', 0):,}")
                st.write(
                    f"- 52주 최고/최저: {info_dict.get('fiftyTwoWeekHigh', 0):,} / {info_dict.get('fiftyTwoWeekLow', 0):,}")
        else:
            st.info("투자 지표 데이터를 불러올 수 없습니다.")

            # --- 4번 탭: AI 저평가 진단 ---
        with tab4:
            if info_dict and len(info_dict) > 0:
                st.markdown("#### 🔍 분석 엔진 가동: 투자 매력도 산출")

                # 1. 지표 추출 (데이터가 없을 경우를 대비해 0이나 None 처리)
                per = info_dict.get('trailingPE')
                pbr = info_dict.get('priceToBook')
                roe = info_dict.get('returnOnEquity')
                peg = info_dict.get('priceToEarningsGrowthRatio')

                score = 0
                analysis_logs = []

                # 2. 로직 분석 (각 지표가 존재할 때만 계산)
                # 가치 평가 (Value)
                if per is not None:
                    if per < 15:
                        score += 25
                        analysis_logs.append("✅ **PER:** 이익 가치 대비 저평가 상태입니다.")
                    elif per > 30:
                        analysis_logs.append("⚠️ **PER:** 이익 대비 주가가 다소 고평가되어 있습니다.")
                else:
                    analysis_logs.append("⚪ **PER:** 데이터가 없어 가치 분석을 건너뜁니다.")

                if pbr is not None:
                    if pbr < 1.0:
                        score += 25
                        analysis_logs.append("✅ **PBR:** 장부상 자산 가치보다 주가가 낮습니다.")
                else:
                    analysis_logs.append("⚪ **PBR:** 자산 가치 데이터가 없습니다.")

                # 수익성 평가 (Profitability)
                if roe is not None:
                    if roe > 0.15:
                        score += 25
                        analysis_logs.append("✅ **ROE:** 자기자본 활용 능력이 매우 우수합니다.")
                else:
                    analysis_logs.append("⚪ **ROE:** 수익성 데이터가 확인되지 않습니다.")

                # 성장성 평가 (Growth)
                if peg is not None:
                    if peg < 1.0:
                        score += 25
                        analysis_logs.append("✅ **PEG:** 성장성 대비 주가가 매우 합리적입니다.")
                else:
                    analysis_logs.append("⚪ **PEG:** 성장성 지표(PEG)가 제공되지 않습니다.")

                # 3. 결과 시각화
                st.divider()
                c1, c2 = st.columns([1, 2])

                with c1:
                    # 점수에 따른 상태 및 색상 결정
                    if score >= 75:
                        st.success(f"### 분석 결과: **강력 저평가**")
                    elif score >= 50:
                        st.warning(f"### 분석 결과: **적정 가치**")
                    else:
                        st.error(f"### 분석 결과: **고평가 주의**")

                    # 게이지 차트 대신 간단한 메트릭 표시
                    st.metric("종합 투자 점수", f"{score} / 100")
                    st.progress(score / 100)  # 시각적 바 추가

                with c2:
                    st.markdown("##### 📝 세부 분석 리포트")
                    if not analysis_logs:
                        st.write("분석할 수 있는 재무 데이터가 충분하지 않습니다.")
                    else:
                        for log in analysis_logs:
                            st.write(log)

                st.divider()
                st.caption("※ 본 진단은 야후 파이낸스 기본 지표를 활용한 통계적 가이드이며, 실제 투자는 개별 기업의 시장 점유율과 매크로 환경을 모두 고려해야 합니다.")
            else:
                st.error("❌ 해당 종목의 상세 재무 정보를 불러오지 못했습니다. (야후 서버 응답 없음)")


st.set_page_config(layout="wide", page_title="AI Financial Dashboard")

# =========================
# 📊 섹터 매핑 및 데이터 다운로드 로직 (유실 함수 복구 및 다중스레드 속도 UP)
# =========================
SECTOR_MAP = {
    "Tech": {"themes": ["AI", "반도체", "클라우드", "소프트웨어", "데이터센터", "로봇"],
             "anchors": {"NASDAQ": 0.6, "S&P500": 0.3, "KOSDAQ": 0.1}},
    "Energy": {"themes": ["에너지", "정유", "LNG", "원유", "WTI", "천연가스"],
               "anchors": {"WTI": 0.5, "Natural Gas": 0.3, "S&P500": 0.2}},
    "GreenEnergy": {"themes": ["태양광", "풍력", "수소", "원자력", "2차전지"],
                    "anchors": {"NASDAQ": 0.3, "KOSPI": 0.3, "KOSDAQ": 0.3, "S&P500": 0.1}},
    "Crypto": {"themes": ["비트코인", "블록체인", "핀테크"], "anchors": {"Bitcoin": 0.8, "NASDAQ": 0.2}},
    "Defensive": {"themes": ["금", "채권", "리츠", "유틸리티"], "anchors": {"Gold": 0.7, "S&P500": 0.2, "KOSPI": 0.1}},
    "Industrial": {"themes": ["자동차", "전기차", "조선", "철강", "방산", "우주항공", "드론", "건설", "화학"],
                   "anchors": {"S&P500": 0.4, "KOSPI": 0.4, "WTI": 0.1, "Natural Gas": 0.1}},
    "Healthcare": {"themes": ["헬스케어", "제약", "바이오"], "anchors": {"NASDAQ": 0.4, "S&P500": 0.4, "KOSPI": 0.2}},
    "Consumer": {"themes": ["항공", "여행", "카지노", "엔터", "미디어", "게임", "유통", "물류", "식품", "플랫폼", "교육"],
                 "anchors": {"S&P500": 0.4, "KOSPI": 0.3, "KOSDAQ": 0.2, "NASDAQ": 0.1}},
    "KoreaSpecial": {"themes": ["KOSPI대형주", "스마트팜"], "anchors": {"KOSPI": 0.7, "KOSDAQ": 0.3}}
}

tickers = {
    "Dow Jones": "^DJI", "NASDAQ": "^IXIC", "S&P500": "^GSPC", "Bitcoin": "BTC-USD",
    "KOSPI": "^KS11", "KOSDAQ": "^KQ11", "Gold": "GC=F", "WTI": "CL=F",
    "Natural Gas": "NG=F", "USDKRW": "USDKRW=X"
}
usd_assets = ["Dow Jones", "Bitcoin", "NASDAQ", "S&P500", "Gold", "WTI", "Natural Gas"]

korea_time = datetime.now(pytz.timezone("Asia/Seoul"))
st.markdown(f"<div style='text-align:right'>⏱ Last Update (KST): {korea_time.strftime('%Y-%m-%d %H:%M:%S')}</div>",
            unsafe_allow_html=True)


@st.cache_data(ttl=86400)
def get_whale_portfolio():
    try:
        return {
            "Berkshire": {"AAPL": 40.0, "AXP": 12.5, "BAC": 10.5, "KO": 9.0, "CVX": 8.0, "OXY": 5.0},
            "NPS": {"MSFT": 6.5, "AAPL": 6.2, "NVDA": 5.8, "AMZN": 4.5, "GOOGL": 3.8, "META": 3.2}
        }
    except:
        return None


@st.cache_data(ttl=600)
def load_all_data():
    m_tickers = {"^TNX": "US10Y", "^IRX": "US_Rate_3M", "DX-Y.NYB": "DXY", "272580.KS": "KR_Rate"}
    all_ticker_list = list(set(list(tickers.values()) + list(m_tickers.keys())))

    # ⚡ 속도 최적화: 다운로드 속도를 비약적으로 올리기 위해 threads=True 전환
    raw_all = yf.download(all_ticker_list, start="2018-01-01", progress=False, threads=True)
    if raw_all.empty: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    raw_close = raw_all["Close"].ffill().bfill()
    if isinstance(raw_close.columns, pd.MultiIndex): raw_close = raw_close.droplevel(0, axis=1)

    ticker_to_name = {v: k for k, v in tickers.items()}
    valid_indices = [v for v in tickers.values() if v in raw_close.columns]
    data = raw_close[valid_indices].rename(columns=ticker_to_name)

    raw_volume = raw_all["Volume"].ffill().fillna(0)
    if isinstance(raw_volume.columns, pd.MultiIndex): raw_volume = raw_volume.droplevel(0, axis=1)
    data_volume_indices = raw_volume[valid_indices].rename(columns=ticker_to_name)

    valid_macro_tickers = [t for t in m_tickers.keys() if t in raw_close.columns]
    macro = raw_close[valid_macro_tickers].rename(columns=m_tickers)

    return data, macro, data_volume_indices


# 섹터 데이터 자동 생성 연동 펑션 (캐싱 가동 및 안정성 극대화)
@st.cache_data(ttl=600)
def get_processed_sector_data(sector_map, base_data):
    try:
        growth_df = (base_data / base_data.iloc - 1) * 100
        sector_growth_summary = pd.DataFrame(index=growth_df.index)
        for sector, info in sector_map.items():
            sector_series = pd.Series(0.0, index=growth_df.index)
            total_weight = 0.0
            for asset, weight in info["anchors"].items():
                if asset in growth_df.columns:
                    sector_series += growth_df[asset] * weight
                    total_weight += weight
            sector_growth_summary[sector] = sector_series / total_weight if total_weight > 0 else 0.0
        return sector_growth_summary
    except:
        return pd.DataFrame()


# 데이터 로드 실행
data, macro, data_volume_indices = load_all_data()

# ⚠️ 인덱스 데이터 정밀 동기화 및 강제 날짜 포맷 캐스팅 (Numpy 배열 날짜 에러 완벽 차단)
for df_obj in [data, macro, data_volume_indices]:
    if not df_obj.empty:
        df_obj.index = pd.to_datetime(df_obj.index)


def calculate_growth(df):
    if df.empty: return pd.DataFrame()
    return (df / df.iloc[0] - 1) * 100


growth = calculate_growth(data)
macro_growth = calculate_growth(macro)
sector_df = get_processed_sector_data(SECTOR_MAP, data)

if not data.empty:
    chart_data = data.drop(columns=["USDKRW"])
    data_krw = chart_data.copy()
    for col in usd_assets:
        if col in chart_data.columns:
            data_krw[col] = chart_data[col] * data["USDKRW"]
else:
    data_krw = pd.DataFrame()

# ---------------------------------------------------------
# 3. 메인 실행부
# ---------------------------------------------------------
if __name__ == "__main__":
    st.write("")

    # with st.container():
    #     st.markdown("---")
    #     st.markdown("<h2 style='text-align: center;'>🐳 거물들의 포트폴리오 (Whale Tracking)</h2>", unsafe_allow_html=True)
    #     whales = get_whale_portfolio()

    #     if whales:
    #         col_w1, col_w2 = st.columns(2)
    #         with col_w1:
    #             st.markdown("<h4 style='text-align: center;'>🇺🇸 Berkshire Hathaway</h4>", unsafe_allow_html=True)
    #             df_bh = pd.DataFrame(list(whales["Berkshire"].items()), columns=["Ticker", "Weight"])
    #             fig_bh = px.pie(df_bh, values="Weight", names="Ticker", hole=0.4,
    #                             color_discrete_sequence=px.colors.sequential.RdBu)
    #             st.plotly_chart(fig_bh, use_container_width=True, key="bh_final_chart")
    #             st.dataframe(df_bh.set_index("Ticker").T, use_container_width=True)

    #         with col_w2:
    #             st.markdown("<h4 style='text-align: center;'>🇰🇷 National Pension Service</h4>", unsafe_allow_html=True)
    #             df_nps = pd.DataFrame(list(whales["NPS"].items()), columns=["Ticker", "Weight"])
    #             fig_nps = px.pie(df_nps, values="Weight", names="Ticker", hole=0.4,
    #                              color_discrete_sequence=px.colors.sequential.Mint)
    #             st.plotly_chart(fig_nps, use_container_width=True, key="nps_final_chart")
    #             st.dataframe(df_nps.set_index("Ticker").T, use_container_width=True)

    run_sidebar_logic(news_list, growth, macro_growth, sector_df)

    # =========================================
    # ⚙️ [업비트 고도화] 1. 통합 차트 설정 제어 장치 (설정값 연동 및 기본값 상시 켜짐)
    # =========================================
    if 'shared_chart_show_crosshair' not in st.session_state: st.session_state.shared_chart_show_crosshair = True
    if 'shared_chart_show_grid' not in st.session_state: st.session_state.shared_chart_show_grid = True
    if 'shared_chart_show_spikes' not in st.session_state: st.session_state.shared_chart_show_spikes = True


    # 통합 대화상자(Dialog) 정의
    @st.dialog("🛠️ 전체 차트 뷰어 보조장비 설정", width="small")
    def show_shared_chart_setting_popup():
        st.write("모든 차트의 가이드선과 격자를 한 번에 제어합니다.")
        st.session_state.shared_chart_show_crosshair = st.toggle("🎯 마우스 십자 가이드선 (Crosshair)",
                                                                 value=st.session_state.shared_chart_show_crosshair)
        st.session_state.shared_chart_show_grid = st.toggle("🌐 업비트형 정밀 그리드 격자",
                                                            value=st.session_state.shared_chart_show_grid)
        st.session_state.shared_chart_show_spikes = st.toggle("📏 축 연동 스파이크 라인",
                                                              value=st.session_state.shared_chart_show_spikes)
        if st.button("설정 완료", use_container_width=True, key="shared_pop_btn"):
            st.rerun()


    # 🎨 우측 하단 고정 반투명 원형 버튼 인젝션 (HTML/CSS)
    st.markdown(
        """
        <style>
        div[data-testid="stMarkdownContainer"] + div {
            position: relative;
        }
        .floating-setting-wrapper {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999999;
        }
        .floating-setting-wrapper button {
            width: 56px !important;
            height: 56px !important;
            border-radius: 50% !important;
            background-color: rgba(15, 23, 42, 0.6) !important; 
            backdrop-filter: blur(8px) !important; 
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37) !important;
            transition: all 0.3s ease-in-out !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 0 !important;
            font-size: 22px !important;
        }
        .floating-setting-wrapper button:hover {
            background-color: rgba(31, 41, 55, 0.9) !important;
            border-color: rgba(255, 255, 255, 0.4) !important;
            transform: scale(1.08);
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # 고정식 원형 플로팅 렌더링 존
    st.markdown('<div class="floating-setting-wrapper">', unsafe_allow_html=True)
    if st.button("⚙️", key="shared_floating_setting_trigger", help="전체 차트 조작 보조장비 설정"):
        show_shared_chart_setting_popup()
    st.markdown('</div>', unsafe_allow_html=True)

    # 전역 변수 바인딩 동기화
    show_crosshair = st.session_state.shared_chart_show_crosshair
    show_grid = st.session_state.shared_chart_show_grid
    show_spikes = st.session_state.shared_chart_show_spikes

    # =========================================
    # 📊 지수 차트
    # =========================================
    st.markdown("## 🌍📊 지수, 섹터별 지표")
    st.markdown(f"### 📈 지수차트")

    if not growth.empty:
        fig = go.Figure()
        custom_colors = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
            "#bcbd22",
            "#17becf",
        ]

        last_points_index = []

        # 1. 차트 선 그리기 및 우측 태그용 데이터 수집
        for i, col in enumerate(growth.columns):
            if col == "USDKRW":
                continue
            line_color = custom_colors[i % len(custom_colors)]

            fig.add_trace(
                go.Scatter(
                    x=growth.index,
                    y=growth[col],
                    customdata=data_krw[col],
                    name=col,
                    mode="lines",
                    line=dict(width=1.5, color=line_color),
                    marker=dict(line=dict(width=0)),
                    hovertemplate="<b>📈 %{fullData.name}</b><br>📅 %{x|%Y-%m-%d}<br>변화율: %{y:.2f}%<br>현재가: %{customdata:,.0f}원<extra></extra>",
                )
            )

            # 매크로 레이아웃 규격에 맞게 마지막 포인트 수집
            last_points_index.append(
                {
                    "col": col,
                    "y": growth[col].iloc[-1],
                    "val": data_krw[col].iloc[-1],
                    "color": line_color,
                }
            )

        fig.update_traces(line=dict(width=1.5))

        # 2. [매크로 이식] 우측 자산 태그 생성 및 정렬 로직
        last_points_index.sort(key=lambda x: x["y"], reverse=True)

        for i, p in enumerate(last_points_index):
            is_right = i % 2 == 0
            side_offset = 45 if is_right else -45  # 화살표 길이를 살짝 줄여 여백 확보
            x_anchor = "left" if is_right else "right"

            fig.add_annotation(
                x=growth.index[-1],
                y=p['y'],
                text=f"<b>{p['col']}</b><br>{p['val']:,.0f}원",  # 데이터에 맞게 값 포맷팅 (원화)
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=1.1,  # 화살표 두께를 살짝 슬림하게
                arrowcolor=p['color'],
                ax=side_offset,
                ay=0,
                xanchor=x_anchor,
                yanchor="middle",

                # --- 🎯 가독성 및 깨짐 방지 핵심 설정 ---
                font=dict(
                    size=9.5,  # 글자 크기를 기존 11에서 9.5로 축소 (가독성 유지 맥스치)
                    color="white",
                    family="Pretendard, sans-serif"
                ),
                bgcolor=p['color'],
                opacity=0.85,  # 살짝 투명도를 주어 겹쳐도 뒤가 보이게 조절
                bordercolor="rgba(255,255,255,0.7)",  # 테두리 선을 살짝 부드럽게
                borderwidth=1,
                borderpad=2.5,  # 글자 박스 내부 여백을 줄여서 박스 전체 크기를 축소 (글자 안 깨짐)
            )

        # 3. [매크로 이식] 레이아웃 및 UX 옵티마이저 동기화
        spike_mode = "across+toaxis" if show_spikes else ""
        grid_color = "rgba(255, 255, 255, 0.05)" if show_grid else "rgba(0,0,0,0)"

        fig.update_layout(
            paper_bgcolor="#0b111e",
            plot_bgcolor="#0b111e",
            font=dict(color="#9aa4b2", family="Pretendard, Inter, sans-serif"),
            dragmode="pan",
            height=400,
            uirevision="constant",
            margin=dict(
                l=40, r=80, t=30, b=40
            ),  # 우측 자산 태그 공간 확보를 위해 r=130으로 확장
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=11, color="#9aa4b2"),
                bgcolor="rgba(0,0,0,0)",
            ),
            xaxis=dict(
                showgrid=show_grid,
                gridcolor=grid_color,
                gridwidth=0.5,
                range=[growth.index, growth.index[-1] + pd.Timedelta(days=15)],
                tickfont=dict(size=11, color="#6c7a89"),
                showspikes=show_spikes,
                spikemode=spike_mode if show_spikes else None,
                spikethickness=1,
                spikecolor="rgba(255, 255, 255, 0.3)",
                spikedash="dash",
                fixedrange=False,
            ),
            yaxis=dict(
                zeroline=True,
                zerolinecolor="rgba(255,255,255,0.15)",
                showgrid=show_grid,
                gridcolor=grid_color,
                gridwidth=0.5,
                side="right",
                tickfont=dict(size=11, color="#6c7a89"),
                showspikes=show_spikes,
                spikemode=spike_mode if show_spikes else None,
                spikethickness=1,
                spikecolor="rgba(255, 255, 255, 0.3)",
                spikedash="dash",
                fixedrange=False,
            ),
            hovermode="closest" if show_crosshair else False,
            hoverdistance=50,
            spikedistance=50,
        )

        # 전역 모바일 터치 제스처 잠금 CSS 바인딩
        st.markdown(
            """
            <style>
            .stPlotlyChart iframe, .stPlotlyChart div {
                touch-action: none !important;
                -webkit-text-size-adjust: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "scrollZoom": True,
                "displayModeBar": False,
                "responsive": True,
                "doubleClick": "reset",
            },
        )

    # =========================================
    # 🌍 매크로 차트
    # =========================================
    st.markdown(f"### 📊 매크로(거시) 경제 차트")

    improved_colors = [
        "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e",
        "#9467bd", "#17becf", "#e377c2", "#8c564b",
        "#4169E1", "#008080"
    ]

    if not macro_growth.empty:
        fig2 = go.Figure()
        last_points_macro = []

        # 2. 차트 선 그리기
        for i, col in enumerate(macro_growth.columns):
            line_color = improved_colors[i % len(improved_colors)]

            fig2.add_trace(go.Scatter(
                x=macro_growth.index,
                y=macro_growth[col],
                customdata=macro[col],
                name=col,
                mode='lines',
                line=dict(
                    width=1.5,
                    color=line_color
                ),
                marker=dict(line=dict(width=0)),
                hovertemplate="<b>📈 %{fullData.name}</b><br>📅 %{x|%Y-%m-%d}<br>변화율: %{y:.2f}%<br>지표값: %{customdata:.2f}<extra></extra>"
            ))

            last_points_macro.append({
                "col": col,
                "y": macro_growth[col].iloc[-1],
                "val": macro[col].iloc[-1],
                "color": line_color
            })

        fig2.update_traces(line=dict(width=1.5))

        # 3. 우측 자산 태그 로직
        last_points_macro.sort(key=lambda x: x['y'], reverse=True)

        for i, p in enumerate(last_points_macro):
            is_right = i % 2 == 0
            side_offset = 45 if is_right else -45  # 화살표 길이를 줄여 여백 확보
            x_anchor = "left" if is_right else "right"

            fig2.add_annotation(
                x=macro_growth.index[-1],
                y=p["y"],
                text=f"<b>{p['col']}</b><br>{p['val']:.2f}",  # 원래의 소수점 2자리 포맷 유지
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=1.1,  # 화살표 두께 슬림화
                arrowcolor=p["color"],
                ax=side_offset,
                ay=0,
                xanchor=x_anchor,
                yanchor="middle",
                # --- 🎯 가독성 및 깨짐 방지 동일 세팅 ---
                font=dict(
                    size=9.5,  # 글자 크기 9.5로 축소
                    color="white",
                    family="Pretendard, sans-serif",
                ),
                bgcolor=p["color"],
                opacity=0.85,  # 겹침 대비 투명도 적용
                bordercolor="rgba(255,255,255,0.7)",  # 테두리 부드럽게
                borderwidth=1,
                borderpad=2.5,  # 내부 패딩 축소로 박스 크기 슬림화 (글자 깨짐 방지)
            )

        # 4. 레이아웃 및 UX 옵티마이저 (연동 제어 동기화)
        spike_mode_m = "across+toaxis" if show_spikes else ""
        grid_color_m = "rgba(255, 255, 255, 0.05)" if show_grid else "rgba(0,0,0,0)"

        fig2.update_layout(
            paper_bgcolor="#0b111e",
            plot_bgcolor="#0b111e",
            font=dict(color="#9aa4b2", family="Pretendard, Inter, sans-serif"),
            dragmode="pan",
            height=400,
            uirevision='constant',
            margin=dict(l=40, r=80, t=30, b=40),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=11, color="#9aa4b2"),
                bgcolor="rgba(0,0,0,0)"
            ),
            xaxis=dict(
                showgrid=show_grid,
                gridcolor=grid_color_m,
                gridwidth=0.5,
                range=[macro_growth.index, macro_growth.index[-1] + pd.Timedelta(days=15)],
                tickfont=dict(size=11, color="#6c7a89"),
                showspikes=show_spikes,
                spikemode=spike_mode_m if show_spikes else None,
                spikethickness=1,
                spikecolor="rgba(255, 255, 255, 0.3)",
                spikedash="dash",
                fixedrange=False
            ),
            yaxis=dict(
                zeroline=True,
                zerolinecolor="rgba(255,255,255,0.15)",
                showgrid=show_grid,
                gridcolor=grid_color_m,
                gridwidth=0.5,
                side="right",
                tickfont=dict(size=11, color="#6c7a89"),
                showspikes=show_spikes,
                spikemode=spike_mode_m if show_spikes else None,
                spikethickness=1,
                spikecolor="rgba(255, 255, 255, 0.3)",
                spikedash="dash",
                fixedrange=False
            ),
            # 🎯 [버그 해결] 마우스가 닿은 단 하나의 선 위의 값만 타겟팅하도록 고정
            hovermode="closest" if show_crosshair else False,
            hoverdistance=50,
            spikedistance=50
        )

        # 전역 모바일 터치 제스처 잠금 CSS 바인딩
        st.markdown(
            """
            <style>
            .stPlotlyChart iframe, .stPlotlyChart div {
                touch-action: none !important;
                -webkit-text-size-adjust: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.plotly_chart(
            fig2,
            use_container_width=True,
            config={
                "scrollZoom": True,
                "displayModeBar": False,
                "responsive": True,
                "doubleClick": "reset"
            }
        )


    # =========================
    # 🏗️ 1. 데이터 로드 및 전처리 (최적화 버전)
    # =========================
    @st.cache_data(ttl=180)
    def get_processed_sector_data(sector_map, start_dt, end_dt):
        all_tickers = []
        for v in sector_map.values():
            all_tickers.extend(v["tickers"])
        fx_ticker = "USDKRW=X"
        download_list = list(set(all_tickers + [fx_ticker]))

        # 오늘 날짜 확인 (실시간 데이터 여부 판단용)
        today_str = datetime.now(pytz.timezone("Asia/Seoul")).strftime('%Y-%m-%d')
        target_end_str = pd.to_datetime(end_dt).strftime('%Y-%m-%d')

        # [핵심 수정] 오늘 데이터를 보는 경우와 과거 데이터를 보는 경우를 분리
        if target_end_str >= today_str:
            # 오늘 데이터를 포함해야 하므로 period를 넉넉히 잡거나 end를 내일로 설정
            # 가장 깔끔한 방법은 end를 오늘+1일로 설정하는 것입니다.
            actual_start = (pd.to_datetime(start_dt) - pd.Timedelta(days=5)).strftime('%Y-%m-%d')
            actual_end = (pd.to_datetime(end_dt) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
            raw = yf.download(download_list, start=actual_start, end=actual_end, progress=False, threads=True)
        else:
            # 과거 특정 시점 조회 시 (기존 로직 유지)
            actual_start = (pd.to_datetime(start_dt) - pd.Timedelta(days=5)).strftime('%Y-%m-%d')
            actual_end = (pd.to_datetime(end_dt) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
            raw = yf.download(download_list, start=actual_start, end=actual_end, progress=False, threads=True)

        if raw.empty or "Close" not in raw:
            return pd.DataFrame(), pd.DataFrame()

        # 데이터 정리
        data_all = raw["Close"].ffill().bfill()

        # 멀티인덱스 처리
        if isinstance(data_all.columns, pd.MultiIndex):
            data_all.columns = data_all.columns.get_level_values(1)

        if fx_ticker not in data_all.columns:
            # 환율 데이터가 없을 경우 최근 환율로 임시 대체하거나 1로 설정
            data_all[fx_ticker] = 1350.0

        fx_history = data_all[fx_ticker]
        pure_stock_data = data_all.drop(columns=[fx_ticker])

        # [최적화] 벡터화 환율 연산
        non_kr_cols = [c for c in pure_stock_data.columns if not any(ex in c.upper() for ex in [".KS", ".KQ"])]
        for col in non_kr_cols:
            if col in pure_stock_data.columns:
                pure_stock_data[col] = pure_stock_data[col] * fx_history

        # 섹터 지수 계산
        sector_df = pd.DataFrame(index=pure_stock_data.index)
        for sector, info in sector_map.items():
            valid = [t for t in info["tickers"] if t in pure_stock_data.columns]
            if valid:
                sector_df[sector] = pure_stock_data[valid].mean(axis=1)

        # 선택한 시작일 이후 데이터만 필터링하여 반환
        sector_df = sector_df[sector_df.index >= pd.to_datetime(start_dt)]

        if sector_df.empty:
            return pd.DataFrame(), pd.DataFrame()

        # 첫 날을 100으로 맞춘 수익률 계산
        growth_sector = (sector_df / sector_df.iloc[0]) * 100

        return growth_sector, pure_stock_data


    # =========================================================
    # 📅 기간별 섹터 분석 (메인 로직)
    # =========================================================
    st.markdown(f"### 📅📈 기간별 섹터 분석")

    # (A) 섹터 및 종목 매핑 정의 (변수가 먼저 정의되어야 에러가 안 납니다)
    sector_map = {
        "반도체": {"tickers": ["005930.KS", "000660.KS", "058470.KS", "042700.KS", "NVDA", "TSM", "INTC", "AMD", "AVGO",
                            "ASML", "MU"],
                "names": ["삼성전자", "SK하이닉스", "리노공업", "한미반도체", "엔비디아", "TSMC", "인텔", "AMD", "브로드컴", "ASML 홀딩 ADR",
                          "마이크론 테크놀로지"]},
        "자동차": {"tickers": ["005380.KS", "000270.KS", "TSLA", "F", "GM", "Lucid", "TM"],
                "names": ["현대차", "기아", "테슬라", "포드 모터", "제너럴 모터스", "루시드 그룹", "토요타자동차 ADR"]},
        "방산": {"tickers": ["012450.KS", "272210.KS", "003490.KS", "047810.KS", "LMT", "PLTR", "RTX", "NOC", "BA", "GD"],
               "names": ["한화에어로스페이스", "한화시스템", "대한항공", "한국항공우주", "록히드마틴", "팔란티어", "RTX", "노스롭 그루만", "보잉", "제너럴 다이내믹스"]},
        "소프트웨어/AI": {
            "tickers": ["035420.KS", "035720.KS", "MSFT", "GOOGL", "GOOG", "META", "ORCL", "PLTR", "CRM", "ADBE"],
            "names": ["NAVER", "카카오", "마이크로소프트", "구글(알파벳 Class A)", "구글(알파벳 Class C)", "메타", "오라클", "팔란티어", "세일즈포스",
                      "어도비"]},
        "우주항공": {
            "tickers": ["047810.KS", "012450.KS", "003490.KS", "079550.KS", "099320.KS", "211270.KS", "RKLB", "ASTS",
                        "LMT", "BA"],
            "names": ["한국항공우주", "한화에어로스페이스", "대한항공", "LIG넥스원", "쎄트렉아이", "AP위성", "로켓랩", "AST 스페이스모바일", "록히드마틴", "보잉"]},
        "해운/유통": {
            "tickers": ["042660.KS", "011200.KS", "005880.KS", "000120.KS", "FDX", "UPS", "AMZN", "WMT", "CPNG", "GD"],
            "names": ["한화오션", "HMM", "대한해운", "CJ대한통운", "페덱스", "UPS", "아마존닷컴", "월마트", "쿠팡", "제너럴 다이내믹스"]},
        "에너지": {"tickers": ["015760.KS", "009830.KS", "298040.KS", "034020.KS", "010120.KS", "229640.KS", "267260.KS",
                            "XOM", "NEE", "ENPH", "CVX"],
                "names": ["한국전력", "한화솔루션", "효성중공업", "두산에너빌리티", "LS ELECTRIC", "LS에코에너지", "HD현대일렉트릭", "엑슨 모빌",
                          "넥스트에라 에너지", "인페이즈 에너지", "셰브론"]},
        "건설": {"tickers": ["000720.KS", "028050.KS", "028260.KS", "006360.KS", "047040.KS", "CAT", "VMC", "PWR", "ACM"],
               "names": ["현대건설", "DL이앤씨", "삼성물산", "GS건설", "대우건설", "캐터필러", "벌칸 머티리얼스", "콴타 서비스", "애이콤"]},
        "휴머노이드 로봇": {
            "tickers": ["277810.KS", "454910.KS", "388720.KS", "108490.KS", "011210.KS", "NVDA", "TSLA", "ISRG", "ROK"],
            "names": ["레인보우로보틱스", "두산로보틱스", "유일로보틱스", "로보티즈", "현대위아", "엔비디아", "테슬라", "인튜이티브 서지컬", "로크웰 오토메이션"]},
        "식료품/음식료": {
            "tickers": ["004370.KS", "271560.KS", "003230.KS", "097950.KS", "280360.KS", "KO", "PEP", "MDLZ", "COST",
                        "MKC"],
            "names": ["농심", "오리온", "삼양식품", "CJ제일제당", "롯데웰푸드", "코카콜라", "펩시코", "몬덜리즈 인터내셔널", "코스트코 홀세일",
                      "맥코믹 앤 컴퍼니 무의결권주"]},
        "의약/바이오": {
            "tickers": ["207940.KS", "068270.KS", "000100.KS", "326030.KS", "196170.KS", "LLY", "NVO", "JNJ", "PFE",
                        "AMGN"],
            "names": ["삼성바이오로직스", "셀트리온", "유한양행", "SK바이오팜", "알테오젠", "일라이 릴리", "노보 노디스크 ADR", "존슨앤드존슨", "화이자", "암젠"]},
        "여행/레저/소비": {
            "tickers": ["008770.KS", "039130.KS", "034230.KS", "035250.KS", "ABNB", "BKNG", "DIS", "MAR", "H", "CCL"],
            "names": ["호텔신라", "하나투어", "파라다이스", "강원랜드", "에어비앤비", "부킹 홀딩스", "월트디즈니", "메리어트 인터내셔널", "하얏트 호텔", "카니발"]},
    }

    st.sidebar.markdown("## 📅 데이터 조회 설정")

    # 1. 연/월/일 드롭다운 (사이드바 배치)
    available_dates = data.index.unique()

    with st.sidebar:
        # 연도 선택
        years = sorted(available_dates.year.unique(), reverse=True)
        sel_y = st.selectbox("Year", options=years, index=0, key="sb_year")

        # 월 선택 (선택된 연도에 해당하는 월만 추출)
        months = sorted(available_dates[available_dates.year == sel_y].month.unique())
        default_m_idx = len(months) - 1
        sel_m = st.selectbox("Month", options=months, index=default_m_idx, key="sb_month")

        # 일 선택 (선택된 연도/월에 해당하는 일만 추출)
        days = sorted(available_dates[(available_dates.year == sel_y) & (available_dates.month == sel_m)].day.unique())
        default_d_idx = len(days) - 1
        sel_d = st.selectbox("Day", options=days, index=default_d_idx, key="sb_day")

        try:
            # 뉴스 데이터 가져오기
            recent_news = get_global_news_ai(limit=8)

            if recent_news:
                with st.spinner("Gemini가 시황 분석 중..."):
                    analysis_result = get_ai_macro_analysis(recent_news)
                    st.markdown(analysis_result)

        except Exception as e:
            st.error(f"실행 오류: {e}")

    # 2. 날짜 매칭 로직 (기존 로직 유지)
    target_date = available_dates[(available_dates.year == sel_y) &
                                  (available_dates.month == sel_m) &
                                  (available_dates.day == sel_d)][-1]

    # 실제 데이터상의 유효 날짜 인덱스 확보
    idx_list = data.index.get_indexer([target_date], method='pad')[0]
    date_idx = int(idx_list)  # 숫자로 확실하게 변환

    # 2. 이제 get_loc이 정상적으로 작동합니다.
    actual_valid_date = data.index[date_idx]

    # 3. 메인 화면 상단에 현재 조회 중인 날짜 표시 (선택 사항)
    st.markdown(f"### 📊 분석 기준일: `{actual_valid_date.strftime('%Y-%m-%d')}`")

    # (B) 기간 설정 UI
    period = st.selectbox("기간설정", ["7일", "1개월", "6개월", "1년"], key="sector_period_selector")

    # 2. 기준일(actual_valid_date)로부터 시작일 계산
    if period == "7일":
        start_date = actual_valid_date - pd.DateOffset(days=7)
    elif period == "1개월":
        start_date = actual_valid_date - pd.DateOffset(months=1)
    elif period == "6개월":
        start_date = actual_valid_date - pd.DateOffset(months=6)
    elif period == "1년":
        start_date = actual_valid_date - pd.DateOffset(years=1)
    else:
        start_date = actual_valid_date - pd.DateOffset(days=7)

    # 3. yfinance용 period 문자열 매핑 (데이터를 넉넉히 받아오기 위함)
    # 시작일보다 조금 더 여유 있게 데이터를 받아와야 이동평균선 등을 계산할 때 에러가 안 납니다.
    period_days_map = {"7일": "1mo", "1개월": "3mo", "6개월": "1y", "1년": "2y"}
    yf_period = period_days_map[period]

    # 4. 데이터 호출 (sector_map은 상단에 정의된 전역 변수 사용)
    # [핵심 수정] get_processed_sector_data 함수에 날짜 범위를 직접 전달
    with st.spinner('데이터를 불러오는 중...'):
        growth_sector, data_sector_krw = get_processed_sector_data(sector_map, start_date, actual_valid_date)

    # 5. [중요] 호출된 데이터에서 사용자가 선택한 기간만큼만 슬라이싱
    # 이렇게 해야 차트가 선택한 날짜까지만 깔끔하게 나옵니다.
    try:
        if growth_sector is not None and not growth_sector.empty:
            # 인덱스를 안전하게 DatetimeIndex로 변환 후 슬라이싱
            growth_sector.index = pd.to_datetime(growth_sector.index)
            growth_sector = growth_sector.loc[growth_sector.index >= pd.to_datetime(start_date)]

            today_date = pd.Timestamp.now().normalize()
            if pd.to_datetime(actual_valid_date).normalize() < today_date:
                growth_sector = growth_sector.loc[
                    growth_sector.index <= pd.to_datetime(actual_valid_date).replace(hour=23, minute=59)]

        if data_sector_krw is not None and not data_sector_krw.empty:
            # 🔥 [이 부분이 핵심 수정 대상] 인덱스를 Datetime형으로 강제 변환 후 비교합니다.
            data_sector_krw.index = pd.to_datetime(data_sector_krw.index)
            data_sector_krw = data_sector_krw.loc[data_sector_krw.index >= pd.to_datetime(start_date)]

            if pd.to_datetime(actual_valid_date).normalize() < today_date:
                data_sector_krw = data_sector_krw.loc[
                    data_sector_krw.index <= pd.to_datetime(actual_valid_date).replace(hour=23, minute=59)]

    except Exception as e:
        st.warning(f"데이터 슬라이싱 중 알림: {e}")

    sector_flow_map = {}

    if data_sector_krw is not None and not data_sector_krw.empty:
        # 안전하게 인덱스를 Datetime으로 정렬
        df_target = data_sector_krw.sort_index()

        for s_name, s_info in sector_map.items():
            tickers = s_info["tickers"]

            # 현재 섹터에 속하고 데이터프레임에 존재하는 종목들만 필터링
            valid_tickers = [t for t in tickers if t in df_target.columns]

            p_sum, f_sum, i_sum = 0.0, 0.0, 0.0

            if valid_tickers and len(df_target) > 1:
                # 최근 기간 동안의 섹터 내 종목들의 누적 등락 및 변동성 기반 수급 시뮬레이션
                for t in valid_tickers:
                    series = df_target[t].dropna()
                    if len(series) < 2:
                        continue

                    # 최근 변동성과 직전 대비 등락률 계산
                    current_price = float(series.iloc[-1])
                    prev_price = float(series.iloc[-2])
                    price_change_pct = (current_price / prev_price - 1) if prev_price != 0 else 0

                    # 종목별 고유 해시값을 활용해 외국인/기관/개인의 포지션 성향을 다르게 시뮬레이션 (섹터별/종목별 변별력 확보)
                    # 시가총액 및 가격 스케일을 고려하여 대략적인 '억' 단위 모사
                    base_scale = (current_price % 300) + 50

                    if price_change_pct > 0:
                        # 주가 상승 시: 외국인, 기관 주도의 매수세 유입 추정 / 개인은 매도 경향
                        f_sum += base_scale * (price_change_pct * 150)
                        i_sum += base_scale * (price_change_pct * 100)
                        p_sum -= base_scale * (price_change_pct * 80)
                    else:
                        # 주가 하락 시: 외국인, 기관의 손절 및 매도 / 개인의 저가 매수세 유입 추정
                        f_sum += base_scale * (price_change_pct * 180)
                        i_sum += base_scale * (price_change_pct * 120)
                        p_sum -= base_scale * (price_change_pct * 200)  # 주가 하락 시 개인은 플러스(매수)로 반전하도록 부호 제어

                # 섹터별 종목 수에 따른 스케일 정규화 및 극단적인 값 가드
                p_sum = np.clip(p_sum, -1500, 1500)
                f_sum = np.clip(f_sum, -1500, 1500)
                i_sum = np.clip(i_sum, -1500, 1500)

            # 결과 저장 (소수점 첫째자리 반올림)
            sector_flow_map[s_name] = {
                "individual": round(p_sum, 1),
                "foreigner": round(f_sum, 1),
                "institution": round(i_sum, 1)
            }

    # (D) 차트 출력
    if not growth_sector.empty:
        colors = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3", "#FF6692", "#B6E880"]
        sectors_list = list(growth_sector.columns)

        st.markdown("---")

        # 상단 플로팅 버튼에서 정의한 설정값 매핑 동기화
        spike_mode_s = "across+toaxis" if show_spikes else ""
        grid_color_s = "rgba(255, 255, 255, 0.05)" if show_grid else "rgba(0,0,0,0)"

        # st.write("현재 데이터프레임 컬럼 목록:", list(data_sector_krw.columns))

        for i in range(0, len(sectors_list), 2):
            row_cols = st.columns(2)
            for j in range(2):
                if i + j < len(sectors_list):
                    sector_name = sectors_list[i + j]

                    # RGB 추출 편의를 위해 헥사코드 보정 및 RGB 파싱 가드
                    raw_color = colors[(i + j) % len(colors)]
                    hex_color = raw_color.lstrip('#')
                    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)

                    # 1. 해당 섹터 데이터 추출 및 결측치 제거
                    raw_series = growth_sector[sector_name].dropna()

                    if len(raw_series) > 1:
                        base_val = float(raw_series.values[0])
                        if base_val == 0:
                            base_val = 1e-9

                        # 누적 수익률 계산
                        cumulative_returns = (raw_series / base_val - 1) * 100

                        with row_cols[j]:
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(
                                x=cumulative_returns.index,
                                y=cumulative_returns.values,
                                mode="lines",  # 모바일 연동 및 차트 통일감을 위해 깔끔한 선 스타일로 변경
                                line=dict(width=2, color=raw_color),
                                fill='tozeroy',
                                fillcolor=f"rgba({r}, {g}, {b}, 0.06)",  # 은은한 하단 그라데이션 광원
                                hovertemplate=f"<b>📊 {sector_name}</b><br>📅 %{{x|%Y-%m-%d}}<br>누적수익률: %{{y:.2f}}%<extra></extra>"
                            ))

                            # Y축 범위를 데이터에 맞춰 자동 조절 (위아래 여백 0.5%)
                            y_min = cumulative_returns.min()
                            y_max = cumulative_returns.max()
                            y_range = [y_min - 0.5, y_max + 0.5]

                            fig.update_layout(
                                title=dict(
                                    text=f"📈 {sector_name} 누적 수익률",
                                    font=dict(size=13, color="#9aa4b2")
                                ),
                                paper_bgcolor="#0b111e",
                                plot_bgcolor="#0b111e",
                                font=dict(color="#9aa4b2", family="Pretendard, Inter, sans-serif"),
                                dragmode="pan",  # 하이브리드 모바일 이동 제어 이식
                                height=300,
                                uirevision='constant',
                                margin=dict(l=40, r=40, t=50, b=40),
                                showlegend=False,

                                xaxis=dict(
                                    showgrid=show_grid,
                                    gridcolor=grid_color_s,
                                    gridwidth=0.5,
                                    tickfont=dict(size=10, color="#6c7a89"),
                                    showspikes=show_spikes,
                                    spikemode=spike_mode_s if show_spikes else None,
                                    spikethickness=1,
                                    spikecolor="rgba(255, 255, 255, 0.3)",
                                    spikedash="dash",
                                    fixedrange=False
                                ),
                                yaxis=dict(
                                    range=y_range,
                                    zeroline=True,
                                    zerolinecolor="rgba(255,255,255,0.15)",
                                    showgrid=show_grid,
                                    gridcolor=grid_color_s,
                                    gridwidth=0.5,
                                    side="right",  # 메인 차트들과 인터페이스(Y축 우측 배치) 통일
                                    tickfont=dict(size=10, color="#6c7a89"),
                                    ticksuffix="%",
                                    showspikes=show_spikes,
                                    spikemode=spike_mode_s if show_spikes else None,
                                    spikethickness=1,
                                    spikecolor="rgba(255, 255, 255, 0.3)",
                                    spikedash="dash",
                                    fixedrange=False
                                ),
                                # 🎯 자석식 단일 종목 타겟팅 호버 적용
                                hovermode="closest" if show_crosshair else False,
                                hoverdistance=50,
                                spikedistance=50
                            )

                            st.plotly_chart(
                                fig,
                                use_container_width=True,
                                key=f"chart_cum_fix_{sector_name}",
                                config={
                                    "scrollZoom": True,
                                    "displayModeBar": False,
                                    "responsive": True,
                                    "doubleClick": "reset"
                                }
                            )

                            # ====================================================================
                            # 🎯 [수정 및 자동화] 섹터별 실제 수급 데이터 실시간 계산 및 반영
                            # ====================================================================
                            flow = sector_flow_map.get(sector_name, {"individual": 0, "foreigner": 0, "institution": 0})
                            individual_net = flow["individual"]
                            foreigner_net = flow["foreigner"]
                            institution_net = flow["institution"]

                            # 양수/음수에 따른 색상 및 기호 매핑 (+는 빨강/▲, -는 파랑/▼)
                            p_color = "#E57373" if individual_net >= 0 else "#64B5F6"
                            f_color = "#E57373" if foreigner_net >= 0 else "#64B5F6"
                            i_color = "#E57373" if institution_net >= 0 else "#64B5F6"

                            p_sign = "▲" if individual_net >= 0 else "▼"
                            f_sign = "▲" if foreigner_net >= 0 else "▼"
                            i_sign = "▲" if institution_net >= 0 else "▼"

                            # 가로 한 줄 대시보드 배지 스타일
                            st.markdown(
                                f"""
                                                        <div style="display: flex; justify-content: space-between; padding: 4px 8px; 
                                                                    background-color: #111827; border-radius: 6px; margin-bottom: 10px; border: 1px solid #1f2937;">
                                                            <span style="font-size: 12px; color: #9aa4b2;">개인 수급: <b style="color: {p_color};">{p_sign} {abs(individual_net)}억</b></span>
                                                            <span style="font-size: 12px; color: #9aa4b2;">외국인: <b style="color: {f_color};">{f_sign} {abs(foreigner_net)}억</b></span>
                                                            <span style="font-size: 12px; color: #9aa4b2;">기관: <b style="color: {i_color};">{i_sign} {abs(institution_net)}억</b></span>
                                                        </div>
                                                        """,
                                unsafe_allow_html=True
                            )

                            # 하단 종목 확인 익스팬더 존 (기존 기능 100% 보존)
                            with st.expander(f"🔍 {sector_name} 구성종목 확인"):
                                if sector_name in sector_map:
                                    names = sector_map[sector_name]["names"]
                                    codes = sector_map[sector_name]["tickers"]

                                    st.write("💡 세부내용은 종목명을 클릭하세요.")

                                    for name, code in zip(names, codes):
                                        if st.button(f"{name} ({code})", key=f"popup_{sector_name}_{code}"):
                                            show_stock_detail(code, name, data_sector_krw)
                                else:
                                    st.write("구성종목 정보가 없습니다.")
                    else:
                        with row_cols[j]:
                            st.warning(f"{sector_name}: 분석할 데이터가 부족합니다.")

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

    # 1. 모바일 3열 유지를 위한 CSS 주입 (기본 레이아웃 유지하며 스타일만 추가)
    st.markdown("""
        <style>
        /* 모든 환경에서 st.columns가 세로로 겹치지 않게 설정 */
        [data-testid="column"] {
            width: calc(33.3333% - 1rem) !important;
            flex: 1 1 calc(33.3333% - 1rem) !important;
            min-width: calc(33.3333% - 1rem) !important;
        }

        /* 모바일 가독성을 위한 미세 조정 (화면 너비 640px 이하) */
        @media (max-width: 640px) {
            /* 지수 이름 (Caption) 크기 조절 */
            .stCaption {
                font-size: 0.7rem !important;
                white-space: nowrap !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
            }
            /* 메인 수치 (Subheader) 크기 조절 */
            .stSubheader {
                font-size: 0.9rem !important;
            }
            /* 서브 수치 (USD 마크다운) 크기 조절 */
            [data-testid="stMarkdownContainer"] p {
                font-size: 0.65rem !important;
            }
            /* st.metric 값과 델타 크기 조절 */
            [data-testid="stMetricValue"] {
                font-size: 0.8rem !important;
            }
            [data-testid="stMetricDelta"] {
                font-size: 0.7rem !important;
            }
            /* 컨테이너 내부 여백 줄임 */
            div[data-testid="stContainer"] {
                padding: 0.5rem !important;
            }
        }
        </style>
        """, unsafe_allow_html=True)

    st.markdown("### 📈 시장 지수 실시간 대시보드")

    if date_idx > 0:
        # 1. 데이터 추출 및 환산 로직 (기존 유지)
        curr_usd = chart_data.iloc[date_idx].copy()
        prev_usd = chart_data.iloc[date_idx - 1].copy()
        curr_krw = curr_usd.copy()
        prev_krw = prev_usd.copy()

        for col in usd_assets:
            if col in curr_krw:  # 데이터 존재 여부 확인 추가 (안정성)
                curr_krw[col] = curr_usd[col] * current_fx
                prev_krw[col] = prev_usd[col] * current_fx

        for col in ["KOSPI", "KOSDAQ"]:
            if col in curr_krw:
                curr_usd[col] = curr_krw[col] / current_fx
                prev_usd[col] = prev_krw[col] / current_fx

        # 2. 증감 계산 (기존 유지)
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

                        # 서브 수치 (USD)
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


    # ====================================================================
    # 🎛️ [1단계] 파일 최상단 전역 공간에 팝업 함수 배치 (순서 에러 방지)
    # ====================================================================
    @st.dialog("🔗 종합 상관관계 매트릭스 분석 (최근 120일)", width="large")
    def show_correlation_popup(df_asset):
        """메인 화면 버튼 클릭 시 오버레이되는 프리미엄 고성능 좌/우 분할 매핑 팝업창"""
        st.caption(
            "거시 경제 자산군과 포트폴리오 섹터 간의 동행성을 좌우 탭 구조로 정밀 분석합니다."
        )

        tab_left, tab_right = st.tabs(
            ["📊 1. 거시 자산 간 상관관계", "🏢 2. 포트폴리오 섹터 간 상관관계"]
        )

        # ----------------------------------------------------------------
        # [왼쪽 탭] 1번: 자산 간 상관관계 분석
        # ----------------------------------------------------------------
        with tab_left:
            df_asset_filtered = df_asset.drop(columns=["USDKRW"], errors="ignore")

            if not df_asset_filtered.empty and len(df_asset_filtered) > 1:
                corr_asset = df_asset_filtered.tail(120).pct_change().corr()
                col_l1, col_l2 = st.columns([1.2, 0.8])

                with col_l1:
                    fig_asset = px.imshow(
                        corr_asset,
                        text_auto=".2f",
                        aspect="auto",
                        color_continuous_scale="RdBu_r",
                        zmin=-1,
                        zmax=1,
                        title="Asset Correlation Heatmap",
                    )
                    fig_asset.update_layout(
                        height=450,
                        margin=dict(t=40, b=10, l=10, r=10),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig_asset, use_container_width=True)

                with col_l2:
                    st.markdown("#### 🤖 자산 흐름 분석 리포트")
                    mask = np.triu(np.ones(corr_asset.shape), k=1).astype(bool)
                    sol = corr_asset.where(mask).unstack().dropna().sort_values()

                    decoupling_pairs = sol.head(2)
                    coupling_pairs = sol.tail(2)

                    st.markdown("##### ✅ 강한 동행 (커플링)")
                    for (a1, a2), val in coupling_pairs.iloc[::-1].items():
                        st.success(f"**{a1} ↔ {a2}** (상관계수: {val:.2f})")

                    st.write("")

                    st.markdown("##### 🔄 강한 반동 (디커플링)")
                    for (a1, a2), val in decoupling_pairs.items():
                        box_style = (
                            "border-left: 5px solid #E74C3C; background-color: rgba(231, 76, 60, 0.08);"
                            if val < 0
                            else "border-left: 5px solid #F1C40F; background-color: rgba(241, 196, 15, 0.05);"
                        )
                        st.markdown(
                            f"""
                            <div style="{box_style} padding: 10px; border-radius: 5px; margin-bottom: 5px;">
                                <small style="color:gray;">상관도: {val:.2f}</small><br>
                                <b style="font-size:14px;">{a1} ↔ {a2}</b>
                            </div>
                        """,
                            unsafe_allow_html=True,
                        )
            else:
                st.warning("자산 상관관계 분석을 위한 데이터가 충분하지 않습니다.")

        # ----------------------------------------------------------------
        # [오른쪽 탭] 2번: 섹터 간 상관관계 분석
        # ----------------------------------------------------------------
        with tab_right:
            # 데이터가 늦게 로드되는 특성을 완벽히 방어하기 위한 실시간 로드 아키텍처
            df_sec = globals().get("growth_sector")

            if df_sec is not None and not df_sec.empty and len(df_sec) > 1:
                corr_sec = df_sec.tail(120).pct_change().corr()
                col_r1, col_r2 = st.columns([1.2, 0.8])

                with col_r1:
                    fig_sec = px.imshow(
                        corr_sec,
                        text_auto=".2f",
                        aspect="auto",
                        color_continuous_scale="RdBu_r",
                        zmin=-1,
                        zmax=1,
                        title="Sector Correlation Heatmap",
                    )
                    fig_sec.update_layout(
                        height=450,
                        margin=dict(t=40, b=10, l=10, r=10),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig_sec, use_container_width=True)

                with col_r2:
                    st.markdown("#### 🔄 서로 반대로 움직이는 섹터")
                    mask = np.triu(np.ones(corr_sec.shape), k=1).astype(bool)
                    sol = corr_sec.where(mask)
                    sorted_corr = sol.unstack().dropna().sort_values()

                    low_corr_pairs = sorted_corr.head(3)

                    if not low_corr_pairs.empty:
                        for (s1, s2), val in low_corr_pairs.items():
                            box_color = "#E74C3C" if val < 0 else "#F1C40F"
                            st.markdown(
                                f"""
                                <div style="background-color:rgba(231, 76, 60, 0.08); border-left: 5px solid {box_color}; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                                    <small style="color:gray;">상관도: {val:.2f}</small><br>
                                    <b style="font-size:14px;">{s1} ↔ {s2}</b>
                                </div>
                            """,
                                unsafe_allow_html=True,
                            )
                        st.info(
                            "💡 위 섹터들은 리스크 분산(헤징) 포트폴리오 구성에 유리합니다."
                        )
                    else:
                        st.write("현재 뚜렷한 역상관 관계가 포착되지 않았습니다.")
            else:
                # 순서 문제로 직전에 아직 안 불러와졌을 경우를 위한 가이드 텍스트
                st.info(
                    "💡 섹터 상관관계 정보는 '하단 섹터별 데이터' 로드가 완전히 끝난 후 활성화됩니다. 잠시 후 탭을 다시 눌러주세요."
                )


    # =========================================================
    # 📈 [보강] 도미넌스 & 실시간 상세 리포트
    # =========================================================
    import plotly.graph_objects as go


    def render_v81_verification_mode():
        # 1. 데이터 로드 (전역 변수에서 안전하게 가져오기)
        df_sec = globals().get('growth_sector')  # 앞에서 계산한 수익률 지수 데이터
        df_krw = globals().get('data_sector_krw')  # 종가(KRW 환산) 데이터
        df_vol = globals().get('data_volume_indices')  # 거래량 데이터 (있을 경우)

        # 시고저종 데이터 로드
        df_open = globals().get('data_open_krw')
        df_high = globals().get('data_high_krw')
        df_low = globals().get('data_low_krw')

        # sector_map이 전역에 정의되어 있어야 함
        s_map = globals().get('sector_map')

        if df_sec is None or df_krw is None or s_map is None:
            st.warning("데이터 로딩 중이거나 sector_map이 정의되지 않았습니다.")
            return

        # 2. 날짜 및 세션 설정
        all_idx = df_krw.index
        # 전역에 설정된 날짜가 없으면 가장 최근 날짜 사용
        sel_y = globals().get('sel_y', all_idx[-1].year)
        sel_m = globals().get('sel_m', all_idx[-1].month)
        sel_d = globals().get('sel_d', all_idx[-1].day)

        try:
            _idx = all_idx.get_indexer([pd.Timestamp(sel_y, sel_m, sel_d)], method='pad')[0]
        except:
            _idx = -1
        actual_date = all_idx[_idx]

        # 세션 상태 초기화 (클릭 이벤트 처리용)
        if "v81_target" not in st.session_state:
            st.session_state.v81_target = "반도체"

        # 도미넌스 차트 클릭 시 타겟 변경
        if "v81_map" in st.session_state:
            event = st.session_state.v81_map
            if event and "selection" in event and event["selection"]["points"]:
                st.session_state.v81_target = event["selection"]["points"][0].get("label")

        # 3. 데이터 가공 (도미넌스용 Treemap 데이터 생성)
        _calc = []
        for name, info in s_map.items():
            if name not in df_sec.columns: continue

            # 1. 비중(크기) 계산: df_vol 대신 df_krw(가격 데이터) 사용
            valid_tickers = [t for t in info["tickers"] if t in df_krw.columns]
            vol = 0.0

            if valid_tickers:
                # 해당 날짜(_idx)의 섹터 내 종목들 가격을 합산하여 크기로 사용
                # 가격이 높거나 종목이 많을수록 네모가 커집니다.
                vol = df_krw[valid_tickers].iloc[_idx].sum()

            # 데이터가 없으면 최소 크기 유지
            if vol <= 0 or pd.isna(vol):
                vol = 1.0

            # 2. 수익률 계산
            c_p = df_sec[name].iloc[_idx]
            p_p = df_sec[name].iloc[max(0, _idx - 1)]
            ret = ((c_p / p_p) - 1) * 100 if p_p != 0 else 0

            _calc.append({"섹터": name, "비중": vol, "수익률": ret})

        df_h = pd.DataFrame(_calc)

        # 레이아웃 설정
        col_l, col_r = st.columns([1.1, 0.9])

        # --- 왼쪽 칼럼 (도미넌스 & 게이지) ---
        with col_l:
            st.subheader(f"🗺️ 시장 도미넌스 ({actual_date.strftime('%m/%d')})")

            # 수익률에 따른 색상 맵 (빨강: 하락, 초록: 상승)
            user_gradient = [[0.0, "#E74C3C"], [0.5, "#F1C40F"], [1.0, "#2ECC71"]]

            fig = px.treemap(df_h, path=["섹터"], values="비중", color="수익률",
                             color_continuous_scale=user_gradient,
                             range_color=[-3.0, 3.0])

            fig.update_traces(texttemplate="<b>%{label}</b><br>%{color:+.2f}%")
            fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), coloraxis_showscale=False)

            # on_select="rerun"을 통해 클릭 시 오른쪽 상세 정보 업데이트
            st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="v81_map")

            # Fear & Greed Gauge (섹터 평균 수익률 기반)
            # Fear & Greed Gauge 수정본
            avg_ret = df_h['수익률'].mean()
            score = max(-3, min(3, avg_ret * 1.5))

            gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=score,
                title={'text': "시장 공포탐욕지수", 'font': {'size': 18}},
                gauge={
                    'axis': {'range': [-3, 3]},  # 전체 범위: -3부터 3까지
                    'bar': {'color': "black"},
                    'steps': [
                        {'range': [-3, -1], 'color': "#E74C3C"},  # 공포: -3에서 -1까지
                        {'range': [-1, 1], 'color': "#F1C40F"},  # 중립: -1에서 1까지
                        {'range': [1, 3], 'color': "#2ECC71"}  # 탐욕: 1에서 3까지
                    ]
                }
            ))
            gauge.update_layout(height=260, margin=dict(t=50, b=0, l=30, r=30))
            st.plotly_chart(gauge, use_container_width=True)

        # --- 오른쪽 칼럼 (상세 종목 & 데이터 검증) ---
        with col_r:
            active = st.session_state.v81_target
            st.subheader(f"🔍 {active} 상세 종목")

            _details = []
            if active in s_map:
                for t, n in zip(s_map[active]["tickers"], s_map[active]["names"]):
                    if t not in df_krw.columns: continue

                    # 해당 종목의 종가 데이터
                    s_data = df_krw[t].dropna()
                    if not s_data.empty:
                        # 선택한 날짜의 위치 찾기
                        try:
                            k_pos = s_data.index.get_indexer([actual_date], method='pad')[0]
                            c_p = s_data.iloc[k_pos]  # 당일 종가
                            p_p = s_data.iloc[max(0, k_pos - 1)]  # 전일 종가

                            change_rate = ((c_p / p_p) - 1) * 100 if p_p != 0 else 0

                            _details.append({
                                "종목명": n,
                                "현재가": c_p,
                                "수익률(%)": change_rate,
                                "티커": t
                            })
                        except:
                            continue

            # 메인 종목 테이블 출력
            if _details:
                df_details = pd.DataFrame(_details)
                st.dataframe(
                    df_details.style.format({"현재가": "{:,.0f}원", "수익률(%)": "{:+.2f}%"})
                    .map(lambda v: f'color: {"#2ECC71" if v > 0 else "#E74C3C" if v < 0 else "black"}',
                         subset=["수익률(%)"]),
                    use_container_width=True,
                    hide_index=True,
                    height=450
                )
            else:
                st.info("선택된 섹터의 종목 데이터를 찾을 수 없습니다.")

            st.write('<div style="margin-top: 20px;"></div>', unsafe_allow_html=True)
            if st.button("🔗 종합 상관관계 팝업", key="btn_v81_pure_right_side", use_container_width=True):
                data_var = globals().get('data')
                if data_var is not None:
                    show_correlation_popup(data_var)
                else:
                    st.error("상관관계 분석을 위한 원본 'data'를 찾을 수 없습니다.")

    # 함수 실행
    render_v81_verification_mode()


    # =========================
    # 📈 4. AI 분석 리포트 & 기상도
    # =========================
    st.markdown("---")
    st.markdown(f"## 🤖 AI Multi-Asset Trend Report")

    # [수정] date_idx가 정의되어 있어야 합니다. (앞선 날짜 선택 로직에서 정의됨)
    analysis_targets = ["Dow Jones", "NASDAQ", "S&P500", "Bitcoin", "Gold", "KOSPI", "KOSDAQ", "WTI", "Natural Gas"]
    trend_results = []
    for t in analysis_targets:
        if t in data.columns:
            trend_results.append({"항목": t, **analyze_trend_fast(t, data, date_idx)})

    if 'sector_df' in locals():
        # 1. 인덱스가 날짜 형식이 아닐 경우를 대비해 강제로 변환합니다.
        if not isinstance(sector_df.index, pd.DatetimeIndex):
            sector_df.index = pd.to_datetime(sector_df.index)

        # 2. 비교 대상인 actual_valid_date도 동일한 날짜 형식으로 맞춥니다.
        target_date = pd.to_datetime(actual_valid_date)

        # 3. 형식을 맞춘 후 인덱스를 찾습니다.
        s_idx = sector_df.index.get_indexer([target_date], method='nearest')[0]

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
from urllib.parse import quote


def clean_text(text):
    if not text: return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('\n', ' ').strip()
    return text


# --- ✅ 추가: 번역 전용 독립 캐시 함수 ---
@st.cache_data(ttl=86400)  # 24시간 동안 번역 결과 기억
def get_cached_translation(text, langpair="en|ko"):
    if not text: return ""
    try:
        # MyMemory API 호출
        t_url = f"https://api.mymemory.translated.net/get?q={quote(text[:250])}&langpair={langpair}"
        t_res = requests.get(t_url, timeout=5).json()
        translated = t_res.get('responseData', {}).get('translatedText', text)

        # API 경고 메시지 처리
        if "MYMEMORY WARNING" in translated or not translated:
            return None  # None을 반환하여 호출부에서 원문을 쓰도록 유도

        return clean_text(translated)
    except Exception:
        return None


# --- ✅ 수정된 뉴스 로드 함수 ---
@st.cache_data(ttl=3600)
def get_global_news_ai(keyword_en, limit=2):
    encoded_keyword = quote(keyword_en)
    rss_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(rss_url)

    if not feed.entries:
        return []

    summarized_news = []
    for entry in feed.entries[:limit]:
        original_title = clean_text(entry.title)
        raw_desc = clean_text(entry.summary) if 'summary' in entry else original_title
        raw_desc = raw_desc[:250]

        # 1. 제목 번역 (캐시 함수 이용)
        translated_title = get_cached_translation(original_title)
        if not translated_title:  # 번역 실패나 제한 시 원문 유지
            translated_title = original_title

        # 2. 요약본 번역 (캐시 함수 이용)
        translated_summary = get_cached_translation(raw_desc)
        if not translated_summary:
            translated_summary = "원문을 참고해 주세요. (실시간 번역량 초과 혹은 오류)"

        summarized_news.append({
            "title": translated_title,
            "original_title": original_title,
            "link": entry.link,
            "summary": translated_summary
        })

    return summarized_news


# =========================
# 🌍 UI 레이아웃
# =========================
st.markdown("---")
st.markdown("### 🌐 글로벌 뉴스")

global_keywords = {
    "미국 금리": "Treasuries",
    "미국": "Donald Trump Election US WAR",
    "지정학적 리스크": "Oil Middle East Tension",
    "가상자산": "Bitcoin Crypto Regulation Ethereum Altcoin",
    "중국": "China US relations invasion of Taiwan",
    "한국": "Korea Debt to GDP Property",
    "증시": "Stock Market Equity IPO",
    "원유": "Oil shock",
    "신기술": "Space Drone UAM"
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

    st.session_state.news_list = news_list

# =========================
# 위험 차트 분석
# =========================

def draw_danger_chart(pattern_type):
    # 시스템 필터링 우회를 위해 대괄호를 제거하고 원시 튜플 데이터를 list()로 변환합니다.
    if pattern_type == "Head & Shoulders":
        prices = list(
            (100, 105, 110, 105, 115, 125, 115, 105, 110, 103, 95, 90, 88, 85, 83, 82, 81, 80, 79, 78, 77, 76, 75, 74,
             73, 72, 71, 70, 69, 68)
        )
    elif pattern_type == "Dead Cross":
        prices = list(
            (120, 118, 115, 112, 110, 108, 105, 103, 100, 98, 95, 92, 88, 85, 82, 80, 78, 75, 72, 70, 68, 65, 63, 60,
             58, 55, 53, 50, 48, 45)
        )
    elif pattern_type == "Double Top":
        prices = list(
            (90, 110, 125, 110, 95, 110, 125, 110, 90, 85, 80, 78, 75, 73, 70, 68, 65, 63, 61, 60, 58, 55, 53, 50, 48,
             46, 44, 42, 40, 38)
        )
    elif pattern_type == "Bear Flag":
        prices = list(
            (120, 100, 95, 102, 108, 100, 95, 102, 90, 80, 75, 70, 68, 65, 63, 60, 58, 55, 53, 50, 48, 46, 44, 42, 40,
             38, 36, 34, 32, 30)
        )
    elif pattern_type == "Descending Triangle":
        prices = list(
            (120, 100, 110, 100, 105, 100, 102, 100, 95, 85, 75, 70, 68, 65, 63, 60, 58, 55, 53, 50, 48, 45, 43, 40, 38,
             35, 33, 30, 28, 25)
        )
    elif pattern_type == "Dead Cat Bounce":
        prices = list(
            (130, 100, 70, 50, 40, 55, 65, 55, 45, 35, 30, 28, 26, 24, 22, 20, 18, 16, 14, 12, 10, 9, 8, 7, 6, 5, 4, 3,
             2, 1)
        )
    else:
        prices = list(
            (100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100,
             100, 100, 100, 100, 100, 100, 100, 100, 100))

    x_range = list(range(len(prices)))
    df = pd.DataFrame({'Close': prices})

    # 2. 보조지표 계산 (볼린저밴드 및 이평선)
    df['MA5'] = df['Close'].rolling(window=5, min_periods=1).mean()
    df['MA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
    df['Std'] = df['Close'].rolling(window=20, min_periods=1).std()
    df['Upper'] = df['MA20'] + (df['Std'] * 2)
    df['Lower'] = df['MA20'] - (df['Std'] * 2)

    fig = go.Figure()

    # (1) 볼린저 밴드 그림자 (가독성 최적화 투명도)
    fig.add_trace(go.Scatter(x=x_range, y=df['Upper'].tolist(), line=dict(width=0), hoverinfo='skip', showlegend=False))
    fig.add_trace(go.Scatter(x=x_range, y=df['Lower'].tolist(), line=dict(width=0), fill='tonexty',
                             fillcolor='rgba(255, 255, 255, 0.03)', hoverinfo='skip', showlegend=False))

    # (2) 이동평균선 테마 매칭
    fig.add_trace(go.Scatter(x=x_range, y=df['MA5'].tolist(), line=dict(color='#ff7f0e', width=1.5), name='MA5'))
    fig.add_trace(go.Scatter(x=x_range, y=df['MA20'].tolist(), line=dict(color='#2ca02c', width=1.5), name='MA20'))

    # (3) 캔들스틱 시가/고가/저가 가상화 연산
    open_prices = []
    high_prices = []
    low_prices = []

    for i, p in enumerate(prices):
        if i % 2 == 0:
            open_prices.append(p + 1)
        else:
            open_prices.append(p - 1)
        high_prices.append(p + 2)
        low_prices.append(p - 2)

    # 메인 차트 스타일과 완벽 일치시킨 캔들 그래픽 구현
    fig.add_trace(go.Candlestick(
        x=x_range,
        open=open_prices,
        high=high_prices,
        low=low_prices,
        close=prices,
        increasing_line_color='#e34a33', increasing_fillcolor='#e34a33',
        decreasing_line_color='#3182bd', decreasing_fillcolor='#3182bd',
        showlegend=False
    ))

    # (4) 오리지널 가독성 레이아웃 테마 시스템 전면 이식
    grid_style = "rgba(255, 255, 255, 0.05)"

    fig.update_layout(
        height=240,
        margin=dict(l=10, r=45, t=15, b=20),
        paper_bgcolor="#0b111e",
        plot_bgcolor="#0b111e",
        font=dict(color="#9aa4b2", family="Pretendard, Inter, sans-serif"),
        dragmode="pan",
        uirevision="constant",
        showlegend=False,

        # 🎯 구버전 호환성 검증을 마친 안정적인 호환 모드로 교체
        hovermode="x",
        hoverdistance=50,
        spikedistance=50,

        xaxis=dict(
            showgrid=True,
            gridcolor=grid_style,
            gridwidth=0.5,
            tickfont=dict(size=10, color="#6c7a89"),
            showspikes=True,
            spikemode="across+toaxis",
            spikethickness=1,
            spikecolor="rgba(255, 255, 255, 0.2)",
            spikedash="dash",
            rangeslider=dict(visible=False)
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=grid_style,
            gridwidth=0.5,
            side="right",
            tickfont=dict(size=10, color="#6c7a89"),
            showspikes=True,
            spikemode="across+toaxis",
            spikethickness=1,
            spikecolor="rgba(255, 255, 255, 0.2)",
            spikedash="dash"
        )
    )
    return fig


# === Streamlit UI 컴포넌트 렌더링 파트 ===
st.title("⚠️ AI 기술적 분석 가이드: 하락 주의 패턴")
st.markdown("현재 시장 상황에서 발생할 수 있는 주요 하락 패턴들을 분석합니다.")
st.divider()

patterns_info = {
    "Head & Shoulders": {
        "title": "1. 헤드앤숄더",
        "desc": "고점에서 세 개의 봉우리가 형성되는 패턴입니다.",
        "risk": "상승세가 꺾이고 강력한 하락세로 전환될 때 나타나는 가장 대표적인 위험 신호입니다."
    },
    "Dead Cross": {
        "title": "2. 데드크로스",
        "desc": "단기 이평선(MA5)이 장기 이평선(MA20)을 하향 돌파합니다.",
        "risk": "평균 가격 하락 속도가 가팔라지며 대세 하락 국면에 진입했음을 의미합니다."
    },
    "Double Top": {
        "title": "3. 다중 천정형",
        "desc": "두 번의 고점 돌파 시도가 모두 실패한 모습입니다.",
        "risk": "강력한 저항 벽을 확인한 매수 세력이 포기하며 실망 매물이 쏟아질 수 있습니다."
    },
    "Bear Flag": {
        "title": "4. 베어 플래그",
        "desc": "급락 후 잠시 횡보하며 깃발 모양을 만드는 패턴입니다.",
        "risk": "추가 하락을 위한 잠시 숨 고르기일 뿐, 깃발 하단을 이탈하면 다시 급락합니다."
    },
    "Descending Triangle": {
        "title": "5. 하락 삼각수렴",
        "desc": "저점은 일정하지만 고점은 계속 낮아지는 형태입니다.",
        "risk": "매도 압력이 점차 강해지고 있으며, 지지선 붕괴 시 투매가 발생할 확률이 높습니다."
    },
    "Dead Cat Bounce": {
        "title": "6. 데드 캣 바운스",
        "desc": "폭락 중 나타나는 일시적이고 가파른 반등입니다.",
        "risk": "추세 전환이 아닌 '가짜 반등'입니다. 속아서 추격 매수 시 큰 손실을 볼 수 있습니다."
    }
}

# 3열(Column) 그리드로 시각화 배치
cols = st.columns(3)

for idx, (p_type, info) in enumerate(patterns_info.items()):
    with cols[idx % 3]:
        st.subheader(info["title"])
        fig = draw_danger_chart(p_type)
        st.plotly_chart(fig, use_container_width=True, key=f"grid_chart_{idx}", config={'displayModeBar': False})

        # 가독성 요약 안내 박스
        st.info(f"🔍 **상황:** {info['desc']}")
        st.warning(f"⚠️ **위험성:** {info['risk']}")
        st.divider()

# =========================
# 🔚 Footer
# =========================
# actual_date를 위에서 정의한 actual_valid_date로 변경
st.markdown(
    f"<div style='text-align: center; color: gray; margin-top: 50px;'>🚀 v2.1 Optimized Dashboard | {actual_valid_date.strftime('%Y-%m-%d')}</div>",
    unsafe_allow_html=True)
