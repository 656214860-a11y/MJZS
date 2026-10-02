# R672 只读诊断轮——剧本准备产物在剧本结构阶段不可见

## 诊断结论

现象已复现且根因明确：当前项目的自然剧本位于正确的 `01剧本准备/.../项目剧本/`，写入目录与剧本结构读取目录一致；但正文含 Markdown 表格，`script_contract.natural_script_violations()` 将其判定为 `字段表格`，`natural_script_paths()` 遂将其从候选列表排除，最终 `resolve_script_source()` 返回 `None`。这不是旧 `writing/` 路径遗留、阶段目录错位或 R520 的目录识别回归。

本轮严格只读：未修改 `.py`、配置、用户项目数据或测试；仅新增本报告，未运行任何会写入项目的数据命令。

## A. 文件实际位置

用户未提供具体文件名（任务文本中为 `<填文件名>`）。按“剧本准备 → 项目剧本”候选定位到的唯一在用自然剧本为：

`D:\漫剧下载\项目\摄像头3_20260924\01剧本准备\Anthropic\cladue--opus-5.5\创意_20260925\项目剧本\摄像头3_自然剧本_第01-05集_20260925.md`

文件大小为 10,287 字节，最后修改时间为 2026-09-26 23:48:18。文件名经 `stage_file_info()` 解析为 `file_type=自然剧本`、`content=第01-05集`。

该目录属于第 1 阶段“剧本准备”，不是“剧本结构”：

`pet_bus.py:18-20`
```python
STAGES = ('script', 'script_structure', 'storyboard', ...)
STAGE_NAMES = {'script': '剧本准备', 'script_structure': '剧本结构', ...}
```

`stage_layout.py:36-40`
```python
STAGES = (
    ('01剧本准备', 'script', '剧本准备', ...),
    ('02剧本结构', 'script_structure', '剧本结构', ...),
```

## B. 剧本准备的写入路径

### B1/B2. 自然剧本的主要写入入口

手动创建的自然剧本由 `idea_chat.save_manual_creative()` 写入；它经 `project_stages.writing()` 得到 `01剧本准备`，未直接调用 `stage_path_service`：

`idea_chat.py:406-423`
```python
def save_manual_creative(root, text, at=None):
    from project_stages import writing
    creative_dir = _numbered_path(writing(root), '创意_' + day)
    from script_contract import require_natural_script
    require_natural_script(value)
    target = creative_dir / project_document_directory('自然剧本') / project_script_filename(...)
    save_text(target, value)
```

`project_stages.py:6-20`
```python
STAGES = {'script': '01剧本准备', 'structure': '02剧本结构', ...}
def writing(project): return stage(project, 'script')
```

下载聊天产出经 `Desktop.download_script()` 调用同一服务。`idea_chat.save_reply()` 同样使用 `project_stages.writing(root)`；当分类为自然剧本时，目标是 `创意_日期/项目剧本/`：

`desktop.py:1607-1622`
```python
def download_script(self):
    reply = idea_chat.latest_text(self.root)
    saved = idea_chat.save_reply(self.root, reply, provider=provider, model=model)
```

`idea_chat.py:380-404`
```python
from project_stages import writing
creative_dir = _numbered_path(writing(root) / provider_name / model_name, '创意_' + day)
file_type = _project_file_type(value)
if file_type == '自然剧本':
    value = require_natural_script(value)
dest = creative_dir / project_document_directory(file_type) / project_script_filename(...)
save_text(dest, value[:REPLY_LIMIT])
```

HOLLMWOOD 的原始稿则直接通过 `stage_path_service.write_dir()` 写到阶段根 `01剧本准备/script_raw.md`：

`writing_api.py:169-181`
```python
def _write_script_raw(project, text):
    from stage_path_service import write_dir
    from script_contract import require_natural_script
    text = require_natural_script(text)
    folder = write_dir(root, 'script')
    target = folder / 'script_raw.md'
    save_text(target, text + '\n')
```

`stage_path_service.py:25-40`
```python
def write_dir(project, stage):
    """返回唯一的当前阶段写入目录；绝不创建或返回旧英文目录。"""
    folder = next((row[0] for row in stage_layout.STAGES if row[1] == key), None)
    return stage_layout.paths(Path(project), folder)['root']
```

所以：手动/下载自然剧本与 HOLLMWOOD 都落在当前第 1 阶段，但子目录不同；前者不直接经过 `stage_path_service`，后者经过。不存在向旧 `writing/` 写入的这两条路径。

### B3. 保存方式是否统一

不完全统一：

- 手动保存、下载的“自然剧本”写至 `01剧本准备/<提供商>/<模型>/创意_日期/项目剧本/`；下载内容若被 `_project_file_type()` 分类为“项目设定”或“项目大纲”，会进入相应分类目录而非 `项目剧本`（`idea_chat.py:442-447`）。
- HOLLMWOOD 写 `01剧本准备/script_raw.md`；它被常规列表排除，只作为 `resolve_script_source()` 的后备源。
- 附件转存并不是自然剧本保存：`idea_attachments.py:51-75` 经 `write_dir(root, 'script')` 写入 `01剧本准备/输入/故事创意_<时间戳>.md`，随后由工作区归为“项目设定”。

```python
def input_folder(root):
    from stage_path_service import write_dir
    return write_dir(Path(root), 'script') / INPUT_FOLDER
...
target = folder / ('故事创意_%s%s.md' % (...))
save_text(target, text + '\n')
```

受控工具写入也固定到当前目录；旧 `writing/` 仅用于读取兼容：`writing_tools.py:30-40`。

## C. 剧本结构的读取路径

### C1/C3. 扫描入口与路径服务

结构页从 `script_workspace_service.script_structure_documents()` 获得来源列表：

`desktop.py:3925-3933, 4132-4135`
```python
def script_structure(self):
    from script_workspace_service import script_structure_documents
    structure = script_structure_documents(self.root)
...
self.script_structure_source_box = content_box(
    split_area, '自然剧本', '自然剧本目录（01剧本准备）',
    structure.source_documents, source, '尚未找到剧本准备阶段的剧本。请先生成、下载或导入剧本。')
```

`script_workspace_service.py:136-161`
```python
source_directory = write_dir(project, 'script').resolve()
output_directory = write_dir(project, 'structure').resolve()
source = script_contract.resolve_script_source(project)
all_source = tuple(script_contract.natural_script_paths(project))
sources = tuple(path for path in all_source if inside(path, source_directory)) or all_source
```

它通过 `stage_path_service.write_dir()` 获取当前 `01剧本准备`；`natural_script_paths()` 又通过 `stage_path_service.read_dirs(project, 'script')` 查询当前目录优先、旧目录只读回退。因此 C1、C3 均经过 `stage_path_service` 和 `stage_layout`。

### C2. 候选过滤条件

`script_contract.py:146-202`
```python
roots = read_dirs(project, 'script')
...
for path in writing.rglob('*.md'):
    relative = path.relative_to(writing)
    if (not path.is_file() or path.name in ignored or path.name == RAW_SCRIPT_NAME
            or STRUCTURED_SCRIPT_DIR in relative.parts):
        continue
    categorized_script = '项目剧本' in relative.parts
    numbered_script = bool(re.search(..., path.name))
    if ('剧本' not in path.name and 'script' not in name
            and not numbered_script and not categorized_script):
        continue
    if path.stat().st_size and is_natural_script(path.read_text(encoding='utf-8')):
        candidates.append((priority, path))
```

即扩展名仅 `.md`；排除内部 `script_raw.md`、固定忽略文件和 `结构剧本` 目录；文件名须含“剧本”/`script`、集数标记，或位于 `项目剧本`；正文还必须通过自然剧本校验。之后按“当前目录优先、修改时间倒序、相对路径”排序，并按相对路径和 SHA-256 正文指纹去重。

本项目文件命中过路径和名称规则，却在正文校验失败。实测调用结果：

```text
natural_script_violations(...) = ('字段表格',)
is_natural_script(...) = False
natural_script_paths(project) = ()
resolve_script_source(project) = None
```

对应规则是 `script_contract.py:70-84, 107-109`：
```python
if re.search(r'(?m)^\s*\|.+\|\s*$', value):
    violations.append('字段表格')
...
def is_natural_script(text):
    return not natural_script_violations(text)
```

该自然剧本正文实际含 `| 镜号 | 时长 | 画面 | 对白 / 独白 | 音效 |` 及后续表格行，故被排除。

## D. 路径对比

| 对照点 | 实际路径/规则 | 结论 |
| --- | --- | --- |
| A2 | `01剧本准备/.../项目剧本/` | 第 1 阶段当前目录 |
| B1 | `project_stages.writing()` → `01剧本准备` | 写入当前目录 |
| C1 | `write_dir(project, 'script')` / `read_dirs(..., 'script')` → `01剧本准备`（兼容读 `writing/`） | 读取当前目录优先 |

D1：三者一致。D2：属于“路径一致但过滤条件不匹配”，具体是内容校验将包含 Markdown 字段表格的文件排除；没有发现写旧读新、写新读旧或分类目录错位。

## E. 历史比对

### E1. R520 规则及现状

R520 的修复记录在 `tasks_round/tasks_round_520_result.md:9-16`：此前只按文件名含“剧本 / script / EP 集数”发现来源；修复后，受控 `项目剧本` 目录亦是自然剧本的命名证据，但仍须“文件非空、正文通过自然剧本校验”，并排除结构剧本与 `script_raw.md`。

该规则仍生效：当前 `script_contract.py:172` 为 `categorized_script = '项目剧本' in relative.parts`，且后续 `if` 将它纳入文件名门槛。本文件并非被 R520 的目录规则遗漏，而是被 R520 也保留的正文校验排除。

### E2. R520 后路径变更审计

检索 R521–R671 的结果文件以及当前代码，未发现对 `natural_script_paths()`、`resolve_script_source()`、`script_structure_documents()` 或 `script/script_structure` 当前目录映射的后续修改。相关轮次为：

- R543：新增附件转存到 `01剧本准备/输入/故事创意_*.md`（`tasks_round/tasks_round_543_result.md:14-17`），并明确归类为“项目设定”，不改变自然剧本来源扫描。
- R549、R561、R646：分别涉及结构执行、工作区/UI、剧本准备页拆分；审计记录未改变上述写入或扫描目录契约。

## F. 本项目特例

### F1. 多文件与去重

项目中存在：1 个在用自然剧本（A 节路径）、2 个 `02剧本结构/结构剧本/` 结构稿，以及 1 个历史回收站副本：

`D:\漫剧下载\项目\摄像头3_20260924\工作流任务\回收站\20260926_152111_344518_5555c7\01剧本准备\DeepSeek\DeepSeek V4 Flash\创意_20260926\剧本准备_自然剧本_EP001_20260926.md`

回收站不在 `read_dirs(project, 'script')` 的扫描根内，不能被选中或去重误删；结构稿又因 `结构剧本` 目录排除。当前空列表发生在候选生成前的内容校验，非多文件选择或 SHA-256 去重导致。

### F2. 阶段 SKILL 配置

`D:\漫剧下载\项目\摄像头3_20260924\skill_config.json` 的 `script_structure` 仅配置 `model: auto` 及四个 SKILL：`script-character-extraction`、`script-structured-generation`、`script-worldbuilding`、`pipeline-script-structure`。其中没有自然剧本来源文件路径、文件名或产物绑定字段，故不存在失效来源绑定。

## J. 整改路线（不在本轮执行）

最小改动集是调整自然剧本内容契约，而非迁移文件或改变阶段扫描路径：为“正文叙事中包含镜头/分镜 Markdown 表格”的合法上游稿定义明确策略，并在 `natural_script_violations()` 中只拒绝“纯字段表格型结构稿”或取消对单行 `|...|` 的无条件拒绝。随后让现有 `natural_script_paths()` 自动重新发现该文件。

不建议迁移该文件：它已在正确的 `01剧本准备/.../项目剧本`。也不建议只放宽该项目的扫描规则，否则会破坏自然稿与结构稿的全局边界。

## K. 测试计划（下轮修复时补充）

1. `项目剧本/` 中、含普通叙事段落和一张 Markdown 镜头表的 `.md`，应可被 `natural_script_paths()` 和 `resolve_script_source()` 发现。
2. 纯 Markdown 字段表格型结构稿、`结构剧本/` 下文件和 `script_raw.md` 的常规列表排除仍应保持。
3. `script_structure_documents()` 应将该当前阶段文件展示在“自然剧本”列表；不依赖旧 `writing/`。
4. 当前目录与旧 `writing/` 同时有副本时，验证当前优先及正文指纹去重不变。

## 自审

已逐项提供 A–F 的路径、代码位置或实测证据；本轮仅做只读文件与代码诊断，未修改 `.py`、配置、项目用户数据或阶段目录，唯一新增文件为本报告。
