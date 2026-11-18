# 残留 SKILL 治理任务书

> 编写日期：2026-11-18　｜　轮次：R3276（只读诊断轮产物）
> 前置诊断：[R3276_残留SKILL无法删除_诊断报告.md](R3276_残留SKILL无法删除_诊断报告.md)（同轮产出）
> 本文为只读诊断产物，不含代码改动。行号基于 master `8317c4cc`（R3258）实测。
> 口径：本文所有数字均经本树实测。

---

## 0. 总目标

让用户能真正摆脱残留 SKILL 的干扰，同时不破坏「内置 SKILL 随程序分发」的既有契约。三件事必须同时成立：

1. **看得见**——`skills/` 下不属于 01–13 的目录，能在管理界面被列出、被处置。
2. **禁得掉**——内置 `pipeline-*` 可以被禁用（文件保留，列表消失，升级后仍保持禁用）。
3. **删得净**——删除残留包后，git 索引不残留 gitlink，不会「删了又回来」。

**明确不做**：不放开内置层的**删除**（L2-D18 已定）；不引入任何新第三方依赖；不改 `_stage_directories()` 的严格语义。

---

## 1. 已确认决策清单（执行者不得自行变更）

| 编号 | 决策 | 依据 |
| --- | --- | --- |
| L2-D14 | 三个缺陷分开修，不混一轮 | 用户 Q1：(c) 但分开修 |
| L2-D15 | 内置层放开**禁用**，删除仍禁止 | 用户 Q2 按推荐 |
| L2-D16 | 残留包走**独立受控通道**，不进阶段注册表 | 用户 Q3 按推荐 |
| L2-D17 | 「pipeline skill」指 `01-13` 下的 `pipeline-*.skill.md` | 用户 Q4：是 (b) |
| L2-D18 | 内置 skill 删除仍禁止 | 既存契约 + 用户未推翻 |
| L2-D19 | 不引入新依赖，复用 `set_skill_disabled` / `recycle_paths` / `_package_source` | 用户 Q7 按推荐 |
| **L2-D20** | **重装整包 `AIGC创作全流程`，不是逐个子技能** | **用户 Q9：a** |
| **L2-D21** | **00 ＝ 总包（整个流程的项目级 skill）；01–13 ＝ 阶段 skill 位置；用户自选阶段单独安装；统一由共享输入框调用** | **用户 Q10** |
| **L2-D22** | **重装由用户本人操作，不由执行者代跑** | **用户 Q11：由我自己操作重装** |
| **L2-D23** | **验收只要求 (a)：管理界面能删掉 AIGC 包、删除后 git 干净、重装成功** | **用户 Q12：a** |
| **L2-D24** | **后续不再拆分 pipeline skill** | **用户 Q12** |

### 1.1 Q21 澄清带来的架构修正（重要）

用户 Q10 明确了 `00` 与 `01–13` 的分工，这**修正了本人此前的一个判断**：

- 此前我认为「`00全流程SKILL` 应当纳入注册表成为可见 skill」。
- 用户澄清：`00` 是**总包**语义，`01–13` 才是**阶段 skill 位置**，用户自选阶段单独安装。
- 因此 **`00全流程SKILL` 不应该被塞进阶段注册表**——那会污染阶段配置的下拉选项，且 `stage` 字段对总包无意义。

**修正后的方案**：`00` 保持「总包」语义不变，但需要一条**管理通道**让它可见、可删、可重装。这正是 L2-D16 的「独立受控通道」。

### 1.2 13 个子技能（非 14）的实测事实

| 项 | 实测 |
| --- | --- |
| 含 `SKILL.md` 的子目录 | **13 个** |
| 名单 | `sd-asset-engine`、`sd-combat-engine`、`sd-decision-engine`、`sd-feed-engine`、`sd-jieshuo-engine`、`sd-overseas-engine`、`sd-qc-engine`、`sd-real-engine`、`sd-recon-engine`、`sd-script-engine`、`sd-storyboard-engine`、`sd-xuanhuan-engine`、`short-drama-director` |
| frontmatter `stage` 字段 | **13 个全为空** |
| 包根 README 自称 | 「1 总控 + 12 子技能」——**与实物不符**（实为 12 `sd-*` + 1 `short-drama-director` = 13） |
| `assets/` 目录 | 无 `SKILL.md`，纯资源图片，不计入 |

因 L2-D23 只要求整包级验收，**13 个子技能不逐个安装**，其 `stage` 缺失问题不再阻塞本轮。

---

## 2. 现状盘点（详见诊断报告，此处只列要点）

### 2.1 三个缺陷

| # | 缺陷 | 根因位置 | 症状 |
| --- | --- | --- | --- |
| D1 | 非阶段目录不进注册表 | `orchestrator/skill_registry.py:494` `_stage_directories()` | `AIGC创作全流程` 在列表里不存在 |
| D2 | 内置层三面封死 | `pet_skills_manage.py:303`/`:411`；`ui/skill_lifecycle_service.py:91`/`:331` | `pipeline-*` 删除与禁用均被拦 |
| D3 | 孤儿 gitlink | git index `160000 1a43ae5a...`；`.gitmodules` 不存在 | 删目录后 git 持续报错、可能被重新检出 |

### 2.2 D1 的影响面：8 个目录不可见

`程序\skills\` 根下：`imagegen`(6)、`short-drama-storyboard`(6)、`storyboard-image-prompts`(4)、`templates`(14)、`video-storyboard-gen`(14)
`00全流程SKILL\` 下：`AIGC创作全流程`、`cinematic-director`、`jingju-skills`

### 2.3 D3 的 gitlink 清单：4 个

```
160000 3ef9f995... 程序/reference/HoLLMwood                             （.git 存在）
160000 1a43ae5a... 程序/skills/00全流程SKILL/AIGC创作全流程             （.git 不存在）
160000 6c3d7399... 程序/skills/01 剧本准备SKILL/剧本锻造                 （.git 存在）
160000 357d1348... 程序/skills/01 剧本准备SKILL/编剧技能集               （.git 存在）
```

### 2.4 既有能力（全部可直接复用，无需造轮子）

| 能力 | 实现 | 状态 |
| --- | --- | --- |
| 禁用登记 | `ui/skill_lifecycle_service.py:85` `set_skill_disabled()` → `data/skills/disabled_skills.json` | 对 user/project 层**正常工作** |
| 回收站 | `infra/storage_maintenance.recycle_paths()` | 对本类目录**实测有效**（`status: moved`） |
| 包发现 | `skill_registry.Registry._package_source()` | 已支持「SKILL.md 优先，README 兜底」 |
| 导入管线 | `ui/skill_import_service.py:248` `perform_import()`（暂存→换入→试冻结→登记） | 完备，含失败回滚 |
| 仓库导入 | `ui/skill_import_service.py:572` `import_from_repo()` | 支持 local 与 url 两种 kind |

### 2.5 测试现状

全仓搜索「内置 SKILL 只读」→ 仅 4 处**生产代码**，`tests/` **0 处**。**改动这些拦截不会撞断现有断言。**

---

## 3. 分轮拆解

共 **轮 0–4**。每轮独立领号、独立提交、可单独回滚。

| 轮 | 类型 | 内容 | 触发全量 |
| --- | --- | --- | --- |
| 0 | 只读诊断轮 | 本任务书 + 诊断报告 | 否 |
| 1 | 修复轮 | D2：放开内置层禁用 | 否 |
| 2 | 功能轮 | D1：残留包管理通道 | 是（L3 注册表相关） |
| 3 | 修复轮 | D3：清理孤儿 gitlink（需用户授权） | 否 |
| 4 | 验证轮 | 用户本人执行删除 + 重装，执行者记录结果 | 否 |

### 轮 0：只读诊断轮（本轮）

**交付物**：
- `程序/tasks_round/R3276_残留SKILL无法删除_诊断报告.md`
- `程序/tasks_round/残留SKILL治理任务书.md`（本文件）

**不做**：任何 `.py` 改动、任何 git 索引操作、任何目录删除。

**验收**：
- [ ] 两份文档落盘
- [ ] 诊断报告的证据索引逐条可复现

---

### 轮 1：修复轮（D2 — 放开内置层禁用）

**类型**：§3.2 修复轮。**前置**：轮 0 通过。

**改动**（2 处，最小 diff）：

1. `ui/skill_lifecycle_service.py:91-92`：删除内置层禁用拦截，让 `set_skill_disabled()` 对 `builtin` 生效。
2. `pet_skills_manage.py:411-413`：删除 UI 侧的同名预检，改为只提示不阻止。

**保留不动**：
- `pet_skills_manage.py:303`（删除预检）——L2-D18 删除仍禁止。
- `ui/skill_lifecycle_service.py:331`（删除服务端）——同上。

**为什么禁用而不是删除**：内置 skill 随程序分发，物理删除后下次升级安装会原样回来，用户会再次撞上同一问题——**删除对内置层是假解决**。而禁用登记在 `data/skills/disabled_skills.json`，升级安装保留，能真正解决「被干扰」。

**验收（先红后绿）**：
- [ ] 复现用例：内置 skill 调用 `set_skill_disabled` 时改前抛 `ImportBlocked`，改后成功（改前失败输出贴入结果文件）
- [ ] 用例：禁用后 `getAll()` 不再返回该 skill
- [ ] 用例：禁用后文件仍在磁盘（不是删除）
- [ ] 用例：重新启用后 skill 回到列表
- [ ] 用例：`disabled_skills.json` 有对应条目，且层为 `builtin`
- [ ] 用例：内置 skill 删除仍被拦（回归保护，确认没有误放开）
- [ ] `smoke_test.py --affected pet_skills_manage skill_lifecycle_service` 绿

---

### 轮 2：功能轮（D1 — 残留包管理通道）

**类型**：§3.1 功能轮。**前置**：轮 1 通过。

**设计**：不改 `_stage_directories()` 的严格语义（它服务阶段配置，必须保持「只认 01–13」）。新增一条**只读发现 + 受控处置**的管理通道。

**改动**：

1. **新增 L2 服务** `domain/skill_residue_service.py`：
   - `scan_residue(program)` → 列出 `skills/` 下**不属于** 01–13 的一层目录与包，返回 `[{name, path, kind, size, sub_skill_count}]`。
   - `dispose_residue(program, names, publisher)` → 逐个委托 `storage_maintenance.recycle_paths()`；返回 `ServiceResult`（`success` / `UserError` / `SystemError`）。
   - **只读发现，不做删除决策**；删除仍唯一走 `recycle_paths`（硬约束 14）。
2. **L4 入口**：`ui/skill_residue_panel.py`（或在既有 `skill_panel` 加一个「残留包」页签），列出条目、显示子技能数与占用空间、提供「移入回收站」按钮，二次确认。
3. `tests/architecture/_layers.py`：`_register(2, "skill_residue_service")`。
4. `architecture.md` §3 的 L2 行补 `skill_residue_service`。
5. 刷新覆盖率基线（653 → 654）。

**关键约束**：
- 发现逻辑**必须**复用 `skill_project_layer.stage_from_path()` 判定「是否阶段目录」，不得另写一套正则。
- 处置**必须**经 `recycle_paths()`，不得直接 `shutil.rmtree`。
- 对 `00全流程SKILL` 下的**包**（`AIGC创作全流程` 等），`kind='package'`，删除时收整个包目录。
- 对 `skills/` 根下的目录（`imagegen` 等），同样按包处理。

**验收（先红后绿）**：
- [ ] 复现用例：临时目录构造 `skills/00全流程SKILL/AIGC创作全流程`，改前 `scan_residue` 不存在 → 改后能列出该条目
- [ ] 用例：`scan_residue` **不**返回 01–13 下的任何目录（防止误伤）
- [ ] 用例：`dispose_residue` 后目录消失、回收记录完整、可经 `restore_recycle_batch` 恢复
- [ ] 用例：处置一个不存在的名字返回 `UserError` 而非抛异常
- [ ] 用例：`ServiceResult` 四字段契约（`ok`/`reason`/`recoverable`/`data`）
- [ ] `smoke_test.py --architecture` 绿（新增模块后的基线一致性）
- [ ] 触发全量（L3 注册表相关 + 层级登记表改动）

---

### 轮 3：修复轮（D3 — 清理孤儿 gitlink）

**类型**：§3.2 修复轮。**前置**：轮 2 通过，**且用户明确授权 git 索引操作**。

> ⚠️ **本轮涉及不可逆的 git 索引改动，执行前必须取得用户逐条授权。**

**改动**（只做 `AIGC创作全流程` 一个，验证后再议其余三个）：

1. `git rm --cached '程序/skills/00全流程SKILL/AIGC创作全流程'` —— 清除 gitlink 索引记录。
2. 判定：该目录内**无 `.git`**，即内容不受子仓库管理 → 应转为普通目录跟踪，或（若用户要删）不再跟踪。
3. 若用户选择保留内容：`git add '程序/skills/00全流程SKILL/AIGC创作全流程'` 重新纳入普通文件跟踪。
4. 若用户选择删除：轮 2 的 `dispose_residue` 移入回收站后，索引记录已由第 1 步清除，git 状态应干净。

**不动的三个**：`HoLLMwood`、`剧本锻造`、`编剧技能集` 有 `.git`，属独立议题，本轮只记录欠账。

**验收**：
- [ ] `git ls-files -s | grep 160000` 不再包含 `AIGC创作全流程`
- [ ] `git status` 无 `no submodule mapping found` 报错
- [ ] 目录内容未丢失（若选择保留）或已在回收站（若选择删除）
- [ ] 结果文件记录授权来源与操作前后索引对比

---

### 轮 4：验证轮（用户本人执行）

**类型**：§3.6 验证基线轮（或按用户指定）。**前置**：轮 1–3 通过。

**由用户本人操作**（L2-D22）：
1. 打开 `设置 → SKILL管理`
2. 在「残留包」通道找到 `AIGC创作全流程`，执行「移入回收站」
3. 确认列表消失、磁盘目录消失、git 状态干净
4. 自行重装 `AIGC创作全流程` 整包（L2-D20）
5. 确认重装后能正常显示与调用

**执行者职责**：
- 提供操作步骤与预期结果清单
- 用户操作后，记录实际结果到 `tasks_round_N_result.md`
- 若有异常，按 `diagnosing-bugs` 重新建环

**验收**（L2-D23 口径）：
- [ ] 管理界面能看到并删掉 `AIGC创作全流程`
- [ ] 删除后 `git status` 干净
- [ ] 重装成功
- [ ] **不要求** 13 个子技能逐个可见（L2-D24：后续不再拆分 pipeline skill）

---

## 4. 测试方案

### 4.1 每轮必跑（轮 0 除外）

```powershell
& '..\运行环境\Python\python.exe' -B smoke_test.py --probe
& '..\运行环境\Python\python.exe' -B run_selftests.py -k <本轮模块名>
```

### 4.2 新测试要求

- **先红后绿**：结果文件贴改动前失败输出。
- 断言检验**行为**而非源码字符串。
- 禁用类测试必须构造**临时 program 目录**（`default_registry(program)` 接受任意路径），不依赖真项目、不依赖真 Tk——毫秒级可跑。
- 必须包含「**不误伤**」用例：确认 `01–13` 下的正常 skill 不受影响。

### 4.3 三个基线（每轮结束必报）

| 基线 | 要求 |
| --- | --- |
| 默认冒烟 | 9/9（当前实测为 9 项） |
| 架构门禁 | 当轮实际总数、失败集合、改前后比较 |
| 全量回归 | `full-safe-receipts.json` 真实凭据为唯一权威 |

---

## 5. 风险与回滚

| 风险 | 处置 |
| --- | --- |
| **误放开内置删除** | 轮 1 只动禁用相关 2 处；专门加「内置删除仍被拦」回归用例 |
| **`scan_residue` 误伤阶段目录** | 必须复用 `stage_from_path()` 判定；专门加「不返回 01–13」用例 |
| **git 索引改动不可逆** | 轮 3 前逐条取得授权；操作前记录 `git ls-files -s` 快照；只做 1 个 gitlink |
| **回收站数据丢失** | 全程走 `recycle_paths()`，可用 `restore_recycle_batch()` 恢复；轮 2 加恢复用例 |
| **禁用登记在升级安装后丢失** | `data/skills/` 属升级保留目录（`AGENTS.md` §2.1 与 `distribution_manifest.md`），需在结果文件确认 |
| **新增 L2 模块触发覆盖率门禁** | 轮 2 同轮刷新 `覆盖率基线.json`（工具已存在，见 L2 任务书 §2.10） |
| **与 L0/L1/L3 并发车道冲突** | 本任务书涉及文件：`pet_skills_manage.py`、`ui/skill_lifecycle_service.py`、`orchestrator/skill_registry.py`（只读）、`orchestrator/skill_project_layer.py`（只读引用）、`infra/storage_maintenance.py`（只调用）。**均不在 L0/L1/L3 任务书改动面内**；`storage_maintenance` 只调用不改动 |

**回滚**：每轮独立 commit，优先 `git revert`。git 索引操作的回滚为 `git rm --cached` 前先记录快照。

---

## 6. 与并发重构的关系（用户重点关切）

| 层 | 当前状态 | 与本任务书的交集 |
| --- | --- | --- |
| L0 | 只完成轮 0 文档；唯一代码改动 R3246 悬于 3 条未合并分支 | **无交集**——本任务书不碰 `contract/` |
| L1 | **轮 0 与轮 1 均已合入 master**（R3247 / R3268）；轮 2–6 未开工 | **极低**——轮 1 改的是 `api_endpoints`、`model_metering`、`model_pool`、`pet_llm`、`request_ledger`，**未碰 `storage_maintenance`**；本任务书只**调用** `recycle_paths()`，不改它；L1 轮 2「无界增长」会动 `storage_maintenance`，但改的是台账/缓存增长，不是 `recycle_paths` 的签名 |
| L3 | 未找到独立 L3 任务书 | **低**——对本任务书而言 `skill_registry` 只读引用 |
| L2（本会话另一任务书） | `L2领域服务层优化任务书.md` 10 轮未开工 | **中**——两个任务书都会新增 L2 模块、都要刷新覆盖率基线。**须协调基线刷新顺序** |

### 6.1 与 L2 任务书的基线冲突（需处理）

两个任务书都要刷新 `维护记录/覆盖率基线.json`：

- `L2领域服务层优化任务书` 轮 1：653 → 657（+4 模块）
- 本任务书轮 2：+1 模块（`skill_residue_service`）

**注意**：L1 轮 1（R3268）合入时已刷新过一次基线，但当前 `modules_total` 仍为 **653**，而实测生产模块为 **654**（差额为 `agent/__init__.py`，`L1基础设施层优化任务书` §2.1 已记录该既存口径差）。即基线当前处于「差 1」的既存状态，不是本轮引入。

**处置**：谁的轮次先开工，谁先刷新基线；后开工者基于前者的结果再刷。**不得并行刷新**（会互相覆盖）。刷新命令见 `L2领域服务层优化任务书` §2.10。

---

## 7. 交付留痕

### 7.1 每轮收尾

按 `AGENTS.md` §7：领号 → `tasks_round_N_result.md`（三问）→ 状态页轮次头同步 → `N == M + 1` 检查 → §2.6 提交。

### 7.2 任务书收口

全部轮次后输出 `程序/tasks_round/任务完成/残留SKILL治理·任务完成.md`，逐条列证据（轮次号、结果文件、测试凭据、commit hash）；未完成项如实标注。

---

## 8. 验收总清单

| # | 项 | 判据 |
| --- | --- | --- |
| 1 | 内置 pipeline skill 可禁用 | 禁用后不在 `getAll()`，文件仍在磁盘，升级后仍禁用 |
| 2 | 内置 skill 删除仍被拦 | 回归用例绿 |
| 3 | 残留包可见 | `scan_residue` 列出 `AIGC创作全流程` 等 8 个目录 |
| 4 | 残留包可处置 | `dispose_residue` 移入回收站，可恢复 |
| 5 | 不误伤阶段目录 | `scan_residue` 不返回 01–13 任何目录 |
| 6 | gitlink 清除 | `AIGC创作全流程` 不再有 `160000` 记录 |
| 7 | git 状态干净 | 无 `no submodule mapping found` |
| 8 | 用户重装成功 | 用户本人操作后确认 |
| 9 | 无新依赖 | `requirements.txt` 不变 |

---

## 9. 明确不做（记欠账）

| 项 | 理由 |
| --- | --- |
| 放开内置 skill **删除** | 内置随程序分发，删了升级会回来，是假解决（L2-D18） |
| 把 `00全流程SKILL` 纳入阶段注册表 | 破坏 `_stage_directories()` 的严格语义，污染阶段配置（L2-D21） |
| 13 个子技能逐个安装到 01–13 | L2-D23 只要求整包验收；且它们无 `stage` 字段，需先补 frontmatter（L2-D24） |
| 拆分新的 pipeline skill | L2-D24 明确不再拆 |
| 另三个 gitlink（`HoLLMwood`、`剧本锻造`、`编剧技能集`） | 有 `.git`，属独立 submodule 议题，本轮只记录 |
| 引入第三方依赖 | 既有能力已足够（L2-D19） |
| 改 `_stage_directories()` 语义 | 它服务阶段配置，保持「只认 01–13」 |

---

## 10. 附：证据索引

| 结论 | 取证方式 |
| --- | --- |
| 3 个缺陷与根因位置 | 见诊断报告 §一、§六 |
| `00全流程SKILL` 被排除 | 实跑 `_stage_directories()` → 13 个阶段目录，无 00 |
| 注册表 73 项无 AIGC | 实跑 `getAll()`，`contains AIGC? False` |
| 13 个子技能无 stage | 逐目录读 `SKILL.md` frontmatter，13 个全为 `(none)` |
| 内置删除/禁用拦截 | 读 4 处源码（`pet_skills_manage.py:303/:411`、`skill_lifecycle_service.py:91/:331`） |
| 无测试锁定 | `grep '内置 SKILL 只读'` → tests 0 处 |
| 孤儿 gitlink | `git ls-files -s` → `160000 1a43ae5a...`；`.gitmodules` 不存在 |
| `recycle_paths` 有效 | 临时目录实跑，`status: moved` |
| 禁用机制已完备 | 读 `skill_lifecycle_service.py:85-96` |

**未运行**：冒烟、架构门禁、全量——只读诊断轮按 `AGENTS.md` §3.5 不跑测试。
