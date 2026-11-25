import json
from pathlib import Path

import httpx

DEFAULT_API_URL = "http://opendata.trudvsem.ru/api/v1/vacancies/region/39"


def unpack_vacancies(payload):
    if not isinstance(payload, dict):
        raise ValueError("Ответ должен быть объектом JSON")
    if "status" in payload and payload["status"] not in ("200", 200):
        raise ValueError(f"Портал вернул статус {payload['status']}")
    results = payload.get("results")
    rows = results.get("vacancies") if isinstance(results, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Ожидается массив results.vacancies")
    vacancies = []
    for row in rows:
        vacancy = row.get("vacancy") if isinstance(row, dict) else None
        if not isinstance(vacancy, dict):
            raise ValueError("Запись в results.vacancies должна содержать объект vacancy")
        vacancies.append(vacancy)
    return vacancies


def fetch_vacancies(url: str, max_vacancies: int):
    if max_vacancies < 1:
        raise ValueError("MAX_VACANCIES должен быть положительным числом")
    page_size = min(20, max_vacancies)
    vacancies = []
    for offset in range((max_vacancies + page_size - 1) // page_size):
        response = httpx.get(url, params={"offset": offset, "limit": page_size},
                             timeout=20, follow_redirects=True)
        response.raise_for_status()
        page = unpack_vacancies(response.json())
        vacancies.extend(page[:max_vacancies - len(vacancies)])
        if len(page) < page_size:
            break
    return vacancies


def load_local_vacancies(filepath: Path):
    with filepath.open(encoding="utf-8-sig") as stream:
        return unpack_vacancies(json.load(stream))
