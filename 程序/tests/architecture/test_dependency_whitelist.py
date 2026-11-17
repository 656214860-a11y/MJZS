"""
架构门禁：依赖白名单检查

守卫：
1. 随包环境（``sysconfig`` purelib，即 ``运行环境\\Python\\Lib\\site-packages``）
   下的所有第三方分发包都在白名单内；
2. 白名单库的版本与记录一致；
3. 白名单中的库都已安装（随包环境完整）。

取径说明：只统计随包环境内的分发包，不扫描用户级 site-packages
（开发机上的 mypy 等不属于随包交付物）。

R3199 新增；R3211 修复核验缺陷（原实现按 sys.path 首个 site-packages
取径会命中用户目录、urllib3 被 urllib 前缀误吞、模块级函数无法被
unittest 发现）。
"""
import sysconfig
import unittest
from importlib.metadata import distributions
from pathlib import Path

# 白名单：随包环境允许的第三方分发包 → 期望版本。
# requests 链为 R3199 批准的首个运行时依赖（R3200 起替换自实现 HTTP 客户端）；
# 其余为随包环境内的维护/开发工具，仅脚本使用，不进入产品运行路径。
WHITELIST = {
    "requests": "2.34.2",
    "urllib3": "2.8.0",
    "certifi": "2026.10.23",
    "charset-normalizer": "3.5.2",
    "idna": "3.20",
    "gallery_dl": "1.32.19",
    "pillow": "13.0.0",
    "playwright": "1.65.1",
    "greenlet": "3.5.6",
    "apted": "1.0.3",
    "ruff": "0.15.20",
    "tree-sitter": "0.26.0",
    "tree-sitter-python": "0.25.0",
}

# 包管理器自身不计入白名单。
EXEMPT = {"pip", "setuptools", "wheel"}


def _canon(name):
    return name.strip().lower()


def bundled_distributions():
    """随包环境（purelib）内的 {规范化包名: 版本}。"""
    root = Path(sysconfig.get_paths()["purelib"]).resolve()
    found = {}
    for dist in distributions():
        try:
            loc = Path(dist.locate_file("")).resolve()
        except Exception:
            continue
        if loc != root and root not in loc.parents:
            continue
        name = dist.metadata.get("Name")
        if name:
            found[_canon(name)] = dist.version
    return found


class DependencyWhitelistTests(unittest.TestCase):
    """检查 site-packages 下的所有包都在白名单内"""

    def test_site_packages_whitelist(self):
        installed = bundled_distributions()

        # 检查是否有未在白名单中的包
        unknown = set(installed) - set(WHITELIST) - EXEMPT

        self.assertFalse(unknown,
                         f"发现未在白名单中的第三方包: {sorted(unknown)}\n"
                         f"如需添加新依赖，请先更新 维护记录/依赖白名单.md 和本测试的 WHITELIST")

    def test_whitelist_versions(self):
        """检查白名单库的版本与记录一致"""
        installed = bundled_distributions()

        version_mismatches = []
        for pkg, expected_version in WHITELIST.items():
            actual_version = installed.get(pkg)
            if actual_version is None:
                version_mismatches.append(f"{pkg}: 未安装（预期 {expected_version}）")
            elif actual_version != expected_version:
                version_mismatches.append(f"{pkg}: {actual_version}（预期 {expected_version}）")

        self.assertFalse(version_mismatches,
                         "白名单库版本不一致:\n" + "\n".join(f"  - {m}" for m in version_mismatches))

    def test_whitelist_completeness(self):
        """检查白名单中的库都已安装"""
        installed = bundled_distributions()

        missing = [pkg for pkg in WHITELIST if pkg not in installed]

        self.assertFalse(missing,
                         f"白名单中的包未安装: {missing}\n"
                         f"请检查 运行环境\\Python\\Lib\\site-packages 是否完整")


if __name__ == "__main__":
    unittest.main()
