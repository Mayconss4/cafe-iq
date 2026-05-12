from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.registry import TOOLS, tool_metadata

app = FastAPI(title="servico-mcp")


class InvokeRequest(BaseModel):
    tool: str
    params: dict = {}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tools")
def list_tools():
    return {"tools": tool_metadata()}


@app.post("/invoke")
def invoke(req: InvokeRequest):
    entry = TOOLS.get(req.tool)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Ferramenta '{req.tool}' não encontrada. "
                   f"Disponíveis: {list(TOOLS)}",
        )
    try:
        result = entry["handler"](req.params)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"tool": req.tool, "resultado": result}
