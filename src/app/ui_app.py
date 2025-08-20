import streamlit as st
from services.chat_service import ChatService
from services.notice_crawler import show_notices
import warnings

warnings.filterwarnings("ignore", category=FutureWarning, module="torch")

@st.cache_resource
def get_service():
    return ChatService()

st.set_page_config("로욜라도서관 FAQ 챗봇", layout="wide")
left, right = st.columns([1, 1])

with left:
    st.header("로욜라도서관 FAQ 챗봇")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if st.sidebar.button("대화 초기화"):
        st.session_state.chat_history = []

    q = st.text_input("로욜라 도서관에 대해서 질문해 주세요", placeholder="방학 중 도서관 이용 시간은?")
    if q:
        st.session_state.chat_history.append({"role": "user", "content": q})
        svc = get_service()
        ans = svc.answer(q, st.session_state.chat_history)
        st.session_state.chat_history.append({"role": "assistant", "content": ans.text})

    for m in st.session_state.chat_history[-12:]:
        st.chat_message("user" if m["role"]=="user" else "assistant").write(m["content"])

    if q and ans.sources:
        for s in ans.sources:
            with st.expander("관련 문서"):
                st.write(s.snippet)
                if s.url:
                    st.write(s.url)

with right:
    show_notices()
