import logging
import random
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
}

# Alpha Vantage: Global Price of Coffee (cents per pound, mensal)
_AV_URL   = (
    "https://www.alphavantage.co/query"
    "?function=COFFEE&interval=monthly&apikey=demo"
)
_WTTR_URL = "https://wttr.in/{cidade}?format=j1"
_NEWS_URL = (
    "https://news.google.com/rss/search"
    "?q=caf%C3%A9+arabica+mercado&hl=pt-BR&gl=BR&ceid=BR:pt"
)

_FALLBACK_HEADLINES = [
    "Safra 2025 de café arábica supera expectativas no Sul de Minas",
    "Exportações de café do Brasil crescem 12% no primeiro semestre",
    "Geada atípica ameaça lavouras cafeeiras em Minas Gerais",
    "Preço do café no mercado internacional bate máxima do ano",
    "Consumo interno de café no Brasil cresce pelo quinto ano seguido",
]


def collect_noticias() -> list[dict]:
    now = datetime.utcnow().isoformat()
    try:
        resp = requests.get(_NEWS_URL, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")[:3]
        if not items:
            raise ValueError("feed RSS vazio")
        return [
            {
                "tipo": "noticia",
                "titulo": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "coletado_em": now,
                "fonte": "google-news-rss",
            }
            for item in items
        ]
    except Exception as exc:
        log.warning("collect_noticias — usando fallback (%s)", exc)
        headlines = random.sample(_FALLBACK_HEADLINES, k=2)
        return [
            {"tipo": "noticia", "titulo": h, "coletado_em": now, "fonte": "fallback"}
            for h in headlines
        ]


def collect_clima(cidade: str = "Lavras,MG") -> dict:
    now = datetime.utcnow().isoformat()
    try:
        url = _WTTR_URL.format(cidade=cidade.replace(" ", "+"))
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        cur = data["current_condition"][0]
        return {
            "tipo": "clima",
            "cidade": cidade,
            "temperatura_c": float(cur["temp_C"]),
            "umidade_pct": int(cur["humidity"]),
            "condicao": cur["weatherDesc"][0]["value"],
            "coletado_em": now,
            "fonte": "wttr.in",
        }
    except Exception as exc:
        log.warning("collect_clima — usando fallback (%s)", exc)
        return {
            "tipo": "clima",
            "cidade": cidade,
            "temperatura_c": round(random.uniform(15.0, 30.0), 1),
            "umidade_pct": random.randint(45, 95),
            "condicao": "Indisponível",
            "coletado_em": now,
            "fonte": "fallback",
        }


def collect_cotacao() -> dict:
    now = datetime.utcnow().isoformat()
    try:
        resp = requests.get(_AV_URL, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        if "data" not in payload or not payload["data"]:
            raise ValueError("campo 'data' ausente ou vazio")
        latest = payload["data"][0]
        price_usc = float(latest["value"])
        ref_date  = latest["date"]
        return {
            "tipo": "cotacao",
            "produto": "cafe_arabica",
            "referencia_mensal": ref_date,
            "preco_usc_lb": round(price_usc, 2),
            "coletado_em": now,
            "fonte": "alphavantage/ICO",
        }
    except Exception as exc:
        log.warning("collect_cotacao — usando fallback (%s)", exc)
        return {
            "tipo": "cotacao",
            "produto": "cafe_arabica",
            "preco_usc_lb": round(random.uniform(200.0, 300.0), 2),
            "coletado_em": now,
            "fonte": "fallback",
        }


def run_cycle() -> list[dict]:
    messages: list[dict] = []
    messages.extend(collect_noticias())
    messages.append(collect_clima())
    messages.append(collect_cotacao())
    return messages
