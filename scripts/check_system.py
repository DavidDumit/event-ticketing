"""Checks that system.yaml matches the code (run in CI after the schema check).

- every service in system.yaml exists in docker-compose.yml and has its folders and OpenAPI file
- the environment variables listed for a service are exactly the ones its code reads
- every endpoint a service calls exists in the called service's OpenAPI document
"""
import pathlib
import re
import sys

import yaml

root = pathlib.Path(__file__).resolve().parent.parent
system = yaml.safe_load((root / "system.yaml").read_text())
compose = yaml.safe_load((root / "docker-compose.yml").read_text())
problems = []

for name, svc in system["services"].items():
    if name not in compose["services"]:
        problems.append(f"{name}: not a service in docker-compose.yml")
    for key in ("path", "migrations", "openapi"):
        if not (root / svc[key]).exists():
            problems.append(f"{name}: {key} {svc[key]} does not exist")

    code = "\n".join(p.read_text() for p in (root / svc["path"]).rglob("*.py") if "tests" not in p.parts)
    read_by_code = set(re.findall(r"""os\.environ(?:\.get\(|\[)["']([A-Z][A-Z0-9_]*)["']""", code))
    listed = set(svc["env"])
    for var in sorted(read_by_code - listed):
        problems.append(f"{name}: code reads {var} but system.yaml doesn't list it")
    for var in sorted(listed - read_by_code):
        problems.append(f"{name}: system.yaml lists {var} but the code never reads it")

    for call in svc.get("calls", []):
        target = system["services"][call["service"]]
        paths = yaml.safe_load((root / target["openapi"]).read_text())["paths"]
        for endpoint in call["endpoints"]:
            method, path = endpoint.split(" ", 1)
            if method.lower() not in paths.get(path, {}):
                problems.append(f"{name}: calls {endpoint}, which is not in {target['openapi']}")

for p in problems:
    print("ERROR:", p)
print("system.yaml matches the code" if not problems else f"{len(problems)} problem(s)")
sys.exit(1 if problems else 0)
