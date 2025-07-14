import os
import json
from src.config_loader import load_config

# crawler 설정 로드
cfg = load_config("crawler")
SAVE_DIR   = cfg["save_directory"]
FILENAMES  = cfg["filenames"]

class DataManager:
    def __init__(self, key: str):
        """
        key: "menu" 또는 "detail"
        """
        # config에서 디렉터리와 파일명 가져오기
        filename = FILENAMES.get(key)
        if not filename:
            raise ValueError(f"No filename configured for key '{key}'")

        self.path = os.path.join(SAVE_DIR, filename)
        os.makedirs(SAVE_DIR, exist_ok=True)
        self.buffer = []

    def save(self, data):
        """중복제거 후 JSON 저장"""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"▶ [INFO] 데이터 저장 완료: {self.path}")

    def load(self):
        """기존 JSON 로드 (없으면 빈 리스트)"""
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)
