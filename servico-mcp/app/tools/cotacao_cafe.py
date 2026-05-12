import random
from datetime import date


def run(_params: dict) -> dict:
    base_ice = 220.50   # USc/lb
    base_b3 = 1_085.00  # BRL/saca 60kg

    variation = lambda base: round(base + random.uniform(-5, 5), 2)

    return {
        "data": date.today().isoformat(),
        "ICE_arabica_usc_lb": variation(base_ice),
        "B3_arabica_brl_saca60kg": variation(base_b3),
        "fonte": "mock — substituir por API ICE/B3",
    }
