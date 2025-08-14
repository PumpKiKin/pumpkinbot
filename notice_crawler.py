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
        # 다른 후보들 시도
        content = (
            s.select_one(".board-view .board-txt") or
            s.select_one(".bbs_view .view_con") or
            s.select_one(".contents") or
            s.select_one("article") or
            s.select_one("#content")
        )

    body_parts = []

    if content:
        # 이미지 처리
        for img in content.find_all("img"):
            img_url = urljoin(BASE_URL, img.get("src"))
            body_parts.append(f"![이미지]({img_url})")

        # 텍스트 처리
        text_only = clean_notice_content(content)
        if text_only:
            body_parts.append(text_only)


    # if content:
    #     # 이미지 처리
    #     for img in content.find_all("img"):
    #         img_url = urljoin(BASE_URL, img.get("src"))
    #         body_parts.append(f"![이미지]({img_url})")

    #     # 텍스트 처리
    #     text_only = content.get_text("\n", strip=True)
    #     if text_only:
    #         body_parts.append(text_only)

    body_text = "\n\n".join(body_parts)

    # 첨부파일 처리
    atts = []
    for a in s.select('a[href]'):
        href = a["href"]
        if any(k in href.lower() for k in ["download", "attach", "file", "files"]):
            atts.append({"name": a.get_text(strip=True), "url": urljoin(BASE_URL, href)})

    seen = set(); attachments = []
    for x in atts:
        if x["url"] not in seen:
            seen.add(x["url"]); attachments.append(x)

    title = (s.select_one("h3, h2, .title, .board-tit") or content)
    title_text = title.get_text(strip=True) if title else ""

    return {
        "url": url,
        "title": title_text,
        "body": body_text,
        "attachments": attachments
    }


def show_notices():
    st.subheader("공지사항")
    with st.spinner("목록 불러오는 중..."):
        df = fetch_notices()
    st.dataframe(df, use_container_width=True, hide_index=True)

    # st.divider()
    
    # 1) 선택 후 상세 보기
    titles = df["제목"].tolist()
    choice = st.selectbox("공지사항 자세히 보기", options=["선택 안 함"] + titles)
    if choice != "선택 안 함":
        url = df.loc[df["제목"] == choice, "링크"].iloc[0]
        with st.spinner("상세 불러오는 중..."):
            d = fetch_notice_detail(url)
        st.markdown(f"### {choice}")
        
        if "![이미지]" in d["body"]:
            st.write(d["body"] or "(본문을 찾지 못했습니다)")
        else:
            st.text(d["body"] or "(본문을 찾지 못했습니다)")
        
        if d["attachments"]:
            st.markdown("**첨부:**")
            for a in d["attachments"]:
                st.write(f"- [{a['name']}]({a['url']})")
    
    # 2) 공지사항 새로고침
    if st.button("공지사항 새로고침"):
            fetch_notices.clear()
            st.rerun()


def get_notice_content(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")

    content_div = soup.find("div", class_="boardContent")
    if not content_div:
        return "(본문을 찾지 못했습니다)"

    # <br> → 줄바꿈
    for br in content_div.find_all("br"):
        br.replace_with("\n")

    # 블록 태그(<p>, <div>, <li>)는 문단 구분용 줄바꿈
    for block in content_div.find_all(["p", "div", "li"]):
        block.insert_before("\n")
        block.insert_after("\n")

    # 인라인 태그는 줄바꿈 없이 텍스트만 합치기
    text = content_div.get_text()
    
    # 여러 줄바꿈을 하나로 정리
    lines = [line.strip() for line in text.splitlines()]
    clean_text = "\n".join(line for line in lines if line)

    return clean_text




def clean_notice_content(content):
    # 1. <br> 태그는 줄바꿈
    for br in content.find_all("br"):
        br.replace_with("\n")

    # 2. 문단 태그는 전후에 줄바꿈 삽입
    for block in content.find_all(["p", "div", "li"]):
        block.insert_before("\n")
        block.insert_after("\n")

    # 3. 인라인 태그는 그냥 풀어서 텍스트만 유지
    for inline in content.find_all(["span", "strong", "b", "em", "font"]):
        inline.unwrap()

    # 4. 전체 텍스트 추출
    text = content.get_text()

    # 5. 불필요한 연속 줄바꿈 정리
    lines = [line.strip() for line in text.splitlines()]
    clean_text = "".join(line for line in lines if line)

    return clean_text
