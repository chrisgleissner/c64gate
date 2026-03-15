from __future__ import annotations

from pathlib import Path

import yaml


def _check_reference(root: Path, reference: str) -> None:
    file_reference = reference.split("::", maxsplit=1)[0]
    file_path = root / file_reference
    if not file_path.exists():
        raise SystemExit(f"missing traceability reference target: {reference}")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    matrix_path = root / "doc/traceability-matrix.yaml"
    payload = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    requirements = payload.get("requirements", [])
    if not requirements:
        raise SystemExit("traceability matrix is empty")
    seen_ids: set[str] = set()
    for row in requirements:
        req_id = row.get("id")
        if not req_id:
            raise SystemExit("traceability row missing id")
        if req_id in seen_ids:
            raise SystemExit(f"duplicate requirement id: {req_id}")
        seen_ids.add(req_id)
        for field in ["section", "requirement", "implementation", "tests", "ci"]:
            if field not in row or not row[field]:
                raise SystemExit(f"traceability row {req_id} missing {field}")
        for group in ["implementation", "tests", "ci"]:
            for reference in row[group]:
                _check_reference(root, reference)
    print(f"validated {len(requirements)} requirement rows")


if __name__ == "__main__":
    main()
