import re
from collections import deque
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from src.app.crawler.base import BaseScraper, clean_text
from src.data_manager import DataManager
from src.config_loader import load_config

cfg = load_config("crawler")
dm  = DataManager("detail")

class DetailScraper(BaseScraper):
    def __init__(self, menu_items):
        super().__init__(cfg["base_url"])
        self.queue   = deque(menu_items)
        self.details = []
        self.visited = set()

    def _parse_block(self, block, desc, key):
        # —————————————————————————————————————————————
        # 0) block 자체가 UL(pdl14, subjectGuide 등)일 경우, 직접 LI 파싱
        if block.name == "ul":
            items = [
                clean_text(li.get_text())
                for li in block.find_all("li", recursive=False)
            ]
            if items:
                desc.setdefault(key, []).extend(items)
            # 이 후에도 <p>나 표 파싱은 필요할 수 있으므로 return 하지 않습니다.
        # —————————————————————————————————————————————
        # 1) 모든 <p>
        for p in block.select("p"):
            txt = clean_text(p.get_text())
            if txt:
                desc.setdefault(key, []).append(txt)

        # 2) 강조 목록(li.mBgn)
        for li in block.select("ul li.mBgn"):
            txt = clean_text(li.get_text())
            desc.setdefault(key, []).append(txt)

        # 3) 일반 리스트
        for ul in block.select("ul.pdl14"):
            items = [ clean_text(li.get_text()) for li in ul.select("li") ]
            if items:
                desc.setdefault(key, []).extend(items)

        # 4) guideTable 표
        tbl = block.select_one("div.guideTable.type2 table")
        if tbl:
            table = {}
            for tr in tbl.select("tbody tr"):
                cols = tr.select("td")
                if len(cols)==2:
                    k = clean_text(cols[0].get_text())
                    vals = [ clean_text(s.get_text()) for s in cols[1].select("span.tableList") ]
                    if not vals:
                        vals = [ clean_text(li.get_text()) for li in cols[1].select("li") ]
                    table[k] = vals
            desc[key] = table  # 표가 있으면 리스트 덮어쓰기

    def extract_detail(self, entry):
        # 1) entry unpack
        url, category, subcategory, title = (
            entry["url"],
            entry["category"],
            entry["subcategory"],
            entry["title"],
        )

        # 2) HTML → soup
        html = self.fetch_html(url)
        soup = self.parse_html(html)

        # 3) 현재 선택된 탭 이름
        tab_el = soup.select_one(cfg["detail"]["tab_selector"])
        tab = clean_text(tab_el.get_text()) if tab_el else title

        # 4) 본문 컨테이너
        container = soup.select_one(cfg["detail"]["raw_container"])
        if not container:
            self.details.append({
                "category":    category,
                "subcategory": subcategory,
                "title":       title,
                "tab":         tab,
                "url":         url,
                "description": {},
                "contact":     {},
                #"raw_html":    html,
            })
            return

        raw_html = container.decode_contents()

        # ─── contact 파싱 ─────────────────────────────────────────
        contact = {}
        for cd in container.select(cfg["detail"]["contacts"]["selector"]):
            first_li = cd.select_one("ul > li")
            span0    = first_li.select_one("span") if first_li else None
            if not span0:
                continue
            dept = clean_text(span0.get_text()); span0.extract()
            info = {"부서명": clean_text(first_li.get_text().lstrip(": "))}
            for li in cd.select("ul > li")[1:]:
                sp = li.select_one("span")
                if not sp:
                    continue
                k = clean_text(sp.get_text().rstrip(":")); sp.extract()
                v = clean_text(li.get_text()).lstrip(": ")
                if cfg["detail"]["contacts"]["strip_tel"]:
                    v = re.sub(r'^[Tt]el\.?\s*', "", v)
                info[k] = v
            contact[dept] = info
        if len(contact) == 1:
            _, contact = contact.popitem()

        # ─── description 구축 ──────────────────────────────────────
        desc = {}

        # 1) intro_block (탭 제목 바로 아래 처음 단락/강조)
        ib = cfg["detail"].get("intro_block")
        if ib:
            section_key = title if ib["section"] == "from_title" else ib["section"]
            for el in container.select(ib["selector"]):
                desc.setdefault(section_key, [])
                self._parse_block(el, desc, section_key)

        # 2) list_sections (h3, h4 등 기준 블록)
        for ls in cfg["detail"]["list_sections"]:
            for hdr in container.select(ls["name_from"]):
                sec = clean_text(hdr.get_text())
                if sec == "문의":
                    continue

                # find associated block
                sel = ls["selector"]
                tag, _, cls = sel.partition(".")
                if cls:
                    block = hdr.find_next_sibling(tag, class_=cls)
                else:
                    block = hdr.find_next_sibling(tag)
                if not block:
                    parent_li = hdr.find_parent("li")
                    if parent_li:
                        block = (
                            parent_li.find(tag, class_=cls)
                            if cls else
                            parent_li.find(tag)
                        )
                if not block:
                    continue

                # init slot
                if ls.get("drilldown"):
                    desc.setdefault(sec, {})
                else:
                    desc.setdefault(sec, [])

                # 일반 파싱 (현재 페이지 리스트/표)
                if not ls.get("drilldown"):
                    self._parse_block(block, desc, sec)

                # inline drilldown → 자식 페이지 바로 파싱
                else:
                    for a in block.select(cfg["detail"]["drilldown"]["link_selector"]):
                        link_text = clean_text(a.get_text())
                        href = a.get("href", "").strip()
                        if not href or href.startswith("javascript"):
                            continue

                        # fetch child page
                        child_url  = href if href.startswith("http") else urljoin(self.base_url, href)
                        child_html = self.fetch_html(child_url)
                        child_soup = self.parse_html(child_html)
                        child_cont = child_soup.select_one(cfg["detail"]["raw_container"])
                        if not child_cont:
                            continue

                        # prepare child slot
                        desc[sec].setdefault(link_text, [])

                        # a) child intro_block
                        if ib:
                            for el in child_cont.select(ib["selector"]):
                                self._parse_block(el, desc[sec], link_text)

                        # b) child list_sections
                        for ls2 in cfg["detail"]["list_sections"]:
                            for hdr2 in child_cont.select(ls2["name_from"]):
                                sub2 = clean_text(hdr2.get_text())
                                if sub2 == "문의":
                                    continue
                                # find block2
                                sel2 = ls2["selector"]
                                tag2, _, cls2 = sel2.partition(".")
                                if cls2:
                                    blk2 = hdr2.find_next_sibling(tag2, class_=cls2)
                                else:
                                    blk2 = hdr2.find_next_sibling(tag2)
                                if not blk2:
                                    pl2 = hdr2.find_parent("li")
                                    if pl2:
                                        blk2 = (
                                            pl2.find(tag2, class_=cls2)
                                            if cls2 else
                                            pl2.find(tag2)
                                        )
                                if not blk2:
                                    continue
                                # parse into the same child bucket
                                self._parse_block(blk2, desc[sec], link_text + " / " + sub2)

                        # c) child secondary tabs
                        st = cfg["detail"]["secondary_tabs_selector"]
                        sb = cfg["detail"]["secondary_content_selector"]
                        if st and sb:
                            titles = [clean_text(li.get_text()) for li in child_cont.select(st)]
                            blocks = child_cont.select(sb)
                            for t2, blk2 in zip(titles, blocks):
                                self._parse_block(blk2, desc[sec], link_text + " / " + t2)

                        # d) flatten 단일값
                        for kk, vv in list(desc[sec].items()):
                            if isinstance(vv, list) and len(vv) == 1:
                                desc[sec][kk] = vv[0]

        # 3) secondary tabs (부탭)
        st = cfg["detail"]["secondary_tabs_selector"]
        sb = cfg["detail"]["secondary_content_selector"]
        if st and sb:
            titles = [clean_text(li.get_text()) for li in container.select(st)]
            blocks = container.select(sb)
            for t, blk in zip(titles, blocks):
                desc.setdefault(t, [])
                self._parse_block(blk, desc, t)

        # 4) flatten 최종 단일 리스트
        for k, v in list(desc.items()):
            if isinstance(v, list) and len(v) == 1:
                desc[k] = v[0]

        # 5) 결과 저장
        self.details.append({
            "category":    category,
            "subcategory": subcategory,
            "title":       title,
            "tab":         tab,
            "url":         url,
            "description": desc,
            "contact":     contact,
            #"raw_html":    raw_html,
        })


    def run(self):
        allowed_netloc = urlparse(self.base_url).netloc
        while self.queue:
            entry = self.queue.popleft()
            url = entry["url"]

            # 0) 메뉴 포맷 정규화
            if not isinstance(entry, dict):
                u,c,s,t = entry
                entry = {"url":u,"category":c,"subcategory":s,"title":t}
            
            # 1) 중복 방지
            key = (entry["url"], entry["category"], entry["subcategory"], entry["title"])
            if key in self.visited:
                continue
            self.visited.add(key)

            # 2) 도메인 필터
            netloc = urlparse(url).netloc
            if netloc and netloc != allowed_netloc:
                print(f"⚠️ 스킵(도메인 불일치): {url}")
                continue

            print(f"▶ 크롤링: {entry['category']} / {entry['subcategory']} / {entry['title']} → {url}")
            try:
                # 3) 상세 파싱 (한 번만)
                self.extract_detail(entry)
            except Exception as e:
                print(f"❌ 에러 건너뜀: {url} → {e}")
                continue

            # 다시 HTML 로드 (탭 링크를 바깥(raw) 컨테이너가 아닌 tab_container에서만 찾기)
            html2 = self.fetch_html(entry["url"])
            soup2 = self.parse_html(html2)

                
            # — 메인 탭만 —
            tab_dom = soup2.select_one(cfg["detail"]["tab_container"])
            if tab_dom:
                for a in tab_dom.select(cfg["detail"]["tab_selector"]):
                    href = a.get("href","").strip()
                    if href and not href.startswith("javascript"):
                        url2 = href if href.startswith("http") else urljoin(self.base_url, href)
                        if urlparse(url2).netloc == urlparse(self.base_url).netloc:
                            self.queue.append({
                                "url":         url2,
                                "category":    entry["category"],
                                "subcategory": entry["title"],
                                "title":       clean_text(a.get_text())
                            })

            # — 내부 탭도 같은 container에서 —
            inner_dom = soup2.select_one(cfg["detail"]["inner_tab_container"])
            if inner_dom:
                for a in inner_dom.select(cfg["detail"]["inner_tab_selector"]):
                    href = a.get("href","").strip()
                    if href and not href.startswith("javascript"):
                        url2 = href if href.startswith("http") else urljoin(self.base_url, href)
                        if urlparse(url2).netloc == urlparse(self.base_url).netloc:
                            self.queue.append({
                                "url":         url2,
                                "category":    entry["category"],
                                "subcategory": entry["title"],
                                "title":       clean_text(a.get_text())
                            })


        dm.save(self.details)

def main():
    menu = DataManager("menu").load()
    scraper = DetailScraper(menu)
    scraper.run()
