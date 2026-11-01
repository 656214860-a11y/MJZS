# R621 只读诊断：SKILL 扫描范围收窄 + 删除功能作用域重定向

## 轮次编号与开工自检

实际使用 **R621**。`tasks_round/` 已存在连续的 R613–R620 结果文件，R621 未被占用。`project_status.md` 首行仍写“619 待执行”，与已存在 R619、R620 结果不一致；依 AGENTS.md 连续编号规则（N=M+1），不能复用 619 或 620，因此采用下一个未占用编号 R621。本轮只新增本文件。

## AGENTS.md 第 7 节三问

1. 本轮是功能轮还是整理轮？**都不是；这是只读诊断轮。**
2. 测试跑了吗？三个基线过了吗？**未跑。**本轮禁止修改，且测试不是本轮验收动作。
3. `project_status.md` 的欠账少了吗？**没有。**只收集修复证据，未消除任何欠账。

## A. 扫描范围

### A1. `.codex\\skills` 的来源

`skill_registry.py` 没有 `CODEX_HOME`、`.codex` 或第二扫描根；注册表根在 [skill_registry.py](D:/漫剧制作助手/程序/skill_registry.py:42) 固定为程序同级 `skills/`：

```python
def default_root(program=None):
    return Path(program or Path(__file__).resolve().parent) / 'skills'
```

`.codex` 的来源是固定预设文件的优先探测，而非目录扫描：[workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:61) 计算 `%CODEX_HOME%/skills/<folder>/SKILL.md`，默认 `Path.home() / '.codex'`；[workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:69) 在该文件存在时返回它，否则才回落到程序 `skills/`。原始关键代码：

```python
def _home_skill(folder):
    return Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'skills' / folder / 'SKILL.md'

def preset_skill(folder):
    home = _home_skill(folder)
    return home if home.is_file() else _bundled_skill(folder)
```

阶段配置调用点是 [skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:162) 的 `flow_skill_choices(flow)`；其 [skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:172) 遍历 `workflow_settings.SKILL_PRESETS`，仅把 `preset_skill(folder)` 返回的**现存单文件**加入候选。因此不存在“`C:\Users\LAIBIAO\.codex\skills` 被递归扫描”的代码事实。

### A2. 完整根目录清单

1. 注册表 `Registry` 的递归 `*.skill.md` 根：`D:\漫剧制作助手\程序\skills`（[skill_registry.py](D:/漫剧制作助手/程序/skill_registry.py:42)、[skill_registry.py](D:/漫剧制作助手/程序/skill_registry.py:397)）。
2. 预设候选的单文件优先位置：`%CODEX_HOME%\skills\<preset>\SKILL.md`，此机默认 `C:\Users\LAIBIAO\.codex\skills\...`（[workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:61)）。
3. 预设候选的单文件回落位置：`D:\漫剧制作助手\程序\skills\<preset 或 alias>\SKILL.md`（[workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:65)）。

没有第三、第四个自动目录扫描根。另有手工“选择 SKILL 文件”入口可选择任意文件，但它不是扫描：[skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:900)。

### A3. 引入轮次

对现存 `tasks_round/tasks_round_*_result.md` 搜索 `CODEX_HOME`、`.codex`、`_home_skill`、`preset_skill`：没有结果文件记录引入 `.codex` **扫描**，原因是当前实现并没有该扫描。R616、R617 只记录了个人 SKILL 删除范围：

- `tasks_round/tasks_round_616_result.md`：新增删除已安装项的逻辑，范围为 `%CODEX_HOME%\\skills`。
- `tasks_round/tasks_round_617_result.md`：交互改为勾选后“删除已勾选”，仍限定个人目录。

它们不是 `workflow_settings.py` 的预设优先探测引入记录，也不能作为其来源证据。

## B. 删除功能

### B1. 当前完整实现

当前 UI 已不是“删除已安装…”下拉，而是 [skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:812) 的按钮 `删除已勾选`，命令为 `delete_checked_personal_skills`。该函数在 [skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:915)：从 `self.flow_vars` 取已勾选路径（917），只保留 `is_personal_skill_file(path)`（918），确认后调用 `recycle_paths(...)`（936）。

`is_personal_skill_file` 在 [skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:80)：必须是名字为 `SKILL.md` 的真实文件，且 `item.parent.parent == personal_skills_root()`；因此当前候选来自预设/已选路径而非全量 `.skill.md` 枚举。

### B2. 回收路径

[storage_maintenance.py](D:/漫剧制作助手/程序/storage_maintenance.py:29) 把回收批次建立为 `root/工作流任务/回收站/自动维护_<时间戳>`；[storage_maintenance.py](D:/漫剧制作助手/程序/storage_maintenance.py:48) 用 `shutil.move` 移动文件并写 `恢复位置.json`。当前 root 是 `personal_skills_root()`，所以物理位置为：

`C:\Users\LAIBIAO\.codex\skills\工作流任务\回收站\自动维护_<时间戳>\...`

这是可恢复的项目内回收站，不是 Windows 系统回收站。

### B3. 清除流程引用

删除后 [skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:947) 重新汇集幸存的勾选路径，并在 949 调用 `set_flow_skills(self.project(), self._flow, picked)`。写入路径为：

`<项目>\工作流任务\工作流调用设置.json`

（[workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:160)）。`set_flow_skills` 在 [skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:243) 更新当前 `flows.<flow>.profiles.<engine>` 内的 `skill` 与 `skills` 字段并由 [skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:266) 保存。它不写 `skill_config.json`。

### B4. 与程序内置 `skills/` 的耦合

当前逻辑与程序 `skills/` 的删除作用域是隔离的：`is_personal_skill_file` 的 `item.parent.parent == personal_skills_root()` 条件会拒绝它。若按新决策改为程序树下所有 `.skill.md`，应改的正是 [skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:80)–86 的范围/文件名判断，以及 [skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:936) 的 `recycle_paths` 根参数。

注意直接把回收根改成 `程序\\skills` 会产生耦合：Registry 在 [skill_registry.py](D:/漫剧制作助手/程序/skill_registry.py:397) 递归搜 `*.skill.md`，会把 `skills\\工作流任务\\回收站` 中被移动的 `.skill.md` 再扫描回来。回收站必须放在 `skills` 扫描树之外，或注册表显式排除该子树；这是由现有代码直接推出的作用域风险。

## C. 命名与识别约定

### C1. 文件名

注册表扫描的命名是 `*.skill.md`，常量 [skill_registry.py](D:/漫剧制作助手/程序/skill_registry.py:22) 为 `SKILL_SUFFIX = '.skill.md'`，搜集点是 [skill_registry.py](D:/漫剧制作助手/程序/skill_registry.py:397)。固定预设路径则是 `SKILL.md`（见 A1）；两套入口目前并存。

### C2. 合法性

[skill_registry.py](D:/漫剧制作助手/程序/skill_registry.py:129) 的 `parse()` 读取 frontmatter；[skill_registry.py](D:/漫剧制作助手/程序/skill_registry.py:288) 的 `validate_skill()` 验证必填 frontmatter、字段类型、能力、阶段、声明阶段与目录阶段一致性（291–308），以及文件名 stem 与声明 `name` 一致（320–324）。因此注册表合法性依赖 `*.skill.md` 文件名、frontmatter 和目录阶段三者，不是只看位置。

## D. 缓存 bug（R613 历史问题）

### D1. 当前缓存键和 stat 时机

当前 `_file_cache_key()` 在 [skill_registry.py](D:/漫剧制作助手/程序/skill_registry.py:366) 每次由 `files()`（408）或 `fingerprint()`（412）进入时执行：根目录 `stat().st_mtime_ns`（369）加上每个一级子目录的 `(绝对路径字符串, stat().st_mtime_ns)` 有序元组（375–384）。`_refresh_file_cache()`（386）仅在这个组合键变化时重新 `rglob`。这已经是 R614 对 R613“只看根 mtime”的修复。

### D2. 缓存位置

只有进程内缓存：每个 `Registry` 的 `_directory_mtime_ns`、`_child_directory_mtimes`、`_directory_cache_key`、`_file_records`（[skill_registry.py](D:/漫剧制作助手/程序/skill_registry.py:360)），及 `_DEFAULTS` 的按根路径 Registry 单例（[skill_registry.py](D:/漫剧制作助手/程序/skill_registry.py:507)）。未发现任何落盘注册表缓存、TTL 或哈希缓存文件。

### D3. 根目录改名矛盾：原始输出和判断

R613 未解释“根目录改名又改回仍不刷新”。R614 的同进程对照实验原始输出如下（`tasks_round/tasks_round_614_result.md` 第 13–17 行）：

```text
before=1790674382687697400 renamed=1790674382687697400 restored=1790674382687697400 equal_before_restored=True
```

这证明在该 NTFS 实验中重命名目录本身未改变该目录自身 mtime；旧键只取根 mtime 时不会失效。现代码每次调用都会再次执行根和一级子目录 `stat`（D1 的调用链与行号），不是“首次 `new Registry()` 时才计算”。本轮未对真实 `skills/` 重命名，避免违反只允许新增报告的边界。

## E. 现存引用与测试

### E1. 配置中的 `.codex` 路径

只读 JSON 路径计数结果：

| 文件 | `.codex` 路径条数 |
| --- | ---: |
| `D:\漫剧下载\项目\摄像头3_20260924\skill_config.json` | 0 |
| `D:\漫剧下载\项目\摄像头3_20260924\工作流任务\工作流调用设置.json` | 10 |

后者命中字段为 `skill` 5 条、`skills` 5 条（同一流程配置的双字段存储），共 2 个去重路径。本轮未读取、修改或清理这些用户数据。

### E2. 既有测试

没有测试断言“应用必须递归扫描 `.codex\\skills`”。[tests/test_core.py](D:/漫剧制作助手/程序/tests/test_core.py:825) 的 `test_preset_paths_recomputed_when_home_changes` 只断言修改 `CODEX_HOME` 后预设路径缓存对象重建，且首条路径前缀为临时 home。

删除功能确有断言：[tests/test_skills.py](D:/漫剧制作助手/程序/tests/test_skills.py:1185) 断言旧下拉项不在、按钮文字为“删除已勾选”；[tests/test_skills.py](D:/漫剧制作助手/程序/tests/test_skills.py:1195) 的 `test_delete_personal_skill_recycles_file_and_removes_current_flow_reference` 断言删除个人 `SKILL.md`、从当前流程引用移除，并在 `home/skills/工作流任务/回收站` 找到被回收文件。这些测试须随新作用域重定向更新。

### E3. 缓存失效测试

已有精确覆盖：[tests/test_skills.py](D:/漫剧制作助手/程序/tests/test_skills.py:184) 的 `test_hot_reload_tracks_add_and_delete_inside_stage_directory`：空目录首次取数，子目录新建合法 `.skill.md` 后再次 `reg.files()` 必须包含它，删除后再次取数必须不包含它；同时断言 add/delete 前后 fingerprint 和 `_directory_cache_key` 均变化（184–208）。因此当前测试已经覆盖题述 R606 缺失的回归。

## J. 整改路线

### 1. 移除 `.codex` 预设探测

最小文件集：`workflow_settings.py`、`tests/test_core.py`，必要时 `skill_panel.py` 的文案/选择路径测试。将 `preset_skill()` 改为仅返回 `_bundled_skill()`，并删除或停用 `_home_skill()` 的优先分支。影响面：阶段配置的固定预设将不再从用户 `.codex` 覆盖程序版本；Registry 本身无需修改。

### 2. 删除功能重定向到程序 `skills/`

最小文件集：`skill_panel.py`、`tests/test_skills.py`；若需调整回收基址，`storage_maintenance.py` 与其测试。将个人目录判定换为“位于 `skill_registry.default_root()` 之下且后缀为 `.skill.md`”，候选改为该树可见的全部合法/可选 `.skill.md`，不再以 `SKILL.md` 或“内置不可删”为条件。继续用 `set_flow_skills()` 清除当前流程的 `skill`/`skills` 引用。

回收不能落入 `程序\\skills\\工作流任务\\回收站`，否则递归扫描会重新发现文件。最小安全方案是在仍限制待删路径为 `程序\\skills` 的前提下，以程序目录为 `recycle_paths()` 根，使回收位置为 `D:\漫剧制作助手\程序\工作流任务\回收站\...`，处于扫描树外。影响面：删除后的候选刷新、恢复清单相对路径、现有个人目录删除测试。

### 3. 缓存 bug

最小文件集当前为零：R614 已将键扩展为根 + 一级子目录 mtime，并已有增删回归。下一修复轮只应在复现当前源码仍失败时再改 `skill_registry.py`；否则不能重复改动已修根因。影响面为 Registry 所有调用者，但正常命中仍避免递归扫描。

## K. 测试计划

1. 在 `tests/test_core.py`：创建同时具备临时 `CODEX_HOME` 预设和程序 `skills` 预设的情形，断言阶段候选只使用程序路径；不再断言 home 前缀。
2. 在既有 `tests/test_skills.py`：创建程序 `skills/01 .../x.skill.md`，勾选删除后断言文件离开扫描树、当前流程 `skill` 和 `skills` 均不再含该路径、回收目录存在可恢复文件；随后重新取 Registry，断言不再出现。另断言回收批次不在 `skills/` 内。
3. 保留并运行 [tests/test_skills.py](D:/漫剧制作助手/程序/tests/test_skills.py:184) 的子目录增删 Registry 回归；若改扫描排除规则，再新增“回收目录中同后缀文件不被 Registry 返回”的断言。

## 自审

- 本轮未修改任何 `.py`、测试、配置、用户数据或既有结果文件；唯一新增文件为本报告。
- A–E 每项均给出当前代码文件:行号、历史结果原始输出或只读计数证据。
- 未把固定预设单文件探测误报为递归扫描；未将 R613 的历史缓存问题误报为当前未修复问题。
