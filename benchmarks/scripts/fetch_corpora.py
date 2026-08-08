#!/usr/bin/env python3
"""Opt-in, non-destructive fetcher for benchmark public corpora."""
import argparse, json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()
def entries(corpora):
    for corpus in corpora["corpora"]:
        if "members" in corpus:
            for member in corpus["members"]:
                yield f'{corpus["id"]}/{member["id"]}', member
        else: yield corpus["id"], corpus

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--destination", required=True, type=pathlib.Path); args=p.parse_args()
    data=json.loads((ROOT/"corpora.json").read_text()); args.destination.mkdir(parents=True, exist_ok=True)
    for name, item in entries(data):
        target=args.destination/name
        if target.exists():
            if not (target/".git").is_dir(): raise SystemExit(f"refusing non-git target: {target}")
            sha=run("git", "rev-parse", "HEAD", cwd=target)
            print(f"reuse {name}: {sha}"); continue
        target.parent.mkdir(parents=True, exist_ok=True)
        # clone is deliberately non-shallow so revision tags resolve consistently.
        run("git", "clone", "--branch", item["revision"], "--single-branch", item["source_url"], str(target))
        print(f"fetched {name}: {run('git', 'rev-parse', 'HEAD', cwd=target)}")
if __name__ == "__main__": main()
