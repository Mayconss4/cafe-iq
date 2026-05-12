import random


_CONDITIONS = ["Ensolarado", "Parcialmente nublado", "Nublado", "Chuva leve", "Chuva forte"]

_REGIONS: dict[str, dict] = {
    "patrocinio":   {"temp_base": 24, "humidity_base": 65},
    "araguari":     {"temp_base": 23, "humidity_base": 68},
    "guaxupe":      {"temp_base": 22, "humidity_base": 70},
    "varginha":     {"temp_base": 21, "humidity_base": 72},
    "mococa":       {"temp_base": 25, "humidity_base": 60},
    "lavras":       {"temp_base": 22, "humidity_base": 74},  # Fix 5: cidade padrão do scrapper
}


def run(params: dict) -> dict:
    cidade_raw: str = params.get("cidade", "")
    cidade_key = cidade_raw.lower().strip()

    region = _REGIONS.get(cidade_key, {"temp_base": 23, "humidity_base": 65})
    temp = round(region["temp_base"] + random.uniform(-3, 3), 1)
    humidity = min(100, max(0, region["humidity_base"] + random.randint(-10, 10)))
    condition = random.choice(_CONDITIONS)

    return {
        "cidade": cidade_raw or "desconhecida",
        "temperatura_c": temp,
        "umidade_pct": humidity,
        "condicao": condition,
        "fonte": "mock — substituir por API de clima",
    }
