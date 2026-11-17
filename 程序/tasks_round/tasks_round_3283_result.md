# R3283：残留 SKILL 治理轮 2（D1 残留包管理通道）
<!-- round-evidence: {"commit_base": "9b620f1c", "credential_hits": 0, "evidence_sha256": "bb0aed70f543b088", "exit": 0, "failed": 0, "passed": 65, "round": 3283, "tests": "run_selftests.py -k skill_residue_service pet_skills_manage skill_project_layer skill_notes architecture.test_service_return_contract"} -->

- 轮次类型：§3.1 功能轮，仅任务书轮 2；前轮独立提交 `9b620f1c`。
- 测试与三个基线：先红后绿；默认冒烟 8 核心检查＋1 隐藏桌面 probe＝日志 9 通过／0 失败；最终 affected 56/56，8.0 秒，0 skip；真实 Tk 夹具／多选 UI／服务合跑 40/40。最终架构 532/532，290.652 秒，退出 0，与前轮 532 持平，失败集合为空。完整全量尝试中断，无汇总、无凭据；既存语音设置高度断言仍红，不称全量通过。
- 欠账：D1 实现完成；识别并适配既存真实测宽测试夹具；语音设置超屏／Tk 分类历史阻断由 lead 后续独立验收修复轮处理。D3 索引与用户本人重装不在本轮执行。

## 计划与设计复核

当前分支 `codex/skill-residue-governance`，工作树 `dsh-6187d0c7-f35d`；统一入口实领 R3283，scope 扫描与其余 53 条活跃分支无重叠。先读任务书、R3276 报告、R3279 恢复记录与现行实现。

REQ-D1：管理页可见并单独管理非阶段包；00 下各包独立展示；01–13 阶段与阶段注册表不变；回收须二次确认、可恢复，非法／不存在目标返回 UserError。

DES-D1：新 L2 `domain/skill_residue_service.py` 仅消费注入的 `stage_from_path`、`package_source` 与回收 `publisher`；由既有 L3 `skill_project_layer` 薄适配注入自身阶段判定、`Registry._package_source` 与 L1 `recycle_paths`。这是对任务书“L2 直接复用 L3”示意的最小分层适配，避免反向 import 和重复路径／包发现权威。扫描仅按用户打开管理菜单时懒执行；包始终不注册为阶段 skill。根目录 00 作为容器，独立收其下一层包；其他非阶段根目录作为独立包。拒绝链接／junction 和越界，处置时重新发现目标。

## 先红证据

命令：`python -B run_selftests.py -k skill_residue_service`（随附解释器、PYTHONUTF8=1）。结果：0/1，退出 1，0 skip。

```text
ImportError: Failed to import test module: test_skill_residue_service
from domain.skill_residue_service import scan_residue, dispose_residue
ModuleNotFoundError: No module named 'domain.skill_residue_service'
```

运行器同时提示他树 GUI 令牌占用；本失败为纯导入缺失，可直接归因，不是 GUI 并发。

## 实现与架构适配

- 扫描返回任务书五字段 `name/path/kind/size/sub_skill_count`，额外包含相对路径标识与既有包说明名称；空间以字节计，子技能统计子目录 `SKILL.md` 与 `.skill.md`，不计整包入口。递归统计不跟随符号链接／junction，不在启动路径调用。
- 管理页复用当前窗口、DataTable 和列宽约定，增加「残留包管理…」入口；按包展示名称、位置、子技能数、占用空间、包说明。支持多选，两次确认明确完整路径及包数；成功后刷新列表。
- `dispose_residue` 同时接受单名和 names 列表，先整批校验再向注入 `recycle_paths` 发布器提交整批目标。相对路径用于消歧；任一无效目标拒绝整批，避免静默忽略多选或产生前半批成功。相比任务书示意的“逐个委托”，使用现有回收器原子批次与回滚能力，减少部分成功风险。
- 服务结果成功、缺失／非法参数、IO 故障分别为 `success/UserError/SystemError`，始终四字段；返回回收权威的真实逐项记录，不伪造凭据路径。
- `_layers.py` 与 architecture L2 表登记新实体。采用方门禁原先只认可顶层文件或历史逻辑名，首次运行 26 条中 2 红：新服务未登记 scope 和批准 adopter。登记后按现有顶层判定会错误归入“历史未实体化”，故仅新增 `第一项.entity_paths` 映射，指向新实体且测试断言必须等于既有 `entity_file(name)` 解析、文件真实存在。原 adopter 扫描全集、历史缺失集合与豁免数断言均保留；新服务和既有采用方接受同一 AST 契约扫描，临时目录行为用例另验证成功／用户错误／系统错误的四字段。

## 补充红绿与环境取证

补充 size/count 与批量前，7 条中 2 红：`KeyError: sub_skill_count`，多目标返回“请选择要回收的残留包”；补实现后服务 10/10 通过。用例包含全部 13 个阶段编号、真实 Windows junction 指向外目录且不被扫描／处置、mock 符号链接／根 junction、空／缺失／越界／阶段／容器目标、发布器错误、真实整包回收记录与 `restore_recycle_batch` 恢复。

覆盖率首次未带 FFmpeg PATH，媒体 fixture 3 个错误，工具拒写基线；补齐环境后 10 组目标全绿，真实测得 654 个模块、75 个有覆盖、579 个未被该定向组触及，新服务 57/61（93.4%）。同步 runbook §11 的定向口径，没有手工填写测量值。

UI 首轮新测试引用了不存在的 helper／fixture 名，暴露 NameError 与 AttributeError；已改用本文件既有 `_dialog_buttons/walk/self.win` 测试接口，断言不弱化。界面隐藏桌面定向当时 39/39、0 skip，后续再补多选完整行为验收。

## 全量中断与失败闭环（第一次）

第一次完整诊断在他树 PID50708 退出后启动（后台 job `pwsh-74e43b9b3c00412d`），静态架构发现 Registry→ProjectLayer→Registry 环，即使函数内 import 也构成静态图回边。保留 L3 适配，改为由 UI 当前已有的 `Registry._package_source` 参数注入 L3，L3 不 import Registry；阶段判定与回收发布器仍由 L3 注入。循环依赖＋服务＋采用方门禁定向 21/21 绿，无环豁免不增加。

本次全量启动后修改过代码和测试，只作诊断，不作最终完整通过证据。会话中断后旧 job 返回 unknown job，已无本树 Python 进程；`R3283_full_safe.log` 仅有隐藏桌面启动行，`hidden_selftest.log` 未含结尾用例总数／退出摘要，故不能推断最终用例数或最终失败数。现场已原样保全 `logs/R3283_full_interrupted.log`。已见红模块仅能报告：循环依赖 2、行尾 1、model_manager_actions 1、skill_notes 1。

- 行尾：独立复现确认仅前轮生成的三个可再生日志 `logs/r3279_architecture.txt`、`r3279_architecture_final.txt`、`r3279_commit.txt` 为 UTF16，原内容转 UTF8并核对等价，不提交日志；`test_line_endings` 16/16 绿。
- `skill_notes`：旧 Mock panel 无 Tk root，而现主干 U1 `_display_width` 已变真实字体计量，触发 `Too early to text_measure_font: no default root window`。按新测宽契约给唯一涉及测宽的用例建立真实 Tk root、withdraw、销毁清理；原选择与显示两条断言不变，不 mock 量宽。与本轮新多选 UI／服务隐藏桌面合跑 40/40、0 skip。
- 语音设置测试：继承 Batch7Case，运行器直接 import 分类未识别 Tk；显式 `gui_hidden` 真复验仍出现窗高 1061 < 请求 1227 的既存裁切问题（23 条中 2 红，另一个为修复前的 skill_notes）。没有修改或跳过尺寸断言。lead 已核验裸 Card 的内容请求高度超出当前屏幕，明确不把范围外生产 UI 修复和运行器分类混入 D1；后续独立领号修复滚动容器／测试分类再最终全量。当前无本轮改动造成且未闭环的已知红项。

## 最终冻结验收与接续检查点

已冻结本轮源码与测试后：

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| 默认冒烟 | 8 核心＋1 probe，9 通过／0 失败，退出 0 | `logs/R3283_smoke.log` |
| 最终 affected | 56/56，8.0 秒，0 skip，退出 0 | `logs/R3283_affected_final.log` |
| 真实 Tk 夹具＋多选 UI＋服务 | 40/40，5.9 秒，0 skip，退出 0 | `logs/R3283_fixture_green.log` |
| 循环依赖＋服务结果采用方＋服务 | 21/21，5.6 秒，0 skip | 统一运行器输出 |
| 行尾 | 16/16，1.2 秒 | 统一运行器输出 |
| 定向行覆盖率 | 最终冻结代码重测 10 组全绿，654 模块，75 覆盖，服务 93.4%，退出 0 | `维护记录/覆盖率基线.json`；`logs/R3283_coverage_final.log` |
| 最终全部架构 | 532/532，290.652 秒，退出 0；较前轮 532 不变，失败集合为空 | `logs/R3283_architecture_final.log`；后台 `pwsh-200516f5f98e4a91` 已采集退出 0 |
| 完整全量 | 已尝试但会话中断，无最终汇总，无正式凭据；语音既存超屏未闭环 | `logs/R3283_full_interrupted.log`、`logs/R3283_tk_baseline.log` |

最终 affected 命令为 `smoke_test.py --affected skill_residue_service pet_skills_manage skill_project_layer`；新服务、管理页、ProjectLayer 和安全消费用例均覆盖。默认冒烟与 affected 已自动 probe，不传不支持的 `--probe`。全程使用随附解释器、PYTHONUTF8=1、FFmpeg PATH；含 Tk 用统一隐藏桌面运行器，不抢 GUI 令牌。

冻结验收源码 SHA256 前16位：`domain/skill_residue_service.py=9232eca1e9ba0980`、`orchestrator/skill_project_layer.py=b52898d7549108d2`、`pet_skills_manage.py=136bcadd2e885f77`；测试 `test_skill_residue_service=861a49062ff5fd55`、`test_pet_skills_manage=9703f9c664378737`、`test_skill_notes=32dfde8260f8398a`。最终 affected、Tk 合跑及全部架构均针对该冻结实现。

本树只读真实扫描 AIGC 总包：`size=3660831` 字节、`sub_skill_count=13`、`description=README.md`；Registry 仍 73 项、13 个阶段目录，AIGC 不在注册表。未对真实总包执行回收，仅临时 fixture 验证。

本树 `project_status.md` 架构期间临时投影 3284 满足 N=M+1；架构完成后已按 `git show HEAD:程序/project_status.md` 精确恢复原始字节和轮次 3278，工作区无该文件差异，不暂存／不提交；master 最终统一同步。dirty diagnostic 不写正式绿色凭据；最近正式收据仍为 R3258，不能把中断诊断当通过。本轮可独立提交的 D1 变更与历史全量阻断分开报告；lead 将另开专门验收修复子会话处理语音问题和最终全量，再推进轮3／master 合入。此子会话不执行轮3，不合master，不标整体任务书完成；任务书全部收口时由 lead 生成同名任务完成文件。

## 提交核对

`git diff --check` 通过；计划仅暂存 D1 新服务／既有 L3 适配／UI、对应测试、分层／采用方登记、覆盖率真实基线与文档、R3283 结果及前轮 hash 补记。不暂存状态页、日志、用户数据、私有配置、复制的 gitlink 测试资源。统一提交入口将执行凭据扫描与 `--tests skill_residue_service pet_skills_manage skill_project_layer skill_notes architecture.test_service_return_contract`，生成 `tasks_round/evidence/R3283.json`。本文件在提交前写入，提交 hash 由 lead 下一轮接续补记；不得为补自身 hash 混入第二次源码提交。
