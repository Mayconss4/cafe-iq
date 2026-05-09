from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.consumer import start_consumer_thread
from app.mcp_enricher import fetch_enrichments
from app.rag import answer_question, ingest_document


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_consumer_thread()
    yield


app = FastAPI(title="servico-rag", lifespan=lifespan)


class QueryRequest(BaseModel):
    pergunta: str


class QueryResponse(BaseModel):
    resposta: str
    fontes: list[str]


class IngestRequest(BaseModel):
    texto: str
    fonte: str


class IngestResponse(BaseModel):
    id: str
    mensagem: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    try:
        extra_context = fetch_enrichments(req.pergunta)
        result = answer_question(req.pergunta, extra_context=extra_context)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    fontes = list(
        {doc.metadata.get("fonte", "") for doc in result.get("source_documents", [])}
    )
    return QueryResponse(resposta=result["result"], fontes=fontes)


@app.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest):
    try:
        doc_id = ingest_document(req.texto, req.fonte)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return IngestResponse(id=doc_id, mensagem="Documento indexado com sucesso.")
