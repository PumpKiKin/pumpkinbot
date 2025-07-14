import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 기본 URL은 서강대 도서관으로 고정하지 않고, 상속받는 클래스가 설정하도록 둡니다.

def clean_text(text: str) -> str:
    """여러 공백을 하나로, 앞뒤 공백 제거"""
    text = re.sub(r"\s+", " ", text)
    return text.strip()

class BaseScraper:
    def __init__(self, base_url: str):
        self.base_url = base_url
        
    def fetch_html(self, url: str) -> str:
        """문자열 HTML을 반환"""
        resp = requests.get(url)
        print(f"▶ [DEBUG] GET {url} → {resp.status_code}, len={len(resp.text)}")
        resp.raise_for_status()
        return resp.text

    def parse_html(self, html: str) -> BeautifulSoup:
        """HTML 문자열을 BeautifulSoup 객체로 변환"""
        return BeautifulSoup(html, "html.parser")

    def extract_text(self, soup: BeautifulSoup, parent_tag: str, parent_class: str, text_tag: str, text_class: str = None) -> list[str]:
        """부모 영역 내에서 특정 태그·클래스를 가진 텍스트 리스트 추출"""
        results = []
        parents = soup.find_all(parent_tag, class_=parent_class) if parent_class else [soup]
        for p in parents:
            for elem in p.find_all(text_tag, class_=text_class):
                results.append(clean_text(elem.get_text()))
        return results

    def extract_table(self, soup: BeautifulSoup, parent_tag: str, parent_class: str, table_tag: str = "table") -> list[dict]:
        """부모 영역 내의 테이블을 구조화된 리스트(dict)로 반환"""
        parent = soup.find(parent_tag, class_=parent_class)
        if not parent:
            return []
        table = parent.find(table_tag)
        if not table:
            return []
        # 헤더 추출
        headers = [clean_text(th.get_text()) for th in table.find_all("thead")[0].find_all("th")]
        rows = []
        for tr in table.find("tbody").find_all("tr"):
            cols = [clean_text(td.get_text()) for td in tr.find_all("td")]
            if len(cols) == len(headers):
                rows.append(dict(zip(headers, cols)))
        return rows

    def extract_qna(self, soup: BeautifulSoup, parent_tag: str, parent_class: str,
                    question_tag: str, answer_tag: str) -> list[str]:
        """QnA 형태(질문-답변) 텍스트 리스트로 반환"""
        results = []
        parent = soup.find(parent_tag, class_=parent_class)
        if not parent:
            return results
        questions = parent.find_all(question_tag)
        answers   = parent.find_all(answer_tag)
        for q, a in zip(questions, answers):
            q_text = clean_text(q.get_text())
            a_text = clean_text(a.get_text())
            results.append(f"Q: {q_text} A: {a_text}")
        return results

    def extract_key_value(self, soup: BeautifulSoup, parent_tag: str, parent_class: str,
                            item_tag: str = "li", key_tag: str = "span") -> dict:
        """부모 영역 내 li 요소를 key: value 쌍으로 반환"""
        data = {}
        parent = soup.find(parent_tag, class_=parent_class)
        if not parent:
            return data
        for li in parent.find_all(item_tag):
            key_elem = li.find(key_tag)
            key = clean_text(key_elem.get_text()) if key_elem else ""
            value = clean_text(li.get_text().replace(key, "")) if key else clean_text(li.get_text())
            data[key or f"_misc_{len(data)+1}"] = value
        return data
