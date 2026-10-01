"""Package only deployable code and the compiled UI, excluding secrets and data."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent


def main():
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise SystemExit("First run: npm run build")
    output = ROOT / "dist/aws-authenticator.zip"
    output.parent.mkdir(exist_ok=True)
    files = [ROOT / name for name in ("requirements.txt", "wsgi.py", "README.md", "Task.md")]
    files += list((ROOT / "backend").glob("*.py"))
    files += [ROOT / "backend/schema.sql"]
    for folder in ("frontend/dist", "deploy", "docs"):
        files += [path for path in (ROOT / folder).rglob("*") if path.is_file()]
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for file in sorted(files):
            archive.write(file, file.relative_to(ROOT).as_posix())
    print(f"Created {output} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
