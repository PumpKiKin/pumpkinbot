from bs4 import BeautifulSoup
from .base import BaseScraper, clean_text
from src.data_manager import DataManager
from src.config_loader import load_config
from urllib.parse import urljoin, urlparse
from collections import defaultdict

# 설정 로드
cfg = load_config("crawler")
dm  = DataManager("menu")  # key="menu" → save_directory + filenames["menu"]

class MenuScraper(BaseScraper):
    def __init__(self):
        super().__init__(cfg["base_url"])
        self.items = []

    def extract_menu_items(self, section):
        """
        section: <li class="wholeMenuX"> 한 덩어리 블록
        → category: 최상위 <a> title
        → sub-ul 트리를 재귀 순회하며 (category, parent_subcat, title, url) 생성
        """
        menu_items = []
        # 1) 최상위 카테고리
        cat_a = section.find("a", recursive=False)
        if not cat_a:
            return menu_items
        category = cat_a.get("title", "").strip()

        # 2) 재귀 함수 정의
        def walk(ul_tag, parent_subcat):
            # ul_tag 바로 아래의 li만 순회
            for li in ul_tag.find_all("li", recursive=False):
                a = li.find("a", recursive=False)
                if not a or not a.get("href"):
                    continue
                title = a.get("title", "").strip() or clean_text(a.get_text())
                href  = a["href"].strip()
                # URL 조립 (절대/상대 모두 처리)
                url = href if href.startswith("http") else urljoin(self.base_url, href)

                # append this item
                menu_items.append({
                    "category":    category,
                    "subcategory": parent_subcat,
                    "title":       title,
                    "url":         url
                })

                # 자식 ul이 있으면, 이 title을 parent_subcat로 내려서 다시 순회
                child_ul = li.find("ul", recursive=False)
                if child_ul:
                    walk(child_ul, title)

        # 3) 최상위 ul 태그 찾아서 재귀 시작
        top_ul = section.find("ul", recursive=False)
        if top_ul:
            walk(top_ul, "")   # 최상위에선 parent_subcat = 빈 문자열

        return menu_items

    def run(self):
        html = self.fetch_html(self.base_url)
        soup = self.parse_html(html)

        sections = soup.select(cfg["menus"]["css_selector"])
        for sec in sections:
            self.items.extend(self.extract_menu_items(sec))

        print(f"▶ [DEBUG] 수집 전 메뉴 아이템 수: {len(self.items)}")

        # ─── URL별로 그룹핑 후, 자식(subcategory)이 있으면 부모 빈(subcategory="") 항목 제거 ───
        grouped = defaultdict(list)
        for item in self.items:
            grouped[item["url"]].append(item)

        filtered = []
        for url, entries in grouped.items():
            # 같은 URL 중 subcategory가 비어있지 않은 항목만 추출
            non_empty = [e for e in entries if e["subcategory"]]
            if non_empty:
                filtered.extend(non_empty)
            else:
                # 모두 빈 subcategory인 경우는 원본 그대로
                filtered.extend(entries)

        self.items = filtered
        print(f"▶ [DEBUG] 필터 후  메뉴 아이템 수: {len(self.items)}")

        # JSON으로 저장
        dm.save(self.items)

def main():
    MenuScraper().run()
