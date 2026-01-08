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
from difflib import get_close_matches # 아파트 이름 유추용

# -----------------------------------------------------------------------------
# 1. 화면 디자인 및 설정 (사이드바 400px 확장 + 다크모드 최적화 CSS)
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

def save_my_apts(df):
    df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')

# -----------------------------------------------------------------------------
# 3. 데이터 수집 함수 (아파트/토지)
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# 4. 링크 및 병합 유틸리티
# -----------------------------------------------------------------------------
def get_links(dong, name, is_land=False):
    q = f"춘천 {dong} {name}"
    enc = urllib.parse.quote(q)
    if is_land:
        return {
            "kb": f"https://map.naver.com/p/search/{enc}",
            "naver": f"https://new.land.naver.com/search?sk={enc}"
        }
    return {
        "kb": f"https://kbland.kr/search?q={enc}",
        "naver": f"https://new.land.naver.com/search?sk={enc}"
    }

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
# 5. 이름 유추 및 뉴스 수집 기능
# -----------------------------------------------------------------------------
def get_inferred_apt_name(api_data, input_name, input_dong):
    """최근 거래 데이터에서 가장 유사한 아파트 이름을 찾아줌"""
    if not api_data or not input_name:
        return input_name
    # 해당 동의 아파트 이름 목록만 추출
    dong_apts = list(set([d['아파트명'] for d in api_data if d['동'] == input_dong]))
    # 가장 유사한 이름 찾기
    matches = get_close_matches(input_name, dong_apts, n=1, cutoff=0.3)
    return matches[0] if matches else input_name

def get_news_list(category="전체"):
    sites = "site:kado.net OR site:kwnews.co.kr OR site:ccpost.co.kr OR site:gwnews.org OR site:chunsa.kr"
    noise = "-운세 -부고 -인사 -동정 -게시판"
    if category == "부동산":
        keyword = f"춘천 (부동산 OR 아파트 OR 주택 OR 분양 OR 매매 OR 토지) {noise}"
    else:
        keyword = f"춘천 -부동산 -아파트 {noise}"

    query = f"{keyword} ({sites}) when:7d"
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(f"{rss_url}&t={int(time.time())}", headers=headers, timeout=5)
        feed = feedparser.parse(response.content)
        news = []
        today_str = datetime.now().strftime("%Y-%m-%d")
        for e in feed.entries:
            if hasattr(e, 'published_parsed'):
                dt = datetime.fromtimestamp(time.mktime(e.published_parsed))
                date_str = dt.strftime("%Y-%m-%d")
                news.append({
                    'title': e.title, 'link': e.link, 'date_str': date_str, 'date_obj': dt,
                    'source': e.source.title if hasattr(e, 'source') else "언론사",
                    'is_today': (date_str == today_str)
                })
        return sorted(news, key=lambda x: x['date_obj'], reverse=True)[:50]
    except:
        return []

# -----------------------------------------------------------------------------
# 6. 메인 UI 및 사이드바 로직
# -----------------------------------------------------------------------------
st.title("🏙️ 춘천 지역 통합 관제 시스템")

# [사이드바 구성]
with st.sidebar:
    st.header("🔑 1. API 설정")
    # Secrets 자동 연결 확인
    if "molit_key" in st.secrets:
        api_key = st.secrets["molit_key"]
        st.success("✅ 인증키가 자동 연결되었습니다.")
    else:
        api_key = st.text_input("공공데이터포털 인증키(Decoding)", type="password")
        st.info("관리자 도구(Secrets)에 키를 등록하면 편리합니다.")
    
    st.divider()
    
    st.header("📌 2. 관심 아파트 관리")
    st.caption("이름을 대략적으로 적어도 거래 데이터를 통해 보정합니다.")
    
    # 최근 데이터를 미리 불러옴 (이름 유추용)
    api_raw_for_inference = get_apt_data_api(api_key)
    
    with st.form("add_apt_form", clear_on_submit=True):
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            input_dong = st.selectbox("동 선택", CHUNCHEON_DONGS)
        with col_s2:
            input_name = st.text_input("아파트명 (예: 한숲)")
        
        if st.form_submit_button("목록에 추가"):
            if input_name:
                # 이름 유추 로직 작동
                corrected_name = get_inferred_apt_name(api_raw_for_inference, input_name, input_dong)
                if corrected_name != input_name:
                    st.toast(f"💡 '{input_name}'을(를) '{corrected_name}'(으)로 인식했습니다.")
                
                curr_df = load_my_apts()
                if not ((curr_df['동'] == input_dong) & (curr_df['아파트명'] == corrected_name)).any():
                    new_entry = pd.DataFrame({"동": [input_dong], "아파트명": [corrected_name]})
                    save_my_apts(pd.concat([curr_df, new_entry], ignore_index=True))
                    st.rerun()
                else:
                    st.warning("이미 목록에 있는 아파트입니다.")

    st.markdown("### 📋 현재 관리 목록")
    my_df = load_my_apts()
    for idx, row in my_df.iterrows():
        c1, c2 = st.columns([0.8, 0.2])
        c1.text(f"[{row['동']}] {row['아파트명']}")
        if c2.button("삭제", key=f"del_{idx}"):
            save_my_apts(my_df.drop(idx))
            st.rerun()

# [메인 화면 필터링]
st.markdown("### 🔍 조회 지역 필터링")
all_filter_dongs = sorted(list(set(my_df['동'].unique().tolist() + CHUNCHEON_DONGS)))
selected_dongs = st.multiselect("조회할 동네를 선택하세요:", all_filter_dongs, default=["퇴계동", "온의동"])
st.markdown("---")

# [메인 탭 구성]
tab1, tab2, tab3 = st.tabs(["🏢 아파트 실거래", "⛰️ 토지 실거래", "📰 지역 뉴스(1주일치)"])

with tab1:
    st.markdown("#### 최근 6개월 아파트 거래 내역")
    if selected_dongs:
        data_apt = get_apt_data_api(api_key)
        df_v_apt = merge_data(data_apt, my_df, selected_dongs)
        df_v_apt['kb_link'] = df_v_apt.apply(lambda x: get_links(x['동'], x['아파트명'])['kb'], axis=1)
        df_v_apt['naver_link'] = df_v_apt.apply(lambda x: get_links(x['동'], x['아파트명'])['naver'], axis=1)
        st.dataframe(
            df_v_apt,
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
        data_land = get_land_data_api(api_key)
        df_l = pd.DataFrame(data_land) if data_land else pd.DataFrame()
        if not df_l.empty:
            df_l = df_l[df_l['동'].isin(selected_dongs)].copy()
        if df_l.empty:
            df_l = pd.DataFrame([{'계약일': '-', '동': selected_dongs[0], '아파트명': '-', '면적': '-', '국토부 실거래가': '-'}])
        
        df_l['kb'] = df_l.apply(lambda x: get_links(x['동'], x['아파트명'], True)['kb'], axis=1)
        df_l['naver'] = df_l.apply(lambda x: get_links(x['동'], x['아파트명'], True)['naver'], axis=1)
        st.dataframe(
            df_l,
            column_config={
                "아파트명": st.column_config.TextColumn("지목"),
                "kb": st.column_config.LinkColumn("위치", display_text="확인"),
                "naver": st.column_config.LinkColumn("네이버", display_text="확인"),
                "국토부 실거래가": st.column_config.NumberColumn(format="%d"),
            },
            column_order=["계약일", "동", "아파트명", "면적", "국토부 실거래가", "kb", "naver"],
            hide_index=True, use_container_width=True
        )

with tab3:
    st.subheader(f"📅 춘천 주요 소식 (최신순 50개)")
    nt1, nt2 = st.tabs(["🏠 부동산 뉴스", "📑 일반/통합 뉴스"])
    
    def render_news_section(cat):
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
            st.info(f"최근 1주일간 소식이 없습니다.")

    with nt1: render_news_section("부동산")
    with nt2: render_news_section("전체")
    
    if st.button("뉴스 새로고침"):
        st.rerun()