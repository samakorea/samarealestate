import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import feedparser
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
import os

# -----------------------------------------------------------------------------
# 1. 화면 디자인 (사이드바 400px 확장 + 다크모드 최적화 CSS)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="춘천 지역 통합 관제", 
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        /* 사이드바 너비 400px로 고정 */
        [data-testid="stSidebar"] {
            min-width: 400px !important;
            max-width: 400px !important;
        }

        /* 뉴스 박스 스타일 */
        .news-box {
            background-color: #262730; 
            padding: 18px;
            border-radius: 10px;
            margin-bottom: 12px;
            border-left: 5px solid #4da6ff;
            border: 1px solid #363945;
        }
        .news-title {
            font-size: 17px;
            font-weight: bold;
            color: #ffffff !important; 
            text-decoration: none;
            display: block;
            margin-bottom: 5px;
        }
        .news-title:hover {
            color: #4da6ff !important;
            text-decoration: underline;
        }
        .news-meta {
            font-size: 13px;
            color: #a0a0a0; 
        }
        .badge-today {
            background-color: #ff4b4b;
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            margin-right: 8px;
        }
        
        /* 링크 색상 보정 */
        a { color: #4da6ff !important; text-decoration: none; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. 설정 및 관심 아파트 관리 (CSV 파일 연동)
# -----------------------------------------------------------------------------
LAWD_CD = "42110" # 춘천시
CSV_FILE = "my_apts.csv"

CHUNCHEON_DONGS = sorted([
    "퇴계동", "온의동", "석사동", "후평동", "동면", "신북읍", 
    "우두동", "효자동", "근화동", "소양로", "약사명동", "칠전동", "사농동"
])

def load_my_apts():
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame({
            "동": ["퇴계동", "온의동"], 
            "아파트명": ["e편한세상춘천한숲시티", "춘천센트럴타워푸르지오"]
        })
        df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')
        return df
    try:
        return pd.read_csv(CSV_FILE)
    except:
        return pd.DataFrame(columns=["동", "아파트명"])

def add_my_apt(dong, name):
    df = load_my_apts()
    if not ((df['동'] == dong) & (df['아파트명'] == name)).any():
        new_row = pd.DataFrame({"동": [dong], "아파트명": [name]})
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')
        return True
    return False

def remove_my_apt(dong, name):
    df = load_my_apts()
    df = df[~((df['동'] == dong) & (df['아파트명'] == name))]
    df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')

# -----------------------------------------------------------------------------
# 3. 실거래가 수집 및 링크 함수
# -----------------------------------------------------------------------------
def get_search_links(dong, apt_name):
    q = f"{dong} {apt_name}" if apt_name != '-' else f"춘천 {dong} 아파트"
    enc = urllib.parse.quote(q)
    return {
        "kb": f"https://kbland.kr/search?q={enc}",
        "naver": f"https://new.land.naver.com/search?sk={enc}"
    }

def get_land_links(dong, jimok):
    q = f"춘천시 {dong} {jimok}" if jimok != '-' else f"춘천시 {dong} 토지"
    enc = urllib.parse.quote(q)
    return {
        "kb": f"https://map.naver.com/p/search/{enc}",
        "naver": f"https://new.land.naver.com/search?sk={enc}"
    }

def get_recent_months(months=6):
    now = datetime.now()
    return [(now - relativedelta(months=i)).strftime("%Y%m") for i in range(months)]

@st.cache_data(ttl=3600)
def get_apt_data_api(api_key):
    if not api_key: return []
    months = get_recent_months(6)
    all_data = []
    url = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTradeDev"
    for ym in months:
        params = {'serviceKey': api_key, 'LAWD_CD': LAWD_CD, 'DEAL_YMD': ym, 'numOfRows': '1000'}
        try:
            response = requests.get(url, params=params, timeout=5)
            root = ET.fromstring(response.content)
            for item in root.findall('.//item'):
                try:
                    price = int(item.findtext('거래금액').strip().replace(',', ''))
                    all_data.append({
                        '계약일': f"{item.findtext('년')}-{item.findtext('월').zfill(2)}-{item.findtext('일').zfill(2)}",
                        '동': item.findtext('법정동').strip(),
                        '아파트명': item.findtext('아파트').strip(),
                        '면적': float(item.findtext('전용면적')),
                        '국토부 실거래가': price,
                    })
                except: continue
        except: continue
    return all_data

@st.cache_data(ttl=3600)
def get_land_data_api(api_key):
    if not api_key: return []
    months = get_recent_months(6)
    all_data = []
    url = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcLandTrade"
    for ym in months:
        params = {'serviceKey': api_key, 'LAWD_CD': LAWD_CD, 'DEAL_YMD': ym, 'numOfRows': '1000'}
        try:
            response = requests.get(url, params=params, timeout=5)
            root = ET.fromstring(response.content)
            for item in root.findall('.//item'):
                try:
                    price = int(item.findtext('거래금액').strip().replace(',', ''))
                    all_data.append({
                        '계약일': f"{item.findtext('년')}-{item.findtext('월').zfill(2)}-{item.findtext('일').zfill(2)}",
                        '동': item.findtext('법정동').strip(),
                        '아파트명': item.findtext('지목'),
                        '면적': float(item.findtext('거래면적')),
                        '국토부 실거래가': price,
                    })
                except: continue
        except: continue
    return all_data

def merge_data(api_list, my_df, selected_dongs):
    df_real = pd.DataFrame(api_list) if api_list else pd.DataFrame(columns=['계약일', '동', '아파트명', '면적', '국토부 실거래가'])
    if selected_dongs:
        df_real = df_real[df_real['동'].isin(selected_dongs)]
    
    final_rows = df_real.to_dict('records')
    target_df = my_df[my_df['동'].isin(selected_dongs)] if selected_dongs else my_df
    traded_apts = set(df_real['아파트명'].unique()) if not df_real.empty else set()

    for _, row in target_df.iterrows():
        t_name = str(row['아파트명'])
        t_dong = str(row['동'])
        is_traded = any(t_name in str(t) for t in traded_apts)
        if not is_traded:
            final_rows.append({'계약일': '-', '동': t_dong, '아파트명': t_name, '면적': '-', '국토부 실거래가': '-'})

    df_final = pd.DataFrame(final_rows)
    if not df_final.empty:
        df_final['sort'] = df_final['계약일'].apply(lambda x: '0000' if x == '-' else x)
        df_final = df_final.sort_values(by=['sort', '동'], ascending=[False, True]).drop(columns=['sort'])
    return df_final

# -----------------------------------------------------------------------------
# 4. 뉴스 수집 (부동산 / 일반 통합 탭, 1주일치, 최대 50개)
# -----------------------------------------------------------------------------
def get_news_list(category="전체"):
    sites = "site:kado.net OR site:kwnews.co.kr OR site:ccpost.co.kr OR site:gwnews.org OR site:chunsa.kr"
    noise = "-운세 -부고 -인사 -동정 -게시판"

    if category == "부동산":
        keyword = f"춘천 (부동산 OR 아파트 OR 주택 OR 분양 OR 매매 OR 토지) {noise}"
    else:
        # 통합 뉴스: 부동산을 제외한 경제, 정치, 사회 전반
        keyword = f"춘천 -부동산 -아파트 {noise}"

    # 일주일 전(7d)까지의 뉴스 수집
    query = f"{keyword} ({sites}) when:7d"
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(f"{rss_url}&t={int(time.time())}", headers=headers, timeout=5)
        feed = feedparser.parse(response.content)
    except:
        return []
    
    news = []
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for e in feed.entries:
        if hasattr(e, 'published_parsed'):
            dt = datetime.fromtimestamp(time.mktime(e.published_parsed))
            date_str = dt.strftime("%Y-%m-%d")
            news.append({
                'title': e.title, 
                'link': e.link, 
                'date_str': date_str,
                'date_obj': dt,
                'source': e.source.title if hasattr(e, 'source') else "언론사",
                'is_today': (date_str == today_str)
            })

    # 최신 날짜 및 시간순 정렬 후 최대 50개 반환
    return sorted(news, key=lambda x: x['date_obj'], reverse=True)[:50]

# -----------------------------------------------------------------------------
# 5. UI 메인 구성
# -----------------------------------------------------------------------------
st.title("🏙️ 춘천 지역 통합 관제 시스템")

# [사이드바]
with st.sidebar:
    st.header("🔑 1. API 설정")
    api_key = st.text_input("공공데이터포털 인증키(Decoding)", type="password")
    st.divider()
    
    st.header("📌 2. 관심 아파트 추가")
    st.caption("거래가 없어도 표에 고정됩니다.")
    with st.form("add_apt_form", clear_on_submit=True):
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            input_dong = st.selectbox("동 선택", CHUNCHEON_DONGS)
        with col_s2:
            input_name = st.text_input("아파트명")
        if st.form_submit_button("목록에 추가"):
            if input_name and add_my_apt(input_dong, input_name):
                st.success(f"{input_name} 추가됨")
                time.sleep(0.5)
                st.rerun()

    st.markdown("### 📋 현재 관리 목록")
    my_df = load_my_apts()
    for idx, row in my_df.iterrows():
        c1, c2 = st.columns([0.8, 0.2])
        c1.text(f"[{row['동']}] {row['아파트명']}")
        if c2.button("삭제", key=f"del_{idx}"):
            remove_my_apt(row['동'], row['아파트명'])
            st.rerun()

# [메인 화면 필터]
st.markdown("### 🔍 조회 지역 필터링")
all_dongs = sorted(list(set(my_df['동'].unique().tolist() + CHUNCHEON_DONGS)))
selected_dongs = st.multiselect("조회할 동네를 선택하세요:", all_dongs, default=["퇴계동", "온의동"])
st.markdown("---")

# [탭 구성]
tab1, tab2, tab3 = st.tabs(["🏢 아파트 실거래", "⛰️ 토지 실거래", "📰 지역 뉴스(1주일치)"])

with tab1:
    st.markdown("#### 최근 6개월 아파트 거래 내역")
    if selected_dongs:
        data = get_apt_data_api(api_key)
        df_v = merge_data(data, my_df, selected_dongs)
        df_v['kb_link'] = df_v.apply(lambda x: get_search_links(x['동'], x['아파트명'])['kb'], axis=1)
        df_v['naver_link'] = df_v.apply(lambda x: get_search_links(x['동'], x['아파트명'])['naver'], axis=1)
        st.dataframe(
            df_v,
            column_config={
                "계약일": st.column_config.TextColumn("계약일", width="small"),
                "kb_link": st.column_config.LinkColumn("KB시세", display_text="확인"),
                "naver_link": st.column_config.LinkColumn("네이버", display_text="확인"),
                "국토부 실거래가": st.column_config.NumberColumn(format="%d"),
            },
            column_order=["계약일", "동", "아파트명", "면적", "국토부 실거래가", "kb_link", "naver_link"],
            hide_index=True, use_container_width=True
        )
    else:
        st.info("동네를 선택해주세요.")

with tab2:
    st.markdown("#### 최근 6개월 토지 거래 내역")
    if selected_dongs:
        l_data = get_land_data_api(api_key)
        if l_data:
            ldf = pd.DataFrame(l_data)
            ldf = ldf[ldf['동'].isin(selected_dongs)].copy()
        else: ldf = pd.DataFrame()
        
        if ldf.empty:
            ldf = pd.DataFrame([{'계약일': '-', '동': selected_dongs[0], '아파트명': '-', '면적': '-', '국토부 실거래가': '-'}])
        
        ldf['kb_link'] = ldf.apply(lambda x: get_land_links(x['동'], x['아파트명'])['kb'], axis=1)
        ldf['naver_link'] = ldf.apply(lambda x: get_land_links(x['동'], x['아파트명'])['naver'], axis=1)
        st.dataframe(
            ldf,
            column_config={
                "아파트명": st.column_config.TextColumn("지목"),
                "kb_link": st.column_config.LinkColumn("위치", display_text="확인"),
                "naver_link": st.column_config.LinkColumn("네이버", display_text="확인"),
                "국토부 실거래가": st.column_config.NumberColumn(format="%d"),
            },
            column_order=["계약일", "동", "아파트명", "면적", "국토부 실거래가", "kb_link", "naver_link"],
            hide_index=True, use_container_width=True
        )

with tab3:
    st.subheader(f"📅 춘천 주요 소식 (최신순 50개)")
    # 뉴스 세부 카테고리 탭 (부동산 / 일반 통합)
    nt1, nt2 = st.tabs(["🏠 부동산 뉴스", "📑 일반/통합 뉴스"])
    
    def render_news(cat):
        items = get_news_list(cat)
        if items:
            for n in items:
                badge = '<span class="badge-today">오늘</span>' if n['is_today'] else ''
                st.markdown(f"""
                    <div class="news-box">
                        <a href="{n['link']}" target="_blank" class="news-title">{badge}{n['title']}</a>
                        <div class="news-meta">{n['source']} | {n['date_str']}</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info(f"최근 1주일간 '{cat}' 관련 최신 뉴스가 없습니다.")

    with nt1: render_news("부동산")
    with nt2: render_news("전체")
    
    if st.button("뉴스 새로고침"):
        st.rerun()