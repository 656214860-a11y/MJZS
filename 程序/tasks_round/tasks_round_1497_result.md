# R1497 阶段 01–06 SKILL 兼容审核结果
- 本轮类型：兼容轮（SKILL 内容审核与适配）。
- 校验跑了吗：health 与引用／冻结校验通过；验收补修按用户指定直接 unittest，195 tests / 62.924s / OK，退出码 0。
- 欠账变化：阶段适配及三处合同复测红项已修复，定向测试欠账清零；运行时不按锚点裁剪的既有欠账仍保留，未改业务 Python。
- 结论：内容适配已完成；“只内联被引用章节”硬红线尚未满足，不能宣称全项验收完成。
- 边界：累计修改阶段 01–06 的 10 份 .skill.md、本结果及用户本次授权的两份合同测试；仅在 skillauditA 工作树操作，未改主树、包内文件、业务代码、总控或状态文件，未提交或切分支。

## 审核发现（下列短名均指所属阶段的同名 .skill.md）
| 文件 | 问题／核对结果 | 处理 |
|---|---|---|
| 01/pipeline-script-preparation | 缺新版主／条件引擎；模型画幅仅建议；三条全文件引用与情绪曲线旧锚点 | 已改：项目锁填写、六阶段及条件挂载、全部章节链接、修正锚点 |
| 02/pipeline-script-structure | 缺新版分集规划与项目锁读取 | 已改：六阶段链／分集门只取结构职责，不重新创作或询问 |
| 03/pipeline-storyboard-draft | 缺新版分镜／打戏路由与项目锁读取 | 已改：按段条件挂载，保留初稿及场次交付契约 |
| 04/pipeline-animatic | 缺线稿卡与文字平面图引用、项目锁读取 | 已改：保留 SG-A/B、媒体预演及重试边界，不把加载技能当出图授权 |
| 05/pipeline-assets | 缺素材形态与新版挂载；声称 4View／16 项锁权威不可用 | 已改：M0/M1/M2、默认提示词、出图授权及现有权威链；T1→T3 无依据不冒充核验 |
| 06/pipeline-continuity | 缺跨镜台账挂载；D 锁误作放行权；F7/F19 锚点失配 | 已改：D=splice_mode、状态台账、素材形态与正确章节锚点 |
| 02/script-structured-generation | 默认每集 60–120 秒与项目目标可能冲突 | 已改：读取已确认目标，缺失记缺口 |
| 02/script-dialogue-polish | 全面口语化会破坏海外及特定文体合同 | 已改：按赛道／文体润色，保留角色声线 |
| 03/storyboard-duration-estimate | 将 2–15 秒当统一单镜平台硬限，并钳短真实估时 | 已改：区分单镜与生成段，按模型核对，超限提出拆段不截对白 |
| 05/asset-auto-fill | 原创直接生图、把 ComfyUI 说成搜索，缺授权边界 | 已改：提示词优先、明确出图与分批授权、正确区分检索／生成 |
| 02/script-character-extraction | 未见确定新版冲突；保留来源与稳定编号 | 仅记录，未改 |
| 02/script-worldbuilding | 未见确定新版冲突；旧页面编号不属本轮版本语义修复 | 仅记录，未改 |
| 03/storyboard-camera-language | 保留叙事驱动与镜头多样性；页面编号待另核 | 仅记录，未改 |
| 03/storyboard-pacing-check | 只报告、用户决定修改的职责保留 | 仅记录，未改 |
| 03/storyboard-scene-breakdown | 缺场景事实的澄清不是重新弹问项目锁 | 仅记录，未改 |
| 03/storyboard-shot-generation | 单镜≤8 秒是本地业务限制，未证实被新版废止 | 仅记录，未擅改限制 |
| 05/asset-candidate-wall | 半自动选图确认与锁确认不同，功能保留 | 仅记录，未改 |
| 05/asset-copyright-filter | 来源与许可过滤未见确定新版冲突 | 仅记录，未改 |
| 05/asset-dedupe | 不直接删除、保留来源的既有业务保留 | 仅记录，未改 |
| 05/asset-visual-rank | 仅排序不改图，未见确定新版冲突 | 仅记录，未改 |
| 06/continuity-anchor-freeze | 冻结既有锚点与状态，不重写 | 仅记录，未改 |
| 06/continuity-conflict-adjudicate | 人工裁决参考职责不同于项目锁弹问 | 仅记录，未改 |
| 06/continuity-cross-batch-guard | 按 kind/id/state 比对，无确定新版冲突 | 仅记录，未改 |
| 06/continuity-drift-audit | 比对冻结值／现值，不代改资产 | 仅记录，未改 |
| 06/continuity-triplet-check | 只读判断与回送定稿职责保留 | 仅记录，未改 |
| 01/剧本锻造/SKILL.md:152 | 分镜密度缺失会暂停询问；不能误套到已配置流水线 | 只审不改，适配入口限制跨阶段职责 |
| 01/影视剧本写作技能/SKILL.md:44 | 基础表缺项主动询问、用户无法回答取默认；可能覆盖预填锁 | 只审不改，项目锁优先；独立使用仍须核对 |
| 01/短剧工业化流水线/SKILL.md:48,213 | 明确保留内容确认门，不等同重新询问制作锁 | 只审不改，不删除原确认功能 |
| 01/短剧编剧搭子/SKILL.md:194 | 内容方向确认不是制作锁，未发现确定锁默认冲突 | 只审不改 |
| 01/编剧技能集 | 26 个入口以写作方法为主；广泛方法／文体默认不宜强行统一 | 只审不改；未逐字复核全部参考长文 |

## 改动与体量
- 六份适配文件统一列出任务书全部锁 key：准备阶段填写，后续读取不弹问；选填空值声明包内默认，必填缺失回送配置，不自造默认。
- 仅新增职责所需的带锚点链接；保留原方法、输出路径、调试／人工入口及总控可替换性；四份小技能替换原因已逐项列明。
- 体量使用实际 freeze_skills({stage_skills:[绝对路径]}) 的 frozen_skill_prompt，UTF-8 字节数包含冻结包装及写作质检附加内容。
| 适配文件 | 内联字节 | 字符 |
|---|---:|---:|
| pipeline-script-preparation | 105283 | 50060 |
| pipeline-script-structure | 99762 | 87328 |
| pipeline-storyboard-draft | 161796 | 121132 |
| pipeline-animatic | 51585 | 23836 |
| pipeline-assets | 102936 | 86924 |
| pipeline-continuity | 110923 | 103896 |
- 六份均冻结成功、低于当前 300000 字符上限；上限单位是字符而非字节。未据此宣称组合请求／任意模型上下文都足够。

## 校验结果
- 解释器：D:/漫剧制作助手/运行环境/Python/python.exe；工作目录：程序；均使用 -B。
- git diff --check 通过；本次增量仅两份适配文件、两份合同测试及本结果。
- 指定 master_skill.health(AIGC全流程, default_registry()) 返回 []。
- 25 份阶段文件逐份审查；34 条直接 Markdown 文件引用路径与章节锚点通过（修正后三处失配归零）。
- 外部五包 128 份 Markdown 做风险检索和文件引用检查，284 条 Markdown 文件链接无缺失；不等同完整参考正文／锚点逐项验收。
- 指定 run_selftests.py -k test_master_skill test_skills test_skill_reference_injection test_stage_prompt_governance test_workflow_writing_stages：未完成；启动器仅输出“申请跨树 GUI 令牌（最多等待 900.0 秒）”，约 13 分钟后为遵守总时限中止，非用例失败、未产生通过凭据。

## 未完成／未解决
- workflow_settings.py:749–754 读取并追加引用目标全文，忽略 fragment；条件链接也无条件加载，嵌套引用仅登记。章节链接有效≠API 已按章节注入。属禁止修改的 Python 范围，本轮不能修；需运行时支持后再验收硬红线。
- 新锁 UI／持久化由 R1483 负责，本轮未联调；总控预设缺预演的既有编排不在本轮改动范围。
- 外部包保持只读；其独立调用的交互默认、T1→T3 指定依据及本地单镜≤8 秒与各模型的关系仍需后续专项核对。

## 验收补修（三处合同红项）
- 恢复 pipeline-assets 的“不能把它们伪装为本阶段已验证规则”；核对合同其余片段，pipeline-continuity 恢复“不取得 D 锁的段缝放行权”，新增锁解释置于原门控之外。
- 连贯性保留旧 F7 定位字符串的迁移说明，实际 Markdown 链接仍指向新版有效锚点；不恢复已失效的链接。
- 情绪曲线测试：锚点随新版标题同步，断言逻辑未动。
- 链接合同明确枚举原有 4 个 reference 链接＋新增 5 条子技能链接，以 assertCountEqual 验证完整目标集合及重复项；保留路径归属与文件存在性断言，不只改数字。
- 复测命令（工作目录程序）：`PYTHONPATH=tests D:/漫剧制作助手/运行环境/Python/python.exe -B -m unittest test_master_skill test_skills test_stage_prompt_governance test_workflow_writing_stages architecture.test_skill_reference_injection`。
- 输出尾部：`Ran 195 tests in 62.924s` / `OK`；退出码 0。此前 run_selftests 的 GUI 等待记录为历史，本次直接 unittest 已完成验收复测。
