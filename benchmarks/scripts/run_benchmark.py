#!/usr/bin/env python3
"""Run a local newline-JSON adapter and write a provenance-rich benchmark result.
Adapter protocol: first request has operation=index, later requests operation=task. Each
response is one JSON object. Index response may include metrics; task response may include
precision_at_k, mrr, edge_precision, edge_recall, mcp_success, response, error, status.
"""
import argparse, datetime, json, os, pathlib, platform, re, subprocess, sys, time, uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
SECRET=re.compile(r"(pass(word)?|secret|token|key|credential|auth)", re.I)
def read_json(path): return json.loads(path.read_text())
def git(*args, cwd): return subprocess.run(["git",*args], cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()
def corpus_checkouts(root, manifest):
    found=[]
    for corpus in manifest["corpora"]:
        members=corpus.get("members") or [corpus]
        for member in members:
            name=f'{corpus["id"]}/{member["id"]}' if "members" in corpus else corpus["id"]
            directory=root/name
            if not (directory/".git").is_dir(): raise ValueError(f"missing git checkout: {directory}")
            found.append({"id":name,"path":str(directory),"resolved_sha":git("rev-parse","HEAD",cwd=directory)})
    return found
def redact(value):
    if isinstance(value,dict): return {k:("[REDACTED]" if SECRET.search(k) else redact(v)) for k,v in value.items()}
    if isinstance(value,list): return [redact(v) for v in value]
    return value
def hardware():
    info={"platform":platform.platform(),"python":platform.python_version(),"cpu_count":os.cpu_count()}
    try:
        for line in pathlib.Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                info["cpu_model"]=line.split(":",1)[1].strip(); break
        for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                info["memory_bytes"]=int(line.split()[1])*1024; break
    except OSError: pass
    return info
def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("--tool",required=True); p.add_argument("--adapter-config",required=True,type=pathlib.Path); p.add_argument("--corpora-dir",required=True,type=pathlib.Path); p.add_argument("--output",required=True,type=pathlib.Path); p.add_argument("--mode",choices=["cold","warm","update"],default="cold"); a=p.parse_args()
 if a.output.exists(): raise SystemExit(f"refusing to overwrite {a.output}")
 config=read_json(a.adapter_config); command=config.get("command")
 if not isinstance(command,list) or not command or not all(isinstance(x,str) for x in command): raise SystemExit("adapter config needs a non-empty command array")
 corpora=corpus_checkouts(a.corpora_dir,read_json(ROOT/"corpora.json")); tasks=read_json(ROOT/"tasks.json")["tasks"]
 env=os.environ.copy(); env.update({str(k):str(v) for k,v in config.get("environment",{}).items()})
 proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
 def request(payload):
  started=time.monotonic(); proc.stdin.write(json.dumps(payload)+"\n"); proc.stdin.flush(); line=proc.stdout.readline()
  if not line: raise RuntimeError("adapter ended without a JSON response")
  answer=json.loads(line); return answer, time.monotonic()-started
 try:
  index,index_time=request({"operation":"index","mode":a.mode,"corpora":corpora})
  outcomes=[]
  for task in tasks:
   try:
    answer,elapsed=request({"operation":"task","task":task,"corpora":corpora}); answer={k:v for k,v in answer.items() if k in {"status","precision_at_k","mrr","edge_precision","edge_recall","mcp_success","response","error"}}; answer.setdefault("status","ok")
   except Exception as exc: answer={"status":"failed","error":str(exc)}; elapsed=0.0
   outcomes.append({"id":task["id"],"wall_seconds":elapsed,**answer})
 finally:
  if proc.stdin: proc.stdin.close()
  stderr=proc.stderr.read() if proc.stderr else ""; proc.wait(timeout=10)
 result={"schema_version":"1.0","tool":{"name":a.tool,"version":str(index.get("tool_version","unknown")),"configuration":redact(config)},"run":{"id":str(uuid.uuid4()),"started_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"mode":a.mode},"provenance":{"harness_git_sha":git("rev-parse","HEAD",cwd=ROOT.parent),"corpora":corpora,"hardware":hardware(),"adapter":{"command":command,"stderr":stderr[-4000:]}},"metrics":{"index_wall_seconds":index.get("index_wall_seconds",index_time),"peak_rss_bytes":index.get("peak_rss_bytes"),"index_disk_bytes":index.get("index_disk_bytes"),"update_wall_seconds":index.get("update_wall_seconds"),"measurement_notes":index.get("measurement_notes","Adapter did not provide a measurement method.")},"tasks":outcomes}
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+"\n"); print(a.output)
if __name__=="__main__": main()
