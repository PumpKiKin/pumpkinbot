## streamlit 모듈 불러오기
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.documents.base import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.prompts import PromptTemplate
from langchain_core.runnables import Runnable
from langchain.schema.output_parser import StrOutputParser
from typing import List
import os
import re
import json

## 환경변수 불러오기
from dotenv import load_dotenv,dotenv_values
load_dotenv()

from notice_crawler import show_notices

############################### 0단계 : 대화 맥락 유지 관련 HISTORY 함수들 ##########################
# 세션 히스토리 초기화
if "chat_history" not in st.session_state:
    # role: "user" | "assistant"
    st.session_state.chat_history = []
if "summary" not in st.session_state:
    st.session_state.summary = ""   # (선택) 요약 버퍼

# 리셋 버튼
st.sidebar.button("대화 초기화", on_click=lambda: (st.session_state.update(chat_history=[]), st.session_state.update(summary="")))

# 히스토리 포맷터
def format_history_for_prompt(history, window_size=8):
    """프롬프트에 넣을 수 있게 간단 문자열로 정리"""
    recent = history[-window_size:]
    lines = []
    for m in recent:
        prefix = "사용자" if m["role"] == "user" else "어시스턴트"
        lines.append(f"{prefix}: {m['content']}")
    return "\n".join(lines)



############################### 1단계 : JSON 문서를 벡터DB에 저장하는 함수들 ##########################

## 1: 임시폴더에 파일 저장, 이제 이 함수는 사용하지 않음(데이터 업로드 X, 내장 O)
def save_uploadedfile(uploadedfile: UploadedFile) -> str : 
    temp_dir = "JSON_임시폴더"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    file_path = os.path.join(temp_dir, uploadedfile.name)
    with open(file_path, "wb") as f:
        f.write(uploadedfile.read()) 
    return file_path

## 2: 저장된 JSON 파일을 Document로 변환
def json_to_documents(json_path:str) -> List[Document]:
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = []
    for i, item in enumerate(data):
        content = item.get("description", "")
        
         # list 처리: 내부에 dict가 있는 경우를 포함하여 문자열로 변환
        if isinstance(content, list):
            content = "\n".join(
                [elem if isinstance(elem, str) else json.dumps(elem, ensure_ascii=False) for elem in content]
            )
        # dice 처리: key: value 형식으로 변환
        elif isinstance(content, dict):
            content = "\n".join(f"{key}: {value}" for key, value in content.items())

        # metadata 불러오기(.json의 구조를 참고해야 함)
        metadata = {
            "category": item.get("category", ""),
            "subcategory": item.get("subcategory", ""),
            "title": item.get("title", ""),
            "url": item.get("url", ""),
        }
        documents.append(Document(page_content=content, metadata=metadata))

    return documents

## 3: Document를 더 작은 document로 변환
def chunk_documents(documents: List[Document]) -> List[Document]:
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    return text_splitter.split_documents(documents)

## 4: Document를 벡터DB로 저장
def save_to_vector_store(documents: List[Document]) -> None:
    embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sbert-nli")
    vector_store = FAISS.from_documents(documents, embedding=embeddings)
    vector_store.save_local("faiss_index")



############################### 2단계 : RAG 기능 구현과 관련된 함수들 ##########################


## 사용자 질문에 대한 RAG 처리
@st.cache_data
def process_question(user_question, history_text):

    embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sbert-nli")

    ## 벡터 DB 호출
    new_db = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)

    ## 관련 문서 3개를 호출하는 Retriever 생성
    retriever = new_db.as_retriever(search_kwargs={"k": 3})
    ## 사용자 질문을 기반으로 관련문서 3개 검색 
    retrieve_docs : List[Document] = retriever.invoke(user_question)

    ## RAG 체인 선언
    chain = get_rag_chain()
    ## 질문과 문맥을 넣어서 체인 결과 호출
    response = chain.invoke({
        "question": user_question, 
        "context": retrieve_docs,
        "history": history_text
    })

    return response, retrieve_docs



def get_rag_chain() -> Runnable:
    template = """
    다음의 컨텍스트를 활용해서 질문에 답변해줘
    - 질문에 대한 응답을 해줘
    - 간결하게 5줄 이내로 해줘
    - 곧바로 응답결과를 말해줘
    
    이전대화 : {history}

    컨텍스트 : {context}

    질문: {question}

    응답:"""

    custom_rag_prompt = PromptTemplate.from_template(template)
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
    return custom_rag_prompt | model | StrOutputParser() # pipe로 관리하여 in-out 쉽게 넣어주기



############################### 3단계 : 응답결과와 문서를 함께 보도록 도와주는 함수 ##########################
@st.cache_data(show_spinner=False)
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text for text in re.split(r'(\d+)', s)]

def main():

    if not os.path.exists("faiss_index"):
        json_file = "database/test_data.json"
        json_document = json_to_documents(json_file)
        smaller_documents = chunk_documents(json_document)
        save_to_vector_store(smaller_documents)

    st.set_page_config("로욜라도서관 FAQ 챗봇", layout="wide")

    left_column, right_column = st.columns([1, 1]) # 화면 왼쪽에 채팅, 오른쪽에 참고 텍스트
    with left_column:
        st.header("로욜라도서관 FAQ 챗봇")
        # json_file = st.file_uploader("JSON Uploader", type="json")
        # button = st.button("JSON 업로드하기")
        # if json_file and button:
        #     with st.spinner("JSON 문서 저장 중"):
        #         json_path = save_uploadedfile(json_file)
        #         json_document = json_to_documents(json_path)
        #         smaller_documents = chunk_documents(json_document)
        #         save_to_vector_store(smaller_documents)
        user_question = st.text_input("로욜라 도서관에 대해서 질문해 주세요", 
                                    placeholder="방학 중 도서관 이용 시간은 어떻게 되나요?")
    
    if user_question:
        # 1) 사용자 질문 히스토리에 추가
        st.session_state.chat_history.append({"role": "user", "content": user_question})

        # 2) 히스토리 윈도우를 프롬프트용 텍스트로 변환
        history_text = format_history_for_prompt(st.session_state.chat_history, window_size=8)

        # 3) 응답 생성
        response, context = process_question(user_question, history_text)

        # 4) 어시스턴트 응답을 히스토리에 추가
        st.session_state.chat_history.append({"role": "assistant", "content": response})

        # 5) 좌측: 대화 렌더링
        with left_column:
            for msg in st.session_state.chat_history[-12:]:  # 최근 12개만 표시
                if msg["role"] == "user":
                    st.chat_message("user").write(msg["content"])
                else:
                    st.chat_message("assistant").write(msg["content"])

        # 6) 우측: 근거 문서
        with right_column:
            show_notices()

            for document in context:
                with st.expander("관련 문서"):
                    st.text(document.page_content)
                    st.text(document.metadata.get('url', ''))

if __name__ == "__main__":
    main()