# -*- coding: utf-8 -*-
"""资产参考图候选自检：打分、阈值、去重、版权字段与确认入库。运行：python test_reference_search.py"""
import base64, json, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import asset_reference_search as search

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")

ASSET = {'id': 'CHAR_001', 'name': '银发少女', 'image_prompt': '银发长大衣少女，正面全身立绘，冷色调'}


def png(size=4096, fill=b'\x00'):
    """真实可校验的 PNG 形状：保留签名与结尾 IEND 块，中间补足长度。"""
    body = fill * max(0, size - len(PNG))
    return PNG[:-12] + body + PNG[-12:]


def candidate(**values):
    item = {'url': 'https://img.example.com/a.png', 'page': 'https://example.com/a',
            'title': '银发少女 立绘', 'author': '张三', 'license': 'CC BY',
            'width': 1200, 'height': 1600, 'tags': ['银发', '长发']}
    item.update(values)
    return item


def project(td):
    base = Path(td) / 'proj'
    file = base / 'assets/资产清单/assets.json'
    file.parent.mkdir(parents=True)
    file.write_text(json.dumps({'CHAR_001': {'name': '银发少女'}}, ensure_ascii=False), encoding='utf-8')
    return base


def bindings(base, aid='CHAR_001'):
    file = base / 'assets/资产清单/assets.json'
    return json.loads(file.read_text(encoding='utf-8'))[aid].get('reference_images', [])


class NormalizeTests(unittest.TestCase):
    def test_license_aliases(self):
        self.assertEqual(search.normalize({'license': 'CC0'})['license'], 'CC0 公共领域')
        self.assertTrue(search.normalize({'license': 'CC0'})['commercial'])
        self.assertTrue(search.normalize({'license': 'CC BY-SA'})['commercial'])
        self.assertFalse(search.normalize({'license': 'CC BY-NC'})['commercial'])

    def test_unknown_license_is_never_commercial(self):
        item = search.normalize({'license': '仅供学习交流'})
        self.assertEqual(item['license'], '仅供学习交流')
        self.assertFalse(item['commercial'])

    def test_source_falls_back_to_page(self):
        self.assertEqual(search.normalize({'source': 'https://example.com/x'})['page'], 'https://example.com/x')

    def test_tags_may_be_text(self):
        self.assertEqual(search.normalize({'tags': '银发, 长发 立绘'})['tags'], ['银发', '长发', '立绘'])

    def test_missing_fields_are_empty(self):
        item = search.normalize(None)
        self.assertEqual(item['url'], '')
        self.assertEqual(item['tags'], [])
        self.assertEqual(item['width'], 0)

    def test_size_from_text(self):
        self.assertEqual(search.normalize({'width': '1200', 'height': 1600})['width'], 1200)
        self.assertEqual(search.normalize({'width': '很大'})['width'], 0)


class UsableTests(unittest.TestCase):
    def test_full_credit_is_usable(self):
        self.assertTrue(search.usable(candidate()))

    def test_without_license_is_not_usable(self):
        self.assertFalse(search.usable(candidate(license='')))

    def test_without_page_is_not_usable(self):
        self.assertFalse(search.usable(candidate(page='', source='')))

    def test_without_url_is_not_usable(self):
        self.assertFalse(search.usable(candidate(url='')))


class QueryTests(unittest.TestCase):
    def test_first_query_is_name_plus_category(self):
        self.assertEqual(search.queries(ASSET)[0], '银发少女 角色设定')

    def test_prompt_words_join_the_query(self):
        self.assertIn('银发长大衣少女', ' '.join(search.queries(ASSET)))

    def test_limit_is_honoured(self):
        self.assertEqual(len(search.queries(ASSET, limit=1)), 1)

    def test_name_is_required(self):
        with self.assertRaises(ValueError):
            search.queries({})

    def test_asset_id_is_used_when_the_name_is_missing(self):
        self.assertIn('CHAR_001', search.queries({'id': 'CHAR_001'})[0])

    def test_prompt_words_ignore_the_name(self):
        self.assertEqual(search.prompt_words({'name': '银发少女'}), [])
        self.assertIn('冷色调', search.prompt_words(ASSET))


class ScoreTests(unittest.TestCase):
    def test_small_image_is_flagged(self):
        value, reasons = search.score(candidate(width=400, height=500), ASSET)
        self.assertIn('太小', ' '.join(reasons))
        self.assertLess(value, search.score(candidate(), ASSET)[0])

    def test_more_pixels_score_higher(self):
        big = search.score(candidate(width=2048, height=2048), ASSET)[0]
        small = search.score(candidate(width=600, height=800), ASSET)[0]
        self.assertGreater(big, small)

    def test_keyword_hits_raise_the_score(self):
        hit = search.score(candidate(title='银发少女 立绘'), ASSET)[0]
        miss = search.score(candidate(title='蓝天白云'), ASSET)[0]
        self.assertGreater(hit, miss)

    def test_non_commercial_costs_points(self):
        free = search.score(candidate(license='CC BY'), ASSET)[0]
        limited = search.score(candidate(license='CC BY-NC'), ASSET)[0]
        self.assertGreater(free, limited)

    def test_no_license_costs_points(self):
        self.assertGreater(search.score(candidate(license='CC BY'), ASSET)[0],
                           search.score(candidate(license=''), ASSET)[0])

    def test_asset_without_prompt_is_neutral(self):
        value, reasons = search.score(candidate(), {'id': 'CHAR_001', 'name': '银发少女'})
        self.assertIn('还没有图片提示词', ' '.join(reasons))
        self.assertGreater(value, 0)

    def test_reasons_are_readable(self):
        value, reasons = search.score(candidate(), ASSET)
        self.assertTrue(all(isinstance(reason, str) and reason for reason in reasons))

    def test_score_is_deterministic(self):
        self.assertEqual(search.score(candidate(), ASSET), search.score(candidate(), ASSET))

    def test_score_stays_in_range(self):
        for item in (candidate(), candidate(width=1, height=1), candidate(width=99999, height=99999, license='CC0')):
            value = search.score(item, ASSET)[0]
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 100)


class FingerprintTests(unittest.TestCase):
    def test_same_image_at_two_urls_shares_a_fingerprint(self):
        first = search.fingerprint(candidate(url='https://a.example.com/1.png'))
        second = search.fingerprint(candidate(url='https://b.example.com/2.png'))
        self.assertEqual(first, second)

    def test_different_size_is_a_different_image(self):
        self.assertNotEqual(search.fingerprint(candidate()), search.fingerprint(candidate(height=1200)))

    def test_without_title_falls_back_to_url(self):
        item = candidate(title='')
        self.assertEqual(search.fingerprint(item), item['url'])


class RankTests(unittest.TestCase):
    def test_threshold_drops_the_weak(self):
        wall = search.rank([candidate(width=600, height=800)], ASSET)
        self.assertEqual(wall, [])
        self.assertTrue(search.rank([candidate(width=600, height=800)], ASSET, threshold=50))

    def test_threshold_boundary_is_inclusive(self):
        value = search.score(candidate(), ASSET)[0]
        self.assertEqual(len(search.rank([candidate()], ASSET, threshold=value)), 1)
        self.assertEqual(len(search.rank([candidate()], ASSET, threshold=value + 1)), 0)

    def test_duplicates_keep_the_better_license(self):
        wall = search.rank([candidate(url='https://a/1.png', license='CC BY-NC'),
                            candidate(url='https://b/2.png', license='CC BY')], ASSET)
        self.assertEqual(len(wall), 1)
        self.assertEqual(wall[0]['url'], 'https://b/2.png')
        self.assertTrue(wall[0]['commercial'])

    def test_sorted_by_score_descending(self):
        wall = search.rank([candidate(url='https://a/1.png', width=2048, height=2048),
                            candidate(url='https://b/2.png', width=1200, height=1600),
                            candidate(url='https://c/3.png', width=1024, height=1024)], ASSET)
        self.assertEqual([item['score'] for item in wall], sorted([item['score'] for item in wall], reverse=True))

    def test_limit_truncates(self):
        wall = search.rank([candidate(url=f'https://a/{index}.png', width=2048, height=2048 + index * 64)
                            for index in range(5)], ASSET, limit=2)
        self.assertEqual(len(wall), 2)

    def test_every_entry_carries_score_and_reasons(self):
        wall = search.rank([candidate()], ASSET)
        self.assertIn('score', wall[0])
        self.assertTrue(wall[0]['reasons'])


class SearchTests(unittest.TestCase):
    def test_merges_all_queries_and_dedupes(self):
        asked = []
        def transport(query):
            asked.append(query)
            return [candidate()]
        result = search.search(transport, ASSET)
        self.assertEqual(len(asked), len(result['queries']))
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(result['errors'], [])

    def test_one_broken_query_does_not_break_the_wall(self):
        def transport(query):
            if '参考图' in query:
                raise RuntimeError('429 太频繁')
            return [candidate()]
        result = search.search(transport, ASSET)
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(len(result['errors']), 1)
        self.assertIn('429', result['errors'][0]['error'])


class CandidatesFromFileTests(unittest.TestCase):
    def test_json_array(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / 'c.json'
            file.write_text(json.dumps([candidate()], ensure_ascii=False), encoding='utf-8')
            self.assertEqual(len(search.candidates_from_file(file)), 1)

    def test_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / 'c.jsonl'
            file.write_text('\n'.join(json.dumps(candidate(url=f'https://a/{i}.png')) for i in range(2)), encoding='utf-8')
            self.assertEqual(len(search.candidates_from_file(file)), 2)

    def test_object_with_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / 'c.json'
            file.write_text(json.dumps({'candidates': [candidate()]}, ensure_ascii=False), encoding='utf-8')
            self.assertEqual(len(search.candidates_from_file(file)), 1)

    def test_bad_shape_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / 'c.json'
            file.write_text('"不是清单"', encoding='utf-8')
            with self.assertRaises(ValueError):
                search.candidates_from_file(file)


class SuffixTests(unittest.TestCase):
    def test_png(self):
        self.assertEqual(search.suffix_of(png()), '.png')

    def test_jpeg(self):
        self.assertEqual(search.suffix_of(b'\xff\xd8\xff\xe0' + b'x' * 64), '.jpg')

    def test_webp(self):
        self.assertEqual(search.suffix_of(b'RIFF' + b'\x00' * 4 + b'WEBP' + b'x' * 32), '.webp')

    def test_html_error_page_is_rejected(self):
        self.assertEqual(search.suffix_of(b'<html>404</html>'), '')

    def test_address_extension_does_not_decide(self):
        self.assertEqual(search.suffix_of(png()), '.png')


class FetchTests(unittest.TestCase):
    def test_plain_http_is_refused(self):
        with self.assertRaises(ValueError):
            search.fetch_bytes('http://img.example.com/a.png')

    def test_missing_scheme_is_refused(self):
        with self.assertRaises(ValueError):
            search.fetch_bytes('img.example.com/a.png')


class AdoptTests(unittest.TestCase):
    def fetch_of(self, raw):
        return lambda url: raw

    def test_adopts_and_records_credit(self):
        with tempfile.TemporaryDirectory() as td:
            base = project(td)
            result = search.adopt(base, 'CHAR_001', [candidate()], fetch=self.fetch_of(png()), role='长相')
            self.assertEqual(len(result['adopted']), 1)
            self.assertEqual(result['skipped'], [])
            self.assertEqual(len(bindings(base)), 1)
            relative = bindings(base)[0]
            credits = json.loads((base / search.CREDITS).read_text(encoding='utf-8'))
            self.assertEqual(credits[relative]['license'], 'CC BY 署名')
            self.assertTrue(credits[relative]['commercial'])
            self.assertEqual(credits[relative]['page'], 'https://example.com/a')
            plan = json.loads((base / 'assets/资产清单/assets.json').read_text(encoding='utf-8'))
            self.assertEqual(plan['CHAR_001']['reference_roles'][relative], '长相')

    def test_missing_credit_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            base = project(td)
            result = search.adopt(base, 'CHAR_001', [candidate(license='')], fetch=self.fetch_of(png()))
            self.assertEqual(result['adopted'], [])
            self.assertIn('版权信息不全', result['skipped'][0]['reason'])
            self.assertEqual(bindings(base), [])

    def test_non_image_bytes_are_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            base = project(td)
            result = search.adopt(base, 'CHAR_001', [candidate()], fetch=self.fetch_of(b'<html>404</html>' * 100))
            self.assertIn('不是 PNG', result['skipped'][0]['reason'])
            self.assertEqual(bindings(base), [])

    def test_tiny_image_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            base = project(td)
            result = search.adopt(base, 'CHAR_001', [candidate()], fetch=self.fetch_of(png(600)))
            self.assertIn('太小', result['skipped'][0]['reason'])
            self.assertEqual(bindings(base), [])

    def test_broken_jpeg_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            base = project(td)
            broken = b'\xff\xd8' + b'x' * 4096
            result = search.adopt(base, 'CHAR_001', [candidate()], fetch=self.fetch_of(broken))
            self.assertEqual(result['adopted'], [])
            self.assertIn('入库失败', result['skipped'][0]['reason'])

    def test_one_failure_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as td:
            base = project(td)
            def fetch(url):
                if url.endswith('bad.png'):
                    raise RuntimeError('网络连接失败')
                return png()
            picks = [candidate(url='https://a/bad.png', title='坏图'),
                     candidate(url='https://a/good.png', title='好图', width=1500)]
            result = search.adopt(base, 'CHAR_001', picks, fetch=fetch)
            self.assertEqual(len(result['adopted']), 1)
            self.assertEqual(len(result['skipped']), 1)
            self.assertIn('下载失败', result['skipped'][0]['reason'])
            self.assertEqual(len(bindings(base)), 1)

    def test_adopting_twice_does_not_double_bind(self):
        with tempfile.TemporaryDirectory() as td:
            base = project(td)
            search.adopt(base, 'CHAR_001', [candidate()], fetch=self.fetch_of(png()))
            search.adopt(base, 'CHAR_001', [candidate()], fetch=self.fetch_of(png()))
            self.assertEqual(len(bindings(base)), 1)

    def test_candidate_without_url_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            base = project(td)
            result = search.adopt(base, 'CHAR_001', [candidate(url='')], fetch=self.fetch_of(png()))
            self.assertIn('没有图片地址', result['skipped'][0]['reason'])

    def test_unknown_asset_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            base = project(td)
            result = search.adopt(base, 'CHAR_999', [candidate()], fetch=self.fetch_of(png()))
            self.assertEqual(result['adopted'], [])
            self.assertIn('入库失败', result['skipped'][0]['reason'])


class ScorePartsTests(unittest.TestCase):
    def test_parts_carry_label_points_and_note(self):
        value, parts = search.score_parts(candidate(), ASSET)
        self.assertTrue(parts)
        for part in parts:
            self.assertTrue(part['label'])
            self.assertIsInstance(part['points'], int)
            self.assertTrue(part['note'])
        self.assertEqual(value, min(100, sum(part['points'] for part in parts)))

    def test_score_reasons_match_parts(self):
        value, parts = search.score_parts(candidate(), ASSET)
        self.assertEqual(search.score(candidate(), ASSET), (value, [part['note'] for part in parts]))


class ExplainTests(unittest.TestCase):
    def test_adoptable_when_source_and_license_are_complete(self):
        self.assertEqual(search.explain(candidate(), ASSET)['state'], 'adoptable')

    def test_states_cover_missing_fields_and_low_score(self):
        cases = {'missing_url': candidate(url=''),
                 'missing_source': candidate(page='', source=''),
                 'missing_license': candidate(license=''),
                 'non_commercial': candidate(license='CC BY-NC')}
        for state, item in cases.items():
            self.assertEqual(search.explain(item, ASSET)['state'], state)
        self.assertEqual(search.explain(candidate(width=600, height=800), ASSET, threshold=90)['state'], 'low_score')

    def test_note_explains_the_state(self):
        self.assertIn('未声明许可', search.explain(candidate(license=''), ASSET)['note'])


class TraceabilityTests(unittest.TestCase):
    def test_entry_carries_license_basis_and_collection_date(self):
        wall = search.rank([candidate(license_url='https://creativecommons.org/licenses/by/4.0/',
                                      collected_at='2026-10-12')], ASSET)
        self.assertEqual(wall[0]['license_url'], 'https://creativecommons.org/licenses/by/4.0/')
        self.assertEqual(wall[0]['collected_at'], '2026-10-12')
        self.assertTrue(all(part['label'] for part in wall[0]['breakdown']))

    def test_same_image_at_two_sources_is_recorded(self):
        wall = search.rank([candidate(url='https://a/1.png'), candidate(url='https://b/2.png')], ASSET)
        self.assertEqual(len(wall), 1)
        self.assertEqual([alt['url'] for alt in wall[0]['alts']], ['https://b/2.png'])

    def test_conflicting_licenses_raise_a_conflict(self):
        wall = search.rank([candidate(url='https://a/1.png', license='CC BY'),
                            candidate(url='https://b/2.png', license='CC BY-NC')], ASSET)
        self.assertEqual(len(wall), 1)
        self.assertTrue(wall[0]['conflict'])
        self.assertEqual(wall[0]['state'], 'source_conflict')

    def test_agreeing_sources_are_not_a_conflict(self):
        wall = search.rank([candidate(url='https://a/1.png'), candidate(url='https://b/2.png')], ASSET)
        self.assertFalse(wall[0]['conflict'])
        self.assertEqual(wall[0]['state'], 'adoptable')


class SuppressedTests(unittest.TestCase):
    def test_low_score_candidate_is_explained(self):
        self.assertEqual([row['state'] for row in search.suppressed([candidate(width=600, height=800)], ASSET)],
                         ['low_score'])

    def test_duplicate_loser_points_at_the_kept_source(self):
        suppressed = search.suppressed([candidate(url='https://a/1.png'),
                                        candidate(url='https://b/2.png', license='CC BY-NC')], ASSET)
        row = next(item for item in suppressed if item['state'] == 'duplicate')
        self.assertEqual(row['url'], 'https://b/2.png')
        self.assertIn('https://a/1.png', row['note'])

    def test_missing_license_candidate_is_explained(self):
        suppressed = search.suppressed([candidate(url='https://x/9.png', title='另一张', license='')], ASSET)
        self.assertEqual([row['state'] for row in suppressed], ['missing_license'])

    def test_kept_candidates_are_not_listed_as_suppressed(self):
        self.assertEqual(search.suppressed([candidate()], ASSET), [])


class CreditTraceabilityTests(unittest.TestCase):
    def test_credit_records_license_basis_and_collection_date(self):
        with tempfile.TemporaryDirectory() as td:
            base = project(td)
            search.adopt(base, 'CHAR_001',
                         [candidate(license_url='https://creativecommons.org/licenses/by/4.0/',
                                    collected_at='2026-10-12')], fetch=lambda url: png())
            record = next(iter(json.loads((base / search.CREDITS).read_text(encoding='utf-8')).values()))
            self.assertEqual(record['license_url'], 'https://creativecommons.org/licenses/by/4.0/')
            self.assertEqual(record['collected_at'], '2026-10-12')
            self.assertEqual(record['page'], 'https://example.com/a')

    def test_ranking_is_read_only_for_imported_assets(self):
        with tempfile.TemporaryDirectory() as td:
            base = project(td)
            search.adopt(base, 'CHAR_001', [candidate()], fetch=lambda url: png())
            plan = base / 'assets/资产清单/assets.json'
            credit = base / search.CREDITS
            before = (plan.read_bytes(), credit.read_bytes())
            picks = [candidate(), candidate(url='https://b/2.png', license='CC BY-NC')]
            search.rank(picks, ASSET)
            search.suppressed(picks, ASSET)
            self.assertEqual((plan.read_bytes(), credit.read_bytes()), before)


if __name__ == '__main__':
    unittest.main(verbosity=1)
