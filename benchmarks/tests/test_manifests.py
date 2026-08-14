import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class BenchmarkManifestTests(unittest.TestCase):
    def test_checked_in_manifests_validate_offline(self):
        run = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate.py")], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "VALID")

    def test_task_ids_are_unique_and_categories_are_declared(self):
        tasks = json.loads((ROOT / "tasks.json").read_text())
        ids = [task["id"] for task in tasks["tasks"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(task["category"] in tasks["task_categories"] for task in tasks["tasks"]))

    def test_runner_emits_a_valid_result_without_network_or_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary = pathlib.Path(temporary)
            corpus_root = temporary / "corpora"
            for name in (
                "fastapi-stack/fastapi", "fastapi-stack/starlette", "fastapi-stack/pydantic",
                "click-small", "flask-suite/flask", "flask-suite/werkzeug", "flask-suite/jinja",
            ):
                checkout = corpus_root / name
                checkout.mkdir(parents=True)
                subprocess.run(["git", "init"], cwd=checkout, check=True, capture_output=True)
                subprocess.run(["git", "-c", "user.name=Benchmark", "-c", "user.email=benchmark@example.invalid", "commit", "--allow-empty", "-m", "fixture"], cwd=checkout, check=True, capture_output=True)
            adapter = temporary / "adapter.py"
            adapter.write_text("import json, sys\nfor line in sys.stdin:\n r=json.loads(line); print(json.dumps({'tool_version':'test','measurement_notes':'test'} if r['operation']=='index' else {'status':'unsupported'}), flush=True)\n")
            config = temporary / "adapter.json"
            config.write_text(json.dumps({"command": [sys.executable, str(adapter)], "environment": {"API_TOKEN": "not-captured"}}))
            output = temporary / "result.json"
            run = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_benchmark.py"), "--tool", "fixture", "--adapter-config", str(config), "--corpora-dir", str(corpus_root), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(output.read_text())
            self.assertEqual(result["tool"]["configuration"]["environment"]["API_TOKEN"], "[REDACTED]")
            validation = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate.py"), "--result", str(output)], capture_output=True, text=True)
            self.assertEqual(validation.returncode, 0, validation.stderr)

if __name__ == "__main__":
    unittest.main()
