import inspect
import tomllib
from pathlib import Path

from fastapi.params import Depends as DependsParam
from fastapi.params import Param

from app.api.v1.endpoints import (
    admin,
    auth,
    moderation,
    search,
    social,
    users,
    videos,
)
from app.main import app

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ENDPOINT_MODULES = (admin, auth, moderation, search, social, users, videos)


def test_endpoints_do_not_use_b008_default_calls():
    for module in ENDPOINT_MODULES:
        for route in module.router.routes:
            endpoint = getattr(route, "endpoint", None)
            if endpoint is None:
                continue
            signature = inspect.signature(endpoint)
            for name, param in signature.parameters.items():
                assert not isinstance(param.default, (DependsParam, Param)), (
                    f"{module.__name__}.{endpoint.__name__} parameter {name!r} "
                    f"uses B008 default call {param.default!r} instead of Annotated"
                )


def test_no_noqa_b008_or_global_ignore_remains():
    endpoints_dir = BACKEND_ROOT / "src" / "app" / "api" / "v1" / "endpoints"
    for py_file in sorted(endpoints_dir.glob("*.py")):
        content = py_file.read_text(encoding="utf-8")
        assert "noqa: B008" not in content, f"Found # noqa: B008 in {py_file}"

    pyproject = tomllib.loads((BACKEND_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    ignored_rules = pyproject.get("tool", {}).get("ruff", {}).get("lint", {}).get("ignore", [])
    assert "B008" not in ignored_rules


def test_openapi_schema_builds_cleanly():
    schema = app.openapi()
    assert schema["paths"]
