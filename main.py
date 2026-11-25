import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAIError

from analyzer import Analyzer
from fetcher import DEFAULT_API_URL, fetch_vacancies, load_local_vacancies
from preprocessor import preprocess
from storage import save_report

def main(argv=None) -> int:
    load_dotenv(Path(__file__).with_name(".env"))
    parser = argparse.ArgumentParser(description="Проверка ясности вакансий")
    parser.add_argument("--mode", choices=("fetch", "verify"), required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path,
                        default=Path(os.getenv("REPORT_PATH", "reports/report.json")))
    args = parser.parse_args(argv)
    if args.mode == "verify":
        if args.input is None:
            parser.error("для --mode verify укажите --input")
        if args.input.resolve() == args.output.resolve():
            parser.error("входной файл и отчёт должны иметь разные пути")
    elif args.input is not None:
        parser.error("--input используется в режиме verify")

    if args.mode == "fetch":
        try:
            rows = fetch_vacancies(os.getenv("API_URL", DEFAULT_API_URL),
                                   int(os.getenv("MAX_VACANCIES", "40")))
        except (httpx.HTTPError, httpx.InvalidURL, ValueError) as error:
            print(f"Не удалось получить вакансии из API: {error}. "
                  "Предыдущий отчёт сохранён, если он был.", file=sys.stderr)
            return 1
    else:
        try:
            rows = load_local_vacancies(args.input)
        except (OSError, ValueError) as error:
            print(f"Не удалось прочитать входной файл: {error}", file=sys.stderr)
            return 1

    try:
        vacancies = {}
        for row in rows:
            vacancy = preprocess(row)
            vacancies[vacancy["vacancy_id"]] = vacancy
        print(f"Получено вакансий: {len(rows)}, уникальных: {len(vacancies)}",
              flush=True)
        reports = {}
        if vacancies:
            analyzer = Analyzer(
                os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
                os.getenv("LLM_API_KEY", "ollama"),
                os.getenv("LLM_MODEL", "qwen2.5:7b"),
            )
            with analyzer.client:
                for vacancy_id, vacancy in vacancies.items():
                    reports[vacancy_id] = analyzer.analyze(vacancy)
        save_report(args.output, reports)
    except (OSError, ValueError, OpenAIError) as error:
        print(f"Отчёт не обновлён: {error}", file=sys.stderr)
        return 1
    print(f"Сохранено записей: {len(reports)}. Отчёт: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
