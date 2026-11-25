from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_field: str
    quote: str


class ModelIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    topic: Literal["должность", "обязанности", "требования", "оплата",
                   "график", "место работы", "занятость"]
    kind: Literal["ambiguous", "contradiction", "missing"]
    evidence: list[Evidence]
    problem: str
    recommendation: str


class Issue(ModelIssue):

    @model_validator(mode="after")
    def check_evidence(self) -> Self:
        expected = 2 if self.kind == "contradiction" else 1
        if len(self.evidence) != expected:
            raise ValueError(f"{self.kind}: ожидается записей об источниках: {expected}")
        for item in self.evidence:
            if not item.source_field.strip():
                raise ValueError("Поле источника обязательно")
            if self.kind == "missing" and item.quote != "":
                raise ValueError("Для пропуска нужна пустая цитата")
            if self.kind != "missing" and not item.quote.strip():
                raise ValueError("Нужна цитата из источника")
        if expected == 2 and self.evidence[0].quote == self.evidence[1].quote:
            raise ValueError("Для противоречия нужны два разных значения")
        if not self.problem.strip() or not self.recommendation.strip():
            raise ValueError("Нужны описание проблемы и рекомендация")
        return self


class VacancyReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    vacancy_id: str
    url: str | None
    issues: list[Issue]


class ModelReport(VacancyReport):
    issues: list[ModelIssue]
