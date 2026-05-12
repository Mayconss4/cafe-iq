from app.tools import cotacao_cafe, clima, noticias

# Each entry: handler callable + metadata exposed on GET /tools
TOOLS: dict[str, dict] = {
    "cotacao_cafe": {
        "handler": cotacao_cafe.run,
        "descricao": "Retorna cotação simulada do café arábica (ICE e B3).",
        "params": [],
    },
    "clima": {
        "handler": clima.run,
        "descricao": "Retorna condições climáticas simuladas para uma cidade produtora.",
        "params": [{"nome": "cidade", "tipo": "string", "obrigatorio": True}],
    },
    "noticias": {
        "handler": noticias.run,
        "descricao": "Retorna 3 manchetes recentes simuladas sobre o mercado de café.",
        "params": [],
    },
}


def tool_metadata() -> list[dict]:
    return [
        {
            "nome": name,
            "descricao": meta["descricao"],
            "params": meta["params"],
        }
        for name, meta in TOOLS.items()
    ]
