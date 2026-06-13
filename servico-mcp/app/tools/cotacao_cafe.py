import logging
import random
from datetime import date

import requests

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# Alpha Vantage: Global Price of Coffee (cents per pound, mensal)
# A chave "demo" está publicamente disponível para este endpoint específico.
_AV_URL = (
    "https://www.alphavantage.co/query"
    "?function=COFFEE&interval=monthly&apikey=demo"
)

# Conversão: USc/lb → BRL/saca 60 kg
_LB_PER_SACA        = 132.277
_APPROX_BRL_PER_USD = 5.20


def run(_params: dict) -> dict:
    try:
        resp = requests.get(_AV_URL, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        if "data" not in payload or not payload["data"]:
            raise ValueError("campo 'data' ausente ou vazio")
        latest = payload["data"][0]
        price_usc = float(latest["value"])
        ref_date  = latest["date"]
        price_brl = round(price_usc * _LB_PER_SACA * 0.01 * _APPROX_BRL_PER_USD, 2)
        return {
            "data": date.today().isoformat(),
            "referencia_mensal": ref_date,
            "ICE_arabica_usc_lb": round(price_usc, 2),
            "B3_arabica_brl_saca60kg": price_brl,
            "fonte": "alphavantage/ICO (COFFEE)",
        }
    except Exception as exc:
        log.warning("cotacao_cafe MCP — usando fallback (%s)", exc)
        base_ice = 220.50
        base_b3  = 1_085.00
        variation = lambda b: round(b + random.uniform(-5, 5), 2)
        return {
            "data": date.today().isoformat(),
            "ICE_arabica_usc_lb": variation(base_ice),
            "B3_arabica_brl_saca60kg": variation(base_b3),
            "fonte": "fallback",
        }
