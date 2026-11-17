# -*- coding: utf-8 -*-
"""资产参考图路径安全与校验自检。运行：python test_reference_images.py"""
import base64, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from tests.architecture._scan import entity_file
from asset_reference_images import EXTENSIONS, safe_name, classified_target, image_bytes

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


class SafeNameTests(unittest.TestCase):
    def test_sanitize(self):
        self.assertEqual(safe_name("a/b:c*d"), "a_b_c_d")
    def test_empty(self):
        self.assertEqual(safe_name(""), "未命名")


class ClassifiedTargetTests(unittest.TestCase):
    def test_path_within_base(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            t = classified_target(base, "CHAR_001", "长相", "d" * 12, ".png", "角色甲")
            self.assertTrue(t.resolve().is_relative_to(base.resolve()))
            self.assertIn("CHAR_001", t.name)

    def test_wrong_role_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                classified_target(Path(td), "CHAR_001", "空间锚定", "d" * 12, ".png", "x")


class ImageBytesTests(unittest.TestCase):
    def test_valid_png(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "f.png"; p.write_bytes(PNG)
            self.assertEqual(image_bytes(p), PNG)

    def test_invalid_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "f.png"; p.write_bytes(b"not a png")
            with self.assertRaises(ValueError):
                image_bytes(p)


class ReferenceInstructionTests(unittest.TestCase):
    def test_empty(self):
        from asset_reference_images import reference_instruction
        self.assertEqual(reference_instruction({}), "")

    def test_non_dict_empty(self):
        from asset_reference_images import reference_instruction
        self.assertEqual(reference_instruction(None), "")
        self.assertEqual(reference_instruction("不是对象"), "")

    def test_non_list_refs_safe(self):
        from asset_reference_images import reference_instruction
        self.assertEqual(reference_instruction({"reference_images": "不是数组"}), "")

    def test_with_refs(self):
        from asset_reference_images import reference_instruction
        text = reference_instruction({"reference_images": ["a.png"], "reference_roles": {"a.png": "长相"}})
        self.assertIn("参考图1", text)
        self.assertIn("长相", text)


class PrepareFoldersTests(unittest.TestCase):
    def test_creates_role_folders(self):
        from asset_reference_images import prepare_folders
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            inboxes = prepare_folders(base)
            self.assertEqual(set(inboxes), {"角色", "场景", "道具"})
            self.assertTrue((base / "assets" / "参考图" / "角色" / "长相").is_dir())
            self.assertTrue((base / "assets" / "参考图" / "角色" / "待导入").is_dir())

    def test_truncates_long_name(self):
        self.assertEqual(len(safe_name("长" * 80)), 48)

    def test_truncation_does_not_end_with_space_or_dot(self):
        self.assertFalse(safe_name("a" * 47 + " " + "b").endswith((" ", ".")))
        self.assertFalse(safe_name("a" * 47 + "." + "b").endswith((" ", ".")))



class ExtensionSourceGuardTests(unittest.TestCase):
    """参考图后缀只留一处定义：选择对话框的文件过滤器必须由 EXTENSIONS 生成。

    对话框里原先另写了一份 '*.png *.jpg *.jpeg *.webp'，而模块里的 EXTENSIONS 从来没人用：
    两处一改一漏，「能选的文件」和「能通过校验的文件」就会悄悄分家。
    """

    def test_dialog_filter_is_built_from_extensions(self):
        source = entity_file("asset_reference_import").read_text(encoding="utf-8")
        self.assertIn("EXTENSIONS", source)
        self.assertNotIn("*.png", source)
        self.assertEqual(EXTENSIONS, {".png", ".jpg", ".jpeg", ".webp"})


class RoleCategoryTests(unittest.TestCase):
    """第 55 期第 6 条：参考图类目补了几条真用得上的，每条都得有「怎么用」的说明。"""

    def test_every_role_has_a_hint(self):
        from asset_reference_images import ROLE_GROUPS, ROLE_HINTS
        for prefix, roles in ROLE_GROUPS.items():
            for role in roles:
                self.assertIn(role, ROLE_HINTS, "%s 的「%s」缺一句用法说明" % (prefix, role))

    def test_the_new_roles_are_there(self):
        from asset_reference_images import ROLE_GROUPS
        self.assertIn("姿态动作", ROLE_GROUPS["CHAR"])
        self.assertIn("表情", ROLE_GROUPS["CHAR"])
        self.assertIn("多角度实景", ROLE_GROUPS["LOC"])
        self.assertIn("俯视布局", ROLE_GROUPS["LOC"])
        self.assertIn("使用场景", ROLE_GROUPS["PROP"])


class RoleSummaryTests(unittest.TestCase):
    """第 55 期第 6 条：「参考图（类目）」那一格的字。"""

    def summary(self, images=None, roles=None):
        from asset_reference_images import role_summary
        asset = {}
        if images is not None:
            asset["reference_images"] = images
        if roles is not None:
            asset["reference_roles"] = roles
        return role_summary(asset)

    def test_no_reference_images(self):
        from asset_reference_images import role_summary
        self.assertEqual(self.summary(), "—")
        self.assertEqual(self.summary([]), "—")
        self.assertEqual(self.summary("不是数组"), "—")
        self.assertEqual(role_summary(None), "—", "读不出资产也不能抛")

    def test_counts_are_grouped_by_role(self):
        self.assertEqual(self.summary(["a", "b", "c"], {"a": "长相", "b": "长相", "c": "服饰"}),
                         "3 张 · 长相2 服饰1")

    def test_roles_follow_the_registered_order(self):
        self.assertEqual(self.summary(["a", "b"], {"a": "服饰", "b": "长相"}), "2 张 · 长相1 服饰1")

    def test_unclassified_sits_last(self):
        self.assertEqual(self.summary(["a", "b"], {"a": "长相"}), "2 张 · 长相1 待分类1")

    def test_an_unregistered_role_is_kept(self):
        self.assertEqual(self.summary(["a"], {"a": "没人登记的类目"}), "1 张 · 没人登记的类目1")

if __name__ == "__main__":
    unittest.main(verbosity=2)
