import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ForkRealismManifestTests(unittest.TestCase):
    def test_checked_in_fork_realism_oracle_validates_offline(self):
        run = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_fork_realism.py")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "VALID")


if __name__ == "__main__":
    unittest.main()
