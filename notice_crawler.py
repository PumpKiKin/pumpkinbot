import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import streamlit as st
import re

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
            "작성자": author,
            "작성일": date,
            "조회수": views,
            "링크": href
        })

    return pd.DataFrame(data)

@st.cache_data(ttl=600)

def fetch_notice_detail(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser")

    # boardContent를 본문으로 잡기
    content = s.select_one(".boardContent")
    if not content:
        content = (
            s.select_one(".board-view .board-txt") or
            s.select_one(".bbs_view .view_con") or
            s.select_one(".contents") or
            s.select_one("article") or
            s.select_one("#content")
        )

    body_parts = []
    if content:
        for img in content.find_all("img"):
            img_url = urljoin(BASE_URL, img.get("src"))
            body_parts.append(f"![이미지]({img_url})")

        text_only = clean_notice_content(content)
        if text_only:
            body_parts.append(text_only)

    body_text = "\n".join(body_parts)

    atts = []
    for a in s.select('a[href]'):
        href = a["href"]
        if any(k in href.lower() for k in ["download", "attach", "file", "files"]):
            atts.append({"name": a.get_text(strip=True), "url": urljoin(BASE_URL, href)})

    seen = set()
    attachments = []
    for x in atts:
        if x["url"] not in seen:
            seen.add(x["url"])
            attachments.append(x)

    title = (s.select_one("h3, h2, .title, .board-tit") or content)
    title_text = title.get_text(strip=True) if title else ""

    return {
        "url": url,
        "title": title_text,
        "body": body_text,
        "attachments": attachments,
        "html": r.text  # HTML 원문 추가
    }


# def show_notices():
#     st.subheader("공지사항")
#     with st.spinner("목록 불러오는 중..."):
#         df = fetch_notices()
#     st.dataframe(df, use_container_width=True, hide_index=True)

#     titles = df["제목"].tolist()
#     choice = st.selectbox("공지사항 자세히 보기", options=["선택 안 함"] + titles)
#     if choice != "선택 안 함":
#         url = df.loc[df["제목"] == choice, "링크"].iloc[0]
#         with st.spinner("상세 불러오는 중..."):
#             d = fetch_notice_detail(url)

#         st.markdown(f"### {choice}")
#         st.markdown(d["body"] or "(본문을 찾지 못했습니다)")

#         # addFiles 안의 첨부파일만 추출
#         soup = BeautifulSoup(d["html"], "html.parser")
#         addfiles_links = [a["href"] for a in soup.select("ul.addFiles a")]

#         cjaqn = True
#         for a in d["attachments"]:
#             if a["url"] in addfiles_links and "개인정보/비밀번호 관리" not in a["name"]:
#                 if cjaqn:
#                     st.markdown("**첨부:**")
#                     cjaqn = False
#                 st.write(f"- [{a['name']}]({a['url']})")

#     if st.button("공지사항 새로고침"):
#         fetch_notices.clear()
#         st.rerun()

#     st.divider()
#     if st.button("캐시 지우고 전체 새로고침"):
#         st.cache_data.clear()
#         st.success("앱 캐시를 모두 지웠습니다. 다시 로딩합니다.")
#         time.sleep(1)
#         st.rerun()

def show_notices():
    st.subheader("공지사항")
    with st.spinner("목록 불러오는 중..."):
        df = fetch_notices()
    st.dataframe(df, use_container_width=True, hide_index=True)

    titles = df["제목"].tolist()
    choice = st.selectbox("공지사항 자세히 보기", options=["선택 안 함"] + titles)
    if choice != "선택 안 함":
        url = df.loc[df["제목"] == choice, "링크"].iloc[0]
        with st.spinner("상세 불러오는 중..."):
            d = fetch_notice_detail(url)

        st.markdown(f"### {choice}")
        st.markdown(d["body"] or "(본문을 찾지 못했습니다)")

        # addFiles 안의 첨부파일만 추출
        soup = BeautifulSoup(d["html"], "html.parser")
        addfiles_links = [a["href"] for a in soup.select("ul.addFiles a")]

        # 필터링된 첨부파일 리스트 생성
        filtered_attachments = [
            a for a in d["attachments"]
            if a["url"] in addfiles_links and "개인정보/비밀번호 관리" not in a["name"]
        ]

        # 첨부파일 출력
        if filtered_attachments:
            st.markdown("**첨부:**")
            for a in filtered_attachments:
                st.write(f"- [{a['name']}]({a['url']})")

    if st.button("공지사항 새로고침"):
        fetch_notices.clear()
        st.rerun()

    st.divider()
    if st.button("캐시 지우고 전체 새로고침"):
        st.cache_data.clear()
        st.success("앱 캐시를 모두 지웠습니다. 다시 로딩합니다.")
        time.sleep(1)
        st.rerun()


def clean_notice_content(content):
    for br in content.find_all("br"):
        br.replace_with("\n")
    text = content.get_text()
    clean_text = re.sub(r'\n{3,}', '\n\n', text)
    return clean_text.strip()