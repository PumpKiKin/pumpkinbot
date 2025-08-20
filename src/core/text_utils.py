import re

def normalize(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\u3000", " ")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    # 시간/요일 간단 정규화 예시
    t = t.replace("오전", "AM ").replace("오후", "PM ")
    return t.strip()
