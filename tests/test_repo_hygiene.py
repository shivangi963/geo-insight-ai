"""Guards for mistakes that have already happened once in this repo."""

import importlib
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", "venv", ".venv"}


def tracked_files():
    """Files git tracks; falls back to walking the tree outside a git checkout."""
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        return [ROOT / p for p in out if (ROOT / p).is_file()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [
            p for p in ROOT.rglob("*")
            if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS)
        ]


def test_every_dockerfile_referenced_by_compose_exists():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    missing = []
    for name, service in compose["services"].items():
        build = service.get("build")
        if not isinstance(build, dict):
            continue
        dockerfile = ROOT / build.get("context", ".") / build.get("dockerfile", "Dockerfile")
        if not dockerfile.is_file():
            missing.append(f"{name}: {dockerfile.relative_to(ROOT)}")
    assert not missing, f"docker-compose.yml points at missing Dockerfiles: {missing}"


def test_no_api_keys_or_database_passwords_in_tracked_files():
    patterns = [
        re.compile(r"AIza[0-9A-Za-z_-]{35}"),                    # Google API key
        re.compile(r"mongodb(\+srv)?://[^:<\s/]+:[^@<\s]+@"),    # URL with a real password
        re.compile(r"sk-[A-Za-z0-9]{32,}"),                      # OpenAI-style key
    ]
    offenders = []
    for path in tracked_files():
        if path.suffix in {".csv", ".jpg", ".png", ".pdf", ".zip", ".pyc", ".json"} or path.stat().st_size > 1_000_000:
            continue
        text = path.read_text(errors="ignore")
        offenders += [str(path.relative_to(ROOT)) for p in patterns if p.search(text)]
    assert not offenders, f"possible secrets in: {sorted(set(offenders))}"


def test_no_generated_or_binary_junk_is_tracked():
    bad = [
        str(p.relative_to(ROOT)) for p in tracked_files()
        if p.suffix in {".zip", ".pyc", ".pt", ".log"} or "__pycache__" in p.parts or ".osmnx_cache" in p.parts
    ]
    assert not bad, f"remove from git (git rm --cached): {bad}"


def test_every_name_in_routers_all_is_a_real_module():
    package = importlib.import_module("app.routers")
    for name in package.__all__:
        importlib.import_module(f"app.routers.{name}")
