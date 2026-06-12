import logging
import random

import requests

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

_WTTR_URL = "https://wttr.in/{cidade}?format=j1"

_FALLBACK_CONDITIONS = ["Ensolarado", "Parcialmente nublado", "Nublado", "Chuva leve"]


def run(params: dict) -> dict:
    cidade: str = params.get("cidade", "Lavras,MG").strip()
    try:
        url = _WTTR_URL.format(cidade=cidade.replace(" ", "+"))
        resp = requests.get(url, headers=_HEADERS, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        cur = data["current_condition"][0]
        return {
            "cidade": cidade,
            "temperatura_c": float(cur["temp_C"]),
            "umidade_pct": int(cur["humidity"]),
            "condicao": cur["weatherDesc"][0]["value"],
            "fonte": "wttr.in",
        }
    except Exception as exc:
        log.warning("clima MCP — usando fallback para '%s' (%s)", cidade, exc)
        return {
            "cidade": cidade,
            "temperatura_c": round(random.uniform(18.0, 30.0), 1),
            "umidade_pct": random.randint(45, 90),
            "condicao": random.choice(_FALLBACK_CONDITIONS),
            "fonte": "fallback",
        }
