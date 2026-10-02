# R619 只读诊断轮：`.codex\\skills` 越界扫描与删除功能

- 本轮是功能轮还是整理轮？只读诊断轮。
- 测试跑了吗？三个基线过了吗？未跑；本轮禁止修改，且诊断不需要测试。
- `project_status.md` 的欠账少了吗？没有；本轮未实现修复。

## 轮次编号

开工前枚举 `tasks_round/tasks_round_6*_result.md`：现有连续编号为 R600—R618，R619 未占用；`project_status.md` 也标记 R619 待执行。因此本报告使用 R619。

## A. 扫描入口事实

### A1. `skill_registry` **没有**把 `.codex\\skills` 纳入扫描范围

`skill_registry.py:42-44` 的默认根目录是程序目录，而非用户主目录：

```python
def default_root(program=None):
    """SKILL 目录：默认与程序同一个盘位下的 skills/（可用参数或参数覆盖，方便自检）。"""
    return Path(program or Path(__file__).resolve().parent) / 'skills'
```

`skill_registry.py:397` 只在该 `self.root` 内递归：

```python
for path in sorted(self.root.rglob('*' + SKILL_SUFFIX)):
```

默认实际根为 `D:\漫剧制作助手\程序\skills`。未发现 `skill_registry.py` 中的 `CODEX_HOME`、`.codex` 或第二扫描根；因此“不受控地把 `C:\Users\LAIBIAO\.codex\skills` 加进注册表扫描”的前提不成立。

### A2. 实际让 `.codex\\skills` 出现在阶段配置候选中的代码

它不是 `Registry` 扫描，而是工作流预设的固定路径优先探测：

`workflow_settings.py:61-71`：

```python
def _home_skill(folder):
    return Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills'/folder/'SKILL.md'

def preset_skill(folder):
    home=_home_skill(folder)
    return home if home.is_file() else _bundled_skill(folder)
```

`skill_panel.py:162-180` 的 `flow_skill_choices(flow)` 遍历固定的 `workflow_settings.SKILL_PRESETS`，逐项调用 `preset_skill(folder)`，并仅当该固定入口文件存在时加入候选。它不会列目录、不会 `glob/rglob`，也不会把 `.codex\\skills` 中任意新包自动枚举为候选。

## B. 引入轮次核查

对全部 `tasks_round/tasks_round_*_result.md` 搜索 `CODEX_HOME`、`.codex/skills`、`_home_skill`、`preset_skill`：只有 R616/R617 命中，且两份报告均明确描述的是**删除个人安装 SKILL 的范围**，没有修改 `workflow_settings.py` 或声称将 `.codex\\skills` 加入注册表扫描。

- `tasks_round/tasks_round_616_result.md:11-15`：引入 `skill_panel.py` 的个人安装删除入口及其 `%CODEX_HOME%/skills/<目录>/SKILL.md` 安全边界。
- `tasks_round/tasks_round_617_result.md:13-16`：把删除交互改为“勾选后点击删除已勾选”，仍只是删除边界。

结论：从现有 `tasks_round` 结果文件不能找到“引入 `.codex\\skills` 扫描”的轮次，因为该扫描并不存在；预设优先探测的引入轮次也没有被现存结果报告记录。R616/R617 引入的是删除功能，不是候选扫描。

## C. 阶段配置候选的完整根目录清单

需区分两类候选：

1. 阶段注册 SKILL 勾选项：只来自 `skill_registry.default_root()`，即 `D:\漫剧制作助手\程序\skills`（`skill_registry.py:42-44,397`）。项目 `skill_config.json` 是已选注册 ID 的存储，不是扫描根。
2. 工作流 SKILL 勾选项（“万能剧本工作流”等）：按 `workflow_settings.SKILL_PRESETS` 的固定目录名探测两个路径，顺序为：
   - `%CODEX_HOME%/skills/<预设目录>/SKILL.md`；未设置变量时即 `C:\Users\LAIBIAO\.codex\skills/<预设目录>/SKILL.md`（`workflow_settings.py:61-62,69-71`）；
   - `D:\漫剧制作助手\程序\skills/<预设目录或别名>/SKILL.md`（`workflow_settings.py:58,65-71`）。

没有第三个扫描根；“项目 skills/”不在当前实现中。用户项目只提供两个配置文件：`<项目>/skill_config.json` 与 `<项目>/工作流任务/工作流调用设置.json`。

## D. 删除功能链路

当前 UI 没有“删除已安装…”下拉项；R617 已改为勾选区按钮“删除已勾选”（`skill_panel.py:812-815`）。实际实现为 `Panel.delete_checked_personal_skills()`，位于 `skill_panel.py:915-958`。

1. `skill_panel.py:917-920` 仅收集当前已勾选、且 `is_personal_skill_file()` 判定为 `%CODEX_HOME%/skills/<一级包>/SKILL.md` 的路径；该严格条件见 `skill_panel.py:80-88`。
2. `skill_panel.py:936` 调用 `recycle_paths(personal_skills_root(), paths, '删除个人已安装 SKILL')`。
3. `storage_maintenance.py:48-65` 将文件移动到根目录下 `工作流任务/回收站/自动维护_时间戳/`，并写 `恢复位置.json`；不是永久删除。
4. 成功后 `skill_panel.py:947-955` 重新收集未删且仍勾选的路径，调用 `set_flow_skills()`，移除勾选框并刷新说明/布局。
5. `set_flow_skills()` 在 `skill_panel.py:243-268` 写的不是 `skill_config.json`：它写 `<项目>/工作流任务/工作流调用设置.json`，具体为 `flows[flow].profiles[engine]` 下的 `skill` 与 `skills` 字段（通过 `workflow_settings.set_skills(profile, picked)`）。

## E. 现有配置引用与测试

### E1. 当前数据引用

按默认用户项目根 `D:\漫剧下载\项目` 枚举到当前项目 `摄像头3_20260924` 的两个相关配置，并递归检查字符串值：

| 文件 | `.codex\\skills` 路径条数 |
| --- | ---: |
| `D:\漫剧下载\项目\摄像头3_20260924\skill_config.json` | 0 |
| `D:\漫剧下载\项目\摄像头3_20260924\工作流任务\工作流调用设置.json` | 10 |

后者 10 条由 5 个 `skill` 字段和 5 个 `skills` 列表项组成，去重后为 2 个路径。没有输出路径正文或其他配置内容，避免在诊断报告中扩散用户数据。

### E2. 是否已有“应用必须扫描 `.codex\\skills`”测试

没有。`tests/test_skills.py:1195-1223` 只测试个人目录入口被删除后进入回收站，以及当前流程引用消失；不测试候选扫描。

最接近的测试是 `tests/test_core.py:825-833`：

```python
with mock.patch.dict(os.environ, {"CODEX_HOME": td}):
    after = ws._preset_paths()
    self.assertIsNot(after, before)
    self.assertEqual(len(after), len(before))
    self.assertTrue(str(after[0][1]).startswith(str(Path(td).resolve())))
```

它断言预设路径缓存会随 `CODEX_HOME` 改变而重建，并未断言“应用必须扫描 `.codex\\skills`”，也未创建或枚举任何 SKILL 文件。

## 根因判断

阶段配置出现 `.codex\\skills` 路径的直接来源是 `workflow_settings.preset_skill()` 的“个人预设优先、程序内置回退”规则，而不是 `skill_registry` 越界扫描。删除功能沿用同一 `%CODEX_HOME%/skills` 路径来限制可删除范围，但没有把该目录注册给 `Registry`。

## J. 整改路线（下一修复轮候选）

1. 若产品规则为“阶段配置只能展示程序内置 SKILL”：最小改动为 `workflow_settings.preset_skill()` 删除 `_home_skill()` 优先分支，始终返回 `_bundled_skill()`；影响工作流预设候选、默认工作流配置和已有用户工作流配置中的 `.codex` 路径兼容策略。
2. 保留删除功能，但不要以“移除注册表扫描”为目标：注册表没有该扫描。删除功能可继续仅删除用户主动勾选的个人入口，或另行决定是否连同工作流预设候选一起移除个人目录支持。
3. 修复前先明确迁移策略：现有一个项目配置中 10 条（去重 2 条）个人路径，若取消该支持，需在读取 `工作流调用设置.json` 时保留、替换为内置路径，或显式提示失效；不能悄然改写用户数据。

## K. 测试计划

若执行 J1，在既有 `tests/test_core.py` 的预设路径测试组补（或替换契约变更后的）断言：即便设置 `CODEX_HOME` 并创建同名 `SKILL.md`，`preset_skill(folder)` 仍返回程序 `BUNDLED_SKILLS` 路径；`flow_skill_choices('writing')` 不出现个人目录路径。保留 `tests/test_skills.py` 的删除回收与外部路径拒绝测试，除非产品决定同时废弃个人 SKILL 删除功能。

## 自审

本轮只读：未修改任何 `.py`、测试、配置、用户数据或既有结果文件；唯一新增文件为本报告 `tasks_round/tasks_round_619_result.md`。
