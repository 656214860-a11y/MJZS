# R620 只读诊断轮：`.codex\skills` 来源与删除功能耦合盘点

- 本轮是功能轮还是整理轮？只读诊断轮。
- 测试跑了吗？三个基线过了吗？未跑；本轮未改代码，按只读诊断协议无需运行测试。
- `project_status.md` 的欠账少了吗？没有；本轮只记录事实与整改路线。

## 轮次编号

已检查 `tasks_round/tasks_round_6*_result.md`：R600—R619 均已存在，R620 未占用，因此使用连续编号 R620；不覆盖既有报告。

## A. `.codex\skills` 的来源：不是 `skill_registry` 扫描

### A1. 注册表实际扫描根

`skill_registry.py:42-44`：

```python
def default_root(program=None):
    """SKILL 目录：默认与程序同一个盘位下的 skills/（可用参数或参数覆盖，方便自检）。"""
    return Path(program or Path(__file__).resolve().parent) / 'skills'
```

`skill_registry.py:386-405` 每次刷新以该唯一 `self.root` 生成缓存键，并仅在该根发生变化时递归：

```python
directory_mtime_ns, child_directory_mtimes = self._file_cache_key()
cache_key = (directory_mtime_ns, child_directory_mtimes)
...
for path in sorted(self.root.rglob('*' + SKILL_SUFFIX)):
```

所以默认注册表只扫描 `D:\漫剧制作助手\程序\skills`；`skill_registry.py` 没有 `CODEX_HOME`、`.codex`、用户主目录或第二根目录。不存在“它在某行把 `C:\Users\LAIBIAO\.codex\skills` 纳入注册表扫描”的代码。

### A2. 实际使个人目录出现在候选中的入口

工作流预设不是注册表扫描。`workflow_settings.py:61-71` 按固定预设目录名优先检查个人入口、否则回退程序内置入口：

```python
def _home_skill(folder):
    return Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills'/folder/'SKILL.md'

def _bundled_skill(folder):
    return BUNDLED_SKILLS/SKILL_ALIASES.get(folder,folder)/'SKILL.md'

def preset_skill(folder):
    home=_home_skill(folder)
    return home if home.is_file() else _bundled_skill(folder)
```

`skill_panel.py:162-180` 的 `flow_skill_choices(flow)` 遍历 `SKILL_PRESETS`，对每个固定名称调用 `preset_skill()`；只有返回路径是文件才显示。没有目录枚举、`glob`、`rglob` 或把用户目录下任意 SKILL 自动加入阶段候选。

## B. 引入轮次

对全部现存 `tasks_round/tasks_round_*_result.md` 搜索 `CODEX_HOME`、`.codex/skills`、`_home_skill`、`preset_skill`。唯一命中的轮次是 R616、R617，二者记录的是**删除个人安装 SKILL**，而非修改 `workflow_settings.py`、`skill_registry.py` 或加入扫描根：

- `tasks_round/tasks_round_616_result.md:11-15`：在 `skill_panel.py` 引入“删除已安装…”的个人入口回收；范围限定 `%CODEX_HOME%/skills/<技能目录>/SKILL.md`。
- `tasks_round/tasks_round_617_result.md:13-16`：将交互改为“勾选后点击删除已勾选”，仍只调整删除入口。

结论：现存任务报告中不存在“引入 `.codex\skills` 扫描”的轮次，因为该扫描不存在；固定预设优先探测的历史引入没有在现存结果报告中记载。R616/R617 不能作为扫描功能的引入依据。

## C. 阶段配置候选的完整根目录清单

自动候选有两条独立来源：

| 候选类别 | 根/固定入口 | 代码 |
| --- | --- | --- |
| 阶段注册 `.skill.md` | `D:\漫剧制作助手\程序\skills`，并递归扫描其 `.skill.md` | `skill_registry.py:42-44,397` |
| 工作流预设 `SKILL.md` | 首选 `%CODEX_HOME%\skills\<预设目录>\SKILL.md`；默认即 `C:\Users\LAIBIAO\.codex\skills\<预设目录>\SKILL.md` | `workflow_settings.py:61-62,69-71` |
| 工作流预设回退 `SKILL.md` | `D:\漫剧制作助手\程序\skills\<预设目录或别名>\SKILL.md` | `workflow_settings.py:58,65-71` |

没有第三、第四个自动扫描目录。用户项目的 `skill_config.json` 和 `工作流调用设置.json` 是已选值的存储，不是候选扫描根。`pick_skill_file()` 可让用户手动选择任意名为 `SKILL.md` 的文件（`skill_panel.py:900-913`），但也不是扫描。

## D. 删除功能完整实现

当前源码已不是“删除已安装…”下拉：R617 已把删除动作改为独立按钮“删除已勾选”（`skill_panel.py:812-815`）；下拉只保留全选、取消与新增。

1. 实现函数：`Panel.delete_checked_personal_skills()`，`skill_panel.py:915-958`。
2. 可删条件：`skill_panel.py:80-88` 的 `is_personal_skill_file()` 要求文件名为 `SKILL.md`、存在，且 `item.parent.parent == personal_skills_root()`；根由 `skill_panel.py:75-77` 的 `%CODEX_HOME%/skills` 计算。
3. 回收调用：`skill_panel.py:936`：

```python
records = recycle_paths(personal_skills_root(), paths, '删除个人已安装 SKILL')
```

4. 具体回收位置：`storage_maintenance.py:29-31,48-63` 定义为 `<personal_skills_root>/工作流任务/回收站/自动维护_YYYYMMDD_HHMMSS/<原相对路径>`，并写 `<该批次>/恢复位置.json`，可经回收服务恢复。
5. 清除引用：删除成功后，`skill_panel.py:947-955` 只保留未删且仍勾选的路径并调用 `set_flow_skills()`；后者在 `skill_panel.py:243-268` 写 `<项目>/工作流任务/工作流调用设置.json` 的 `flows[flow].profiles[engine]`，经 `workflow_settings.set_skills(profile, picked)` 更新 `skill` 和 `skills` 字段。它**不修改** `<项目>/skill_config.json`。

## E. 配置、测试与耦合

### E1. 现有用户数据引用

在默认用户项目根 `D:\漫剧下载\项目` 下，当前项目 `摄像头3_20260924` 的相关配置中：

| 文件 | 指向 `.codex\skills` 的字符串条数 |
| --- | ---: |
| `D:\漫剧下载\项目\摄像头3_20260924\skill_config.json` | 0 |
| `D:\漫剧下载\项目\摄像头3_20260924\工作流任务\工作流调用设置.json` | 10 |

后者由 5 个 `skill` 字段与 5 个 `skills` 列表项构成，去重后为 2 条路径；本报告不展开用户路径正文。

### E2. 是否存在必须扫描/必须删除的测试

不存在断言“应用必须扫描 `.codex\skills`”的测试。最接近的是 `tests/test_core.py:825-833`，只断言 `CODEX_HOME` 变更会使固定预设路径缓存重算：

```python
with mock.patch.dict(os.environ, {"CODEX_HOME": td}):
    after = ws._preset_paths()
    self.assertIsNot(after, before)
    self.assertEqual(len(after), len(before))
    self.assertTrue(str(after[0][1]).startswith(str(Path(td).resolve())))
```

存在删除功能测试：

- `tests/test_skills.py:1185-1186`：`self.assertNotIn('删除已安装…', list(panel.flow_skill.cget('values')))` 和 `self.assertEqual(panel.delete_skill_button.cget('text'), '删除已勾选')`，断言当前按钮式交互存在。
- `tests/test_skills.py:1195-1223`：`test_delete_personal_skill_recycles_file_and_removes_current_flow_reference`，断言 `panel.delete_checked_personal_skills()` 返回被删入口、原文件消失、当前流程引用消失，且回收站仍有 `SKILL.md`。
- `tests/test_skills.py:1225-1236`：`test_delete_personal_skill_rejects_external_skill_file`，断言外部文件不删除。

### E3. 删除与项目内置 `skills/` 是否零耦合

默认环境下是隔离的：`personal_skills_root()` 默认为 `C:\Users\LAIBIAO\.codex\skills`，而内置根是 `D:\漫剧制作助手\程序\skills`；内置路径无法通过 `item.parent.parent == personal_skills_root()`，所以不删除。

但不是绝对零耦合：若环境变量 `CODEX_HOME` 被设置为 `D:\漫剧制作助手\程序`，则 `personal_skills_root()` 变成内置 `D:\漫剧制作助手\程序\skills`。此时任一内置 `<一级目录>/SKILL.md` 被当前流程勾选，满足 `is_personal_skill_file()` 的所有条件，删除按钮会把它移到内置根下的回收站。现有 `.skill.md` 阶段注册文件不满足文件名 `SKILL.md`，但任何内置预设包的 `SKILL.md` 满足；这是环境变量配置导致的直接耦合条件。

## J. 整改路线

### 路线 1：只移除个人预设探测，保留删除功能

1. 在 `workflow_settings.preset_skill()` 移除 `_home_skill()` 优先分支，使其始终返回 `_bundled_skill()`。
2. 更新 `tests/test_core.py` 的预设路径缓存契约为“`CODEX_HOME` 不改变候选源”，并新增个人同名 `SKILL.md` 不覆盖内置预设的断言。
3. 读取现有 `工作流调用设置.json` 时选择明确兼容策略（保留失效路径并提示 / 显式迁移 / 回退内置），不得悄然改写当前 10 处用户数据。
4. 保持按钮删除功能不动；它仍只管理用户显式勾选的个人文件。

影响面：`workflow_settings.py`、`tests/test_core.py`，以及含个人预设路径的既有项目运行时兼容。

### 路线 2：移除个人预设探测与删除功能

1. 执行路线 1 的 `preset_skill()` 收口。
2. 删除 `skill_panel.py` 中 `personal_skills_root()`、`is_personal_skill_file()`、删除按钮和 `delete_checked_personal_skills()`；取消 `storage_maintenance.recycle_paths` 的该模块导入。
3. 删除或按新 UI 契约替换 `tests/test_skills.py:1185-1236` 的删除按钮/删除行为测试；不弱化其他 SKILL 选择测试。
4. 保留“新增 SKILL”手动选择能力与否必须由产品另行明确；它允许任意外部 `SKILL.md`，与自动扫描是独立行为。

影响面：`skill_panel.py`、`tests/test_skills.py`、`smoke_test.py` 的受影响映射（若仅为删除回归服务），以及用户对个人安装包的可恢复删除能力。

## K. 测试计划

- 路线 1：在既有 `tests/test_core.py` 断言个人同名入口不覆盖内置候选；在 `tests/test_skills.py` 断言 `flow_skill_choices()` 不返回 `.codex` 路径。保留三条删除回归。
- 路线 2：移除删除功能的契约测试，改为断言阶段配置不存在删除按钮/动作；保留并补充“注册表默认根仅为程序 `skills/`”与“候选不随 `CODEX_HOME` 改变”的测试。
- 两路线共同：以临时目录及 `mock.patch.dict(os.environ, {'CODEX_HOME': ...})` 构造证据，不触及真实 `C:\Users\LAIBIAO\.codex` 或用户项目。

## 自审

本轮确为只读：未修改任何 `.py`、测试、配置、用户数据或既有结果文件；唯一新增文件是 `tasks_round/tasks_round_620_result.md`。
