# R1360：O35 SKILL 引用闭包与依赖类型应明确

类型：功能轮（§3.1；本项为「事实／建议」→ 实现＋回归）。承接 R1267 清单 O35（O01—O34 已完成）。中央轮次 1360（在干净 master 工作树 o07-fullsafe-master 领取）。本轮非五轮全量欠账点，按 O06—O48 验证策略默认只跑定向＋关联＋架构＋默认冒烟。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k skill_ skills workflow_writing stage_prompt_governance request_freeze stage_config codex_skill_sync` 241/241、新增 `tests/test_skill_reference_closure.py` 11/11、关联 `-k writing_api` 全绿；架构门禁 `--layer architecture --all` 312/312（最终树复跑）；默认冒烟 8/8；全 0 红。
- 欠账：O35 关闭，清单剩 O36—O48；1360 − 1356 = 4 < 5，且未命中 §5（未改启动路径／Tk 控件生命周期销毁重建／删除语义／层级登记表），本轮不跑全量；下一欠账点 1361。

## 目标（R1267 清单 O35）
- 证据：`workflow_settings.py:549` 内联只处理直接 Markdown 里的 md／txt 引用、不递归全部嵌套引用；`skill_registry.py:403` 未注册 `dependsOn` 可被视为外部子模块而非一律错误。
- 建议：区别技能依赖、文档引用、可执行工具、可选资源；确需递归时检测环、路径边界、重复、深度和预算，清单显示实际闭包；保留全流程 AIGC 引用，不恢复对可删除 jingju 副本的隐式依赖。
- 验收：直接／嵌套／循环／缺失引用、外部工具依赖均得明确结果；改删非依赖 jingju 包不影响剧本技能；必要引用缺失阻止发送而非静默忽略。

## 实现（skill_registry.py，L3）
- 新增 `REFERENCE_SUFFIXES` 与纯文本解析 `reference_targets(text)`：按出现顺序给出 Markdown 行内链接目标，kind 分 markdown（可内联 md／txt）／other（图片、脚本等资源或工具）／remote（带协议或主机名）／anchor（纯锚点）；只解析文本、不碰文件系统。
- 新增 `classify_dependencies(skill, known)`（在册技能依赖 vs 未在册外部子模块／步骤）与 `dependency_report(skill, known)`（技能依赖／外部依赖／可执行工具 tools）；`external_references` 改为复用同一分类，语义不变。

## 实现（workflow_settings.py，L4）
- `_inline_skill` 拆成 `_skill_blocks`（走直接引用）＋`_inline_skill_report`（返回正文＋引用闭包）＋`_inline_skill`（兼容原接口，只返回正文）；引用判定条件与改动前逐条等值，行为不变。
- 每个直接引用都进闭包：inlined／duplicate／outside／missing／resource／remote／anchor／absolute；引用文件里再出现的链接另记 depth=2 的 nested（不展开）／cycle（回指已加载文件）／outside／missing。仍只加载直接引用、不递归。
- 缺失的直接 md 引用由原来的原始 OSError 改为明确的 ValueError「SKILL 引用缺失，已阻止发送：<路径>」；strict 越界仍是「超出允许目录，已阻止发送」。
- `freeze_skills` 把闭包按技能归属汇总进请求快照 `skill_injection` 的 references 键，随请求一起冻结；桌面与 API 两条入口共用同一份（O15 契约不变）。
- `skill_registry` 改为模块顶部导入（L3→L4 向下，test_layers 通过）。

## 验证
- 新增 `tests/test_skill_reference_closure.py` 11 条：链接分类与归一化（含标题、锚点、目录）／工具与脚本不算文档引用／在册依赖与外部步骤分开／闭包逐项状态（inlined·duplicate·resource·remote·anchor·outside，另 depth2 nested·cycle）／缺失直接引用阻止发送／越界仅 strict 阻止、非 strict 记 outside／嵌套缺失只登记不阻止／freeze 快照按技能归属记录闭包／缺失直接引用时 freeze 阻止发送／删掉非依赖包后剧本技能依赖面不变／真实注册表无技能依赖 jingju 且剧本阶段技能无外部依赖。
- 真实闭包抽样（只读，非新断言）：对真实 73 个注册技能跑一遍非 strict 闭包——depth1 inlined 27、duplicate 18、remote 5、anchor 2、resource 2，没有 depth1 的 outside／missing；depth2 记录 nested 253、cycle 43、remote 20、anchor 5。
- 既有上限：pipeline-continuity／pipeline-delivery／pipeline-storyboard-final／pipeline-video-generation 4 个技能正文＋直接引用超 96,000 字符，仍按原样报「已阻止发送」（阈值归 O36 的模型相关预算，本轮未改）。

## 边界
- 闭包只说明「实际加载／未展开了什么」，不证明引用内容正确；depth2 项只是信息记录、不阻断发送；只有「直接 md 引用缺失」与「strict 越界」才阻断。
- 链接里以盘符开头的绝对路径会被 urlsplit 当成 scheme 归入 remote——这是既有解析口径，本轮未改；新增的 absolute 状态只覆盖 Path 判定为绝对的情形。
- 本轮刻意不动 `idea_chat.py`：该文件主树里带他人已暂存的无关改动（`receive_brief` 里一处重复赋值删除），改它会把他人 WIP 带进本轮提交。闭包已落在请求快照 `skill_injection` 里（即本轮口径的「清单」）；若还要在聊天气泡文案上直接显示，需另开一轮改 `idea_chat.py`，已记后备注。
- 未改分层、未新增顶层模块；未新增 skipTest／裸 json.dump／L2 直写／动态导入；`架构统一基数.json` 未被本轮命中（其 24 项 exemption 均为已豁免、非 pending），架构门禁 312/312 已复验。
- 未实发模型请求、未重启应用、未真实点击界面；本轮未触碰 `desktop.py`。
