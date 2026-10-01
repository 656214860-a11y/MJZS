import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_repo.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_repo", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepositoryValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_current_repository_is_valid(self):
        self.assertEqual(self.module.validate_repository(ROOT), [])

    def test_detects_broken_relative_markdown_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("[missing](references/nope.md)\n", encoding="utf-8")

            errors = self.module.validate_markdown_links(root)

        self.assertTrue(any("references/nope.md" in error for error in errors))

    def test_detects_invalid_eval_weight_total(self):
        payload = {
            "schema_version": "1.0",
            "skill": "video-storyboard-gen",
            "evaluations": [
                {
                    "id": "only",
                    "name": "测试",
                    "prompt": "生成分镜",
                    "expectations": ["包含镜头"],
                    "weight": 0.5,
                }
            ],
        }

        errors = self.module.validate_evals(payload)

        self.assertTrue(any("1.0" in error for error in errors))

    def test_detects_obvious_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "unsafe.txt").write_text(
                "api_key = 'sk-" + "a" * 24 + "'\n",
                encoding="utf-8",
            )

            errors = self.module.scan_secrets(root)

        self.assertTrue(any("unsafe.txt" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
