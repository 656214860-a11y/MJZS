# R1372：O45 把分发声明变为可复验的干净安装流程

类型：功能轮（§3.1；本项「事实／验证」→ 把《分发清单》从声明变成可复跑、可校验的构建器；不执行原地删除／移动，不碰用户项目与密钥）。承接 R1267 清单 O45（O01—O44 已完成）。中央轮次 1372（主树含他人已暂存 WIP，故在干净临时工作树 `o45-claim` 调用 round_claim.py next 领取）。本轮 1372 − last_full_safe_all_round(1371) = 1 < 5，无五轮欠账；改动未命中 §5（无启动路径／Tk 控件生命周期／删除语义／层级登记表），收口仍按流程在干净 master 工作树跑一次 `--all --safe`。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：新增 `tests/test_distribution_build.py` 12/12；定向 `-k distribution_build` 12/12；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；均 0 红。
- 欠账：O45 关闭，清单剩 O46—O48；1372 − 1371 = 1 < 5，无五轮欠账；未命中 §5；收口跑一次干净 master 全量（结果见「全量判定」）。

## 目标（R1267 清单 O45）
- 证据：`distribution_manifest.md:5` 明确当前为未来构建器消费的声明，不执行复制；`:40` 定义未来构建约束。仅凭文档不能证明发行包已按清单构建。
- 建议：在新输出目录构建，验证必要资源／解释器／工具、排除私有配置／开发日志／测试数据，生成版本与摘要清单；新 Windows 用户、非管理员、无开发环境验证启动与升级回退。
- 验收：干净环境可完成离线示例链路；默认模型／SKILL 不依赖开发者绝对路径；升级不覆盖用户项目和密钥；删除独立 jingju 包的隔离要求纳入安装验收。

## 实现
- 新增 `程序/scripts/distribution_build.py`（放在 `程序/scripts/`，按清单本身 `程序/scripts/**` 就不进正式副本）：
  - `parse_manifest(path)`：从清单的「必须保留」「必须排除」两张表里取反引号模式，清单是唯一声明来源。
  - `pattern_regex(pattern)`：`**` 跨目录、`*` 不跨、目录以 `/` 结尾＝整棵子树；`plan(root, manifest)` 把源目录分成三桶——清单要保留／要排除／清单没提需要人工决定。
  - `build(destination, root, manifest, allow_undecided=False)`：只把清单内的文件复制到**新的**输出目录，写 `分发清单.json`（版本＋逐文件 sha256＋字节数＋所用模式）；拒绝输出到开发目录内部、拒绝覆盖非空目录、拒绝在还有未决定文件时静默继续。
  - `verify(destination, root, manifest)`：四项校验——输出里零排除项、必需入口齐全、`分发清单.json` 摘要自洽、`程序/skills/00全流程SKILL/jingju-skills` 整包仍在。
  - 全程不删除、不移动、不重命名；源目录一个字节都不改（测试用前后字节比对证明）。
- 精化 `程序/distribution_manifest.md`：补「必须保留」的 `程序/*.py`（生产 Python 模块）、`程序/agent/**`、`程序/说明/**`、`程序/附加工具/**`、`程序/batch_frames_tool/**`、用户说明与图标；补「必须排除」的 `.wt/**`、`.agent-handoff/**`、`.claude/**`、`.codex/**`、`outputs/**`、`程序/outputs|工作流任务|episode|tasks|_supervisor/**`、`程序/logs/**`、`程序/.*.out`、`维护记录/**`、开发／代理文档；并把 `程序/logs/**/*.log` 放宽为整个 `程序/logs/**`。新增「可复验构建器」一节把清单与工具对上。
- 实测（`--plan`，开发目录 `D:\漫剧制作助手`）：keep 1170、excluded 4684、undecided 36；这 36 个（如 `安装信息.json`、`程序/config.json`、`程序/reference/HoLLMwood/**`、`程序/requirements.txt`、`.lnk`）**故意不猜**，由工具报出来等人工决定——这正是清单「先报告命中项再复制」的要求。
- 未新增顶层模块（`scripts/` 不参与分层扫描）／未新增 `skipTest`／未动启动路径与 Tk；`scripts/` 会被 `test_unification_ratchet` 扫到，因此读摘要用 `agent.core.read_json`（先用裸 `json.loads` 被该棘轮判为「未登记新增债务」，已改为产品同一条读取链）。

## 契约变化与同步
- 只新增文件与文档：`程序/scripts/distribution_build.py`（新）、`程序/tests/test_distribution_build.py`（新）、`程序/distribution_manifest.md`（扩表＋加一节）。没改任何运行期模块、配置默认值或界面。
- 清单仍是声明；区别是现在有一条可复跑工具按它产出候选集、构建与校验，声明与执行不再两条平行线。
- 未新增顶层模块、未改 `_layers.py`／`架构统一基数.json`；架构门禁 312/312。

## 测试（`tests/test_distribution_build.py`，12 条）
- 声明解析：真实清单两张表都能读、表头／分隔行不会被当成模式。
- 分桶：保留（`程序/app.py`、jingju `SKILL.md`）、排除（`程序/tests/**`、`程序/private/**`、`*.pyc`）、未决定（`程序/stray/note.txt`）；`.git/**` 既不在保留也不在排除（构建器进都不进）。
- 构建：只复制清单内的文件，源目录前后字节完全一致；写版本与逐文件 sha256（`程序/app.py` 的摘要等于其字节的 sha256）；拒绝输出到源目录内部、拒绝覆盖非空目录、拒绝在未决定未清时继续（`allow_undecided` 才继续）。
- 校验：干净产物 `ok=True`；人为塞入 `程序/tests/leaked.py` → `no_excluded` 命中；删掉 `程序/app.py` → `keep_present` 缺失；删掉 jingju `SKILL.md` → `jingju_package` 失败。
- CLI：`--plan` 只报告、不产生任何输出目录。

## 边界
- 本环境**无法**真造一个「新 Windows 用户／非管理员／无开发环境」的机器：离线示例链路启动、升级回退、非管理员写权限这些验收**未实机验证**；本轮交付的是可复跑的候选集／构建／校验三件套与其测试。
- `--build` 在真实开发目录上会因 36 个未决定文件而**拒绝继续**（这是设计）：要真正出包，先按报告把这 36 个逐项补进清单或显式 `--allow-undecided`。本轮没有在真实目录上执行 `--build`（避免写入大量文件），只用临时合成树验证行为。
- 「升级不覆盖用户项目和密钥」目前靠两条保证：清单排除 `程序/private/**`、`程序/logs/**` 等，以及构建器**只写全新空目录**、绝不回写开发目录；真正的覆盖式升级器不在本轮范围。
- 「删除独立 jingju 包的隔离要求」本轮按**保留整包并校验其存在**处理：`workflow_settings.py`／`integrations.py` 仍引用 jingju，贸然排除会破坏运行期；若后续确需删除该包，应另开授权轮并同步改引用。
- 「默认模型／SKILL 不依赖开发者绝对路径」本轮未做全量扫描断言，只在清单层约定；如需硬门禁应另加扫描（涉及大范围资源，未在本轮铺开）。
- 清单里仍有 36 个 undecided，属正常待决状态，不是欠账。

## 全量判定
- 1372 − last_full_safe_all_round(1371) = 1 < 5，无五轮欠账；改动未命中 §5（无启动路径／Tk 控件生命周期／删除语义／层级登记表；只新增 `scripts/` 工具与文档）。
- 复用检查：`.git/full-safe-receipts.json` 最近绿凭据为 round=1371、tree=de0084a9…（2026-10-12，7 日内），但本轮新增测试与脚本、改了 `distribution_manifest.md`，`HEAD:程序` 内容树不同，不能复用。
- 全量结果：待收尾补记。

## 提交
- 本轮改动：`程序/scripts/distribution_build.py`（新）、`程序/tests/test_distribution_build.py`（新）、`程序/distribution_manifest.md`、`程序/tasks_round/tasks_round_1372_result.md`（新）、`程序/project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog}.md`。
- 内容提交：待收尾补记（只含 `程序/scripts/distribution_build.py`／`程序/tests/test_distribution_build.py`／`程序/distribution_manifest.md`；未含主树他人已暂存的 `程序/idea_chat.py`／`程序/idea_attachments.py`／`程序/配置/SKILL/预设.json`）。
- 提交状态：待收尾补记。
