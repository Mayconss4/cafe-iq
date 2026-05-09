import chromadb
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain.schema import Document

from app.config import (
    OLLAMA_BASE_URL,
    CHROMA_HOST,
    CHROMA_PORT,
    COLLECTION_NAME,
    LLM_MODEL,
    EMBED_MODEL,
    RETRIEVER_K,
)

_PROMPT_TEMPLATE = """\
Você é um assistente especializado no mercado de café.
Responda de forma precisa e objetiva usando as informações abaixo.
Se não tiver a informação necessária, diga claramente que não sabe.

{context}

Pergunta: {question}
Resposta:"""


def _embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(base_url=OLLAMA_BASE_URL, model=EMBED_MODEL)


def _chroma_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)


def get_vectorstore() -> Chroma:
    return Chroma(
        client=_chroma_client(),
        collection_name=COLLECTION_NAME,
        embedding_function=_embeddings(),
    )


def answer_question(pergunta: str, extra_context: str = "") -> dict:
    """Retrieve relevant docs, optionally prepend real-time MCP context, call the LLM."""
    vectorstore = get_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": RETRIEVER_K})
    source_docs = retriever.invoke(pergunta)

    sections: list[str] = []
    if extra_context:
        sections.append(f"[Dados em tempo real]\n{extra_context}")
    if source_docs:
        kb_text = "\n\n".join(doc.page_content for doc in source_docs)
        sections.append(f"[Base de conhecimento]\n{kb_text}")
    if not sections:
        sections.append("Nenhum contexto disponível no momento.")

    prompt = _PROMPT_TEMPLATE.format(
        context="\n\n".join(sections),
        question=pergunta,
    )

    llm = Ollama(base_url=OLLAMA_BASE_URL, model=LLM_MODEL)
    resposta = llm.invoke(prompt)

    return {"result": resposta, "source_documents": source_docs}


def ingest_document(texto: str, fonte: str) -> str:
    vectorstore = get_vectorstore()
    doc = Document(page_content=texto, metadata={"fonte": fonte})
    ids = vectorstore.add_documents([doc])
    return ids[0]
