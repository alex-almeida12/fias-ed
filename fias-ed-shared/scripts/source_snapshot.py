"""Snapshot de integridade das fontes externas (somente leitura).

Uso:
  python source_snapshot.py create snapshot.json
  python source_snapshot.py verify snapshot.json   # exit 1 se algo mudou
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine-py" / "src"))
from fias_ed_engine.paths import experiments_dir, qti_system_dir  # noqa: E402

IGNORED = {".venv", "node_modules", ".next", "test-results", "__pycache__"}


def scan(root: Path) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for p in root.rglob("*"):
        if any(part in IGNORED for part in p.relative_to(root).parts):
            continue
        if p.is_file():
            st = p.stat()
            out[p.relative_to(root).as_posix()] = [st.st_size, st.st_mtime_ns]
    return out


def snapshot() -> dict:
    return {"experiments": scan(experiments_dir()), "qti_system": scan(qti_system_dir())}


def main() -> int:
    cmd, out = sys.argv[1], Path(sys.argv[2])
    if cmd == "create":
        out.write_text(json.dumps(snapshot()), encoding="utf-8")
        return 0
    old = json.loads(out.read_text(encoding="utf-8"))
    new = snapshot()
    changed = [f"{k}:{f}" for k in old for f in set(old[k]) | set(new[k])
               if old[k].get(f) != new[k].get(f)]
    for c in changed[:50]:
        print("ALTERADO:", c)
    print("OK — nenhuma alteração" if not changed else f"{len(changed)} alterações")
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
