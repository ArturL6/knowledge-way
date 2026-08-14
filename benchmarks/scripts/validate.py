#!/usr/bin/env python3
"""Validate checked-in benchmark manifests or a produced result without dependencies."""
import argparse, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
def load(path):
    try: return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e: raise ValueError(f"{path}: {e}")
def validate_manifests():
    corpora=load(ROOT/"corpora.json"); tasks=load(ROOT/"tasks.json")
    if corpora.get("schema_version") != "1.0" or tasks.get("schema_version") != "1.0": raise ValueError("unsupported manifest schema version")
    ids=set()
    for c in corpora.get("corpora",[]):
        if not c.get("id"): raise ValueError("corpus without id")
        if c["id"] in ids: raise ValueError(f"duplicate corpus id: {c['id']}")
        ids.add(c["id"])
        for m in c.get("members",[]):
            if not all(m.get(k) for k in ("id","source_url","revision","license")): raise ValueError(f"incomplete member in {c['id']}")
            sha = m.get("resolved_sha")
            if sha is not None and (not isinstance(sha, str) or len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha)):
                raise ValueError(f"invalid resolved_sha for {c['id']}/{m['id']}")
    active = corpora.get("active_workspace")
    if active is not None and active not in ids: raise ValueError(f"unknown active_workspace: {active}")
    seen=set()
    for t in tasks.get("tasks",[]):
        if not t.get("id") or t["id"] in seen: raise ValueError(f"duplicate/missing task id: {t.get('id')}")
        seen.add(t["id"])
        root=t.get("corpus", "").split("/")[0]
        if root not in ids: raise ValueError(f"unknown corpus {t.get('corpus')} in {t['id']}")
        if t.get("category") not in tasks["task_categories"]: raise ValueError(f"unknown category in {t['id']}")
def validate_result(path):
    result=load(path); required={"schema_version","tool","run","provenance","metrics","tasks"}
    missing=required-result.keys()
    if missing: raise ValueError("result missing: "+", ".join(sorted(missing)))
    if result["schema_version"] != "1.0": raise ValueError("unsupported result schema version")
    for key in ("name","version","configuration"):
        if key not in result["tool"]: raise ValueError(f"tool missing {key}")
    task_ids={t["id"] for t in load(ROOT/"tasks.json")["tasks"]}
    for item in result["tasks"]:
        if item.get("id") not in task_ids: raise ValueError(f"unknown result task {item.get('id')}")
        if item.get("status") not in {"ok","failed","unsupported"}: raise ValueError(f"invalid task status {item.get('id')}")
def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--result", type=pathlib.Path); a=p.parse_args()
    try:
        validate_manifests()
        if a.result: validate_result(a.result)
    except ValueError as e: print(f"INVALID: {e}", file=sys.stderr); return 1
    print("VALID")
if __name__ == "__main__": raise SystemExit(main())
