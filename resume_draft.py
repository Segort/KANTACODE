import argparse
import os
import re
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, model_validator

from fetcher import DEFAULT_API_URL, fetch_vacancies, load_local_vacancies
from preprocessor import preprocess

SECTIONS = {"experience": "Опыт", "skills": "Навыки", "education": "Образование"}
TOKEN = re.compile(r"\bc(?:\+\+|#)|[^\W_]+")
SHORT_KEYWORDS = {"sql", "1с", "1c", "пк", "c++", "c#"}


class Resume(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    experience: list[str]
    skills: list[str]
    education: list[str]

    @model_validator(mode="after")
    def check_content(self):
        entries = self.experience + self.skills + self.education
        if not entries or any(not entry.strip() for entry in entries):
            raise ValueError("Добавьте хотя бы одну запись и уберите пустые строки")
        return self


def keywords(text: str) -> set[str]:
    return {word for word in TOKEN.findall(text.casefold().replace("ё", "е"))
            if (len(word) >= 4 or word in SHORT_KEYWORDS) and not word.isdecimal()}


def text_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from text_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from text_values(item)


def make_draft(vacancy: dict, resume: Resume) -> str:
    card = preprocess(vacancy)
    fields = card["structured"]
    matching_fields = ("job-name", "duty", "requirements", "requirement",
                       "qualification", "skills")
    target_parts = [fields.get(field) for field in matching_fields] + [card["description"]]
    target_words = keywords(" ".join(text_values(target_parts)))
    title = fields.get("job-name") or "Название не указано"
    lines = ["# Черновик резюме", "", f"**Целевая вакансия** — {title}",
             f"**ID вакансии** — {card['vacancy_id']}"]
    if card["url"]:
        lines.append(f"**Карточка вакансии** — {card['url']}")
    lines.extend(("", "Записи с совпадениями по ключевым словам идут первыми."))
    for field, label in SECTIONS.items():
        entries = getattr(resume, field)
        if entries:
            ranked = sorted(entries, key=lambda item: -len(keywords(item) & target_words))
            lines.extend(("", f"## {label}", ""))
            lines.extend("- " + "\n  ".join(entry.splitlines()) for entry in ranked)
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    load_dotenv(Path(__file__).with_name(".env"))
    parser = argparse.ArgumentParser(description="Черновик резюме под вакансию региона 39")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--list", action="store_true", help="Показать доступные ID вакансий")
    choice.add_argument("--vacancy-id", help="ID выбранной вакансии")
    parser.add_argument("--input", type=Path, help="Локальный JSON вакансий в формате API")
    parser.add_argument("--resume", type=Path, help="Локальный JSON резюме")
    parser.add_argument("--output", type=Path, help="Путь к черновику Markdown")
    args = parser.parse_args(argv)
    if args.list and (args.resume or args.output):
        parser.error("--resume и --output используются с --vacancy-id")
    if not args.list and (not args.vacancy_id.strip() or args.resume is None):
        parser.error("с --vacancy-id укажите --resume")
    if args.output and any(args.output.resolve() == path.resolve()
                           for path in (args.input, args.resume) if path):
        parser.error("--output должен отличаться от путей входных файлов")

    try:
        resume = (Resume.model_validate_json(args.resume.read_text(encoding="utf-8-sig"))
                  if args.resume else None)
        if args.input:
            vacancies = load_local_vacancies(args.input)
        else:
            vacancies = fetch_vacancies(os.getenv("API_URL", DEFAULT_API_URL),
                                        int(os.getenv("MAX_VACANCIES", "40")))
        by_id = {row["id"].strip(): row for row in vacancies
                 if isinstance(row.get("id"), str) and row["id"].strip()}
        if args.list:
            for vacancy_id, row in by_id.items():
                print(f"{vacancy_id}\t{row.get('job-name') or 'Без названия'}")
            return 0
        vacancy = by_id.get(args.vacancy_id.strip())
        if vacancy is None:
            hint = "Проверьте --list с тем же файлом." if args.input else (
                "Проверьте --list или увеличьте MAX_VACANCIES."
            )
            raise ValueError(f"ID не найден в выборке. {hint}")
        draft = make_draft(vacancy, resume)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(draft, encoding="utf-8")
            print(f"Черновик сохранён в {args.output}")
        else:
            print(draft, end="")
    except (httpx.HTTPError, httpx.InvalidURL, OSError, ValueError) as error:
        print(f"Не удалось подготовить черновик: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
