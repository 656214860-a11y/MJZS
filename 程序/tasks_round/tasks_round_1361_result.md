# R1361：O36 上下文预算从统一字符阈值升级为模型相关预估

类型：功能轮（§3.1；本项为「事实／建议」→ 实现＋回归）。承接 R1267 清单 O36（O01—O35 已完成）。中央轮次 1361（在干净 master 工作树 o07-fullsafe-master 领取）。本轮为五轮欠账点（1361 − 1356 = 5 ≥ 5），收口在干净 master 工作树跑一次 --all --safe；字符上限作为硬保护保留。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 -k writing_api hollmwood_roles codex_tasks qwen_adapter workflow_engines idea_chat script_agent_delivery 221/221、新增 tests/test_context_budget_model.py 14/14、关联 -k workflow skill_reference workflow_settings claude_writing_session idea_semantic_brief script_agent_delivery context_budget_model 174 条（1 红为主树本地未跟踪用户配置所致，见「边界」）；架构门禁 --layer architecture --all 312/312；默认冒烟 8/8；全量见下（本轮欠账点）。
- 欠账：O36 关闭，清单剩 O37—O48；1361 − 1356 = 5 ≥ 5 命中五轮欠账，收口跑一次完整安全全量（结果见下「全量」）。未命中 §5 升级条件（未改启动路径／Tk 控件生命周期／删除语义／层级登记表）。

## 目标（R1267 清单 O36）
- 证据：workflow_context_budget.py:3／37 用 96,000 字符阈值，并有无损重复段去重——不是没有限制。
- 建议：保留硬保护前提下，按模型窗口、输出预留、系统提示、附件、历史和 SKILL 分项估算；区分估算 token 与服务端实报 token；超限说明主要占用与可选拆分方案，不能静默截技能。
- 验收：中／英／代码／图片、大小模型、四角色接力皆保留输出空间；预览与实际发送用同一快照；超限无网络请求。

## 实现（workflow_context_budget.py，L0 —— 统一口径）
- 新增 estimate_tokens（ASCII 约 1/3 字符、非 ASCII 约 2 token 保守高估）、text_fingerprint（快照摘要）、budget_sections（固定分项名 → 正文，未知名报错）、default_safety_margin、dominant_sections、budget_split_options、context_budget_report（分项 token＋输入／输出预留／余量＋projected_tokens＋context_limit＋exceeded＋dominant＋split_options＋fingerprint＋usage_note）、budget_advice、context_budget_error。
- prepare_request_context／ensure_request_context 保持原返回形状（无模型信息时仍是 stage／strategy／characters／limit／remaining，字符上限不变）；新增可选 sections／context_limit／output_reserved／safety_margin／report，给了任一项就附上分项 token 报告；字符超限仍抛「<阶段>请求上下文超过 N 字符…」，模型窗口超限抛「<阶段>请求估算 N token…超过模型上下文 M；已阻止发送且未截断正文或 SKILL」，都带「主要占用＋可选择拆分」。任何超限都不截断。

## 实现（writing_api.py，L3）
- DIRECT_REQUEST_CONTEXT_MAX_CHARS 直接复用 L0 的 REQUEST_CONTEXT_MAX_CHARS（消除两套 96000 常量）。
- 新增 _messages_text(messages) 计算消息体文本；_context_budget_error（字符硬保护）追加大 budget_advice（主要占用＋拆分方案）。
- WritingRequestAdapter._call 改用共享 context_budget_report 重建分项预算：sections（system／tools／history）、dominant、projected_tokens、safety_margin、fingerprint；保留 rules_tokens／messages_tokens／input_tokens／context_limit／output_reserved 兼容键；模型窗口判断改为 report 的 exceeded，拒发在 transport 之前。

## 实现（hollmwood_roles.py，L2）
- _ensure_context_budget 增加 context_limit／output_reserved：字符上限不变；给了模型窗口则按 context_budget_report 的「输入＋输出预留＋余量」判超，报「上下文过长…超过模型上下文…」并附拆分方案，仍不截断。
- _ask 从 adapter.record 的 context_length 读取模型窗口（无记录则只走字符保护），并按最坏情况预留输出额度（内容角色 8192、导演与审核 ≥8192、V4 32768）；超限在调用模型前抛出，adapter.chat 不被调用。

## 实现（desktop.py，L4）
- 阶段任务书三处入口（提取／显式写作／阶段续接）的 prepare_request_context(..., report=True)：预览快照带上分项 token、dominant、fingerprint 与拆分建议；发送用的正文就是同一份 prepare_request_context 返回的字符串（预览与发送同一快照）。

## 契约变化与同步
- prepare_request_context 返回体在「给了分项／模型窗口／report」时追加键（estimated／sections／dominant／input_tokens／output_reserved／safety_margin／projected_tokens／context_limit／token_remaining／char_limit／exceeded／split_options／usage_note／char_note／fingerprint）；limit／remaining 仍是字符口径（向后兼容）。tests/test_workflow.py:975 的精确 dict 断言（无模型信息分支）未变、仍通过。
- tests/architecture/test_unification_ratchet.py 第四项以「文件:行号」记身份，本轮 writing_api.py 插入 22 行使既有豁免项 writing_api.py:490（裸 json.loads，非文件读取）位移到 :512；同步更新 程序/维护记录/架构统一基数.json 该豁免项的 point（未新增裸 json.loads，未改扫描集合）。

## 验证
- 新增 tests/test_context_budget_model.py 14 条：中／英／代码／图片负载的 token 预估与单调性；分项报告（sections／dominant／projected ＝ input＋预留＋余量／大小模型 exceeded）；budget_sections 未知名报错；report=True 的 fingerprint 与同快照一致、未超限不改写正文；模型窗口超限抛错含「超过模型上下文／未截断／主要占用」；WritingRequestAdapter 小模型拒发（raw.chat 未被调用，sections／dominant／output_reserved 齐）与大模型保留余量；hollmwood_roles._ensure_context_budget 大小窗口与四角色（ROLE_ORDER）皆留输出空间；_ask 读取 record 的 context_length 后在调用前拒发。
- 定向 -k writing_api hollmwood_roles codex_tasks qwen_adapter workflow_engines idea_chat script_agent_delivery 221/221、0 红。
- 关联 -k workflow skill_reference workflow_settings claude_writing_session idea_semantic_brief script_agent_delivery context_budget_model 174 条 1 红：主树本地未跟踪 程序/配置/宠物/配置.json 把 claude-desktop 标签覆盖成「Claude Desktop」，令 test_stage_model_selects_the_matching_desktop_agent 断言失败；同一 HEAD 的干净工作树 test_workflow 16/16 绿（既有环境项，与本轮改动无关，risks/work-log 早有同类记录）。
- 架构门禁 --layer architecture --all 312/312；默认冒烟 8/8。

## 边界
- 分项估算按字符启发式（非真实分词器），只用于提前拦截；服务端实报 request_usage 与估算分开（usage_note 已标注），不把估算当实报。
- 图片按发送文本（引用文本／base64 文本）计入 attachments 估算；本轮不解析图片实际像素或视觉 token。
- 模型窗口只在能拿到 record 的 context_length 时启用；拿不到就只走字符硬保护（不假装知道窗口）。
- 字符硬保护（96,000）与无损去重 compact_repeated_context 行为保持不变；未新增 skipTest／裸 json.loads／L2 直写／动态导入；未新增顶层模块或分层登记项，未命中 §5。
- 环境项（非本轮改动）：主树 程序/配置/宠物/配置.json 是未跟踪的本地用户配置，把 claude-desktop 标签覆盖成「Claude Desktop」，使 test_workflow／test_model_pool 的桌面模型用例在主树红；干净工作树绿。

## 全量（收口补记）
- 第 1 次：干净 master 工作树 o07-fullsafe-master（HEAD f95c889，工作树干净）run_selftests.py --all --safe，ALL TESTS PASSED、0 红，404.452 秒；绿凭据写入 .git/full-safe-receipts.json（round=1361、tree=3e20f7c4b6a743ce8718878c15163c8cb1a8afec、last_full_safe_all_round=1361）。
- 用例数：上轮绿全量 1356 为 4749 条；本轮仅新增 tests/test_context_budget_model.py 14 条、未改动既有用例数，全量共 4763 条（收口运行仅保留末段输出，此处按「上轮基线＋本轮新增」列示）。
- 与已知抖动项区分：本轮未出现 test_desktop_startup_perf／test_perf_baseline 阈值失败，无需定向复测。
