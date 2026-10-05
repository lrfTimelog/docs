"""Generate the "TimeLog Phoenix Public REST API (POC / WIP)" section of this Mintlify site.

Source of truth is the vault, not this repo:
  <vault>/01 - Projects/New Public API (Phoenix)/deliverables/api-reference/*/openapi.yaml   (draft /v1 contracts)
  <vault>/01 - Projects/New Public API (Phoenix)/deliverables/connectivity-model/TARGET_API_MODEL.md (planned resources)

What it does:
  1. Bundles each contract into a self-contained spec under phoenix-api/openapi/ (the contracts $ref
     ../_shared/components.yaml, which Mintlify cannot resolve) and replaces the placeholder `servers: [/]`
     with presentation base URLs.
  2. Emits one MDX page per operation and per webhook, grouped by business domain (D1-D12).
  3. Emits one overview page per domain, including the 8 domains with no declared operations yet.
  4. Rewrites the Phoenix group in docs.json. The legacy "TimeLog REST API" group is left untouched.

Re-run after any contract change:  python scripts/build_phoenix_poc.py
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
VAULT = Path(
    os.getenv(
        "PHOENIX_API_PROJECT",
        r"C:\Users\LuisdelaRosaFernande\OneDrive - TimeLog A S\Documents\KnowledgeCemter\KnowledgeCenter"
        r"\01 - Projects\New Public API (Phoenix)",
    )
)
SPEC_DIR = VAULT / "deliverables" / "api-reference"
TARGET_MODEL = VAULT / "deliverables" / "connectivity-model" / "TARGET_API_MODEL.md"
OUT = REPO / "phoenix-api"
SECTION = "phoenix-api"
GROUP_NAME = "TimeLog Phoenix Public REST API (POC · WIP)"
SHARED_PREFIX = "../_shared/components.yaml#"

# Presentation base URLs. The real host is still open (ED-006) and so is any prefix before /v1 (ED-005).
# Shape follows TARGET_API_MODEL P1: one base URL per environment, tenant derived from the credential.
SERVERS = [
    {"url": "https://api.timelog.com", "description": "Production"},
    {"url": "https://api.sandbox.timelog.com", "description": "Sandbox"},
]
BASE_URL = SERVERS[0]["url"]
SPECS = ["customers", "projects", "calendar-events"]


@dataclass
class Domain:
    code: str
    slug: str
    name: str
    icon: str
    boundary: str  # 01-domain-map.md section 2, "Plain-English boundary"
    ops: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)


DOMAINS = [
    Domain("D1", "crm", "CRM", "handshake",
           "Who we sell to, and the people at them. Customers, contacts, industry, customer status."),
    Domain("D2", "delivery", "Delivery", "diagram-project",
           "The work we committed to do: projects, tasks, sub-tasks, templates, milestones, stages, project types and categories."),
    Domain("D3", "commercial-terms", "Commercial terms", "file-contract",
           "How a piece of delivery converts into money: contract models, hourly rates, cost prices, payment plans, payors."),
    Domain("D4", "time", "Time", "clock",
           "Recording that work happened: time registrations, time trackers, favourites, weekly registrations, adjustments."),
    Domain("D5", "approval-and-period", "Approval and period", "circle-check",
           "Turning recorded time into settled time: timesheet submission, approval, rejection, resubmission, period close, barriers."),
    Domain("D6", "expense-and-mileage", "Expense and mileage", "receipt",
           "Money spent doing the work: employee expenses, project expenses, mileage, cars, payment methods, expense types, receipts."),
    Domain("D7", "billing", "Billing", "file-invoice-dollar",
           "Turning settled work into a receivable: invoices, lines, credit notes, booking, invoicing potential."),
    Domain("D8", "people", "People", "users",
           "The company and who is in it: employees, departments, legal entities, users, roles, licences, working time, competences."),
    Domain("D9", "planning", "Planning", "calendar-days",
           "Forward-looking capacity: who is planned onto what, when, and how much is left."),
    Domain("D10", "payroll-and-absence", "Payroll and absence", "money-check-dollar",
           "Salary accounts, groups, postings, allowance legislation, holiday calendars, absence codes."),
    Domain("D11", "extensibility", "Extensibility", "plug",
           "The seams: custom fields, external keys and links, external systems, integration conflicts, the change log."),
    Domain("D12", "reporting", "Reporting", "chart-line",
           "Reading the business back: reports, KPIs, widgets and dashboards."),
]
BY_CODE = {d.code: d for d in DOMAINS}

# Contract tag -> domain. An unmapped tag fails the build rather than silently dropping operations.
TAG_DOMAIN = {
    "Customers": "D1", "Customer statuses": "D1",
    "Projects": "D2", "Project lifecycle": "D2", "Project reference lists": "D2",
    "Calendar events": "D4", "Time entries": "D4",
    "Bookings": "D9",
}
WEBHOOK_DOMAIN = {"customers": "D1", "projects": "D2", "calendar-events": "D4"}
METHODS = ("get", "post", "put", "patch", "delete")
ACRONYMS = {"id": "ID"}


# ---------------------------------------------------------------- bundling

def _rewrite_refs(node):
    if isinstance(node, dict):
        return {k: (("#" + v[len(SHARED_PREFIX):]) if k == "$ref" and isinstance(v, str) and v.startswith(SHARED_PREFIX)
                    else _rewrite_refs(v)) for k, v in node.items()}
    if isinstance(node, list):
        return [_rewrite_refs(v) for v in node]
    return node


def _external_refs(node, found: set[str]) -> set[str]:
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str) and not v.startswith("#"):
                found.add(v)
            else:
                _external_refs(v, found)
    elif isinstance(node, list):
        for v in node:
            _external_refs(v, found)
    return found


def bundle(name: str, shared: dict) -> dict:
    spec = yaml.safe_load((SPEC_DIR / name / "openapi.yaml").read_text(encoding="utf-8"))
    spec = _rewrite_refs(spec)
    comps = spec.setdefault("components", {})
    for section, entries in shared.get("components", {}).items():
        target = comps.setdefault(section, {})
        for key, value in entries.items():
            existing = target.get(key)
            # A spec entry that is only a pointer to the shared entry of the same name is replaced by the definition.
            if existing is None or existing == {"$ref": f"#/components/{section}/{key}"}:
                target[key] = copy.deepcopy(value)
            elif existing != value:
                sys.exit(f"{name}: components.{section}.{key} differs from _shared; refusing to guess which wins")
    leftovers = _external_refs(spec, set())
    if leftovers:
        sys.exit(f"{name}: unresolved external $ref after bundling: {sorted(leftovers)[:5]}")
    spec["servers"] = copy.deepcopy(SERVERS)
    return spec


# ---------------------------------------------------------------- target model (planned resources)

def planned_resources() -> dict[str, list[dict]]:
    """`#### `name` (C-xx) · TIER · ...` headings under each `## Dn` section, with their Purpose line."""
    lines = TARGET_MODEL.read_text(encoding="utf-8").splitlines()
    out: dict[str, list[dict]] = {d.code: [] for d in DOMAINS}
    current = None
    for i, line in enumerate(lines):
        m = re.match(r"^## (D\d+) ", line)
        if m:
            current = m.group(1)
            continue
        if line.startswith("## "):
            current = None
        if current and line.startswith("#### "):
            names = re.findall(r"`([^`]+)`", line.split("(")[0])
            tier = "MUST" if " MUST" in line else "SHOULD" if " SHOULD" in line else ""
            kind = "View" if " view " in line or "(V-" in line else "Resource"
            purpose = ""
            for nxt in lines[i + 1 : i + 6]:
                if nxt.startswith("**Purpose.**"):
                    purpose = nxt[len("**Purpose.**"):].strip()
                    break
            out[current].append({"names": names, "tier": tier, "kind": kind, "purpose": purpose})
    return out


# ---------------------------------------------------------------- MDX helpers

def kebab(op_id: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", op_id).lower()


def humanize(op_id: str) -> str:
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", op_id).lower().split()
    words = [ACRONYMS.get(w, w) for w in words]
    text = " ".join(words)
    return text[0].upper() + text[1:]


def mdx_safe(text: str) -> str:
    """Escape MDX-significant characters outside inline code spans."""
    parts = re.split(r"(`[^`]*`)", text)
    return "".join(p if p.startswith("`") else p.replace("{", "\\{").replace("}", "\\}").replace("<", "&lt;")
                   for p in parts)


def first_sentence(text: str, limit: int = 220) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    s = m.group(1) if m else text
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def frontmatter(**kv) -> str:
    body = "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in kv.items() if v is not None)
    return f"---\n{body}\n---\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


WIP_BANNER = (
    "<Warning>\n"
    "**POC · work in progress.** This is a draft `/v1` contract rendered for presentation. "
    "The endpoints are not live, and names, fields and base URLs can still change before the contract freeze.\n"
    "</Warning>\n"
)


# ---------------------------------------------------------------- pages

def domain_page(d: Domain, planned: list[dict], covered: set[str]) -> str:
    has_ops = bool(d.ops)
    fm = frontmatter(
        title=f"{d.code} · {d.name}",
        sidebarTitle="Overview",
        description=d.boundary,
        icon=d.icon,
        tag=None if has_ops else "Planned",
    )
    out = [fm, WIP_BANNER]
    if has_ops:
        out.append(f"\n## Methods\n\n{len(d.ops)} operations are declared in the draft contract for this domain.\n\n"
                   "| Method | Endpoint | What it does |\n|---|---|---|\n")
        for op in d.ops:
            out.append(f"| `{op['method'].upper()}` | [`{op['path']}`](/{SECTION}/{d.slug}/{op['slug']}) "
                       f"| {mdx_safe(op['summary'])} |\n")
        if d.events:
            out.append("\n## Events\n\n| Event | When it fires |\n|---|---|\n")
            for ev in d.events:
                out.append(f"| [`{ev['name']}`](/{SECTION}/{d.slug}/events/{ev['slug']}) | {mdx_safe(ev['summary'])} |\n")
    else:
        out.append("\n<Info>No methods are declared for this domain yet. "
                   "It is listed so the full shape of the API is visible.</Info>\n")

    remaining = [r for r in planned if not all(n.split("/")[0] in covered for n in r["names"])]
    if remaining:
        heading = "Planned resources" if not has_ops else "Planned next in this domain"
        out.append(f"\n## {heading}\n\nFrom the target API model. Not yet specified as a contract.\n\n"
                   "| Resource | Type | Priority | Purpose |\n|---|---|---|---|\n")
        for r in remaining:
            names = " · ".join(f"`{n}`" for n in r["names"])
            out.append(f"| {names} | {r['kind']} | {r['tier']} | {mdx_safe(first_sentence(r['purpose']))} |\n")
    return "".join(out)


def index_page() -> str:
    cards = []
    for d in DOMAINS:
        status = f"{len(d.ops)} methods" if d.ops else "Planned"
        cards.append(f'  <Card title="{d.code} · {d.name}" icon="{d.icon}" href="/{SECTION}/{d.slug}/overview">\n'
                     f"    {status}. {mdx_safe(d.boundary)}\n  </Card>\n")
    total_ops = sum(len(d.ops) for d in DOMAINS)
    total_ev = sum(len(d.events) for d in DOMAINS)
    live = sum(1 for d in DOMAINS if d.ops)
    return (
        frontmatter(title="TimeLog Phoenix Public REST API", sidebarTitle="Introduction",
                    description="The next-generation TimeLog public API, organised by business domain.", icon="flask")
        + WIP_BANNER
        + f"""
The Phoenix Public REST API is one versioned API for every TimeLog business domain. It is designed for
external developers first: predictable resource names, one error shape, cursor pagination and signed events.

This reference is organised the way the business is: **domain → methods**. {len(DOMAINS)} domains are listed;
{live} have a draft contract today ({total_ops} methods, {total_ev} events). The rest are shown as planned, so you can see
the full scope of the API.

## Base URL

```bash
{BASE_URL}/v1
```

| Environment | Base URL |
|---|---|
""" + "".join(f"| {s['description']} | `{s['url']}/v1` |\n" for s in SERVERS) + f"""
The tenant is derived from your credential, so the URL is the same for every customer.

## Authentication

Send a bearer token on every request.

```bash
curl {BASE_URL}/v1/customers \\
  -H "Authorization: Bearer $TIMELOG_API_TOKEN"
```

## Conventions at a glance

| Topic | Convention |
|---|---|
| Ids | `<prefix>_<ULID>`, one prefix per type, for example `cus_` and `prj_` |
| Your own keys | `GET` and `PUT /v1/<resource>/ext:{{ns}}:{{key}}` look up or upsert by your system's id |
| Values | `snake_case` fields, RFC 3339 UTC timestamps, `YYYY-MM-DD` dates |
| Lists | `{{ data, meta: {{ next_cursor, has_more }} }}`, keyset cursor, default 50, max 100 |
| Writes | `Idempotency-Key` header, `ETag` / `If-Match` for safe updates |
| Errors | One problem shape with a stable `code` and a `retryable` flag |
| Rate limits | `RateLimit-*` headers on every response, `429` with `Retry-After` |
| Events | Thin, signed, at-least-once webhooks delivered after commit |

## Domains

<CardGroup cols={{2}}>
""" + "".join(cards) + "</CardGroup>\n"
    )


# ---------------------------------------------------------------- main

def main() -> None:
    shared = yaml.safe_load((SPEC_DIR / "_shared" / "components.yaml").read_text(encoding="utf-8"))
    if OUT.exists():
        shutil.rmtree(OUT)  # generated directory: prune pages the contracts no longer produce
    covered: set[str] = set()

    for name in SPECS:
        spec = bundle(name, shared)
        spec_path = f"/{SECTION}/openapi/{name}.yaml"
        write(OUT / "openapi" / f"{name}.yaml",
              f"# GENERATED by scripts/build_phoenix_poc.py from the vault contract '{name}'. Do not edit.\n"
              + yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=120))

        for path, item in spec["paths"].items():
            covered.add(path.split("/")[2])
            for method in METHODS:
                op = item.get(method)
                if not op:
                    continue
                tag = (op.get("tags") or [None])[0]
                if tag not in TAG_DOMAIN:
                    sys.exit(f"{name}: {method.upper()} {path} has unmapped tag {tag!r}")
                d = BY_CODE[TAG_DOMAIN[tag]]
                slug = kebab(op["operationId"])
                d.ops.append({"method": method, "path": path, "summary": op.get("summary", ""), "slug": slug})
                write(OUT / d.slug / f"{slug}.mdx",
                      frontmatter(openapi=f"{spec_path} {method.upper()} {path}",
                                  sidebarTitle=humanize(op["operationId"])) + "\n" + WIP_BANNER)

        for event, item in (spec.get("webhooks") or {}).items():
            d = BY_CODE[WEBHOOK_DOMAIN[name]]
            op = next(iter(item.values()))
            slug = event.replace(".", "-").replace("_", "-")
            d.events.append({"name": event, "summary": op.get("summary", ""), "slug": slug})
            write(OUT / d.slug / "events" / f"{slug}.mdx",
                  frontmatter(openapi=f"{spec_path} webhook {event}", sidebarTitle=event) + "\n" + WIP_BANNER)

    planned = planned_resources()
    for d in DOMAINS:
        write(OUT / d.slug / "overview.mdx", domain_page(d, planned[d.code], covered))
    write(OUT / "index.mdx", index_page())

    # docs.json: replace (or append) the Phoenix group, keep everything else as is.
    nav_groups = []
    for d in DOMAINS:
        pages: list = [f"{SECTION}/{d.slug}/overview"] + [f"{SECTION}/{d.slug}/{o['slug']}" for o in d.ops]
        if d.events:
            pages.append({"group": "Events", "icon": "bolt",
                          "pages": [f"{SECTION}/{d.slug}/events/{e['slug']}" for e in d.events]})
        nav_groups.append({"group": f"{d.code} · {d.name}", "icon": d.icon, "pages": pages})
    phoenix = {"group": GROUP_NAME, "icon": "flask", "pages": [f"{SECTION}/index", *nav_groups]}

    docs_path = REPO / "docs.json"
    docs = json.loads(docs_path.read_text(encoding="utf-8"))
    top = docs["navigation"]["pages"]
    top[:] = [g for g in top if not (isinstance(g, dict) and g.get("group") == GROUP_NAME)] + [phoenix]
    docs_path.write_text(json.dumps(docs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    print(f"{sum(len(d.ops) for d in DOMAINS)} methods, {sum(len(d.events) for d in DOMAINS)} events, "
          f"{len(DOMAINS)} domains ({sum(1 for d in DOMAINS if not d.ops)} planned-only)")
    for d in DOMAINS:
        print(f"  {d.code:4} {d.name:22} {len(d.ops):3} methods {len(d.events):3} events")


if __name__ == "__main__":
    main()
