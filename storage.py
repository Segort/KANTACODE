import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from schemas import VacancyReport


def save_report(path: Path, reports: dict[str, VacancyReport]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                prefix=f"{path.name}.", suffix=".tmp",
                                delete=False) as stream:
            temporary = Path(stream.name)
            json.dump([report.model_dump(mode="json") for report in reports.values()],
                      stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
