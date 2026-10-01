import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "storyboard_gen.py"


def load_module():
    spec = importlib.util.spec_from_file_location("storyboard_gen", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StoryboardGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_generate_is_deterministic_and_covers_exact_duration(self):
        first = self.module.build_storyboard("山城早餐", "广告", 17, "本地早餐", "抖音")
        second = self.module.build_storyboard("山城早餐", "广告", 17, "本地早餐", "抖音")

        self.assertEqual(first, second)
        self.assertEqual(first["duration_seconds"], 17)
        self.assertEqual(first["shots"][0]["start_seconds"], 0)
        self.assertEqual(first["shots"][-1]["end_seconds"], 17)
        self.assertTrue(all(shot["duration_seconds"] > 0 for shot in first["shots"]))
        self.assertEqual(
            sum(shot["duration_seconds"] for shot in first["shots"]),
            17,
        )

    def test_short_duration_does_not_create_zero_length_shots(self):
        storyboard = self.module.build_storyboard("四秒片", "剧情", 4)

        self.assertEqual(len(storyboard["shots"]), 4)
        self.assertEqual(storyboard["shots"][-1]["end_seconds"], 4)

    def test_markdown_escapes_user_table_content(self):
        storyboard = self.module.build_storyboard("标题|换行\n测试", "宣传", 12)
        rendered = self.module.render_markdown(storyboard)

        self.assertIn("标题\\|换行 测试", rendered)


class StoryboardCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def test_json_output_is_stable_and_machine_readable(self):
        args = ("generate", "山城早餐", "--type", "广告", "--duration", "17", "--format", "json")
        first = self.run_cli(*args)
        second = self.run_cli(*args)

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        payload = json.loads(first.stdout)
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["title"], "山城早餐")

    def test_output_file_is_utf8_and_stdout_stays_empty(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "嵌套" / "分镜.json"
            result = self.run_cli(
                "generate",
                "山城早餐",
                "--format",
                "json",
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["title"], "山城早餐")

    def test_rejects_blank_title(self):
        result = self.run_cli("generate", "   ")

        self.assertEqual(result.returncode, 2)
        self.assertIn("标题不能为空", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_rejects_non_positive_duration(self):
        result = self.run_cli("generate", "测试", "--duration", "0")

        self.assertEqual(result.returncode, 2)
        self.assertIn("正整数", result.stderr)

    def test_missing_command_is_an_error(self):
        result = self.run_cli()

        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
