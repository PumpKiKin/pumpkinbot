## streamlit 관련 모듈 불러오기
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.documents.base import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.prompts import PromptTemplate
from langchain_core.runnables import Runnable
from langchain.schema.output_parser import StrOutputParser
from langchain_community.document_loaders import PyMuPDFLoader
from typing import List
import os
import fitz  # PyMuPDF
import re

## json 관련 모듈 불러오기
import json


## 환경변수 불러오기
from dotenv import load_dotenv,dotenv_values
load_dotenv()



############################### 1단계 : JSON 문서를 벡터DB에 저장하는 함수들 ##########################

## 1: 임시폴더에 파일 저장
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
        
        # if isinstance(content, list):
        #     content = "\n".join(content)
        # elif isinstance(content, dict):
        #     content = "\n".join(f"{key}:{value}" for key, value in content.items())

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
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vector_store = FAISS.from_documents(documents, embedding=embeddings)
    vector_store.save_local("faiss_index")



############################### 2단계 : RAG 기능 구현과 관련된 함수들 ##########################


## 사용자 질문에 대한 RAG 처리
@st.cache_data
def process_question(user_question):


    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    ## 벡터 DB 호출
    new_db = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)

    ## 관련 문서 3개를 호출하는 Retriever 생성
    retriever = new_db.as_retriever(search_kwargs={"k": 3})
    ## 사용자 질문을 기반으로 관련문서 3개 검색 
    retrieve_docs : List[Document] = retriever.invoke(user_question)

    ## RAG 체인 선언
    chain = get_rag_chain()
    ## 질문과 문맥을 넣어서 체인 결과 호출
    response = chain.invoke({"question": user_question, "context": retrieve_docs})

    return response, retrieve_docs



def get_rag_chain() -> Runnable:
    template = """
    다음의 컨텍스트를 활용해서 질문에 답변해줘
    - 질문에 대한 응답을 해줘
    - 간결하게 5줄 이내로 해줘
    - 곧바로 응답결과를 말해줘

    컨텍스트 : {context}

    질문: {question}

    응답:"""

    custom_rag_prompt = PromptTemplate.from_template(template)
    model = ChatOpenAI(model="gpt-4o-mini") # 모델 바꾸고 싶으면 이 부분만 바꾸면 됨.
    # model - ChatAnthropic(model="claude-3-5-sonnet-20240620") # 이런 식으로(Claude)

    return custom_rag_prompt | model | StrOutputParser() # pipe로 관리하여 in-out 쉽게 넣어주기



############################### 3단계 : 응답결과와 문서를 함께 보도록 도와주는 함수 ##########################
@st.cache_data(show_spinner=False)
# def convert_pdf_to_images(pdf_path: str, dpi: int = 250) -> List[str]:
#     doc = fitz.open(pdf_path)  # 문서 열기
#     image_paths = []
    
#     # 이미지 저장용 폴더 생성
#     output_folder = "PDF_이미지"
#     if not os.path.exists(output_folder):
#         os.makedirs(output_folder)

#     for page_num in range(len(doc)):  #  각 페이지를 순회
#         page = doc.load_page(page_num)  # 페이지 로드

#         zoom = dpi / 72  # 72이 디폴트 DPI
#         mat = fitz.Matrix(zoom, zoom)
#         pix = page.get_pixmap(matrix=mat) # type: ignore

#         image_path = os.path.join(output_folder, f"page_{page_num + 1}.png")  # 페이지 이미지 저장 page_1.png, page_2.png, etc.
#         pix.save(image_path)  # PNG 형태로 저장
#         image_paths.append(image_path)  # 경로를 저장
        
#     return image_paths

# def display_pdf_page(image_path: str, page_number: int) -> None:
#     image_bytes = open(image_path, "rb").read()  # 파일에서 이미지 인식
#     st.image(image_bytes, caption=f"Page {page_number}", output_format="PNG", width=600)


def natural_sort_key(s):
    return [int(text) if text.isdigit() else text for text in re.split(r'(\d+)', s)]

def main():
    # st.text(dotenv_values(".env"))
    # st.text("셋팅완료")
    st.set_page_config("로욜라도서관 FAQ 챗봇", layout="wide")

    left_column, right_column = st.columns([1, 1]) # 화면 왼쪽에 채팅, 오른쪽에 참고 텍스트
    with left_column:
        st.header("로욜라도서관 FAQ 챗봇")
        json_file = st.file_uploader("JSON Uploader", type="json")
        button = st.button("JSON 업로드하기")
        if json_file and button:
            with st.spinner("JSON 문서 저장 중"):
                # st.text("여기까지 구현됨")
                json_path = save_uploadedfile(json_file)
                json_document = json_to_documents(json_path)
                smaller_documents = chunk_documents(json_document)
                save_to_vector_store(smaller_documents)
        
        user_question = st.text_input("JSON 문서에 대해서 질문해 주세요", 
                                    placeholder="방학 중 도서관 이용 시간은 어떻게 되나요?")
        
    with right_column:    
        if user_question:
            response, context = process_question(user_question)
            st.text(response)
            # st.text(context)
            for document in context:
                with st.expander("관련 문서"):
                    st.text(document.page_content)
                    st.text(document.metadata.get('url', ''))
                    # file_path = document.metadata.get('source', '')
                    # page_number = document.metadata.get('page', 0) + 1
                    # button_key = f"lint_{file_path}_{page_number}"
                    # refreence_button = st.button(f"{os.path.basename(file_path)} pg.{page_number}", key=button_key)

                    # button_key = f"lint_{file_path}"
                    # refreence_button = st.button(f"{os.path.basename(file_path)}", key=button_key)
                    # if refreence_button:
                    #     st.session_state.page_number = str(page_number)
    
        # page_number 호출 ////// 이미지 대신 링크를 첨부하게 만들면 괜찮을 것 같다.
        # page_number = st.session_state.get('page_number')
        # if page_number:
        #     page_number = int(page_number)
        #     image_folder = "pdf_이미지"
        #     images = sorted(os.listdir(image_folder), key=natural_sort_key)
        #     print(images)
        #     image_paths = [os.path.join(image_folder, image) for image in images]
        #     print(page_number)
        #     print(image_paths[page_number - 1])
        #     display_pdf_page(image_paths[page_number - 1], page_number)

if __name__ == "__main__":
    main()
