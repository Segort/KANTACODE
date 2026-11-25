import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from analyzer import reconcile_issues, validate_findings
from main import main
from preprocessor import preprocess
from resume_draft import Resume, make_draft
from schemas import Evidence, ModelIssue, VacancyReport


class ReportRegressions(TestCase):
    def test_verify_reads_local_input_and_analyzes_each_id_once(self):
        first = {"id": "same", "job-name": "Первый вариант"}
        last = {"id": "same", "job-name": "Последний вариант"}
        payload = {"results": {"vacancies": [{"vacancy": row} for row in (first, last)]}}
        with TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            output_path = Path(directory) / "report.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch("main.fetch_vacancies") as fetch, patch("main.Analyzer") as model:
                analyze = model.return_value.analyze
                analyze.return_value = VacancyReport(vacancy_id="same", url=None, issues=[])
                result = main(["--mode", "verify", "--input", str(input_path),
                               "--output", str(output_path)])

            self.assertEqual(result, 0)
            fetch.assert_not_called()
            analyze.assert_called_once_with(preprocess(last))
            self.assertEqual(json.loads(output_path.read_bytes()),
                             [{"vacancy_id": "same", "url": None, "issues": []}])

    def test_numeric_quote_must_match_the_full_source_value(self):
        vacancy = preprocess({"id": "test", "salary_min": 50000})
        issue = ModelIssue(
            topic="оплата",
            kind="ambiguous",
            evidence=[Evidence(source_field="salary_min", quote="0")],
            problem="Размер оплаты неясен.",
            recommendation="Уточните размер оплаты.",
        )

        self.assertEqual(validate_findings(vacancy, [issue]), [])
        issue.evidence[0].quote = "50000"
        self.assertEqual(len(validate_findings(vacancy, [issue, issue])), 1)

    def test_travel_reimbursement_does_not_count_as_salary(self):
        vacancy = preprocess({"id": "test", "description": "Проезд оплачивается."})
        issues = reconcile_issues(vacancy, [])

        self.assertEqual([(issue.topic, issue.kind) for issue in issues],
                         [("оплата", "missing")])
        self.assertEqual(issues[0].evidence[0].quote, "")

    def test_salary_in_description_prevents_missing_fallback(self):
        vacancy = preprocess({"id": "test", "description": "Оклад 50 000 рублей."})

        self.assertEqual(reconcile_issues(vacancy, []), [])


class ResumeRegression(TestCase):
    def test_short_technical_skills_are_matched_without_rewriting_resume(self):
        vacancy = {"id": "test", "job-name": "Разработчик C++",
                   "duty": "Создавать приложения на C++."}
        resume = Resume(
            experience=["Писал сценарии для учебных проектов."],
            skills=["C#", "C++"],
            education=["Учебная программа по информатике."],
        )
        draft = make_draft(vacancy, resume)

        self.assertIn("- C++\n- C#\n", draft)
        self.assertIn("- " + resume.experience[0], draft)
        self.assertIn("- " + resume.education[0], draft)
