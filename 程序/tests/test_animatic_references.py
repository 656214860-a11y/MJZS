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


class FormalAssetReuseTests(unittest.TestCase):
    """REQ-S04-113：S04 分镜预演按编号／名称／别名只读优先复用 S05 已入库正式资产图。"""

    def test_req_s04_113_formal_asset_entries_distinguish_ids_names_aliases_and_filter_invalid(self):
        """REQ-S04-113：CHAR_001 与 CHAR_002 精确编号隔离不串图；仅采信登记表内真实非空合法图片。"""
        from domain.animatic_references import formal_asset_entries
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            p1 = _image(base / 'assets' / 'characters', 'CHAR_001.png', b'c1')
            p2 = _image(base / 'assets' / 'characters', 'CHAR_002.png', b'c2')
            ps = _image(base / 'assets' / 'scenes', 'LOC_001.jpg', b's1')
            _image(base / 'assets' / 'characters', 'empty.png', b'')
            _image(base / 'assets' / 'characters', 'bad.bmp', b'bmp')
            _image(base / 'assets' / 'characters', 'plan_only.png', b'plan-only')
            outside = _image(base.parent, 'escape_ref_test.png', b'esc')
            self.addCleanup(lambda: outside.exists() and outside.unlink())
            plan = {
                'CHAR_001': {'name': '林夏', 'aliases': ['小夏']},
                'CHAR_002': {'name': '顾城', 'aliases': []},
                'CHAR_003': {'name': '空图'},
                'CHAR_004': {'name': '非法后缀'},
                'CHAR_005': {'name': '越界'},
                'CHAR_006': {'name': '未登记', 'image': 'assets/characters/plan_only.png'},
                'CHAR_007': {'name': '群演', 'requires_asset': False},
                'LOC_001': {'name': '雨夜仓库', 'aliases': ['旧仓库']},
                'PROP_001': {'name': '钥匙'},
            }
            registry = {
                'CHAR_001': {'name': '林夏', 'image': 'assets/characters/CHAR_001.png'},
                'CHAR_002': {'name': '顾城', 'image': 'assets/characters/CHAR_002.png'},
                'CHAR_003': {'image': 'assets/characters/empty.png'},
                'CHAR_004': {'image': 'assets/characters/bad.bmp'},
                'CHAR_005': {'image': '../escape_ref_test.png'},
                'CHAR_007': {'image': 'assets/characters/CHAR_001.png'},
                'LOC_001': {'image': 'assets/scenes/LOC_001.jpg'},
                'PROP_001': {'image': 'assets/characters/CHAR_001.png'},
            }
            entries = formal_asset_entries(plan, registry, base)
            self.assertEqual([e['aid'] for e in entries['角色']], ['CHAR_001', 'CHAR_002'])
            self.assertEqual([e['path'] for e in entries['角色']], [p1, p2])
            self.assertEqual([e['aid'] for e in entries['场景']], ['LOC_001'])
            self.assertEqual([e['path'] for e in entries['场景']], [ps])

            empty_lib = {'角色': [], '场景': [], '风格': [], UNCATEGORIZED: []}
            self.assertEqual(refs_for_shot({'characters': ['CHAR_001'], 'location': 'LOC_001'},
                                           empty_lib, formal_assets=entries), (p1, ps))
            self.assertEqual(refs_for_shot({'characters': ['CHAR_002'], 'location': ''},
                                           empty_lib, formal_assets=entries), (p2,))
            self.assertEqual(refs_for_shot({'characters': ['小夏'], 'location': '旧仓库'},
                                           empty_lib, formal_assets=entries), (p1, ps))

    def test_req_s04_113_formal_assets_take_priority_with_shared_fallback_and_styles(self):
        """REQ-S04-113：同镜角色优先用 S05 正式图，未命中角色回退共享参考库，风格图始终附加。"""
        from domain.animatic_references import formal_asset_entries
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            formal_lin = _image(root / '05资产管理' / 'assets' / 'characters', 'CHAR_001.png', b'formal')
            shared_lin = _image(root / 'shared' / '角色', '林夏.png', b'shared-lin')
            shared_gu = _image(root / 'shared' / '角色', '顾城.png', b'shared-gu')
            shared_scene = _image(root / 'shared' / '场景', '仓库.png', b'shared-scene')
            shared_style = _image(root / 'shared' / '风格', '厚涂.png', b'style')
            lib = library((root / 'shared',))
            formal = formal_asset_entries(
                {'CHAR_001': {'name': '林夏'}},
                {'CHAR_001': {'image': 'assets/characters/CHAR_001.png'}},
                root / '05资产管理',
            )
            picked = refs_for_shot({'characters': ['林夏', '顾城'], 'location': '仓库'},
                                   lib, formal_assets=formal)
            self.assertEqual([Path(p).resolve() for p in picked],
                             [formal_lin, shared_gu, shared_scene, shared_style])
            self.assertNotIn(shared_lin, [Path(p).resolve() for p in picked],
                             '已命中 S05 正式图的角色不重复带共享参考库同名草图')

    def test_req_s04_113_gateway_reuses_s05_read_only_and_degrades_when_missing(self):
        """REQ-S04-113：网关自动只读复用 S05 正式图，缺 S05 时静默降级，绝不写盘修改 S05。"""
        import json
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            # 无 05资产管理 时静默降级为空
            self.assertEqual(refs_for_animatic_shot(root, {'characters': ['林夏'], 'location': '仓库'}), ())
            # 建立 05资产管理 正式资产图
            base = root / '05资产管理'
            char_img = _image(base / 'assets' / 'characters', 'CHAR_001.png', b'formal-char')
            scene_img = _image(base / 'assets' / 'scenes', 'LOC_001.png', b'formal-scene')
            plan_path = base / 'assets' / '资产清单' / 'assets.json'
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_raw = json.dumps({'CHAR_001': {'name': '林夏', 'aliases': ['小夏']},
                                   'LOC_001': {'name': '雨夜仓库'}}, ensure_ascii=False).encode('utf-8')
            plan_path.write_bytes(plan_raw)
            reg_path = base / 'assets.json'
            reg_raw = json.dumps({'CHAR_001': {'image': 'assets/characters/CHAR_001.png'},
                                  'LOC_001': {'image': 'assets/scenes/LOC_001.png'}},
                                 ensure_ascii=False).encode('utf-8')
            reg_path.write_bytes(reg_raw)
            style_img = _image(shared_reference_dir(root) / '风格', '厚涂.png', b'style')

            refs = refs_for_animatic_shot(root, {'characters': ['CHAR_001'], 'location': '雨夜仓库'})
            self.assertEqual([Path(p).resolve() for p in refs],
                             [char_img, scene_img, style_img.resolve()])
            self.assertEqual(plan_path.read_bytes(), plan_raw, 'S04 严禁修改 S05 清单')
            self.assertEqual(reg_path.read_bytes(), reg_raw, 'S04 严禁修改 S05 登记表')

    def test_req_s04_113_status_summary_counts_reusable_formal_assets(self):
        """REQ-S04-113：有可复用正式资产图时状态栏摘要合并计数并标明来源，无资产时格式不变。"""
        from ui.animatic_view_state import format_status_summary
        lib = {'风格': [{'path': Path('style.png')}]}
        plain = format_status_summary({'shots': [{'id': 'SH001'}]}, lib, '静音', None, False)
        self.assertIn('参考图 1 张 /', plain)
        with_assets = format_status_summary(
            {'shots': [{'id': 'SH001'}]}, lib, '静音', None, False, formal_count=2)
        self.assertIn('参考图 3 张（含资产 2 张）', with_assets)

    def test_req_s04_115_113_shot_ref_badges_and_gateway_details(self):
        """REQ-S04-115/113：shot_ref_badges 与 refs_for_shot 严格同序，准确标出五类来源。"""
        import json
        from domain.animatic_references import formal_asset_entries, shot_ref_badges
        from stage_execution_service import shot_ref_details
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            base = root / '05资产管理'
            formal_lin = _image(base / 'assets' / 'characters', 'CHAR_001.png', b'formal-lin')
            plan_path = base / 'assets' / '资产清单' / 'assets.json'
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_path.write_text(json.dumps({'CHAR_001': {'name': '林夏'}}, ensure_ascii=False),
                                 encoding='utf-8')
            (base / 'assets.json').write_text(
                json.dumps({'CHAR_001': {'image': 'assets/characters/CHAR_001.png'}},
                           ensure_ascii=False), encoding='utf-8')
            shared = shared_reference_dir(root)
            shared_gu = _image(shared / '角色', '顾城.png', b'gu')
            shared_scene = _image(shared / '场景', '仓库.png', b'scene')
            shared_style = _image(shared / '风格', '厚涂.png', b'style')
            lib = library((shared,))
            formal = formal_asset_entries(
                {'CHAR_001': {'name': '林夏'}},
                {'CHAR_001': {'image': 'assets/characters/CHAR_001.png'}},
                base)
            shot = {'characters': ['林夏', '顾城'], 'location': '仓库'}
            refs = refs_for_shot(shot, lib, formal_assets=formal)
            badges = shot_ref_badges(shot, lib, formal_assets=formal)
            self.assertEqual([Path(b['path']).resolve() for b in badges],
                             [Path(p).resolve() for p in refs])
            self.assertEqual([b['source'] for b in badges], ['S05 资产', '角色', '场景', '风格'])
            self.assertTrue(all(isinstance(b['label'], str) and b['label'] for b in badges))
            gw_badges = shot_ref_details(root, shot)
            self.assertEqual([b['source'] for b in gw_badges], ['S05 资产', '角色', '场景', '风格'])
            self.assertEqual([Path(b['path']).resolve() for b in gw_badges],
                             [formal_lin, shared_gu.resolve(), shared_scene.resolve(),
                              shared_style.resolve()])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            uncat = _image(shared_reference_dir(root), 'legacy.png', b'old')
            badges = shot_ref_details(root, {'characters': ['无'], 'location': '无'})
            self.assertEqual(len(badges), 1)
            self.assertEqual(badges[0]['source'], UNCATEGORIZED)
            self.assertEqual(Path(badges[0]['path']).resolve(), uncat.resolve())


if __name__ == '__main__':
    unittest.main(verbosity=2)
