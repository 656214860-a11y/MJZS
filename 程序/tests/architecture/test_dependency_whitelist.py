"""依赖门禁：生产六包必装且精确锁版，开发工具只允许、不要求安装。

生产版本唯一来源为 requirements.txt；仅发现当前解释器 purelib 内的
第三方 distribution，不扫描用户 site-packages，也不导入待核验的库。
"""
import re
import sysconfig
import unittest
from importlib.metadata import distributions
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REQUIREMENTS = Path(__file__).resolve().parents[2] / "requirements.txt"

# R3215 已允许的维护工具：存在时检查版本，不要求产品运行环境安装。
# 包管理器保留历史允许策略，但不属于产品依赖锁，也不要求随包安装。
DEVELOPMENT_OPTIONAL = {
    "gallery-dl": "1.32.19",
    "playwright": "1.65.1",
    "greenlet": "3.5.6",
    "apted": "1.0.3",
    "ruff": "0.15.20",
    "tree-sitter": "0.26.0",
    "tree-sitter-python": "0.25.0",
    "pip": None,
    "setuptools": None,
    "wheel": None,
}


def _canon(name):
    """遵循 distribution 名称的大小写及连字符、下划线、点号等价规则。"""
    return re.sub(r"[-_.]+", "-", name.strip()).lower()


def parse_production_lock(text):
    """读取简单的精确版本锁；拒绝范围、重复包和其他安装指令。"""
    locked = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.partition("#")[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)", line)
        if not match:
            raise ValueError(f"requirements.txt 第 {number} 行必须为 包名==精确版本")
        name, version = match.groups()
        name = _canon(name)
        if name in locked:
            raise ValueError(f"requirements.txt 重复包: {name}")
        locked[name] = version
    return locked


def production_requirements():
    return parse_production_lock(REQUIREMENTS.read_text(encoding="utf-8"))


def bundled_distributions():
    """只枚举 purelib 自身，避免默认 sys.path 发现用户级 distribution。"""
    root = Path(sysconfig.get_paths()["purelib"]).resolve()
    return {
        _canon(dist.metadata["Name"]): dist.version
        for dist in distributions(path=[str(root)])
        if dist.metadata.get("Name")
    }


def validate_distributions(installed, production, optional=DEVELOPMENT_OPTIONAL):
    """纯验证函数；映射可注入，不安装、扫描或清理任何环境。"""
    installed = {_canon(name): version for name, version in installed.items()}
    production = {_canon(name): version for name, version in production.items()}
    optional = {_canon(name): version for name, version in optional.items()}
    expected = {**optional, **production}
    return {
        "unknown": sorted(set(installed) - set(expected)),
        "missing": sorted(set(production) - set(installed)),
        "version_mismatches": [
            f"{name}: {installed[name]}（预期 {version}）"
            for name, version in sorted(expected.items())
            if name in installed and version is not None and installed[name] != version
        ],
    }


class DependencyWhitelistTests(unittest.TestCase):
    def setUp(self):
        self.validation = validate_distributions(bundled_distributions(), production_requirements())

    def test_site_packages_whitelist(self):
        self.assertFalse(self.validation["unknown"],
                         f"purelib 发现未允许的第三方包: {self.validation['unknown']}")

    def test_whitelist_versions(self):
        self.assertFalse(self.validation["version_mismatches"],
                         "依赖版本不一致:\n" + "\n".join(self.validation["version_mismatches"]))

    def test_whitelist_completeness(self):
        self.assertFalse(self.validation["missing"],
                         f"purelib 缺少生产依赖: {self.validation['missing']}")


class DependencyValidationTests(unittest.TestCase):
    def setUp(self):
        self.production = production_requirements()

    def test_production_lock_has_exactly_six_packages(self):
        self.assertEqual(set(self.production), {
            "requests", "urllib3", "certifi", "charset-normalizer", "idna", "pillow",
        })
        self.assertTrue(all(self.production.values()))
        self.assertFalse(set(self.production) & set(DEVELOPMENT_OPTIONAL))

    def test_production_only_is_complete(self):
        self.assertEqual(validate_distributions(self.production, self.production), {
            "unknown": [], "missing": [], "version_mismatches": [],
        })

    def test_missing_production_dependency_is_reported(self):
        installed = dict(self.production)
        del installed["requests"]
        self.assertEqual(validate_distributions(installed, self.production)["missing"], ["requests"])

    def test_old_requests_version_is_rejected(self):
        installed = {**self.production, "requests": "2.32.3"}
        self.assertEqual(validate_distributions(installed, self.production)["version_mismatches"],
                         [f"requests: 2.32.3（预期 {self.production['requests']}）"])

    def test_unknown_distribution_is_reported(self):
        installed = {**self.production, "unapproved-package": "1.0"}
        self.assertEqual(validate_distributions(installed, self.production)["unknown"],
                         ["unapproved-package"])

    def test_optional_development_packages_are_allowed(self):
        installed = {**self.production, **{
            name: version or "sample-version" for name, version in DEVELOPMENT_OPTIONAL.items()
        }}
        self.assertEqual(validate_distributions(installed, self.production), {
            "unknown": [], "missing": [], "version_mismatches": [],
        })

    def test_installed_development_package_version_is_checked(self):
        installed = {**self.production, "ruff": "wrong-version"}
        self.assertEqual(validate_distributions(installed, self.production)["version_mismatches"],
                         [f"ruff: wrong-version（预期 {DEVELOPMENT_OPTIONAL['ruff']}）"])

    def test_distribution_names_are_normalized(self):
        installed = {**self.production, "Pillow": self.production["pillow"],
                     "gallery_dl": DEVELOPMENT_OPTIONAL["gallery-dl"]}
        del installed["pillow"]
        self.assertEqual(validate_distributions(installed, self.production), {
            "unknown": [], "missing": [], "version_mismatches": [],
        })
        self.assertEqual(_canon("Tree_Sitter.Python"), "tree-sitter-python")

    def test_production_version_comes_from_lock_mapping(self):
        changed_lock = {**self.production, "requests": "sample-new-lock"}
        result = validate_distributions(self.production, changed_lock)
        self.assertEqual(result["version_mismatches"],
                         [f"requests: {self.production['requests']}（预期 sample-new-lock）"])

    def test_lock_rejects_unpinned_duplicate_or_install_options(self):
        for text in ("requests>=2", "requests", "-r other.txt", "requests==2.*",
                     "Pillow==1\npillow==2"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_production_lock(text)

    def test_lock_accepts_comments_and_normalizes_names(self):
        self.assertEqual(parse_production_lock("# note\nPillow==1.0 # pinned\ngallery_dl==2.0\n"),
                         {"pillow": "1.0", "gallery-dl": "2.0"})

    def test_discovery_passes_only_purelib_to_metadata(self):
        root = (REQUIREMENTS.parent / "purelib-test-only").resolve()
        fake = SimpleNamespace(metadata={"Name": "Pillow"}, version="sample")
        with patch(__name__ + ".sysconfig.get_paths", return_value={"purelib": str(root)}), \
                patch(__name__ + ".distributions", return_value=[fake]) as discover:
            self.assertEqual(bundled_distributions(), {"pillow": "sample"})
        discover.assert_called_once_with(path=[str(root)])


if __name__ == "__main__":
    unittest.main()
