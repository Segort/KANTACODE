FIELDS = (
    "job-name", "duty", "requirement", "requirements", "qualification",
    "skills", "salary", "salary_min", "salary_max", "currency", "schedule",
    "shift", "addresses", "region", "workPlaceType", "employment", "term",
    "conditions",
)


def preprocess(vacancy: dict) -> dict:
    vacancy_id = vacancy.get("id")
    if not isinstance(vacancy_id, str) or not vacancy_id.strip():
        raise ValueError("У вакансии отсутствует строковый id")
    url = vacancy.get("vac_url")
    if url is not None and not isinstance(url, str):
        raise ValueError(f"Вакансия {vacancy_id}: vac_url должен быть строкой")
    return {
        "vacancy_id": vacancy_id.strip(),
        "url": (url.strip() or None) if url is not None else None,
        "structured": {
            key: vacancy[key] for key in FIELDS
            if key in vacancy and vacancy[key] is not None
        },
        "description": vacancy.get("description"),
    }
