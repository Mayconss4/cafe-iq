import logging
import random
import re
from datetime import datetime
from typing import Iterable

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_HTTP_TIMEOUT = 15
_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

_NEWS_SITES = [
    "https://www.noticiasagricolas.com.br/",
    "https://www.agrolink.com.br/",
    "https://agfeed.com.br/",
]

_WEATHER_SITES = [
    "https://www.climatempo.com.br/",
    "https://portal.inmet.gov.br/",
]

_PRICE_SITES = [
    "https://br.investing.com/commodities/real-time-futures",
    "https://economia.uol.com.br/cotacoes/",
    "https://www.bcb.gov.br/estabilidadefinanceira/cotacoesmoedas",
]

_MOCK_HEADLINES = [
    "Safra 2025 de café arábica supera expectativas no Sul de Minas",
    "Exportações de café do Brasil crescem 12% no primeiro semestre",
    "Geada atípica ameaça lavouras cafeeiras em Minas Gerais",
    "Preço do café no mercado internacional bate máxima do ano",
    "Consumo interno de café no Brasil cresce pelo quinto ano seguido",
    "Novas variedades resistentes à ferrugem ganham espaço no Cerrado",
    "Cooperativas investem em rastreabilidade para mercado de cafés especiais",
    "Vietnã reduz produção e eleva demanda por café brasileiro",
]

_CONDITIONS = ["Ensolarado", "Parcialmente nublado", "Nublado", "Chuva leve"]


def _fetch_html(url: str) -> str | None:
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, headers=_DEFAULT_HEADERS, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
    except Exception as exc:
        log.warning("Falha ao buscar %s: %s", url, exc)
        return None


def _find_prices(text: str) -> list[float]:
    raw_numbers = re.findall(r"\d+[\.,]?\d*", text)
    prices: list[float] = []
    for raw in raw_numbers:
        normalized = raw.replace(".", "").replace(",", ".") if raw.count(",") > 0 else raw
        try:
            prices.append(float(normalized))
        except ValueError:
            continue
    return prices


def _extract_headlines(soup: BeautifulSoup, selectors: Iterable[str]) -> list[str]:
    headlines: list[str] = []
    for selector in selectors:
        for element in soup.select(selector):
            title = element.get_text(" ", strip=True)
            if title and len(title) > 20:
                headlines.append(title)
    return headlines


def _parse_noticiasagricolas(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = ["article h2", "article h3", "div.titulo a", "a[href*='/noticias']"]
    return _extract_headlines(soup, selectors)


def _parse_agrolink(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = ["div.card__title", "article h2", "article h3", "a.headline"]
    return _extract_headlines(soup, selectors)


def _parse_agfeed(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = ["article h2", "article h3", "div.titulo", "a.story__title"]
    return _extract_headlines(soup, selectors)


def _collect_external_headlines() -> list[str]:
    headlines: list[str] = []
    for url in _NEWS_SITES:
        html = _fetch_html(url)
        if not html:
            continue
        if "noticiasagricolas" in url:
            headlines.extend(_parse_noticiasagricolas(html))
        elif "agrolink" in url:
            headlines.extend(_parse_agrolink(html))
        elif "agfeed" in url:
            headlines.extend(_parse_agfeed(html))
    return headlines


def _parse_climatempo(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    if "Lavras" not in text:
        return None
    temperatura = None
    umidade = None
    condicao = None
    for fragment in text.split():
        if temp := re.match(r"(-?\d+)[°º]?C", fragment):
            temperatura = float(temp.group(1))
        if humidity := re.match(r"(\d+)%", fragment):
            umidade = int(humidity.group(1))
    for item in ["Ensolarado", "Parcialmente nublado", "Nublado", "Chuva leve"]:
        if item in text:
            condicao = item
            break
    if temperatura is not None and umidade is not None and condicao:
        return {
            "cidade": "Lavras-MG",
            "temperatura_c": temperatura,
            "umidade_pct": umidade,
            "condicao": condicao,
        }
    return None


def _parse_inmet(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    if "Lavras" not in text:
        return None
    temperatures = _find_prices(text)
    if not temperatures:
        return None
    return {
        "cidade": "Lavras-MG",
        "temperatura_c": round(temperatures[0], 1),
        "umidade_pct": 70,
        "condicao": "Nublado",
    }


def _collect_external_clima() -> dict | None:
    for url in _WEATHER_SITES:
        html = _fetch_html(url)
        if not html:
            continue
        if "climatempo" in url:
            result = _parse_climatempo(html)
        elif "inmet" in url:
            result = _parse_inmet(html)
        else:
            result = None
        if result:
            return result
    return None


def _parse_investing_coffee(html: str) -> float | None:
    soup = BeautifulSoup(html, "html.parser")
    if "Café" not in html and "coffee" not in html.lower():
        return None
    texts = [item.get_text(" ", strip=True) for item in soup.select("div, span, a")]
    for text in texts:
        if "café" in text.lower() or "coffee" in text.lower():
            prices = _find_prices(text)
            if prices:
                return prices[0]
    return None


def _parse_economia_uol(html: str) -> float | None:
    soup = BeautifulSoup(html, "html.parser")
    for item in soup.select("a, span, div"):
        text = item.get_text(" ", strip=True)
        if "café" in text.lower() or "coffee" in text.lower():
            prices = _find_prices(text)
            if prices:
                return prices[0]
    return None


def _parse_bcb_cotacoes(html: str) -> float | None:
    soup = BeautifulSoup(html, "html.parser")
    for row in soup.select("tr"):
        text = row.get_text(" ", strip=True).lower()
        if "dólar" in text or "dolar" in text:
            prices = _find_prices(text)
            if prices:
                return prices[0]
    return None


def _collect_external_cotacao() -> float | None:
    for url in _PRICE_SITES:
        html = _fetch_html(url)
        if not html:
            continue
        if "investing.com" in url:
            price = _parse_investing_coffee(html)
        elif "economia.uol.com.br" in url:
            price = _parse_economia_uol(html)
        elif "bcb.gov.br" in url:
            price = _parse_bcb_cotacoes(html)
        else:
            price = None
        if price is not None and price > 0:
            return price
    return None


def collect_noticias() -> list[dict]:
    now = datetime.utcnow().isoformat()
    headlines = _collect_external_headlines()
    if len(headlines) < 2:
        headlines = list(_MOCK_HEADLINES)
    selected = random.sample(headlines, k=min(2, len(headlines)))
    return [
        {
            "tipo": "noticia",
            "titulo": title,
            "coletado_em": now,
            "fonte": "web",
        }
        for title in selected
    ]


def collect_clima() -> dict:
    now = datetime.utcnow().isoformat()
    external = _collect_external_clima()
    if external is None:
        return {
            "tipo": "clima",
            "cidade": "Lavras-MG",
            "temperatura_c": round(random.uniform(15.0, 30.0), 1),
            "umidade_pct": random.randint(45, 95),
            "condicao": random.choice(_CONDITIONS),
            "coletado_em": now,
            "fonte": "mock",
        }
    return {
        "tipo": "clima",
        "cidade": external["cidade"],
        "temperatura_c": external["temperatura_c"],
        "umidade_pct": external["umidade_pct"],
        "condicao": external["condicao"],
        "coletado_em": now,
        "fonte": "web",
    }


def collect_cotacao() -> dict:
    now = datetime.utcnow().isoformat()
    external_price = _collect_external_cotacao()
    if external_price is None:
        external_price = round(random.uniform(200.0, 300.0), 2)
        fonte = "mock"
    else:
        fonte = "web"
    return {
        "tipo": "cotacao",
        "produto": "cafe_arabica",
        "preco_usc_lb": round(external_price, 2),
        "coletado_em": now,
        "fonte": fonte,
    }


def run_cycle() -> list[dict]:
    messages: list[dict] = []
    messages.extend(collect_noticias())
    messages.append(collect_clima())
    messages.append(collect_cotacao())
    return messages
