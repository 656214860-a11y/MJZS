# R2431 结果：总控包 scripts 机检桥（aigc_lint）接入 skill_tools

## 三个必答（§7）

- **轮次类型**：功能轮（§3.1）——新增 L1 模块 `aigc_lint.py`，把总控包（`skills/00全流程SKILL/AIGC创作全流程/.../scripts/`）里被闲置的确定性机检脚本（`validate_prompt.py` C1~C30 / H1~H12、`gate_check.py` 六道闸门、`audit_contract.py` 契约核销、`style-lock-ladder/recommend.py` 画风锁引擎）接进 `skill_tools`，让「提示词质检 / 闸门 / 契约 / 画风锁」从「靠模型自觉」变成「机器断言」。
- **测试跑了吗、三个基线过了吗**：
  - 定向：`tests.test_aigc_lint` **9/9**（5 通过 + 4 按 `REQUIRES_BUNDLED_SKILL` 诚实跳过，因子模块在工作树未初始化）；`tests.architecture.test_layers` 6/6、`test_coverage_baseline` 5/5、`test_no_circular_import` 2/2、`test_static_names` 8/8 均绿。
  - 默认冒烟 **8/8**。
  - 架构门禁：本轮相关门禁（分层/覆盖率/环依赖/静态命名）全绿；`tests.test_skill_tools` 有 4 个 error，均为 DSH 沙箱对 `$TEMP\dsh-OYrQD9` 的临时目录清理拒绝（`PermissionError: [WinError 5]`），是**环境限制、非本轮回归**——该测试文件本轮未改动，且同一文件在沙箱外（主工作区）不受影响。
  - 全量：本轮改 `aigc_lint.py`（新模块）、`skill_tools.py`（L3）为源码轮 +1；未触发 8 轮门禁线，本轮不跑全量（沙箱无法派生工作进程）。
- **project_status.md 的欠账少了吗**：本轮不产生新欠账；`aigc_lint.py` 是「桥」，不复制 400KB 脚本的判据，脚本本身仍是上游子模块的唯一权威，未引入重复逻辑。

## 根因与改动

### 问题（本轮要解决的）

总控包 13 个机检脚本（`validate_prompt.py` 等）在 `skill_registry` 的引用解析里被归为 `resource`「只登记、不内联、不执行」，API 直连路径**永远不会跑**，CLI 路径依赖模型自觉。上游最值钱的确定性校验能力整体闲置。

### 新增 `aigc_lint.py`（L1 基础设施，零第三方依赖）

- **subprocess 桥**：`validate_prompt` / `gate_check` / `audit_contract` 三个吃文件路径的脚本，用 `sys.executable -B` 隔离开跑，退出码映射（0=PASS / 1=FAIL / 2=参数错 / 3=非投喂稿），`--json` 输出稳健解析。
- **import 桥**：`style_recommend` / `style_ladder` 两个纯函数脚本（只 import re）按需 `importlib` 加载，不额外起进程。
- **契约**：子模块未挂载返回 `{'ok': False, 'error': 'SKILL scripts 未挂载…'}`；参数非法/超时/非投喂稿都转结构化 dict，不裸抛 Traceback。
- **只读**：桥只读脚本、不写项目数据；临时投喂稿 md 用后即删。

### 接入 `skill_tools.py`

`READY` 表新增 5 个工具：`feed.validate`、`feed.gateCheck`、`feed.auditContract`、`style.lockRecommend`、`style.lockLadder`；wrapper 从项目锁（`workflow_lock`）取 `video_model_version`/`track`/`aspect_ratio`，缺输入转 `ToolNeedsInput`，未挂载转 `ToolError`。

### 登记与基线

- `tests/architecture/_layers.py` 登记 `aigc_lint` 为 L1（纯标准库依赖，无反向 import）。
- 刷新 `维护记录/覆盖率基线.json`（模块 361→362，覆盖 59 个不变），`runbook.md` §11 数字同步 362 / 303。

## 实测证据

- 上游脚本 `--self-test` 本机全绿：`validate_prompt.py` / `gate_check.py` / `audit_contract.py` 均 PASSED（零第三方依赖，仅 stdlib）。
- 桥真实执行（指到主检出已挂载子模块）：
  - `validate_prompt` 非投喂稿 → exit 3、结构化 dict；真实七段式稿 → exit 0、`issues 0 / warnings 8 / stats{duration_s,shots,chars}`，`--json` 解析正确。
  - `gate_check` 无投喂单元 → exit 2；`style_recommend` → pool 20 项；`style_ladder` → 1393 字符阶梯。

## 环境限制（如实记录，非本轮回归）

1. DSH 沙箱对 `python.exe` 子进程的临时文件写（`$TEMP\dsh-OYrQD9`）做拒绝，`tests.test_skill_tools` 等既有用 `TemporaryDirectory` 的测试在沙箱内 error；覆盖率基线刷新已按用户授权提权（danger-full-access）完成。
2. 工作树子模块 `AIGC创作全流程` 未初始化（父仓库 `.gitmodules` 缺失，gitlink 内容不 checkout），`test_aigc_lint` 里 4 条「挂载路径」用例按 `REQUIRES_BUNDLED_SKILL` 诚实跳过；挂载路径的真实执行已通过「临时指到主检出子模块」的探针实测验证。

## 合入 master 时的既有回归（如实记录，非本分支引入）

合入前 rebase 到最新 master（`ae022295` R2456）后，`tests.architecture.test_no_circular_import` 出现 **2 红**，均为 **master 的 R2450（其他车道）引入的环依赖**：`qwen_adapter → stage_models → workflow_settings`（`workflow_settings.effective_model` 函数内 `import stage_models`，`stage_models` 顶层 `from stage_flow import manual_label`，`qwen_adapter` 顶层 `from workflow_settings import skill_roots_for_config`）。

- 本分支两个提交（`54459042`、`256c8959`）**未触碰** `qwen_adapter.py`/`stage_models.py`/`workflow_settings.py`，本分支代码无环、测试全绿。
- 该环依赖是 R2450 车道的回归，属结构治理轮范畴，超出 R2431 范围；按用户裁定「先合入干净改动、环依赖登记欠账」，**不擅自修复**，留待 R2450 车道另立结构治理轮收口。

## 已提交

- commit `9b6750cb`（rebase 后 `54459042`）：`R2431: 总控包 scripts 机检桥 aigc_lint 接入 skill_tools`
- commit `a621f1e2`（rebase 后 `256c8959`）：`WIP: 补总控包机检桥接入边界的结论文档（R2431 收尾）`
- 文件：`aigc_lint.py`（新）、`skill_tools.py`、`tests/architecture/_layers.py`、`tests/test_aigc_lint.py`（新）、`维护记录/覆盖率基线.json`、`runbook.md`、`说明/总控包脚本机检桥接入边界.md`（新）、`tasks_round/tasks_round_2431_result.md`。
