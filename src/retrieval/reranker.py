from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain.retrievers import ContextualCompressionRetriever

class CrossEncoderWrapper:
    def __init__(self, base_retriever, top_n: int):
        xenc = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-v2-m3")
        compressor = CrossEncoderReranker(model=xenc, top_n=top_n)
        self.retriever = ContextualCompressionRetriever(
            base_retriever=base_retriever,
            base_compressor=compressor,
        )

    def get(self):
        return self.retriever
