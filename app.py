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
from difflib import get_close_matches
import re

# -----------------------------------------------------------------------------
# 1. 화면 디자인 및 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="강원도 부동산 통합 관제", 
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        [data-testid="stSidebar"] { min-width: 400px !important; max-width: 400px !important; }
        .news-box {
            background-color: #262730; padding: 18px; border-radius: 10px;
            margin-bottom: 12px; border-left: 5px solid #03C75A; border: 1px solid #363945;
        }
        .news-title { font-size: 17px; font-weight: bold; color: #ffffff !important; text-decoration: none; display: block; margin-bottom: 5px; }
        .news-title:hover { color: #03C75A !important; text-decoration: underline; }
        .news-meta { font-size: 13px; color: #a0a0a0; }
        .badge-today { background-color: #ff4b4b; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; margin-right: 8px; }
        .highlight-row { background-color: #ff4b4b20 !important; }
        a { color: #03C75A !important; text-decoration: none; }
    </style>
""", unsafe_allow_html=True)

CSV_FILE = "my_apts.csv"

# ★ 지역별 설정 (원주 깔끔하게 정리 완료)
REGIONS = {
    "춘천시": {
        "code": "51110",
        "dongs": sorted(["퇴계동", "온의동", "석사동", "후평동", "동면", "신북읍", "우두동", "효자동", "근화동", "소양로", "약사명동", "칠전동", "사농동"]),
        "publishers": [
            {"name": "전체", "domain_key": "ALL"},
            {"name": "강원일보", "domain_key": "kwnews"},
            {"name": "강원도민일보", "domain_key": "kado"},
            {"name": "MS투데이", "domain_key": "mstoday"}
        ]
    },
    "원주시": {
        "code": "51130",
        "dongs": sorted(["반곡동", "무실동", "단구동", "단계동", "관설동", "지정면", "문막읍", "태장동", "우산동", "명륜동", "개운동", "중앙동", "봉산동", "행구동"]),
        "publishers": [
            {"name": "전체", "domain_key": "ALL"},
            {"name": "강원일보", "domain_key": "kwnews"},
            {"name": "강원도민일보", "domain_key": "kado"}
        ]
    }
}

# -----------------------------------------------------------------------------
# 2. 데이터 관리 함수
# -----------------------------------------------------------------------------
def load_my_apts():
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame({
            "지역": ["춘천시", "원주시"],
            "동": ["퇴계동", "반곡동"], 
            "아파트명": ["e편한세상춘천한숲시티", "원주혁신도시중흥S-클래스프라디움"]
        })
        df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')
        return df
    try: 
        df = pd.read_csv(CSV_FILE)
        if "지역" not in df.columns: df["지역"] = "춘천시"
        return df
    except: return pd.DataFrame(columns=["지역", "동", "아파트명"])

def save_my_apts(df):
    df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')

# -----------------------------------------------------------------------------
# 3. 데이터 수집 함수
# -----------------------------------------------------------------------------
def get_recent_months(months=6):
    now = datetime.now()
    return [(now - relativedelta(months=i)).strftime("%Y%m") for i in range(months)]

@st.cache_data(ttl=60)
def get_apt_data_api(api_key, region_code):
    if not api_key: return []
    months = get_recent_months(6)
    all_data = []
    base_url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
    
    for ym in months:
        query_url = f"{base_url}?serviceKey={api_key}&LAWD_CD={region_code}&DEAL_YMD={ym}&numOfRows=1000&pageNo=1"
        try:
            response = requests.get(query_url, timeout=10, verify=False)
            try:
                root = ET.fromstring(response.content)
                if root.findtext('.//resultCode') not in ['00', '000']: continue
                for item in root.findall('.//item'):
                    try:
                        price = int(item.findtext('dealAmount').strip().replace(',', ''))
                        all_data.append({
                            '계약일': f"{item.findtext('dealYear')}-{item.findtext('dealMonth').zfill(2)}-{item.findtext('dealDay').zfill(2)}",
                            '동': item.findtext('umdNm').strip(),
                            '아파트명': item.findtext('aptNm').strip(),
                            '면적': float(item.findtext('excluUseAr')),
                            '국토부 실거래가': price,
                        })
                    except: continue
            except: continue
        except: continue
    return all_data

@st.cache_data(ttl=60)
def get_land_data_api(api_key, region_code):
    if not api_key: return []
    months = get_recent_months(6)
    all_data = []
    base_url = "https://apis.data.go.kr/1613000/RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade"
    
    for ym in months:
        query_url = f"{base_url}?serviceKey={api_key}&LAWD_CD={region_code}&DEAL_YMD={ym}&numOfRows=1000&pageNo=1"
        try:
            response = requests.get(query_url, timeout=10, verify=False)
            try:
                root = ET.fromstring(response.content)
                if root.findtext('.//resultCode') not in ['00', '000']: continue
                for item in root.findall('.//item'):
                    try:
                        price = int(item.findtext('dealAmount').strip().replace(',', ''))
                        all_data.append({
                            '계약일': f"{item.findtext('dealYear')}-{item.findtext('dealMonth').zfill(2)}-{item.findtext('dealDay').zfill(2)}",
                            '동': item.findtext('umdNm').strip(),
                            '아파트명': item.findtext('jimok'), 
                            '면적': float(item.findtext('dealArea')),
                            '국토부 실거래가': price,
                        })
                    except: continue
            except: continue
        except: continue
    return all_data

# -----------------------------------------------------------------------------
# 4. 유틸리티
# -----------------------------------------------------------------------------
def get_links(region_name, dong, name, is_land=False):
    city = region_name[:2]
    q = f"{city} {dong} {name}"
    enc = urllib.parse.quote(q)
    if is_land: return {"kb": f"https://map.naver.com/p/search/{enc}", "naver": f"https://new.land.naver.com/search?sk={enc}"}
    return {"kb": f"https://kbland.kr/search?q={enc}", "naver": f"https://new.land.naver.com/search?sk={enc}"}

def get_interest_data(api_list, my_df, current_region):
    if not api_list: return pd.DataFrame()
    df_api = pd.DataFrame(api_list)
    region_df = my_df[my_df['지역'] == current_region]
    my_interests = set(zip(region_df['동'], region_df['아파트명']))
    df_interest = df_api[df_api.apply(lambda x: (x['동'], x['아파트명']) in my_interests, axis=1)].copy()
    
    found_interests = set(zip(df_interest['동'], df_interest['아파트명'])) if not df_interest.empty else set()
    dummy_rows = []
    for _, row in region_df.iterrows():
        if (row['동'], row['아파트명']) not in found_interests:
            dummy_rows.append({
                '계약일': '-', '동': row['동'], '아파트명': row['아파트명'], 
                '면적': None, '국토부 실거래가': None 
            })
    
    df_final = pd.concat([df_interest, pd.DataFrame(dummy_rows)], ignore_index=True)
    if df_final.empty: return pd.DataFrame()
    
    df_final['sort_date'] = df_final['계약일'].apply(lambda x: '9999-99-99' if x == '-' else x)
    return df_final.sort_values(by=['sort_date', '동'], ascending=[False, True]).drop(columns=['sort_date'])

def get_inferred_apt_name(api_data, input_name, input_dong):
    if not api_data or not input_name: return input_name
    dong_apts = list(set([d['아파트명'] for d in api_data if d['동'] == input_dong]))
    matches = get_close_matches(input_name, dong_apts, n=1, cutoff=0.2)
    return matches[0] if matches else input_name

# -----------------------------------------------------------------------------
# 5. 네이버 뉴스 수집
# -----------------------------------------------------------------------------
def clean_html(text):
    return re.sub('<.+?>', '', text).replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&')

def get_naver_news_list(client_id, client_secret, region_name, category, publisher_name, domain_key):
    if not client_id or not client_secret: return []
    city = region_name[:2]
    search_keyword = f"{city} 부동산" if category == "부동산" else city
    if publisher_name != "전체": search_keyword += f" {publisher_name}"
        
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    params = {"query": search_keyword, "display": 100 if publisher_name != "전체" else 20, "start": 1, "sort": "date"}
    
    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        if res.status_code == 200:
            items = res.json().get('items', [])
            news = []
            today = datetime.now().strftime("%Y-%m-%d")
            for item in items:
                link = item['link']
                originallink = item.get('originallink', '')
                if domain_key != "ALL":
                    if (domain_key not in link) and (domain_key not in originallink): continue
                try:
                    pub_date = datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S +0900")
                    date_str = pub_date.strftime("%Y-%m-%d")
                except: date_str = item['pubDate']
                
                news.append({
                    'title': clean_html(item['title']),
                    'link': originallink if originallink else link,
                    'date_str': date_str,
                    'is_today': date_str == today,
                    'source': publisher_name
                })
            return news[:20]
        return []
    except: return []

# -----------------------------------------------------------------------------
# 6. 메인 UI (배포용 Secrets 자동 로드 적용)
# -----------------------------------------------------------------------------
st.title("🏔️ 강원도 부동산 통합 관제 시스템")

# [배포용] Secrets 자동 로드 로직
# st.secrets에 키가 있으면 사용하고, 없으면 사이드바 입력창을 띄움
with st.sidebar:
    st.header("🔑 API 설정")
    
    # 1. 공공데이터 인증키
    if "public_api_key" in st.secrets:
        api_key_val = st.secrets["public_api_key"]
        st.success("✅ 공공데이터 키 자동 연결됨")
    else:
        api_key_val = st.text_input("공공데이터 인증키(Decoding)", type="password", help="secrets.toml에 'public_api_key'로 저장하면 자동 로드됩니다.")
    
    st.divider()
    
    # 2. 네이버 API 키
    if "naver_client_id" in st.secrets and "naver_client_secret" in st.secrets:
        naver_id = st.secrets["naver_client_id"]
        naver_secret = st.secrets["naver_client_secret"]
        st.success("✅ 네이버 검색 키 자동 연결됨")
    else:
        st.caption("뉴스 검색용 네이버 키")
        naver_id = st.text_input("Naver Client ID", type="password")
        naver_secret = st.text_input("Naver Client Secret", type="password")
    
    st.divider()

region_tabs = st.tabs(["춘천시", "원주시"])

common_config = {
    "kb_link": st.column_config.LinkColumn("KB", display_text="확인하기"),
    "naver_link": st.column_config.LinkColumn("네이버", display_text="확인하기"),
    "면적": st.column_config.NumberColumn(format="%.2f m²"),
    "국토부 실거래가": st.column_config.NumberColumn(label="국토부 실거래가 (만원)", format="%,d"),
}

def render_region_dashboard(region_name):
    r_code = REGIONS[region_name]["code"]
    r_dongs = REGIONS[region_name]["dongs"]
    r_pubs = REGIONS[region_name]["publishers"]
    
    raw_for_infer = []
    if api_key_val:
        raw_for_infer = get_apt_data_api(api_key_val, r_code)

    with st.sidebar:
        with st.expander(f"📌 {region_name} 관심 아파트 관리", expanded=True):
            with st.form(f"add_apt_{region_name}", clear_on_submit=True):
                c1, c2 = st.columns(2)
                input_dong = c1.selectbox("동 선택", r_dongs)
                input_name = c2.text_input("아파트명")
                if st.form_submit_button("추가"):
                    if input_name:
                        full_name = get_inferred_apt_name(raw_for_infer, input_name, input_dong)
                        if full_name != input_name: st.toast(f"💡 '{full_name}' 보정됨")
                        curr_df = load_my_apts()
                        cond = (curr_df['지역'] == region_name) & (curr_df['동'] == input_dong) & (curr_df['아파트명'] == full_name)
                        if not cond.any():
                            new_entry = pd.DataFrame({"지역": [region_name], "동": [input_dong], "아파트명": [full_name]})
                            save_my_apts(pd.concat([curr_df, new_entry], ignore_index=True))
                            st.rerun()

            st.caption(f"📋 {region_name} 관리 목록")
            my_df = load_my_apts()
            region_my_df = my_df[my_df['지역'] == region_name]
            for idx, row in region_my_df.iterrows():
                rc1, rc2 = st.columns([0.8, 0.2])
                rc1.text(f"[{row['동']}] {row['아파트명']}")
                if rc2.button("삭제", key=f"del_{region_name}_{idx}"):
                    save_my_apts(my_df.drop(idx))
                    st.rerun()

    st.markdown(f"### 🔍 {region_name} 실거래 현황")
    
    t1, t2, t3 = st.tabs(["🏢 아파트", "⛰️ 토지", "📰 지역 뉴스"])

    with t1:
        if api_key_val:
            sub_t1, sub_t2 = st.tabs(["♥ 관심 매물", "📋 전체 실거래"])
            with sub_t1:
                df_interest = get_interest_data(raw_for_infer, my_df, region_name)
                if not df_interest.empty:
                    df_interest['kb_link'] = df_interest.apply(lambda x: get_links(region_name, x['동'], x['아파트명'])['kb'] if x['아파트명'] != '-' else '-', axis=1)
                    df_interest['naver_link'] = df_interest.apply(lambda x: get_links(region_name, x['동'], x['아파트명'])['naver'] if x['아파트명'] != '-' else '-', axis=1)
                    st.dataframe(df_interest, column_config=common_config, column_order=["계약일", "동", "아파트명", "면적", "국토부 실거래가", "kb_link", "naver_link"], hide_index=True, use_container_width=True)
                else: st.info("관심 매물 거래가 없습니다.")
            with sub_t2:
                if raw_for_infer:
                    df_all = pd.DataFrame(raw_for_infer).sort_values(by="계약일", ascending=False)
                    df_all['kb_link'] = df_all.apply(lambda x: get_links(region_name, x['동'], x['아파트명'])['kb'], axis=1)
                    df_all['naver_link'] = df_all.apply(lambda x: get_links(region_name, x['동'], x['아파트명'])['naver'], axis=1)
                    st.dataframe(df_all, column_config=common_config, column_order=["계약일", "동", "아파트명", "면적", "국토부 실거래가", "kb_link", "naver_link"], hide_index=True, use_container_width=True)
                else: st.info("데이터가 없습니다.")
        else: st.warning("공공데이터 API 키가 필요합니다.")

    with t2:
        if api_key_val:
            l_raw = get_land_data_api(api_key_val, r_code)
            sub_l1, sub_l2 = st.tabs(["♥ 관심 동네", "📋 전체 실거래"])
            land_config = common_config.copy()
            land_config["아파트명"] = st.column_config.TextColumn("지목")

            with sub_l1:
                interest_dongs = my_df[my_df['지역'] == region_name]['동'].unique()
                if l_raw:
                    df_l = pd.DataFrame(l_raw)
                    df_l_int = df_l[df_l['동'].isin(interest_dongs)].sort_values(by="계약일", ascending=False)
                    if not df_l_int.empty:
                        df_l_int['kb_link'] = df_l_int.apply(lambda x: get_links(region_name, x['동'], x['아파트명'], True)['kb'], axis=1)
                        df_l_int['naver_link'] = df_l_int.apply(lambda x: get_links(region_name, x['동'], x['아파트명'], True)['naver'], axis=1)
                        st.dataframe(df_l_int, column_config=land_config, column_order=["계약일", "동", "아파트명", "면적", "국토부 실거래가", "kb_link", "naver_link"], hide_index=True, use_container_width=True)
                    else: st.info(f"관심 동네({', '.join(interest_dongs)})의 토지 거래가 없습니다.")
                else: st.info("데이터가 없습니다.")
            with sub_l2:
                if l_raw:
                    df_l_all = pd.DataFrame(l_raw).sort_values(by="계약일", ascending=False)
                    df_l_all['kb_link'] = df_l_all.apply(lambda x: get_links(region_name, x['동'], x['아파트명'], True)['kb'], axis=1)
                    df_l_all['naver_link'] = df_l_all.apply(lambda x: get_links(region_name, x['동'], x['아파트명'], True)['naver'], axis=1)
                    st.dataframe(df_l_all, column_config=land_config, column_order=["계약일", "동", "아파트명", "면적", "국토부 실거래가", "kb_link", "naver_link"], hide_index=True, use_container_width=True)
                else: st.info("데이터가 없습니다.")
        else: st.warning("공공데이터 API 키가 필요합니다.")

    with t3:
        st.subheader(f"📰 {region_name} 주요 소식")
        
        if not naver_id or not naver_secret:
            st.warning("네이버 API Key가 필요합니다.")
        else:
            nt1, nt2 = st.tabs(["🏠 부동산", "📑 일반/통합"])
            def create_news_tabs(cat_name):
                tabs = st.tabs([p['name'] for p in r_pubs])
                for i, tab in enumerate(tabs):
                    with tab:
                        pub_info = r_pubs[i]
                        items = get_naver_news_list(naver_id, naver_secret, region_name, cat_name, pub_info['name'], pub_info['domain_key'])
                        if items:
                            for n in items:
                                b = '<span class="badge-today">오늘</span>' if n['is_today'] else ''
                                st.markdown(f'<div class="news-box"><a href="{n["link"]}" target="_blank" class="news-title">{b}{n["title"]}</a><div class="news-meta">{n["source"]} | {n["date_str"]}</div></div>', unsafe_allow_html=True)
                        else: st.info(f"'{pub_info['name']}' 관련 최신 기사가 없습니다.")
            with nt1: create_news_tabs("부동산")
            with nt2: create_news_tabs("전체")

with region_tabs[0]: render_region_dashboard("춘천시")
with region_tabs[1]: render_region_dashboard("원주시")