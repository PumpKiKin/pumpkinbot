import os
from collections import deque
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from src.app.crawler.base import BaseScraper, clean_text
from src.data_manager import DataManager
from src.config_loader import load_config

# 설정 로드
cfg = load_config("crawler")
dm  = DataManager("detail")  # key="detail" → save_directory + filenames["detail"]

class DetailScraper(BaseScraper):
    """config/crawler.yaml 의 detail 규칙에 따라 상세 페이지를 크롤링해 JSON으로 저장."""
    def __init__(self, menu_items):
        super().__init__(cfg["base_url"])
        # menu_items: dict 리스트 {"url","category","subcategory","title"}
        self.queue   = deque(menu_items)
        self.details = []
        self.visited = set()

    def extract_detail(self, entry: dict):
        """단일 entry에 대해 raw_html, description, contact을 파싱하여 self.details에 추가."""
        url         = entry["url"]
        category    = entry["category"]
        subcategory = entry["subcategory"]
        title       = entry["title"]

        # Fetch & parse
        html = self.fetch_html(url)
        soup = self.parse_html(html)

        # Container: 대부분 #divContents 또는 #divContent 아래 정보
        container = soup.select_one("#divContents") or soup.select_one("#divContent")
        raw_html = container.decode_contents() if container else html

        # 기본 구조화 파싱
        descriptions = []
        for blk in cfg.get("detail", {}).get("text_blocks", []):
            p, e = blk["parent"], blk["extract"]
            descriptions.extend(
                self.extract_text(
                    container or soup,
                    p["tag"], p.get("class"),
                    e["tag"], e.get("class")
                )
            )
        for tbl in cfg.get("detail", {}).get("tables", []):
            p = tbl["parent"]
            td = self.extract_table(
                container or soup,
                p["tag"], p.get("class"), tbl.get("table_tag", "table")
            )
            if td:
                descriptions.extend(td)
        qna_cfg = cfg.get("detail", {}).get("qna", {})
        if qna_cfg:
            q = qna_cfg["parent"]
            descriptions.extend(
                self.extract_qna(
                    container or soup,
                    q["tag"], q.get("class"),
                    question_tag=qna_cfg.get("question"),
                    answer_tag=  qna_cfg.get("answer")
                )
            )
        contact = self.extract_key_value(container or soup, "div", "contact2") or None

        # Append initial detail
        self.details.append({
            "category":    category,
            "subcategory": subcategory,
            "title":       title,
            "url":         url,
            "description": descriptions,
            "contact":     contact,
            "raw_html":    raw_html
        })

        # Page-specific logic
        page_types = cfg.get("detail", {}).get("page_types", {})
        for pt in page_types.values():
            detect_sel = pt.get("detect")
            if detect_sel and container and container.select_one(detect_sel):
                self.apply_page_specific_logic(container, pt.get("extract", []))
                break

    def apply_page_specific_logic(self, container: BeautifulSoup, rules: list):
        """
        컨테이너와 페이지 타입별 extract 규칙을 받아
        self.details 마지막 엔트리의 description을 보강합니다.
        """
        detail = self.details[-1]
        desc = detail.get("description", [])

        for rule in rules:
            # text_blocks
            if "text_blocks" in rule:
                cfg_tb = rule["text_blocks"]
                sel = cfg_tb.get("selector")
                if sel:
                    for el in container.select(sel):
                        text = clean_text(el.get_text(separator=" ", strip=True))
                        desc.append(text)
            # tables
            if "tables" in rule:
                cfg_tbl = rule["tables"]
                sel = cfg_tbl.get("selector")
                if sel:
                    for tbl_parent in container.select(sel):
                        sub_soup = BeautifulSoup(str(tbl_parent), "html.parser")
                        td = self.extract_table(
                            sub_soup,
                            cfg_tbl.get("parent_tag", "div"),
                            cfg_tbl.get("parent_class"),
                            cfg_tbl.get("table_tag", "table")
                        )
                        for row in td:
                            desc.append(row)
            # qna
            if "qna" in rule:
                cfg_qna = rule["qna"]
                ps, qs, ans = cfg_qna.get("parent_selector"), cfg_qna.get("question_selector"), cfg_qna.get("answer_selector")
                if ps and qs and ans:
                    for section in container.select(ps):
                        questions = section.select(qs)
                        answers = section.select(ans)
                        for q, a in zip(questions, answers):
                            q_text = clean_text(q.get_text(separator=" ", strip=True))
                            a_text = clean_text(a.get_text(separator=" ", strip=True))
                            desc.append(f"Q: {q_text} A: {a_text}")
        detail["description"] = desc

    def run(self):
        """메뉴 리스트로부터 시작해, 상세 + 탭을 재귀적으로 모두 크롤링 후 저장."""
        while self.queue:
            entry = self.queue.popleft()
            if not isinstance(entry, dict):
                u, c, s, t = entry
                entry = {"url":u, "category":c, "subcategory":s, "title":t}

            key = (entry["url"], entry["category"], entry["subcategory"], entry["title"])
            if key in self.visited:
                continue
            self.visited.add(key)

            print(f"▶ 크롤링: {entry['category']} / {entry['subcategory']} / {entry['title']} → {entry['url']}")
            self.extract_detail(entry)

            # 탭(하위 카테고리) 링크 수집
            html = self.fetch_html(entry["url"])
            soup = self.parse_html(html)
            tab_sel = cfg.get("detail", {}).get(
                "tab_selector",
                "#mTS_1_container li.mTSThumbContainer a"
            )
            for a in soup.select(tab_sel):
                href = a.get("href", "").strip()
                if not href or href.startswith("javascript"):
                    continue
                if href.startswith("http"):
                    tab_url = href
                else:
                    tab_url = urljoin(self.base_url, href)
                # 내부 도메인만
                if urlparse(tab_url).netloc != urlparse(self.base_url).netloc:
                    print(f"⚠️ 외부 링크 스킵: {tab_url}")
                    continue
                self.queue.append({
                    "url":         tab_url,
                    "category":    entry["category"],
                    "subcategory": entry["title"],
                    "title":       clean_text(a.get_text())
                })
        dm.save(self.details)


def main():
    menu_items = DataManager("menu").load()
    scraper = DetailScraper(menu_items)
    scraper.run()
