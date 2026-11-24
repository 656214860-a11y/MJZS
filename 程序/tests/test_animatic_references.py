"""S04 分镜预演参考库：文件名自动归类、按镜配图、旧根目录兼容与单图改类。

锚定需求设计卡 S04-REF-LIBRARY（需求编号待阶段文件登记后补锚）：导入图
按文件名归入 角色/场景/风格（同名既是角色又是场景时归角色），每镜按
characters 与 location 自动配图，旧版根目录未分类图只读兼容、不搬动，
支持修改单张参考图分类。只用临时目录，不开 Tk、不碰用户项目库。
"""
import tempfile
import unittest
from pathlib import Path

from domain.animatic_references import (
    CATEGORIES,
    UNCATEGORIZED,
    classify,
    import_plan,
    library,
    normalize_name,
    refs_for_shot,
)
from stage_execution_service import (
    animatic_reference_library,
    import_animatic_reference_library,
    reclassify_animatic_reference,
    refs_for_animatic_shot,
)
from contract.stage_path_service import shared_reference_dir


def _image(folder, name, raw):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(raw)
    return path


def _item(folder, name, key, category):
    return {'path': Path(folder) / name, 'name': name, 'stem_key': key, 'category': category}


class NormalizeAndClassifyTests(unittest.TestCase):
    def test_normalize_name_strips_extension_and_variant_suffixes(self):
        """DES-S04-20：去扩展名后取首个 _/- 前段，去首尾空白并做 NFKC 统一。"""
        self.assertEqual(normalize_name('林夏_侧.png'), '林夏')
        self.assertEqual(normalize_name(' 林夏 -特写.webp'), '林夏')
        self.assertEqual(normalize_name('林夏－正脸.jpeg'), '林夏', '全角连字符 NFKC 归一')
        self.assertEqual(normalize_name('雨夜仓库.jpg'), '雨夜仓库')

    def test_classify_character_location_else_style(self):
        """归类规则：匹配角色归角色、匹配场景归场景、否则归风格。"""
        characters, locations = ('林夏', '顾城'), ('雨夜仓库',)
        self.assertEqual(classify('林夏_侧.png', characters, locations), ('角色', '林夏'))
        self.assertEqual(classify('雨夜仓库-日.jpg', characters, locations), ('场景', '雨夜仓库'))
        self.assertEqual(classify('厚涂质感.png', characters, locations), ('风格', '厚涂质感'))

    def test_classify_prefers_character_when_name_is_both(self):
        """DES-S04-20：同一名称既是角色又是场景时归角色。"""
        self.assertEqual(classify('林夏.png', ('林夏',), ('林夏',)), ('角色', '林夏'))


class ImportPlanTests(unittest.TestCase):
    def test_empty_sources_produce_empty_plan(self):
        self.assertEqual(import_plan([]), {})
        self.assertEqual(import_plan([], characters=(), locations=()), {})

    def test_groups_by_category_and_keeps_readable_names(self):
        """导入键为 <类别>/<文件名>，保留可读文件名。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = import_plan(
                [_image(root, '林夏_侧.png', b'linxia'), _image(root, '仓库.png', b'scene'),
                 _image(root, '厚涂.png', b'style')],
                characters=('林夏',), locations=('仓库',))
            self.assertEqual(plan, {'角色/林夏_侧.png': b'linxia', '场景/仓库.png': b'scene',
                                    '风格/厚涂.png': b'style'})

    def test_same_content_different_names_is_deduplicated(self):
        """同内容不同文件名去重跳过。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = import_plan([_image(root, '林夏_正.png', b'same'),
                                _image(root, '林夏_侧.png', b'same')], characters=('林夏',))
            self.assertEqual(plan, {'角色/林夏_正.png': b'same'})

    def test_same_name_different_content_is_numbered(self):
        """不同内容同名自动编号 名(2).png、名(3).png。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = import_plan([_image(root / 'a', '林夏.png', b'a'),
                                _image(root / 'b', '林夏.png', b'b'),
                                _image(root / 'c', '林夏.png', b'c')], characters=('林夏',))
            self.assertEqual(sorted(plan), ['角色/林夏(2).png', '角色/林夏(3).png', '角色/林夏.png'])

    def test_existing_content_and_names_are_respected(self):
        """与库内已有图同内容跳过、同名编号接续。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            held = _image(root / 'ref' / '角色', '林夏.png', b'held')
            self.assertEqual(import_plan([_image(root, '任意.png', b'held')],
                                         characters=('林夏',), existing=(held,)), {})
            plan = import_plan([_image(root, '林夏.png', b'new')],
                               characters=('林夏',), existing=(held,))
            self.assertEqual(list(plan), ['角色/林夏(2).png'])

    def test_explicit_category_overrides_classification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = import_plan([_image(root, '任意名.png', b'x')], category='场景')
            self.assertEqual(list(plan), ['场景/任意名.png'])
            with self.assertRaises(ValueError):
                import_plan([_image(root, 'a.png', b'a')], category='武器')

    def test_rejects_bad_suffix_empty_and_oversize(self):
        """仅 PNG/JPEG/WebP 且 0<大小≤20MB，违例抛 ValueError。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                import_plan([_image(root, 'a.bmp', b'x')])
            with self.assertRaises(ValueError):
                import_plan([_image(root, 'empty.png', b'')])
            big = root / 'big.png'
            with big.open('wb') as stream:
                stream.seek(20 * 1024 * 1024)
                stream.write(b'x')
            with self.assertRaises(ValueError):
                import_plan([big])


class LibraryAndShotRefsTests(unittest.TestCase):
    def test_library_groups_categories_and_marks_root_files_uncategorized(self):
        """根目录旧图归未分类不搬动；角色/场景/风格 子目录各归其类。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / 'ref'
            _image(folder / '角色', '林夏_侧.png', b'a')
            _image(folder / '场景', '仓库.png', b'b')
            _image(folder / '风格', '厚涂.png', b'c')
            legacy_root = _image(folder, 'd3adbeef.png', b'd')       # 旧版摘要命名
            legacy_dir = _image(root / '04资产管理' / '参考图', 'o.jpg', b'o')  # 旧资产参考图目录
            lib = library((folder, legacy_dir.parent))
            self.assertEqual([i['name'] for i in lib['角色']], ['林夏_侧.png'])
            self.assertEqual(lib['角色'][0]['stem_key'], '林夏')
            self.assertEqual([i['name'] for i in lib['场景']], ['仓库.png'])
            self.assertEqual([i['name'] for i in lib['风格']], ['厚涂.png'])
            self.assertEqual({i['path'] for i in lib[UNCATEGORIZED]}, {legacy_root, legacy_dir})
            items = [i for rows in lib.values() for i in rows]
            self.assertEqual(len({i['path'] for i in items}), len(items), '按路径去重')
            self.assertEqual(set(lib), {*CATEGORIES, UNCATEGORIZED})
            self.assertTrue(legacy_root.is_file(), '旧图保持原位')

    def test_refs_for_shot_matches_characters_location_and_all_styles(self):
        """每镜取命中的角色图＋场景图＋全部风格图，去重保序。"""
        lib = {'角色': [_item('r', '林夏_侧.png', '林夏', '角色'),
                        _item('r', '顾城.png', '顾城', '角色')],
               '场景': [_item('r', '仓库.png', '仓库', '场景')],
               '风格': [_item('r', '厚涂.png', '厚涂', '风格')],
               UNCATEGORIZED: [_item('r', '旧.png', '旧', UNCATEGORIZED)]}
        shot = {'characters': ['林夏'], 'location': '仓库'}
        self.assertEqual(refs_for_shot(shot, lib),
                         (lib['角色'][0]['path'], lib['场景'][0]['path'], lib['风格'][0]['path']))
        shot_multi = {'characters': ['林夏', '顾城'], 'location': ''}
        self.assertEqual(refs_for_shot(shot_multi, lib),
                         (lib['角色'][0]['path'], lib['角色'][1]['path'], lib['风格'][0]['path']))

    def test_refs_for_shot_falls_back_to_uncategorized_then_empty(self):
        """未匹配任何分类图时退回未分类全部图；仍空返回 ()。"""
        uncategorized = [_item('r', '旧a.png', '旧a', UNCATEGORIZED),
                         _item('r', '旧b.png', '旧b', UNCATEGORIZED)]
        lib = {'角色': [], '场景': [], '风格': [], UNCATEGORIZED: uncategorized}
        shot = {'characters': ['不存在'], 'location': '也没有'}
        self.assertEqual(refs_for_shot(shot, lib),
                         tuple(i['path'] for i in uncategorized))
        empty = {'角色': [], '场景': [], '风格': [], UNCATEGORIZED: []}
        self.assertEqual(refs_for_shot(shot, empty), ())
        self.assertEqual(refs_for_shot({}, empty), ())


class GatewayTests(unittest.TestCase):
    def test_import_publishes_into_category_subdirs_and_skips_duplicates(self):
        """经共享参考图目录原子发布；同内容再导入去重返回 ()。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = _image(root, '林夏_侧.png', b'linxia')
            target = (shared_reference_dir(root) / '角色' / '林夏_侧.png').resolve()
            published = import_animatic_reference_library(root, [source], characters=('林夏',))
            self.assertEqual(tuple(published), (target,))
            self.assertEqual(target.read_bytes(), b'linxia')
            again = _image(root, '改名.png', b'linxia')
            self.assertEqual(import_animatic_reference_library(root, [again], characters=('林夏',)),
                             (), '同内容已存在不重复写')

    def test_library_and_refs_for_animatic_shot(self):
        """库视图含分类与未分类；按镜配图自动命中并回退。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = shared_reference_dir(root)
            char = _image(folder / '角色', '林夏.png', b'linxia')
            _image(folder / '风格', '厚涂.png', b'style')
            old = _image(folder, 'd3adbeef.png', b'old')
            lib = animatic_reference_library(root)
            self.assertEqual({i['path'] for i in lib['角色']}, {char})
            self.assertIn(old, [i['path'] for i in lib[UNCATEGORIZED]])
            refs = refs_for_animatic_shot(root, {'characters': ['林夏'], 'location': ''})
            self.assertEqual({Path(p).resolve() for p in refs},
                             {char.resolve(), (folder / '风格' / '厚涂.png').resolve()})
            styled = refs_for_animatic_shot(root, {'characters': [], 'location': '不存在'})
            self.assertEqual([Path(p).resolve() for p in styled],
                             [(folder / '风格' / '厚涂.png').resolve()], '未命中角色场景仍附带全部风格图')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = _image(shared_reference_dir(root), '旧.png', b'old')
            fallback = refs_for_animatic_shot(root, {'characters': ['x'], 'location': 'y'})
            self.assertEqual([Path(p).resolve() for p in fallback], [old.resolve()],
                             '没有任何分类图可配时退回未分类全部图')


class ReclassifyTests(unittest.TestCase):
    def test_reclassify_writes_new_path_and_recycles_old(self):
        """改类把图原子写入新分类路径，旧文件进回收站。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = shared_reference_dir(root)
            old = _image(folder, 'd3adbeef.png', b'img')            # 旧根目录未分类图
            target = reclassify_animatic_reference(root, old, '角色')
            self.assertEqual(target, (folder / '角色' / 'd3adbeef.png').resolve())
            self.assertFalse(old.exists())
            self.assertEqual(target.read_bytes(), b'img')
            self.assertEqual({i['name'] for i in animatic_reference_library(root)['角色']},
                             {'d3adbeef.png'})
            renamed = reclassify_animatic_reference(root, target, '场景', new_name='仓库.png')
            self.assertEqual(renamed, (folder / '场景' / '仓库.png').resolve())
            self.assertEqual(renamed.read_bytes(), b'img')
            self.assertFalse(target.exists())

    def test_reclassify_rejects_escape_outside_and_bad_category(self):
        """源与目标必须在共享参考图目录内；越界路径与未知分类拒绝。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = shared_reference_dir(root)
            kept = _image(folder, 'a.png', b'a')
            with self.assertRaises(ValueError):
                reclassify_animatic_reference(root, folder / '..' / 'x.png', '角色')
            with self.assertRaises(ValueError):
                reclassify_animatic_reference(root, kept, '武器')
            with self.assertRaises(ValueError):
                reclassify_animatic_reference(root, kept, '角色', new_name='../逃.png')
            outside = _image(root / '04资产管理' / '参考图', 'o.png', b'o')
            with self.assertRaises(ValueError):
                reclassify_animatic_reference(root, outside, '角色')
            self.assertTrue(outside.is_file(), '旧目录图保持原位不搬动')
            self.assertTrue(kept.is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
