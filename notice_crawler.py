import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import streamlit as st

BASE_URL = "https://library.sogang.ac.kr"
NOTICE_URL = "https://library.sogang.ac.kr/bbs/list/1"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SogangNoticeBot/1.0)"}

@st.cache_data(ttl=300)
def fetch_notices():
    resp = requests.get(NOTICE_URL, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # print(soup.prettify()[:1500])

    rows = soup.select("table tbody tr")
    data = []
    for tr in rows:
        cols = tr.find_all("td")
        if len(cols) < 5:
            continue
        no = cols[0].get_text(strip=True)
        title_cell = cols[1]
        a = title_cell.find("a")
        title = a.get_text(strip=True) if a else title_cell.get_text(strip=True)
        href = urljoin(BASE_URL, a["href"]) if a and a.has_attr("href") else NOTICE_URL
        author = cols[2].get_text(strip=True)
        date = cols[3].get_text(strip=True)
        views = cols[4].get_text(strip=True)

        data.append({
            "No.": no,
            "제목": title,
            "링크": href,
            "작성자": author,
            "작성일": date,
            "조회수": views
        })

    return pd.DataFrame(data)

def show_notices():
    st.subheader("공지사항")
    with st.spinner("공지 불러오는 중..."):
        df = fetch_notices()
    st.dataframe(df, use_container_width=True)

    if st.button("지금 바로 새로고침"):
        fetch_notices.clear()
        st.rerun()
