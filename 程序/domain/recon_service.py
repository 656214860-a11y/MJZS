# -*- coding: utf-8 -*-
"""素材采风：把「对标爆款／热点速成」的公开情报检索回来，装成《对标情报卡》。

边界与 `sd-recon-engine` 轻量版一致：只交付情报卡，不做打分门槛、聚簇、持久化台账、
定时抓取。卡是**来源**不是**设定依据**——下游引用必须保留来源与分级，T2 讨论不得升格
为事实；找不到就写「未找到」，绝不用推测补满。

分工：本模块只管业务（拼检索词、控预算、拼卡片、机检证据），网络与密钥都在 L1
`model_pool.tools_search()`／`tools_fetch()`；这里不 import urllib，也不读密钥。
`authority`／`date`／`rerank_score` 三个字段原样留在卡片里，不在落盘前压成一个分数。
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from collections import abc
from dataclasses import dataclass, replace
from pathlib import Path

import contract.artifact_schema as artifact_schema
import infra.model_pool as model_pool
import contract.stage_layout as stage_layout
import infra.app_logging as app_logging
import infra.idempotency as idempotency
import domain.domain_events as domain_events
from agent import core
from infra.file_cache import read_json
from contract.service_contract import UserError, success
from contract.stage_path_service import write_dir

STAGE = 'script'
KIND = 'recon_card'
CARD_NAME = 'recon_card.json'
REQUEST_NAME = 'recon_request.json'
DOC_NAME = 'intel_card.md'
MARKER_NAME = 'recon_idempotency.json'
UNKNOWN = '未找到'
STATES = ('sources_ready', 'filled')
MATERIAL_SOURCES = ('对标爆款', '热点速成')
# 一次采风的硬预算。超了就写「还有没查到的」，不拿推测补满。
LIMITS = {'search': 6, 'fetch': 6, 'count': 5, 'seconds': 45}
BACKOFF = (1.0, 2.0, 4.0)
ATTEMPTS = 3
MIN_RERANK = 1.5                 # 文档：≥1.5 分算优质结果
MIN_AUTHORITY = 3                # 文档：≥3 分算极权威结果
TIERS = ('T1', 'T1.5', 'T2')
# 常见二级后缀：注册域仍用于归类和别名查找；独立信源另按发布方与同稿合并计数。
SECOND_LEVEL = {'com.cn', 'net.cn', 'org.cn', 'gov.cn', 'edu.cn', 'co.uk', 'org.uk',
                'ac.uk', 'com.hk', 'com.tw', 'co.jp', 'co.kr', 'com.au'}
# 发布方别名：同一发布主体的多个域名只算一个独立信源。
# 依据：新华社／新华网同时使用 news.cn（新华网）与 xinhuanet.com（新华网）；
# xinhuanet.com.cn 是同一主体的历史域名，R1698 真机样本同一篇稿同时出现在三者。
# 只登记能确认的同主体域名，拿不准的不加。
PUBLISHER_ALIASES = {
    'news.cn': 'xinhua',
    'xinhuanet.com': 'xinhua',
    'xinhuanet.com.cn': 'xinhua',
}
# 多人可编辑的百科站点：无论 authority 多高、是否抓到正文，最高只算 T2。
# 依据：用户 2026-10-18 裁决（R1698 任务书第 5 点）；只登记明确点名的站点。
ENCYCLOPEDIA_HOSTS = ('baike.baidu.com', 'baike.sogou.com', 'wikipedia.org', 'baike.com')
INFERENCE_WORDS = ('可能', '大概', '预计', '应该是', '推测', '估计')
SCHEME = re.compile(r'^https?://([^/?#]+)', re.IGNORECASE)


@dataclass(frozen=True)
class ReconPorts:
    """一次采风的可替换端口：发送器、重试暂停、时钟与实际落盘器。

    默认值由本模块装配（检索／抓取经 L1 `model_pool`，落盘经 `agent.core`）；
    自检可整体换成替身，不必把十几个注入项逐项展开成函数参数。
    """
    sender: abc.Callable[..., dict] | None = None
    pause: abc.Callable[[float], None] | None = None
    limits: dict | None = None
    clock: abc.Callable[[], float] = time.time
    official_hosts: tuple = ()
    transport: object | None = None
    headers: dict | None = None
    program: str | None = None
    save: abc.Callable[..., object] | None = None
    save_text: abc.Callable[..., object] | None = None


# ── 位置与读写 ─────────────────────────────────────────────────────────────
def stage_paths(project):
    """本阶段七个固定位置：根目录取当前编号目录，子目录名取 stage_layout。"""
    root = Path(project)
    values = dict(stage_layout.paths(root, stage_layout.dirname_of(STAGE)))
    values['root'] = write_dir(root, STAGE)
    return values


def card_path(project):
    return stage_paths(project)['input'] / CARD_NAME


def request_path(project):
    """采风请求的唯一文件：页面写它，工具读它，两边不各写一套判断。"""
    return stage_paths(project)['input'] / REQUEST_NAME


def load_request(project):
    """读采风请求；缺失或损坏返回空表（采风不是阶段完成条件，读不到不算错）。"""
    try:
        value = read_json(request_path(project))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def save_request(project, values, save=None):
    """写采风请求（原子发布）：`name` 用于③单剧，`type=topic` 让④按简报题材起手。

    `save` 是自检注入点；生产默认 `agent.core.save`，与 `save_card()` 同一写法——
    L2 不保留裸写正式路径的回退（第三项棘轮）。写入成功的数据是请求文件路径。
    """
    target = request_path(project)
    (save or core.save)(target, dict(values or {}))
    return success(target)


def doc_path(project):
    return stage_paths(project)['docs'] / DOC_NAME


def marker_path(project):
    """幂等标记与卡片同目录：记录「最近一次成功采风」的幂等键。"""
    return stage_paths(project)['input'] / MARKER_NAME


def load_card(project):
    """读已有情报卡；缺失或损坏返回空表（采风不是阶段完成条件，读不到不算错）。"""
    path = card_path(project)
    try:
        value = read_json(path)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def save_card(project, card, save=None, save_text=None):
    """按正式产物写：JSON 带 schema_version 走原子发布，人读版同步落 docs/。

    校验失败是可修正的输入错误：返回 `UserError`，由调用方按工具失败展示；
    成功的数据保留原返回内容 `{card, doc, problems}`。
    """
    payload = artifact_schema.stamp(KIND, card)
    problems = artifact_schema.validate(KIND, payload)
    if problems:
        return UserError('；'.join(problems))
    issues = evidence(payload)
    payload['evidence_report'] = list(issues)
    target = card_path(project)
    writer = save or core.save
    writer(target, payload)
    (save_text or core.save_text)(doc_path(project), render(payload))
    return success({'card': str(target), 'doc': str(doc_path(project)), 'problems': list(issues)})


# ── 来源分级与证据机检 ─────────────────────────────────────────────────────
def host_of(url):
    """url → 主机名（小写、去端口、去 userinfo）；认不出来返回空串。"""
    match = SCHEME.match(str(url or '').strip())
    if not match:
        return ''
    authority = match.group(1).rsplit('@', 1)[-1]
    return authority.split(':')[0].strip().lower().strip('.')


def domain_of(url):
    """url → 注册域近似（别名查找用；无别名时它就是发布主体）。"""
    host = host_of(url)
    parts = [part for part in host.split('.') if part]
    if len(parts) <= 2:
        return '.'.join(parts)
    if '.'.join(parts[-2:]) in SECOND_LEVEL:
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])


def publisher_of(url):
    """url → 发布主体：先查别名表，查不到就用注册域。"""
    domain = domain_of(url)
    return PUBLISHER_ALIASES.get(domain, domain)


def is_encyclopedia_host(host):
    """主机名是否属于多人可编辑的百科站点（含其子域名）。"""
    text = str(host or '')
    return any(text == item or text.endswith('.' + item) for item in ENCYCLOPEDIA_HOSTS)


def normalize_content(text):
    """正文规范化：去掉空白与零宽字符，供同稿转载比对。"""
    value = str(text or '').replace('\ufeff', '')
    return re.sub(r'[\s\u200b\u200c\u200d]+', '', value)


def article_digest(source):
    """抓到正文时返回规范化正文的 SHA-256；没有正文返回空串。"""
    text = normalize_content((source or {}).get('content'))
    if not text:
        return ''
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _title_date_key(source):
    """无正文时的同稿线索：规范化标题＋发布日期；缺一项就不算。"""
    title = re.sub(r'\s+', '', str((source or {}).get('title') or '')).casefold()
    date = str((source or {}).get('date') or '').strip()
    return (title, date) if title and date else ()


def independent_source_count(sources):
    """按来源主体计数：同发布方算 1；正文相同（无正文时同标题同日期）的转载合并。"""
    publishers = set()
    digests = set()
    title_dates = set()
    for source in sources or ():
        if not isinstance(source, dict):
            continue
        publisher = publisher_of(source.get('url'))
        if not publisher:
            continue
        digest = article_digest(source)
        key = _title_date_key(source)
        if digest:
            if digest in digests:
                continue
        elif key and key in title_dates:
            continue
        if digest:
            digests.add(digest)
        if key:
            title_dates.add(key)
        publishers.add(publisher)
    return len(publishers)


def _authority_of(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _official(host, official_hosts):
    return any(host == item or host.endswith('.' + str(item)) for item in official_hosts or ())


def tier_of(source, official_hosts=()):
    """来源分级现算，不采信调用方自报：摘要封顶 T2；拿到正文且权威才算 T1。"""
    host = host_of(source.get('url'))
    if is_encyclopedia_host(host):
        return 'T2'
    if str(source.get('evidence') or '') != 'content':
        return 'T2'
    if _authority_of(source.get('authority')) >= MIN_AUTHORITY or _official(host, official_hosts):
        return 'T1'
    return 'T1.5'


def clean_url(url):
    """去掉 #锚点：同一篇文章的 `#1`／`#1#1` 变体不是不同信源（真机实测常见）。"""
    text = str(url or '').strip()
    head, separator, _tail = text.partition('#')
    return head if separator else text


def normalize_source(item, query=''):
    """把一条接口结果补成卡片里的来源记录；没有 url 的结果整条丢掉（无法追溯就不收）。"""
    row = item if isinstance(item, dict) else {}
    raw = str(row.get('url') or '').strip()
    url = clean_url(raw)
    if not host_of(url):
        return {}
    source = {
        'title': str(row.get('title') or ''),
        'url': url,
        'site_name': str(row.get('site_name') or '') or None,
        'date': str(row.get('date') or '') or None,
        'authority': _authority_of(row.get('authority')),
        'rerank_score': row.get('rerank_score'),
        'snippet': str(row.get('snippet') or ''),
        'summary': str(row.get('summary') or ''),
        'content': str(row.get('content') or ''),
        'evidence': 'content' if str(row.get('content') or '').strip() else 'summary',
        'query': str(query or ''),
    }
    if raw and raw != url:
        source['url_raw'] = raw           # 原始地址留档：去锚点只影响去重，不抹掉证据
    source['tier'] = tier_of(source)
    return source


def _rerank_of(source):
    try:
        return float(source.get('rerank_score'))
    except (TypeError, ValueError):
        return 0.0


def _field_rows(fields):
    return fields if isinstance(fields, dict) else {}


def evidence(card, official_hosts=()):
    """六条证据纪律的机检：返回问题清单（空列表＝通过）。只读，不改卡片。"""
    problems = []
    sources = [item for item in card.get('sources') or () if isinstance(item, dict)]
    urls = {str(item.get('url') or '') for item in sources}
    for index, source in enumerate(sources, 1):
        url = str(source.get('url') or '')
        if not url:
            problems.append('来源 %d 缺 url，无法追溯' % index)
            continue
        claimed = str(source.get('tier') or '')
        computed = tier_of(source, official_hosts)
        if claimed and claimed != computed:
            problems.append('来源 %d 自报 %s 与现算 %s 不一致：%s' % (index, claimed, computed, url))
    for name, row in _field_rows(card.get('fields')).items():
        if not isinstance(row, dict):
            problems.append('字段「%s」不是 {value, source} 结构' % name)
            continue
        value = str(row.get('value') or '').strip()
        if not value or value == UNKNOWN:
            if value != UNKNOWN:
                problems.append('字段「%s」空着：找不到要写「%s」' % (name, UNKNOWN))
            continue
        source_url = str(row.get('source') or '').strip()
        if not source_url:
            problems.append('字段「%s」没有来源' % name)
            continue
        if source_url not in urls:
            problems.append('字段「%s」的来源不在 sources 里：%s' % (name, source_url))
            continue
        if any(word in value for word in INFERENCE_WORDS):
            problems.append('字段「%s」含推断措辞，不能当事实' % name)
        matched = [item for item in sources if str(item.get('url') or '') == source_url]
        if matched:
            # 时点必标：真正被引用为证据的那一条必须有发布时间，没被引用的可以空。
            if not matched[0].get('date'):
                problems.append('字段「%s」的来源未标时点：%s' % (name, source_url))
            if _rerank_of(matched[0]) < MIN_RERANK:
                problems.append('字段「%s」只由一个低分结果支撑（rerank<%.1f）' % (name, MIN_RERANK))
    declared = card.get('independent_domains')
    computed_domains = independent_source_count(sources)
    if declared is not None and int(declared) != computed_domains:
        problems.append('独立信源数声明 %s，实际按来源主体去重是 %d' % (declared, computed_domains))
    return problems


# ── 检索词与采风 ───────────────────────────────────────────────────────────
def _dedupe(values):
    seen, out = set(), []
    for value in values:
        text = str(value or '').strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def plan_queries(target, material_source):
    """按「一次采风只回答一到两个主问题」出检索词：③找单剧，④找选题方向。

    ④ 只用题材词拼三条方向词：真机实测把整句问题拼进去会得到「都市情感 这个题材最近
    有哪些能用的结构」这类废词，白花一次计费请求。
    """
    item = target if isinstance(target, dict) else {'name': str(target or '')}
    name = str(item.get('name') or '').strip()
    topic = str(item.get('topic') or '').strip()
    question = str(item.get('question') or '').strip()
    kind = str(item.get('type') or '').strip()
    base = name or topic
    if not base:
        return []
    if kind == 'topic' or (not name and topic):
        queries = [topic + ' 短剧 题材', topic + ' 短剧 爆款 结构', topic + ' 短剧 平台 排行']
    else:
        queries = [name + ' 短剧', name + ' 短剧 热度', name + ' 短剧 剧情 结构']
        if question:
            queries.append(base + ' ' + question[:48])
    return _dedupe(queries)[:LIMITS['search']]


def make_sender(transport=None, headers=None, program=None):
    """默认发送器：只经 L1 的两个工具接口出入；自检可整体换成替身。"""
    def send(kind, value, count=LIMITS['count']):
        if kind == 'search':
            return model_pool.tools_search(value, count=count, transport=transport,
                                           program=program, headers=headers)
        return model_pool.tools_fetch(value, transport=transport, program=program,
                                      headers=headers)
    return send


def _attempt(call, pause):
    """按接口文档重试 408／429／5xx；402／401 与其余 4xx 立即返回，不浪费预算。"""
    result = {}
    for index in range(ATTEMPTS):
        result = call()
        if not isinstance(result, dict):
            return {'ok': False, 'status': 0, 'kind': 'bug', 'error': '传输没有返回结果'}
        if result.get('ok') or not model_pool.tools_retryable(result.get('status')):
            return result
        if index + 1 < ATTEMPTS:
            pause(BACKOFF[min(index, len(BACKOFF) - 1)])
    return result


def _merge_sources(sources):
    """同一 url 只留一条：多个检索词命中同一页面时保留最高排序分那条，独立信源仍算一个。"""
    best, order = {}, []
    for source in sources:
        url = str(source.get('url') or '')
        if not url:
            continue
        current = best.get(url)
        if current is None:
            best[url] = source
            order.append(url)
        elif _rerank_of(source) > _rerank_of(current):
            best[url] = source
    return [best[url] for url in order]


def _resolve_ports(ports):
    """补齐默认发送器与暂停函数；显式传入的端口原样保留。"""
    ports = ports or ReconPorts()
    return replace(
        ports,
        sender=ports.sender or make_sender(transport=ports.transport,
                                           headers=ports.headers, program=ports.program),
        pause=ports.pause or time.sleep)


def _search_all(queries, budget, limits, notes, ports, started):
    sources = []
    for query in queries:
        if budget['search_used'] >= limits['search'] or ports.clock() - started >= limits['seconds']:
            notes.append('预算用完，还有没查到的：%s' % query)
            break
        domain_events.emit(domain_events.PAID_INVOKED, stage=STAGE, op='search',
                           nonce=uuid.uuid4().hex)
        result = _attempt(lambda: ports.sender('search', query, limits['count']), ports.pause)
        budget['search_used'] += 1
        if not result.get('ok'):
            notes.append('检索失败（%s）：%s ｜ %s' % (result.get('kind'), query, result.get('error')))
            if result.get('kind') in ('balance', 'auth'):
                break
            continue
        rows = result.get('results') or []
        if rows:
            budget['search_billed'] += 1
        else:
            notes.append('未命中：%s' % query)
        for row in rows:
            source = normalize_source(row, query)
            if source:
                sources.append(source)
    return sources


def _fetch_all(sources, budget, limits, notes, ports, started):
    """按排序分优先把正文抓回来：抓到正文的来源才可能升到 T1。"""
    ordered = sorted(sources, key=_rerank_of, reverse=True)
    seen = set()
    for source in ordered:
        url = str(source.get('url') or '')
        if not url or url in seen:
            continue
        if budget['fetch_used'] >= limits['fetch'] or ports.clock() - started >= limits['seconds']:
            notes.append('抓取预算用完，仍只有摘要：%s' % url)
            break
        seen.add(url)
        domain_events.emit(domain_events.PAID_INVOKED, stage=STAGE, op='fetch',
                           nonce=uuid.uuid4().hex)
        result = _attempt(lambda: ports.sender('fetch', url), ports.pause)
        budget['fetch_used'] += 1
        if not result.get('ok'):
            notes.append('抓不动（%s，可能需登录或 JS 渲染）：%s' % (result.get('kind'), url))
            continue
        content = str(result.get('content') or '')
        if not content.strip():
            notes.append('抓到空正文：%s' % url)
            continue
        budget['fetch_billed'] += 1
        source['content'] = content
        source['evidence'] = 'content'
        source['tier'] = tier_of(source)
        if not source.get('title') and result.get('title'):
            source['title'] = str(result.get('title'))
    return sources


def collect(target, material_source, *, ports=None):
    """跑一次采风：检索 → 抓正文 → 出卡。返回卡片 dict（不落盘）。

    `ports` 收拢发送器、暂停、时钟、预算与落盘器等注入项，见 `ReconPorts`。
    """
    ports = _resolve_ports(ports)
    limits = dict(LIMITS, **(ports.limits or {}))
    started = ports.clock()
    budget = {'search_used': 0, 'search_billed': 0, 'fetch_used': 0, 'fetch_billed': 0,
              'seconds': 0, 'search_limit': limits['search'], 'fetch_limit': limits['fetch']}
    notes = []
    queries = plan_queries(target, material_source)
    sources = _merge_sources(
        _search_all(queries, budget, limits, notes, ports, started))
    sources = _fetch_all(sources, budget, limits, notes, ports, started)
    budget['seconds'] = round(ports.clock() - started, 3)
    tiered = []
    for source in sources:
        source['tier'] = tier_of(source, ports.official_hosts)
        tiered.append(source)
    return {
        'kind': KIND,
        'state': 'sources_ready',
        'material_source': str(material_source or ''),
        'target': dict(target) if isinstance(target, dict) else {'name': str(target or '')},
        'queries': queries,
        'sources': tiered,
        'fields': {},
        'missing': [],
        'independent_domains': independent_source_count(tiered),
        'budget': budget,
        'not_found': list(notes),
        'collected_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'collected_by': 'recon_service / deepseek-tools',
    }


# ── 幂等：同一采风只付一次费 ──────────────────────────────────────────────
def _idempotency_key(target, material_source, ports):
    """「同一镜头同一参数」的指纹：target／素材来源／生效预算／官方域名。

    只收业务语义参数——sender、transport、时钟、落盘器是执行细节不进键；
    target 与 ``collect()`` 同口径规范化（dict 原样、标量包成 ``{'name': ...}``），
    limits 取 ``collect()`` 相同的生效值，official_hosts 影响分级也必须进键。
    """
    ports = ports or ReconPorts()
    limits = dict(LIMITS, **(ports.limits or {}))
    canonical = {
        'kind': KIND,
        'target': dict(target) if isinstance(target, dict) else {'name': str(target or '')},
        'material_source': str(material_source or ''),
        'limits': limits,
        'official_hosts': sorted(str(item) for item in (ports.official_hosts or ())),
    }
    return idempotency.key_of(json.dumps(canonical, sort_keys=True,
                                         ensure_ascii=False, default=str))


def _load_marker(project):
    """读幂等标记；缺失或损坏返回空表（标记不是产物，读不到按未命中处理）。"""
    try:
        value = read_json(marker_path(project))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _cached_success(project, card):
    """幂等命中：由已落盘卡片字段重建与 ``run()`` 首次成功完全一致的 ``success``。"""
    return success({'card': str(card_path(project)),
                    'doc': str(doc_path(project)),
                    'problems': list(card.get('evidence_report') or ()),
                    'sources': len(card.get('sources') or ()),
                    'queries': list(card.get('queries') or ()),
                    'not_found': list(card.get('not_found') or ()),
                    'budget': card.get('budget') or {}})


def _save_marker(project, key, save=None):
    """写幂等标记（原子发布）；写失败只留痕不挡主流程——宁可下次重采，不丢已落盘的卡。"""
    try:
        (save or core.save)(marker_path(project), {
            'kind': KIND, 'key': str(key),
            'written_at': time.strftime('%Y-%m-%dT%H:%M:%S')})
    except Exception:
        app_logging.swallowed('recon 幂等标记写入失败')


def run(project, target, material_source, *, ports=None):
    """采风并落盘：卡片 JSON ＋ 人读 MD。

    幂等：同一 project＋target＋material_source＋生效参数第二次进入时，若落盘
    标记键一致且情报卡仍在，直接由卡片字段重建结果返回——不再发起付费
    检索／抓取，也不重复写盘；标记损坏或卡片缺失一律按未命中重采。

    返回 `ServiceResult`，成功数据保留原字段
    `{card, doc, problems, sources, queries, not_found, budget}`；落盘失败原样透传。
    """
    ports = ports or ReconPorts()
    key = _idempotency_key(target, material_source, ports)
    marker = _load_marker(project)
    if str(marker.get('key') or '') == key:
        cached = load_card(project)
        if cached:
            return _cached_success(project, cached)
    card = collect(target, material_source, ports=ports)
    saved = save_card(project, card, save=ports.save, save_text=ports.save_text)
    if not saved.ok:
        return saved
    _save_marker(project, key, save=ports.save)
    data = saved.data or {}
    return success({'card': data['card'], 'doc': data['doc'], 'problems': data['problems'],
                    'sources': len(card['sources']), 'queries': card['queries'],
                    'not_found': card['not_found'], 'budget': card['budget']})


# ── 人读版 ─────────────────────────────────────────────────────────────────
def _render_field(name, row):
    if not isinstance(row, dict):
        return '- %s：%s' % (name, UNKNOWN)
    value = str(row.get('value') or '').strip() or UNKNOWN
    source = str(row.get('source') or '').strip()
    return '- %s：%s%s' % (name, value, '（来源：%s）' % source if source else '')


def render(card):
    """情报卡的人读版：来源列全、缺的写「未找到」、预算与未查到的如实写。"""
    target = card.get('target') if isinstance(card.get('target'), dict) else {}
    lines = ['# 对标情报卡', '']
    lines.append('- 素材来源：%s' % (card.get('material_source') or UNKNOWN))
    lines.append('- 对标对象：%s' % (target.get('name') or target.get('topic') or UNKNOWN))
    if target.get('question'):
        lines.append('- 本次主问题：%s' % target['question'])
    lines.append('- 采集时点：%s' % (card.get('collected_at') or UNKNOWN))
    lines.append('- 独立信源：%d 个' % int(card.get('independent_domains') or 0))
    lines.append('')
    lines.append('## 字段')
    rows = card.get('fields') if isinstance(card.get('fields'), dict) else {}
    if rows:
        for name, row in rows.items():
            lines.append(_render_field(name, row))
    else:
        lines.append('- 尚未填字段：先据下方来源填写，填不到写「%s」。' % UNKNOWN)
    lines.append('')
    lines.append('## 来源')
    for index, source in enumerate(card.get('sources') or (), 1):
        lines.append('%d. [%s] %s' % (index, source.get('tier', 'T2'), source.get('title') or UNKNOWN))
        lines.append('   - %s' % source.get('url'))
        lines.append('   - 站点：%s ｜ 时点：%s ｜ 权威性：%s ｜ 排序分：%s ｜ 证据：%s' % (
            source.get('site_name') or UNKNOWN, source.get('date') or UNKNOWN,
            source.get('authority'), source.get('rerank_score'), source.get('evidence')))
    if not card.get('sources'):
        lines.append('- 未找到')
    lines.append('')
    lines.append('## 采集记录')
    budget = card.get('budget') if isinstance(card.get('budget'), dict) else {}
    lines.append('- 检索 %s 次／抓取 %s 次／用时 %s 秒' % (
        budget.get('search_used'), budget.get('fetch_used'), budget.get('seconds')))
    lines.append('- 检索词：%s' % ('、'.join(card.get('queries') or ()) or UNKNOWN))
    for note in card.get('not_found') or ():
        lines.append('- %s' % note)
    problems = card.get('evidence_report') or ()
    if problems:
        lines.append('')
        lines.append('## 机检未通过')
        for problem in problems:
            lines.append('- %s' % problem)
    lines.append('')
    lines.append('> 本卡是**来源**，不是**设定依据**：引用时保留来源与分级，T2 讨论不得当事实。')
    return '\n'.join(lines) + '\n'


def summary(card):
    """一句话摘要，给播报和工具返回值用。"""
    item = card or {}
    return '情报卡：%s 个来源（独立信源 %s 个），检索 %s 次／抓取 %s 次' % (
        len(item.get('sources') or ()), item.get('independent_domains'),
        (item.get('budget') or {}).get('search_used'), (item.get('budget') or {}).get('fetch_used'))


def dumps(card):
    return json.dumps(card, ensure_ascii=False, indent=2)
