import logging
import random
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import requests

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

_NEWS_URL = (
    "https://news.google.com/rss/search"
    "?q=caf%C3%A9+arabica+mercado&hl=pt-BR&gl=BR&ceid=BR:pt"
)

_FALLBACK_HEADLINES = [
    "Exportações brasileiras de café atingem recorde no trimestre",
    "Geada no Sul de Minas preocupa produtores da safra 2025",
    "ICE Arabica recua após dados de estoques acima do esperado",
    "Brasil mantém liderança mundial na produção de café",
    "Relatório USDA projeta safra 2025/26 com 68 milhões de sacas",
]


def run(_params: dict) -> list[dict]:
    try:
        resp = requests.get(_NEWS_URL, headers=_HEADERS, timeout=8)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")[:3]
        if not items:
            raise ValueError("feed RSS vazio")
        today = date.today()
        return [
            {
                "titulo": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "data": (today - timedelta(days=i)).isoformat(),
                "fonte": "google-news-rss",
            }
            for i, item in enumerate(items)
        ]
    except Exception as exc:
        log.warning("noticias MCP — usando fallback (%s)", exc)
        today = date.today()
        sample = random.sample(_FALLBACK_HEADLINES, k=3)
        return [
            {
                "titulo": h,
                "data": (today - timedelta(days=i)).isoformat(),
                "fonte": "fallback",
            }
            for i, h in enumerate(sample)
        ]
