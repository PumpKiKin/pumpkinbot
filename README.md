# pumpkinbot

### 실행 명령어
#### 1) 의존성 설치
```bash
poetry install
```
#### 2) 실행
```bash
PYTHONPATH=src poetry run streamlit run src/app/ui_app.py
```

1) python notice_crawler.py
: 최신 공지사항을 불러와 notiecs.json 파일을 만든다.
2) faiss_index 폴더를 지운다.
3) streamlit run chatbot.py
: 챗봇이 실행된다. 이때 새로운 faiss_index 폴더가 자동적으로 만들어진다.

### 참고
데이터가 되는 .json은 위 명령어를 실행하면 딱 한 번 DB에 저장되게 만들었다.
