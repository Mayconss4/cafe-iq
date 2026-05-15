import json
import logging
import urllib.error
import urllib.request

from app.config import MCP_URL

log = logging.getLogger(__name__)

# (keywords_to_match, tool_name, tool_params)
_RULES: list[tuple[set[str], str, dict]] = [
    ({"preço", "preco", "preços", "precos", "cotação", "cotacao", "cotações", "cotacoes", "ice"},
     "cotacao_cafe", {}),
    ({"clima", "tempo", "chuva", "temperatura"},
     "clima", {"cidade": "Lavras"}),
    ({"notícia", "noticia", "notícias", "noticias", "mercado"},
     "noticias", {}),
]


def _detect_tools(pergunta: str) -> list[dict]:
    lower = pergunta.lower()
    triggered: list[dict] = []
    seen: set[str] = set()
    for keywords, tool, params in _RULES:
        if tool not in seen and any(kw in lower for kw in keywords):
            triggered.append({"tool": tool, "params": params})
            seen.add(tool)
    return triggered


def _call_mcp(tool: str, params: dict) -> dict | list | None:
    payload = json.dumps({"tool": tool, "params": params}).encode()
    req = urllib.request.Request(
        f"{MCP_URL}/invoke",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())["resultado"]
    except Exception as exc:
        log.warning("MCP tool '%s' falhou: %s", tool, exc)
        return None


def _format_result(tool: str, result: dict | list) -> str:
    if tool == "cotacao_cafe" and isinstance(result, dict):
        return (
            f"Cotação do café ({result.get('data', '?')}): "
            f"ICE arábica = {result.get('ICE_arabica_usc_lb')} USc/lb | "
            f"B3 arábica = {result.get('B3_arabica_brl_saca60kg')} BRL/saca 60 kg."
        )
    if tool == "clima" and isinstance(result, dict):
        return (
            f"Clima em {result.get('cidade', '?')}: "
            f"{result.get('temperatura_c')}°C, "
            f"umidade {result.get('umidade_pct')}%, "
            f"{result.get('condicao')}."
        )
    if tool == "noticias" and isinstance(result, list):
        headlines = "\n".join(f"  - {n.get('titulo', '')}" for n in result)
        return f"Notícias recentes sobre café:\n{headlines}"
    # fallback: dump as JSON
    return json.dumps(result, ensure_ascii=False)


def fetch_enrichments(pergunta: str) -> str:
    """Return a formatted string with real-time MCP data relevant to the question,
    or an empty string if no tool matched or all calls failed."""
    tools = _detect_tools(pergunta)
    if not tools:
        return ""

    parts: list[str] = []
    for entry in tools:
        result = _call_mcp(entry["tool"], entry["params"])
        if result is not None:
            parts.append(_format_result(entry["tool"], result))

    return "\n".join(parts)
