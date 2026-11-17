# -*- coding: utf-8 -*-
"""素材采风自检：检索词、来源分级、六条证据机检、预算、落盘与工具登记。

REQ-S01-40／41／42／43／44／45：③④ 才采风、卡是来源不是设定依据、每个字段要么带
来源要么写「未找到」、有硬预算、检索词不含用户原创内容。
运行：python tests/test_recon_service.py
"""
import itertools
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import recon_service as recon
import skill_tools
from contract.script_manifest_contract import STAGE_MANIFESTS

HEADERS = {'Authorization': 'Bearer test', 'Content-Type': 'application/json'}


def row(url, **values):
    item = {'title': '标题', 'url': url, 'site_name': '站点', 'authority': 3,
            'rerank_score': 2.4, 'snippet': '短摘要', 'summary': '长摘要',
            'content': '', 'date': '2026-06-01T00:00:00+00:00'}
    item.update(values)
    return item


def sender(results=None, page='# 正文\n真的', search_status=None, fetch_status=None):
    """假发送器：按 kind 回结果，记下每次调用（自检不需要真网络）。"""
    calls = []

    def send(kind, value, count=5):
        calls.append((kind, value, count))
        if kind == 'search':
            if search_status is not None:
                return {'ok': False, 'status': search_status, 'kind': model_kind(search_status),
                        'error': 'HTTP %s' % search_status}
            return {'ok': True, 'status': 200, 'data': {}, 'results': list(results or [])}
        if fetch_status is not None:
            return {'ok': False, 'status': fetch_status, 'kind': model_kind(fetch_status),
                    'error': 'HTTP %s' % fetch_status}
        return {'ok': True, 'status': 200, 'data': {'title': '抓到的', 'content': page},
                'title': '抓到的', 'content': page}
    send.calls = calls
    return send


def model_kind(status):
    import model_pool
    return model_pool.tools_error_kind(status)


def content_sender(results=None, pages=None):
    """假发送器：检索回固定结果，抓取按 url 回不同正文（用于同稿／异稿去重）。"""
    calls = []
    pages = pages or {}

    def send(kind, value, count=5):
        calls.append((kind, value, count))
        if kind == 'search':
            return {'ok': True, 'status': 200, 'data': {}, 'results': list(results or [])}
        return {'ok': True, 'status': 200, 'data': {'title': '抓到的'},
                'title': '抓到的', 'content': pages.get(value, '')}
    send.calls = calls
    return send


def collect(results=None, **options):
    return recon.collect({'name': '某剧', 'question': '怎么成的'}, '对标爆款',
                         ports=recon.ReconPorts(
                             sender=options.pop('sender', None) or sender(results=results),
                             pause=options.pop('pause', lambda _s: None), **options))


class QueryTests(unittest.TestCase):
    """REQ-S01-40：③找单剧、④找选题方向，检索词分开。"""

    def test_single_drama_and_topic_produce_different_queries(self):
        drama = recon.plan_queries({'name': '某剧', 'question': '怎么成的'}, '对标爆款')
        topic = recon.plan_queries({'type': 'topic', 'topic': '都市情感'}, '热点速成')
        self.assertTrue(drama and topic)
        self.assertTrue(all('某剧' in query for query in drama), drama)
        self.assertTrue(all('都市情感' in query for query in topic), topic)
        self.assertEqual(recon.plan_queries({}, '对标爆款'), [], '没有对象就没有检索词')

    def test_topic_queries_skip_the_question_sentence(self):
        """④ 只用题材词拼三条方向词；真机实测把整句问题拼进去会变成废检索词。"""
        queries = recon.plan_queries({'type': 'topic', 'topic': '都市情感',
                                      'question': '这个题材最近有哪些能用的结构'}, '热点速成')
        self.assertEqual(len(queries), 3, queries)
        self.assertFalse(any('这个题材最近' in query for query in queries), queries)
        self.assertTrue(all('都市情感' in query for query in queries))
        drama = recon.plan_queries({'name': '某剧', 'question': '怎么成的'}, '对标爆款')
        self.assertTrue(any('怎么成的' in query for query in drama),
                        '③ 单剧保留主问题，用来收窄这部剧的具体问法')

    def test_cli_skip_when_material_source_is_not_recon(self):
        """REQ-S01-40：只有③④激活采风，其余来源不打扰用户。"""
        with tempfile.TemporaryDirectory() as td:
            result = skill_tools.call('recon.card', {'project': td, 'material_source': '原创'})
        self.assertTrue(result['ok'])
        self.assertTrue(result.get('skipped'))
        self.assertIn('原创', result['reason'])

    def test_missing_target_asks_for_input_instead_of_failing(self):
        """REQ-S01-40：没有对标对象时按「还缺输入」返回，不让阶段失败。"""
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(skill_tools.ToolNeedsInput):
                skill_tools.call('recon.card', {'project': td, 'material_source': '对标爆款'})


class TierTests(unittest.TestCase):
    """REQ-S01-42：来源分级现算，不采信自报。"""

    def test_summary_is_capped_at_t2_and_content_can_reach_t1(self):
        summary = recon.normalize_source(row('https://a.com/x', authority=4))
        self.assertEqual((summary['evidence'], summary['tier']), ('summary', 'T2'))
        content = recon.normalize_source(row('https://a.com/x', authority=3, content='正文'))
        self.assertEqual((content['evidence'], content['tier']), ('content', 'T1'))
        weak = recon.normalize_source(row('https://a.com/x', authority=1, content='正文'))
        self.assertEqual(weak['tier'], 'T1.5')

    def test_official_hosts_can_promote_without_authority(self):
        source = recon.normalize_source(row('https://www.douyin.com/a', authority=0, content='正文'))
        self.assertEqual(source['tier'], 'T1.5')
        self.assertEqual(recon.tier_of(source, official_hosts=('douyin.com',)), 'T1')

    def test_rows_without_url_are_dropped(self):
        self.assertEqual(recon.normalize_source({'title': '无链接', 'url': ''}), {})

    def test_url_fragments_are_the_same_source(self):
        """真机实测：同一篇文章会带 `#1`／`#1#1` 锚点，去重必须按无锚点地址算。"""
        first = recon.normalize_source(row('https://www.thepaper.cn/newsDetail_forward_1#1'))
        second = recon.normalize_source(row('https://www.thepaper.cn/newsDetail_forward_1#1#1'))
        self.assertEqual(first['url'], 'https://www.thepaper.cn/newsDetail_forward_1')
        self.assertEqual(first['url'], second['url'], '锚点不同的同一篇不能算两个信源')
        self.assertEqual(first['url_raw'], 'https://www.thepaper.cn/newsDetail_forward_1#1',
                         '原始地址留档，去锚点只影响去重')
        card = collect(results=[row('https://a.com/x#1'), row('https://a.com/x#1#1')])
        self.assertEqual(len(card['sources']), 1)
        self.assertEqual(card['independent_domains'], 1)

    def test_independent_domains_ignore_subdomains_and_second_level_suffix(self):
        self.assertEqual(recon.domain_of('https://www.douyin.com/a'), 'douyin.com')
        self.assertEqual(recon.domain_of('https://news.sina.com.cn/a'), 'sina.com.cn')
        self.assertEqual(recon.host_of('https://user:pw@a.com:8443/x'), 'a.com')
        self.assertEqual(recon.host_of('不是网址'), '')


class EvidenceTests(unittest.TestCase):
    """REQ-S01-42：六条证据纪律机检。"""

    def clean_card(self, **values):
        card = collect(results=[row('https://a.com/x', content='正文')])
        card['fields'] = {'①剧名': {'value': '某剧', 'source': 'https://a.com/x'}}
        card.update(values)
        return card

    def test_clean_card_passes(self):
        self.assertEqual(recon.evidence(self.clean_card()), [])

    def test_field_without_source_is_reported(self):
        card = self.clean_card()
        card['fields'] = {'①剧名': {'value': '某剧'}}
        self.assertTrue(any('没有来源' in item for item in recon.evidence(card)))

    def test_field_citing_unknown_source_is_reported(self):
        card = self.clean_card()
        card['fields'] = {'①剧名': {'value': '某剧', 'source': 'https://b.com/y'}}
        self.assertTrue(any('不在 sources' in item for item in recon.evidence(card)))

    def test_empty_field_must_say_not_found(self):
        card = self.clean_card()
        card['fields'] = {'②平台': {'value': ''}}
        self.assertTrue(any('未找到' in item for item in recon.evidence(card)))
        card['fields'] = {'②平台': {'value': recon.UNKNOWN}}
        self.assertEqual(recon.evidence(card), [])

    def test_inference_wording_is_not_a_fact(self):
        card = self.clean_card()
        card['fields'] = {'③时点': {'value': '可能是 2026 年', 'source': 'https://a.com/x'}}
        self.assertTrue(any('推断' in item for item in recon.evidence(card)))

    def test_cited_source_without_date_is_reported(self):
        self.assertTrue(recon.UNKNOWN)
        card = self.clean_card()
        card['sources'][0]['date'] = None
        self.assertTrue(any('未标时点' in item for item in recon.evidence(card)))

    def test_low_rank_source_cannot_support_a_field_alone(self):
        card = self.clean_card()
        card['sources'][0]['rerank_score'] = 0.4
        self.assertTrue(any('低分' in item for item in recon.evidence(card)))

    def test_declared_domain_count_must_match_recomputation(self):
        card = self.clean_card()
        card['independent_domains'] = 9
        self.assertTrue(any('独立信源数' in item for item in recon.evidence(card)))


class PublisherDedupTests(unittest.TestCase):
    """REQ-S01-48：独立信源按来源主体去重，字段名 independent_domains 保持不变。"""

    def collect_with_pages(self, rows, pages):
        return recon.collect({'name': '某剧'}, '对标爆款',
                             ports=recon.ReconPorts(sender=content_sender(rows, pages),
                                                    pause=lambda _s: None))

    def test_req_s01_48_same_xinhua_article_across_domains_counts_once(self):
        first = 'http://xinhuanet.com.cn/ent/20260309/e5d0a170/'
        second = 'https://www.news.cn/ent/20260310/4607eda1/c.html'
        rows = [row(first, title='新华社稿'), row(second, title='新华社稿')]
        pages = {first: '新华社正文 2598', second: '新华社正文\n2598'}
        card = self.collect_with_pages(rows, pages)
        self.assertEqual(len(card['sources']), 2)
        self.assertEqual(card['independent_domains'], 1)

    def test_req_s01_48_same_publisher_different_articles_counts_once(self):
        first = 'https://www.news.cn/ent/a.html'
        second = 'https://www.xinhuanet.com/ent/b.html'
        rows = [row(first, title='稿A'), row(second, title='稿B')]
        card = self.collect_with_pages(rows, {first: '正文A', second: '正文B'})
        self.assertEqual(card['independent_domains'], 1)

    def test_req_s01_48_unrelated_domains_with_different_content_count_separately(self):
        first = 'https://a.com/x'
        second = 'https://b.com/y'
        rows = [row(first, title='A稿'), row(second, title='B稿')]
        card = self.collect_with_pages(rows, {first: '正文A', second: '正文B'})
        self.assertEqual(card['independent_domains'], 2)

    def test_req_s01_48_legacy_card_without_new_fields_is_readable(self):
        card = {'schema_version': 1, 'kind': recon.KIND,
                'target': {'name': '某剧'}, 'fields': {},
                'sources': [recon.normalize_source(row('https://a.com/x'))],
                'independent_domains': 1}
        self.assertEqual(recon.evidence(card), [])
        self.assertIn('独立信源：1 个', recon.render(card))

    def test_req_s01_48_evidence_flags_false_independent_count(self):
        first = 'https://www.news.cn/ent/a.html'
        second = 'https://www.xinhuanet.com/ent/b.html'
        rows = [row(first, title='稿A'), row(second, title='稿B')]
        card = self.collect_with_pages(rows, {first: '正文A', second: '正文B'})
        self.assertEqual(card['independent_domains'], 1)
        card['independent_domains'] = 2
        self.assertTrue(any('独立信源数' in item for item in recon.evidence(card)))


class EncyclopediaTierTests(unittest.TestCase):
    """REQ-S01-49：百科抓到正文也封顶 T2，且照常计入独立信源。"""

    def test_req_s01_49_encyclopedia_with_content_is_capped_at_t2(self):
        source = recon.normalize_source(row('https://baike.baidu.com/item/x',
                                            content='正文', authority=5))
        self.assertEqual(source['tier'], 'T2')
        self.assertEqual(recon.tier_of(source, official_hosts=('baike.baidu.com',)), 'T2')

    def test_req_s01_49_news_site_with_same_authority_still_reaches_t1(self):
        source = recon.normalize_source(row('https://news.example.com/x',
                                            content='正文', authority=5))
        self.assertEqual(recon.tier_of(source, official_hosts=('news.example.com',)), 'T1')

    def test_req_s01_49_encyclopedia_still_counts_as_one_independent_source(self):
        url = 'https://baike.baidu.com/item/x'
        card = recon.collect({'name': '某剧'}, '对标爆款',
                             ports=recon.ReconPorts(
                                 sender=content_sender([row(url, title='百科词条')], {url: '百科正文'}),
                                 pause=lambda _s: None))
        self.assertEqual(len(card['sources']), 1)
        self.assertEqual(card['independent_domains'], 1)
        self.assertEqual(card['sources'][0]['tier'], 'T2')


class BudgetTests(unittest.TestCase):
    """REQ-S01-43：硬预算、重试分工、去重。"""

    def test_duplicate_urls_are_merged_into_one_source(self):
        card = collect(results=[row('https://a.com/x', rerank_score=1.0),
                                row('https://a.com/x', rerank_score=2.9)])
        self.assertEqual(len(card['sources']), 1)
        self.assertEqual(card['sources'][0]['rerank_score'], 2.9)

    def test_search_count_and_fetch_count_respect_the_budget(self):
        rows = [row('https://a%d.com/x' % index) for index in range(8)]
        card = collect(results=rows, limits={'search': 2, 'fetch': 3, 'count': 5, 'seconds': 60})
        self.assertEqual(card['budget']['search_used'], 2)
        self.assertEqual(card['budget']['fetch_used'], 3)
        self.assertTrue(any('预算用完' in note for note in card['not_found']), card['not_found'])

    def test_seconds_budget_stops_between_queries(self):
        clock = itertools.chain([0.0, 5.0], itertools.repeat(5.0))
        card = collect(results=[row('https://a.com/x')], clock=lambda: next(clock),
                       limits={'search': 6, 'fetch': 6, 'count': 5, 'seconds': 1})
        self.assertEqual(card['budget']['search_used'], 0)
        self.assertEqual(card['budget']['fetch_used'], 0)
        self.assertTrue(any('预算用完' in note for note in card['not_found']))

    def test_rate_limit_is_retried_three_times(self):
        pauses = []
        state = {'left': 2}

        def send(kind, value, count=5):
            if kind == 'search':
                if state['left']:
                    state['left'] -= 1
                    return {'ok': False, 'status': 429, 'kind': 'rate', 'error': 'HTTP 429'}
                return {'ok': True, 'status': 200, 'data': {}, 'results': [row('https://a.com/x')]}
            return {'ok': True, 'status': 200, 'data': {'content': '正文'}, 'content': '正文'}

        card = recon.collect({'name': '某剧'}, '对标爆款',
                             ports=recon.ReconPorts(sender=send, pause=pauses.append))
        self.assertEqual(len(pauses), 2)
        self.assertEqual(len(card['sources']), 1)

    def test_balance_stops_the_whole_recon_without_retrying(self):
        pauses = []
        send = sender(search_status=402)
        card = recon.collect({'name': '某剧'}, '对标爆款',
                             ports=recon.ReconPorts(sender=send, pause=pauses.append))
        self.assertEqual(pauses, [])
        self.assertEqual(card['sources'], [])
        self.assertEqual(len(send.calls), 1)
        self.assertTrue(any('balance' in note for note in card['not_found']), card['not_found'])

    def test_auth_stops_the_whole_recon(self):
        send = sender(search_status=401)
        card = recon.collect({'name': '某剧'}, '对标爆款',
                             ports=recon.ReconPorts(sender=send, pause=lambda _s: None))
        self.assertEqual(len(send.calls), 1)
        self.assertTrue(any('auth' in note for note in card['not_found']))

    def test_unfetchable_page_keeps_the_summary_and_says_so(self):
        send = sender(results=[row('https://a.com/x')], fetch_status=404)
        card = recon.collect({'name': '某剧'}, '对标爆款',
                             ports=recon.ReconPorts(sender=send, pause=lambda _s: None))
        self.assertEqual(card['sources'][0]['evidence'], 'summary')
        self.assertTrue(any('抓不动' in note for note in card['not_found']))


class SavingTests(unittest.TestCase):
    """REQ-S01-42／44：落盘位置、版本、缺卡不算错。"""

    def test_card_lands_as_input_json_and_docs_markdown(self):
        card = collect(results=[row('https://a.com/x', content='正文')])
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            saved = recon.save_card(root, card)
            self.assertTrue(saved.ok, getattr(saved, 'reason', ''))
            card_file = Path(saved.data['card'])
            doc_file = Path(saved.data['doc'])
            self.assertEqual(card_file.relative_to(root),
                             Path('01剧本准备') / 'input' / recon.CARD_NAME)
            self.assertEqual(doc_file.relative_to(root),
                             Path('01剧本准备') / 'docs' / recon.DOC_NAME)
            payload = json.loads(card_file.read_text(encoding='utf-8'))
            self.assertEqual(payload['schema_version'], 1)
            self.assertEqual(payload['kind'], recon.KIND)
            self.assertEqual(payload['sources'][0]['url'], 'https://a.com/x')
            text = doc_file.read_text(encoding='utf-8')
            self.assertIn('对标情报卡', text)
            self.assertIn('https://a.com/x', text)

    def test_invalid_card_returns_user_error_instead_of_raising(self):
        """契约：校验失败是用户可修正的错误，不抛裸 ValueError，也不落任何文件。"""
        from contract.service_contract import UserError
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = recon.save_card(root, {'sources': []})
            self.assertIsInstance(result, UserError)
            self.assertFalse(result.ok)
            self.assertIn('缺少必备字段', result.reason)
            self.assertFalse(recon.card_path(root).exists())
            self.assertFalse(recon.doc_path(root).exists())

    def test_run_returns_service_result(self):
        """run 是写入口：成功也走 service_contract，调用方从 .data 取原字段。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = recon.run(root, {'name': '某剧'}, '对标爆款',
                               ports=recon.ReconPorts(
                                   sender=sender(results=[row('https://a.com/x')]),
                                   pause=lambda _s: None))
            self.assertTrue(result.ok, getattr(result, 'reason', ''))
            self.assertEqual(Path(result.data['card']).name, recon.CARD_NAME)
            self.assertEqual(result.data['sources'], 1)
            self.assertTrue(Path(result.data['card']).is_file())

    def test_missing_card_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(recon.load_card(td), {})

    def test_card_is_not_a_stage_completion_condition(self):
        """REQ-S01-44：情报卡是来源不是产物，不进 01 的 manifest 核验。"""
        self.assertNotIn('recon_card.json', STAGE_MANIFESTS['script'])
        import stage_layout
        names = [name for name, _text in stage_layout.DOCS['01剧本准备']]
        self.assertIn('intel_card.md', names, '人读版要登记进 docs 清单')

    def test_render_lists_sources_and_records_budget(self):
        card = collect(results=[row('https://a.com/x', content='正文')])
        card['fields'] = {'①剧名': {'value': '某剧', 'source': 'https://a.com/x'},
                          '②平台': {'value': recon.UNKNOWN}}
        text = recon.render(card)
        self.assertIn('独立信源', text)
        self.assertIn('搜索', text.replace('检索', '搜索'))
        self.assertIn('②平台：未找到', text)
        self.assertIn('来源', text)


class ToolTests(unittest.TestCase):
    """REQ-S01-40／44：工具登记与端到端落盘。"""

    def test_tool_is_registered_and_ready(self):
        self.assertEqual(skill_tools.status_of('recon.card'), 'ready')
        self.assertIn('recon.card', skill_tools.ready_names())

    def test_recon_card_writes_both_files_through_the_tool(self):
        with tempfile.TemporaryDirectory() as td:
            result = skill_tools.call('recon.card', {
                'project': td, 'material_source': '对标爆款',
                'recon_target': {'name': '某剧', 'question': '怎么成的'},
                'transport': _transport, 'headers': HEADERS, 'pause': lambda _s: None})
            self.assertTrue(result['ok'], result)
            self.assertEqual(result['sources'], 1)
            self.assertEqual(Path(result['card']).name, recon.CARD_NAME)
            self.assertTrue(Path(result['doc']).is_file())
            self.assertTrue(Path(result['card']).is_file())

    def test_topic_mode_only_sends_the_genre_word(self):
        """REQ-S01-45：只发题材方向，用户梗概不外传。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            from domain.idea_brief_form import brief_raw_path
            from project_context_factory import project_context
            path = brief_raw_path(project_context(root))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('故事题材：都市情感\n故事梗概：这是私密梗概标记MARKER\n', encoding='utf-8')
            self.assertEqual(skill_tools._recon_topic(root), '都市情感')
            queries = recon.plan_queries({'type': 'topic', 'topic': '都市情感'}, '热点速成')
            self.assertTrue(queries)
            self.assertFalse(any('MARKER' in query for query in queries), queries)


class RequestTests(unittest.TestCase):
    """REQ-S01-47：采风请求只由 input/recon_request.json 一处表达。"""

    def test_request_roundtrip_and_target_precedence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(recon.load_request(root), {})
            target = recon.save_request(root, {'name': '某剧', 'material_source': '对标爆款'})
            self.assertTrue(target.ok, getattr(target, 'reason', ''))
            self.assertEqual(target.data, recon.request_path(root))
            self.assertEqual(recon.load_request(root)['name'], '某剧')
            self.assertEqual(skill_tools._recon_target({}, root, '对标爆款').get('name'), '某剧')
            # 本次上下文优先于文件
            self.assertEqual(skill_tools._recon_target({'recon_target': {'name': '另一部'}},
                                                       root, '对标爆款').get('name'), '另一部')

    def test_topic_request_without_name_falls_back_to_the_brief(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            saved = recon.save_request(root, {'material_source': '热点速成'})
            self.assertTrue(saved.ok, getattr(saved, 'reason', ''))
            self.assertEqual(skill_tools._recon_target({}, root, '热点速成'), {},
                             '没有名字也没有题材时不能瞎猜，交给「还缺输入」')


class EntryTests(unittest.TestCase):
    """REQ-S01-46：页面只做「查来源 → 问剧名 → 写请求 → 交后台」，不联网、不写卡片。"""

    class Page:
        def __init__(self, root):
            self.root, self.win = str(root), None
            self.shown, self.jobs = [], []
            page = self

            class Status:
                def set(self, text):
                    page.shown.append(str(text))
            self.status = Status()

            class Notifier:
                def notify(self, message, **_kwargs):
                    page.shown.append(str(message))
            self.notifier = Notifier()

        def async_(self, fn, done=None, label=None, **_kwargs):
            self.jobs.append((fn, done, label))

        def recon_done(self, result):
            from desktop_writing_page import WritingPageMixin
            return WritingPageMixin.recon_done(self, result)

    def make_project(self, root, source):
        (root / 'skill_config.json').write_text(json.dumps(
            {'workflow': {'name': 'AIGC全流程',
                          'lock': {'AIGC全流程': {'material_source': source}}}},
            ensure_ascii=False), encoding='utf-8')

    def test_wrong_material_source_is_explained_without_running_anything(self):
        from desktop_writing_page import WritingPageMixin
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_project(root, '原创')
            page = self.Page(root)
            WritingPageMixin.collect_recon(page)
            self.assertEqual(page.jobs, [])
            self.assertTrue(any('素材来源' in text for text in page.shown), page.shown)
            self.assertFalse(recon.request_path(root).exists())

    def test_a_drama_name_is_written_to_the_request_and_run_in_the_background(self):
        from unittest import mock
        from desktop_writing_page import WritingPageMixin
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_project(root, '对标爆款')
            page = self.Page(root)
            with mock.patch('desktop_writing_page.ask_string', return_value=' 《某剧》 '):
                WritingPageMixin.collect_recon(page)
            self.assertEqual(len(page.jobs), 1)
            self.assertEqual(page.jobs[0][2], '采集对标情报')
            request = recon.load_request(root)
            self.assertEqual(request['name'], '《某剧》')
            self.assertEqual(request['material_source'], '对标爆款')
            self.assertFalse(recon.card_path(root).exists(), '页面不许自己写卡片')

    def test_topic_mode_writes_no_name(self):
        from unittest import mock
        from desktop_writing_page import WritingPageMixin
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_project(root, '热点速成')
            page = self.Page(root)
            with mock.patch('desktop_writing_page.ask_string', return_value='   '):
                WritingPageMixin.collect_recon(page)
            self.assertEqual(len(page.jobs), 1)
            self.assertNotIn('name', recon.load_request(root))

    def test_cancel_writes_nothing(self):
        from unittest import mock
        from desktop_writing_page import WritingPageMixin
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_project(root, '对标爆款')
            page = self.Page(root)
            with mock.patch('desktop_writing_page.ask_string', return_value=None):
                WritingPageMixin.collect_recon(page)
            self.assertEqual(page.jobs, [])
            self.assertFalse(recon.request_path(root).exists())

    def test_results_are_reported_honestly(self):
        from desktop_writing_page import WritingPageMixin
        page = self.Page('.')
        WritingPageMixin.recon_done(page, {'ok': True, 'sources': 3,
                                           'not_found': ['一条'], 'problems': ['缺口']})
        self.assertIn('3 个来源', page.shown[-1])
        self.assertIn('没查到的 1 条', page.shown[-1])
        self.assertIn('机检待处理 1 条', page.shown[-1])
        WritingPageMixin.recon_done(page, {'ok': False, 'needs': '缺对标对象'})
        self.assertIn('需要先给出对标对象', page.shown[-1])
        WritingPageMixin.recon_done(page, {'skipped': True, 'reason': '素材来源是「原创」'})
        self.assertIn('素材来源是「原创」', page.shown[-1])


def _transport(url, payload, headers, timeout):
    if url.endswith('/v1/tools/search'):
        return {'ok': True, 'status': 200, 'data': {'results': [row('https://a.com/x', content='')]}}
    return {'ok': True, 'status': 200, 'data': {'title': '抓到的', 'content': '# 正文'}}


if __name__ == '__main__':
    unittest.main()
