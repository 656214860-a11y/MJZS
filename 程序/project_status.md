# 项目状态（可独立接续）

R1635：验证/基线轮＋自检器改动（阶段4 T8 剩余收口）。`run_selftests.py` 的工作单元结果加第 8 位“实际跳过清单”，汇总打印 `实际跳过 N 条用例`＋最多 40 条明细（`SKIP_REPORT_LIMIT`）；`tests/test_selftests.py` 加 3 条用例钉住（从结果取跳过、第 8 位必存在、汇总必须打印）。**实测口径更正**：本机实际只跳过 1 条（`test_core.ValidateProfileTests.test_stage_profile_wrong_preset_rejected`／需实机复验 bundled skill），此前“约 3 个”是从登记位推断的；4 个平台可用性条件现场逐条实测均满足，条件类站点实跑 219 条用例只此 1 条跳过。`说明/联调测试出口基线.md` §3 按实测重写、§6 T8 转完成、§7 检查单补一行。注意：本轮动了 `run_selftests.py`（自检器，非产品模块）——按 §5 计为一个源码轮（全量欠账 1／8），不命中风险路径，未强制跑全量；沙箱内无法派生工作进程，全量须在沙箱外跑。R1633：验证/基线轮（阶段4 T6 的本地两条）。新增 `tests/test_perf_batch_queue.py`（3 用例 5.5 秒，`test_perf` 前缀自动进串行性能池）：①批量首帧规划成本 200 镜 0.48 ms／镜、50 镜 0.52 ms／镜（上限 5 ms，验每镜成本不随批量上升）；②持久后台队列每项入队约 132 ms、领取约 123 ms（上限 400 ms），并验满队列拒绝与“优先级降序、同级先到先领”。`tests/performance_contract.py` 加两条阈值与口径注释。**探到范围外瓶颈**：队列成本被 `agent.publication.transaction` 的目录扫描支配（本机单独实测约 100 ms／次，而 `read`／`save` 仅 1–5 ms）——生产队列上限 10，最坏一次入队 1.3 秒；本轮只登记、不改锁语义。供应商延迟与弱网按评估口径只记外因，不进门槛；并发提交吞吐与“队列压力下 UI 响应”（需实机 Tk）未覆盖。只改测试与文档，不算源码轮。R1632：验证/基线轮（阶段4 T1／T7）。新增 `tests/test_recovery_delivery_e2e.py`：把手工离线全链基线脚本收编为 4 条自动用例，共享一次真实全链运行（10 镜、8 类故障恢复、改稿交付第 2 版、真实编码与 assemble、规格与质检），实测 32.5 秒、退化预算 150 秒；手工脚本仍是权威源。新增 `tests/test_soak_light.py`：12 轮 × 3 镜真实落盘生命周期 soak 进全量安全层（约 18 秒），逐轮 1.29–1.48 秒、稳态内存增幅 21 KB／轮（上限 10 秒／128 KB）；`SOAK_MINUTES` 可拉长，3 分钟档实测 105 轮、18.1 KB 每轮。新增 `MISSING_FFMPEG` 跳过原因与 2 条台账（227→229）。本轮探到两个真实约束：①制作秒数额度在约第 50 轮连续重做时拦截提交（长档须显式放大 budget，每墙上秒约耗 4.3 制作秒）——T6 口径必须带额度模型；②轮数由墙上时间决定时“最后一批采用”只能在循环后认。口径更正两条评估前提：全量时长已有 `elapsed_history` 最近 5 次＋中位数（仅打印、无阈值），`test_desktop_startup_perf` 的串行隔离策略既有且有守护用例。只改测试与文档，不算源码轮；未跑全量，最近真实全量仍为 R1624。R1631：修复轮＋测试基线（阶段4 T5／T11）。新增 `tests/test_outbound_request_contract.py`（12 用例）钉住四个内置适配器对同一逻辑请求的请求形状（认证头、system 落点、token 上限与 temperature、OpenAI 兼容三者请求体逐字段一致、端点＝base_url＋协议路径、发出的请求即 payload/headers 产物）与出站素材白名单（只送声明素材、base64 逐字节等于源文件、`.env` 诱饵字节不入请求体、非图片与 >20MB 被拒、参考模式类型顺序固定）。**修两个真实缺陷**：①`DeepSeekAdapter.headers()` 忽略注入 key（`credential()`／`available()` 认、出站头不认，导致“界面说能用”与“实际用哪把钥匙”分叉；生产只在 `model_router.py:468` 不传 key，属潜在缺陷）——改为注入 key 优先、其余保持 pet_llm 三级来源；②`payload()` 在 `wire_api='messages'` 分支丢掉 `temperature`——显式给出时补进请求体。同类扫描：全仓仅 base 与 DeepSeek 两处 headers 覆盖，无同类未修。定向 12/12、相关 208 项、冒烟 8/8、架构 356/356 本轮实测。
R1630：验证/基线轮（阶段4 T2／T3）。阶段门禁端到端探针 `维护记录/基准脚本/探针_阶段门禁端到端.py` 改为**驱动 `stage_parallel.GATES`**（此前硬编码只跑 SG-01..05，漏 SG-A／SG-B），并补 SG-A／SG-B 的真实证据（已采用分镜＋`ui_settings`；真实 `animatic_manifest.json` 含源版本摘要与三项人工确认）；新增 `gates`／`chain`／`missing_gates`，断言门禁链首尾相接（storyboard→…→video）且无漏跑。`tests/test_stage_gate_e2e_probe.py` 记录两类门禁语义（SG-A／SG-B 为"必须有上游成果"入口闸：entry False／started True；SG-01..05 为"上游没做就别拦"：entry True／started False），新增运行期链路连续性用例。定向 5/5、默认冒烟 8/8、架构 356/356 本轮实测。未改产品代码，未给末尾段（视频之后）新增门禁。
R1629：验证/基线轮（阶段4 T4／T10）。新增 `tests/test_model_output_contract.py`（23 用例、四组）：①模型标题进入用户可见文件名时的注入对抗（路径分隔符／`../`／Windows 非法字符／控制字符与 ANSI 转义／超长截 80／纯符号回退，且净化后仍被 `stage_file_info` 认作受控创作文件）；②`write_structured_script` 的三条拒绝路径与「目标路径不由正文决定」；③清单编号同份重复／跨份撞号／缺失必须报出，`normalize` 补缺不改入参；④严格读与宽松读在坏 JSON／缺文件上的差别。定向 23/23、默认冒烟 8/8、架构门禁 356/356 本轮实测。更正一条自设错误前提：`\x1b[31m` 净化后只剩字面 `[31m`，不是注入。既有实现本已正确，本轮是把行为固化为回归基线，未改生产代码。
R1627：结构治理轮·执行（阶段4 联调/测试清单的登记类 T8／T9／T12）。新增 `说明/联调测试出口基线.md`：§1 出口标准四条实测（功能通过率满足＝全量 5407 条 0 红、AI 可用率未评估、P95 未建立、无阻断 Bug 有条件）；§2 US01–US07 需求→用例三态映射（7/7 有自动化主用例，8 项未决项指向实际使用待验收清单）；§3 skip 口径（227 条是守卫式登记位，本机 tkinter 可用）；§4 缺陷台账 3 条 A 级挂账→守护用例索引（均“实现已守护、缺实机证据”）；§5 越权/支付漏洞记 N/A，并更正“无网络监听”的错误前提——`previs_monitor.py:130` 起本地回环只读预览页（127.0.0.1、随机端口、只答 GET、忽略请求路径、无鉴权），登记为 T13 待裁决。本轮只改 .md，不算源码轮。
R1626：结构治理轮·执行（R1610 J 第三批 Q12，清单收口轮）。`runbook.md` 补 §8 辅助依赖清单（FFmpeg／ComfyUI／Blender／Claude Desktop／Codex／Claude Code／Qwen Code 与模型密钥；权威源是 environment_check.py）与 §9 解释器版本策略（随附 3.15.0a2 + 有意裁剪的 58 个标准库模块 PRUNED 清单 + 两道闭包闸；迁移计划六步含「重新决定裁剪清单」）。前提核对纠正两处字面误读：缺模块＝裁剪不是 alpha 缺陷；辅助依赖不是 Python 包（运行时零第三方）。本轮只改 .md，不算源码轮。至此 R1610 J 的 Q1–Q12 全部落地。

R1625：结构治理轮·执行（R1610 J 第三批 Q11）。新增三份文档并接入索引：`data_model.md`（版本化产物＋队列台账＋任务中心投影＋费用 Token 的字段字典）、`task_states.md`（三层状态边界、队列状态机与禁止转移、镜头生命周期词表、run_id/attempt_id/provider_task_id/原因码 的尝试链、8 类重试判定）、`runbook.md`（环境／启动／自检命令与代价／全量欠账与凭据／升级回滚／常见故障）。三份都写明「文档是投影、以代码为准」；有意的取舍：不加文档一致性门禁（会在测试里再造一份字段表），改为点名权威源＋给改动检查单。本轮只改 .md，不算源码轮，欠账计数不变。R1624（13dea0a）的后台安全全量 02:01:23 绿灯结束（502 秒、0 红、凭据 tree bde64b00、round 1624），R1620–R1623 的全量欠账已清；全量最后一次真实通过更新为 R1624。

R1624：结构治理轮·执行（R1610 J 第一批 Q10）。出口脚本：复用 scripts/local_ci.py 新增 exit 模式＝默认冒烟 → 静态门禁（8 个 unittest 目标，含 tests.test_static_names）→ 架构门禁，非 0 即失败、约 4 分钟；根目录 本地CI.cmd 加一行用法说明。顺带修两处拆分回归：pet_cloud_timing._fade_in 用了没定义的 SHAPE_ROUND（R1621 把方法迁出时名字没跟过去，Cloud.show 必经此路，云朵／对话框／贴纸全部打不开；四个形状名改由 pet_cloud_shape.py 定义并原样转出，公开名不变）；tests/test_skill_notes.py 的 markdown_document 补丁随 R1620 迁移改打在定义处 skill_panel_support。验证：test_pet_ui 598 项 OK、定向门禁 58 项 OK。欠账：本轮改源码 +1，d8d0fc5 的后台全量红（退出码 1、未写绿凭据），提交后 post-commit 自动补跑。

R1623：结构治理轮·执行（R1610 J 第三批 Q9 后半）。运行期诊断统一：把 desktop.py 与 native_assets.py 的 3 处运行期 print 改走 logging（app.log）；新增门禁 tests/architecture/test_print_ratchet.py 冻结生产模块 print（只许下降，11 个控制台入口登记豁免）。并更正 R1610「606 处 print」的错误前提——按生产模块口径实际只有 36 处、其中仅 3 处是运行期诊断。见 [R1623](tasks_round/tasks_round_1623_result.md)。

R1622：结构治理轮·执行（R1610 J 第三批 Q9 第 5 批）。拆分 desktop.py 2259→1859 行：拆出 L4 模块 desktop_page_registry.py（页登记表）、desktop_tk_gc.py（Tk 回收护栏＋模块级状态）、desktop_automation_tick.py（AutomationTickMixin，16 方法）；Desktop 再加一个 Mixin，10 个模块级名按原名转发（110 方法零丢失、_PENDING_TK_GC／PAGE 同一对象），上限降到 1950。至此 Q9「拆 5 个大文件」完成。见 [R1622](tasks_round/tasks_round_1622_result.md)。

R1621：结构治理轮·执行（R1610 J 第三批 Q9 第 4 批）。拆分 pet_cloud.py 2137→1802 行：按既有 Mixin 模式拆出 L4 模块 pet_cloud_timing.py（248 行，16 方法＋11 常量）与 pet_cloud_hint.py（115 行，8 方法＋4 常量），Cloud 组合两个 Mixin，15 个常量按原名转发（118 方法零丢失），上限降到 1900。见 [R1621](tasks_round/tasks_round_1621_result.md)。

R1620：结构治理轮·执行（R1610 J 第三批 Q9 第 3 批）。拆分 skill_panel.py 1886→1475 行：新增 L4 模块 skill_panel_support.py（486 行，39 函数＋4 常量），原模块按原名转发 43 个名（旧顶层名零缺失），并入行数棘轮删除线与覆盖率基线。见 [R1620](tasks_round/tasks_round_1620_result.md)。

R1619：结构治理轮·执行（R1610 J 第三批 Q9 第 2 批）。拆分 stage_execution_service.py 1677→1405 行：新增 L3 模块 stage_publication.py、stage_write_preparation_service.py、stage_download_inbox_service.py；原模块按原名转发 15 个顶层名（公开面 163 名零缺失）。并修复 R1608 遗留回归：4 个网关模块把 save_bytes 误改为 save_file 导致 NameError。见 [R1619](tasks_round/tasks_round_1619_result.md)。

R1618：结构治理轮·执行（R1610 J 第三批 Q9 第 1 批）。拆分 script_contract.py 1598→1113 行：新增 L0 模块 script_manifest_schema.py（manifest 编号/物理特征/校验/Schema/完整性）与 script_output_spec.py（交付与预演规格）；原模块按原名转发 58 个顶层名（公开面 159 个名零缺失），层级登记、架构文档与行数棘轮同步。见 [R1618](tasks_round/tasks_round_1618_result.md)。

R1617：结构治理轮·执行（R1610 J 第二批 Q8）。新增 tests/test_state_transition_tables.py：后台队列（queued/claimed/completed/expired/cancelled，含 3 条禁止转移）、视频删除前置门（在途状态全枚举）、重试状态机（8 类目 × 4 次数档）三张全转移表；并经变异验证（4 种变异全红，抓到「状态空间取自被测常量」这一自身缺口）。见 [R1617](tasks_round/tasks_round_1617_result.md)。

R1616：结构治理轮·执行（R1610 J 第三批 Q7）。新增 scripts/coverage_report.py（sys.settrace 定向行覆盖，零第三方依赖；随附 3.15.0a2 未随附标准库 trace）＋基线 维护记录/覆盖率基线.json（8 个核心目标实测 46/270 模块）＋门禁 tests/architecture/test_coverage_baseline.py（结构自洽／口径一致／核心路径下限／子进程真跑工具）；不设全局阈值，不重跑测量，诚实边界见 [R1616](tasks_round/tasks_round_1616_result.md)。

R1615：结构治理轮·执行（R1610 J 第二批 Q6）。新增 tests/test_money_invariants.py；并修复 price() 总额与分项取整不一致的真实缺陷（amount≠settled+reserved，差 1e-4）。见 [R1615](tasks_round/tasks_round_1615_result.md)。

R1614：结构治理轮·执行（R1610 J 第二批 Q5）。新增 tests/test_adapter_failure_conformance.py，把失败分类表钉在 4 个内置文本适配器上。见 [R1614](tasks_round/tasks_round_1614_result.md)。

R1613：结构治理轮·执行（R1610 J 第二批 Q4）。新增 L0 artifact_schema（产物版本登记＋只读校验＋迁移入口）、清单文档与单测；更正 R1610 对产物版本现状的错误表述。见 [R1613](tasks_round/tasks_round_1613_result.md)。

R1612：结构治理轮·执行（R1610 J 第二批 Q2）。新增 tests/architecture/test_function_size_ratchet.py（登记 21 个 ≥150 行函数，只许下降）；未物理拆解最长函数，义务写入棘轮。见 [R1612](tasks_round/tasks_round_1612_result.md)。

R1611：结构治理轮·执行（R1610 J 第一批 Q1+Q3）。新增 tests/architecture/test_static_hygiene.py（无效转义序列/星号导入/生产 eval-exec）并修本仓 1 处无效转义；外部技能包子模块同类缺陷还原，不属本仓。架构 348、冒烟 0 失败。见 [R1611](tasks_round/tasks_round_1611_result.md)。

R1610：结构治理轮·只读诊断。按规范/静态检查、接口契约、单元测试、CR、文档、出口标准六维度评估编码实现阶段，输出待确认优化清单 Q1–Q12（未改代码、未跑测试），见 [R1610](tasks_round/tasks_round_1610_result.md)。

2026-10-16：R1596优化已完成8/12（O1/O2/O7/O3/O4/O5/O6/O11）。R1605/e59e513正式全量5346项通过。R1606/O8剧本页面服务注入已合入主干a013e75（架构345项、冒烟8项通过）。R1607/O9补齐云图溯源字段并出覆盖矩阵，R1608/O10改大媒体为按块复制发布。R1609/O12补齐不付费场景矩阵与可执行估算口径，R1596 清单 12 项至此全部完成。接续以.agent-handoff/snapshot.md、backlog.md和validation.md为准。

旧文首检查点已保留至.agent-handoff/history/r1606-handoff-before/project_status.md。R1606已合入主干，主干最新报告为1606，轮次头已改1607。

更新：2026-10-17｜当前轮次：1643（R1642：发布/灰度阶段只读评估（待确认）：新增 .agent-handoff/stage-eval-stage5.md（U1–U13：无托管流水线载体·构建自检不在出口·发布物未绑提交哈希｜无灰度通道·无发布检查单·无观察判据｜无发布标签与版本↔提交映射·回滚未演练·维护约定引用的 install_release.py 全盘不存在｜无指标聚合与阈值告警；N/A＝GPU 利用率·用户留存·数据库迁移）。默认冒烟 8/8，未跑架构门禁与全量（只读诊断轮，不改源码）；R1641：验证/基线轮（阶段4 清单 T1–T13 收口复核与门禁补齐）。§6 十三行状态均为完成（T13 于 R1640 裁决接受＋暴露面守护用例）；补跑 R1639 漏掉的每轮默认冒烟 8/8，并把 R1638 轮内实际跑过的冒烟与架构门禁补记进只读报告；当前树阶段4 守护用例 107 项在 8684c7b 全绿（含真实全链 E2E 32.8 秒）。仍待真机：T6 队列压力下的 UI 响应；未跑全量（欠账 2／8）；R1640：验证/基线轮（阶段4 T13 收口：裁决＝接受并加守护用例）。新增 tests/test_previs_monitor_exposure.py（3 用例）钉住接受前提——只绑回环、只答 GET、忽略请求路径且不按路径读文件（对编码与非编码的 ../ 穿越路径与 /previs_monitor.py 均回固定页、不含哨兵文件内容）；§5 登记裁决与理由、§6 T13 转完成、文首同步。有意不加鉴权：加令牌不减少真实暴露（能连回环的主体本就能读同一用户项目文件），却会动到需真机目视的 GUI 路径。阶段4 清单 T1–T13 至此均有当前树证据；未跑全量；R1639：验证/基线轮（阶段4 T6 收尾：登记编码队列吞吐与积压不另立用例的口径依据）。本地编码成本＝队列机制（已由 R1633／R1638 测）＋ ffmpeg 单镜编码耗时，ffmpeg 是用户自装的外部工具（本机 D:/Tools/ffmpeg/bin/ffmpeg.exe，缺则按 MISSING_FFMPEG 跳过），与供应商延迟同属外因，只登记不进门槛；§6 T6 行与文首同步。T6 未测项只剩队列压力下的 UI 响应（需实机 Tk）。阶段4 清单仅剩 T13 待用户裁决；未跑全量；R1638：验证/基线轮（阶段4 T6 余量：并发提交吞吐与队列 N 并发排队时延）。新增 tests/test_perf_concurrent_submit.py（4 生产者并发入队＋2 消费者并发领取 16 项，实测 2.07 项／秒、7.74 秒，断言不丢不重、不留 claimed）＋tests/performance_contract.py 加 CONCURRENT_SUBMIT_ITEMS_PER_SECOND＝1.0；§1／§2／§6 同步。结论：入队与领取都在 agent.publication 的进程级 RLock 内串行，并发不提高吞吐、只排队（上限约 1／255 ms），故 T6 的并发提交条目是既有设计上限而非可优化项，真正优化点是事务扫描范围（约 100 ms／次，范围外只登记）；T6 仅剩「队列压力下 UI 响应」需实机 Tk。阶段4 清单仅剩 T13 待用户裁决；未跑全量；R1636：验证/基线轮（阶段4 T12／T13 网络面清单补全与 §4 复核）。只读核验全仓监听面共 2 处，补登随附 skill 资产内的第二个回环监听面（skills/09白模预演SKILL/create-blender-story-video/assets/render-monitor-dashboard/server.py:849：--host 只接受 127.0.0.1／localhost、仅固定只读端点、POST 与 HEAD 返回 405、无任意路径文件服务、带安全响应头，产品代码不启动它），归入供应链面；复核 §4 的三条 A 级挂账索引与源台账一致，未改；只动 说明/联调测试出口基线.md，不改代码与测试。阶段4 清单仅剩 T13（回环预览页无鉴权）待用户裁决；未跑全量；R1635 实际跳过清单机制与实测收口（T8）；R1633 批量规划与持久队列本地口径（T6）；R1632 全链 E2E 自动收编与轻量 soak（T1/T7）；R1631 适配器请求形状对照与出站素材白名单＋两个映射缺陷修复（T5/T11）；R1630 门禁探针覆盖全部 7 条门禁＋运行期链路断言（T2/T3）；R1629 模型产出结构不变量与注入对抗用例（T4/T10）；R1627 阶段4 联调/测试出口基线：需求→用例三态映射、缺陷台账守护索引、N/A 声明与回环预览页 T13（T8/T9/T12）；R1626 辅助依赖清单与解释器迁移策略（Q12）；R1625 文档三件：data_model／task_states／runbook（Q11）；R1624 出口脚本 exit（静态＋架构＋冒烟），并修两处拆分回归：pet_cloud 形状名未定义、skill_panel 补丁点迁移（Q10）；R1623 诊断统一到 app_logging（Q9）；R1622 拆分 desktop（Q9-5）；R1621 拆分 pet_cloud（Q9-4）；R1620 拆分 skill_panel（Q9-3）；R1619 拆分 stage_execution_service 并修 save_bytes 回归（Q9-2）；R1618 拆分 script_contract（Q9-1）；R1617 状态机全转移表（Q8）；R1616 覆盖率基线（Q7）；R1615 金额不变量与总额一致性修复（Q6）；R1614 适配器失败分类一致性（Q5）；R1613 持久化产物版本契约（Q4）；R1612 函数行数棘轮（Q2）；R1611 静态卫生门禁与无效转义修复（Q1+Q3）；R1610 编码实现阶段质量只读评估（待确认）；R1609 不付费场景与成本估算（O12）；R1608 大媒体发布内存（O10）；R1607 云图生成溯源字段（O9）；R1606 剧本页面服务注入（O8）；R1506 拆分 pet_ui；R1505 desktop 拆分步骤 3 成批迁出；R1504 desktop 拆分步骤 3 第 2 页；R1499 desktop 拆分步骤 3 第 1 页；R1490 desktop 拆分步骤 2；R1488 后台全量嵌套仓库对齐，状态由对应车道补记；R1489 SKILL 包文案规则放行；R1482 日志让路用例口径；R1480 拆分 desktop 步骤 1；R1479 页头布局；R1478 全量频率治理；R1477 失败任务手动重试；R1475 失败原因；R1474 状态页文首区迁出；R1472 测试连接接入排队；R1471 文档更正；R1470 任务排队与截图基线；R1469 分发清单恢复 outputs 排除；R1468 根目录整理；R1467 任务历史与根目录登记；R1466 分发自检二次修复；R1465 分发自检修复；R1464 运行状况面板与状态页归档；R1463 开发者统一入口；R1462 分发清单补全与自检；R1461 行数棘轮、分支清理、计时埋点；R1460 状态页历史迁出与更新记录；R1459 静默吞异常留痕；R1458 标准库门禁与启动日志；R1457 统一日志与崩溃钩子；R1455 文档收口；R1453 三虎弹窗；R1451 切页性能与侧栏；R1450 删除按钮；R1447 切页性能与重复提示修复；R1446 改名与布局；R1443 全量风险触发代码强制、钩子自愈、后台失败提示；R1442 清理 HOLLMWOOD 遗留；R1441 HOLLMWOOD 并入剧本 SKILL 并移除；R1440 全量欠账改源码轮次计数、阈值 8、后台自动补跑；R1439 侧栏切换项目加确认与运行中拦截；R1437 清掉其余 8 条全量红；R1436 测试替身补 sync_master_skill；R1435 字符上限提至 30 万；R1434 见另一任务提交；R1433 统筹改总控；R1432 新增 SKILL 稳定导入；R1431 见另一任务提交；R1430 视频／配音逐笔台账；R1429 项目用量总览；R1428 镜头版本锁定回退；R1427 成片导出 EDL/FCPXML；R1426 环境自检；R1425 CLI 失败提示与图形程序误配拦截；R1424 自动搜寻识别商店版 Claude Desktop；R1423 修复模型管理本机 Claude 的 Provider 显示与表单；R1422 已完成交接收尾；R1420 缓存修复安全全量 5024 项、0 失败，R1419 已由 R1421 合入，合并后定向验证见对应报告。历史缺失报告不补造验收。）

历史验收记录：更新：2026-10-10｜当前轮次：1223（R1222 文档收尾，R1219 修复阶段旧路径阻断，实现 7faa7ae。干净 master f40beb4 安全全量 --jobs 4：4304/4304、347.409 秒，含架构 311/311；前两次并发保存失败及定向复验详见 tasks_round/tasks_round_1219_result.md。正式全量 R1219，未重启或实发 API。）
阅读索引：[当前待办](#已知阻塞与待办)｜[验证基线](#验证基线)｜[优化队列](维护记录/优化待办队列.md)｜[R504 历史快照](#r504-阻塞归类与整改路线)。带 R 编号的历史条目仅证明对应轮次；当前范围、未验收条件与后续顺序以当前待办及队列为准。

R1440 以前的 52 条轮次摘要（文首区）已原文迁至 [状态历史归档](维护记录/状态历史归档.md)；对应轮次的凭据以 `tasks_round/` 结果文件与 git 历史为准。

## 新对话接续协议

R1036 后续文档收尾（用户明确授权）：归档原诊断报告与优化待办队列，中央计数器同步既有报告号 1036，登记 J1；不改原诊断报告、不补造当时测试。收尾当次默认冒烟 8/8、架构门禁 301/301（100.552 秒），与既有 301 基线一致；仅文档及 Git 元数据，无生产逻辑改动，未重复全量。提交回执以 Git 的 `R1036: 归档优化诊断与待办队列` 为准。

1. 按程序目录 `AGENTS.md` §0 读取接续资料；本文按轮次记载的旧事实不等于当前树已验收。
2. 架构、目录、SKILL、模型和数据边界参见同目录 `architecture.md` 与 `PROJECT_MAP.md`；唯一权威索引见 `AGENTS.md` §2.2。
3. 每轮范围、验证和收尾分别按 `AGENTS.md` §2、§5、§7；本文不另设测试周期或只读诊断例外。
4. 密钥、用户数据及重启提示边界见 `AGENTS.md` §2.1。
5. 主界面的“齿轮 → 设置”入口必须保留；界面或服务拆分不得删除、隐藏或使该路径不可达。
6. 架构统一待办见 `维护记录/架构统一路线图_v2.md`，第 3、4 项基数见 `维护记录/架构统一基数.json`；UI 统一待办见 `维护记录/UI统一入口路线图_v1.md`。

- 收尾凭据缺口声明（用户 2026-10-04 裁定）：R963–R995（主树干）与 R996–R1016（codex/architecture-contracts、
  codex/architecture-reconcile-996 分支段）区间存在缺 `tasks_round_N_result.md` 的轮次，
  其中主树干 900 号之后缺号 26 个。经用户决定不逐轮补写历史结果文件（补写不构成凭据），
  该区间的改动内容一律以 git 提交历史为唯一事实来源，不得引用为已验收基线。
  自 R1017 起由 pre-commit 硬拦缺结果文件提交，编号由 round_claim.py 中央分配器唯一发放。

## 当前能力

本节保留历轮能力记录，不是当前待办队列；旧记录中的“下一轮”“待迁移”只指当时安排，不应直接执行。现状与剩余边界见[当前待办](#已知阻塞与待办)，逐项验收来源见[优化队列](维护记录/优化待办队列.md)。R1000 以前的条目已迁出（见下一段）。

本节「R1000 以前」的 494 条逐轮能力记录已原文迁至 [状态历史归档](维护记录/状态历史归档.md)；R1000 及以后与跨轮现状条目保留在此。

- 产品：Windows Tkinter「漫剧制作助手」，零第三方依赖，12 阶段由 `skill_orchestrator` 执行；“剧本结构”位于剧本准备与初步分镜之间。剧本输入与结构化输出由 `script_contract`、`stage_path_service` 解析；旧 `writing/` 仅作历史读取兼容。当前可选 SKILL 以 `skill_registry` 懒加载登记结果为准。
- 三虎：带前缀播报和 UTF-8 日志、检查点/恢复、12 阶段 YAML 模板、手动/全自动模式、暂停/阻塞控制、资产跨重启续跑；`auto_*_var` 的写入权只属于三虎，页面不显示自动制作勾选框。
- 剧本准备：模型/用户气泡左右分列，模型名、折叠、思考提示、原位编辑、拖选复制、右键整条复制/删除及恢复最近删除、输入草稿持久化、输入框自适应和文件表刷新均已实现。每个模型保留独立聊天页并使用稳定浅色主题；下方无标题文件表按项目设定、项目大纲、项目剧本分为三列独立紧凑排列，单元格仅显示文件名，不列出用户简报、聊天记录或无关文件。
- 模型：模型管理是唯一池；阶段按所选厂商/协议/模型/密钥/SKILL 直连 API，不回退到 Qwen。GPT API 与 ChatGPT Desktop 归类为 GPT；自定义 Provider 与模型保存后刷新阶段配置。
- Claude：Messages 调用只显示可见正文；thinking/signature 不进入聊天框。剧本阶段仅可读 `writing/`、`data/项目接续.json`，仅可写 `writing/`，不访问资产清单。
- HOLLMWOOD：LLM 请求在既有后台线程运行；角色进度通过 `queue.Queue` 交给 Tk 主线程每 100ms 消化，并写入三虎进度日志。中断会阻止当前请求进入后续角色及 `script_raw.md` 落盘。
- 文件/删除：生成剧本会刷新文件表；允许删除最后一份剧本、无 `episode.json` 的残留项目链接及其项目目录。
- Python：测试统一使用 `D:\漫剧制作助手\运行环境\Python\python.exe`；Round 136 已实测全局 Python 3.14 与项目内置解释器均可初始化 Tcl/Tk。
## 检查点

以下为 2026-09-24 的历史格式示例，不是当前检查点；`02_assets` 是旧标识，现行阶段 ID 以 `pet_bus.STAGES` 为准。

```json
{
  "stage": "02_assets",
  "step": 3,
  "step_name": "生成缺失的正典板",
  "completed_steps": [1, 2],
  "interrupted_at": "2026-09-24 10:40"
}
```

## 验证基线

R1507 核验：R1506 正式记录 tree=`1844649ecd07befa6f6fabd2c0e12e486cb40657`，与开工 `HEAD:程序` 一致，650.358 秒，执行器可复用。凭据未保存当次总数，不追认数字；本轮文档变更后的树不冒称重新全量。详见 R1507 报告。

R1418 首轮历史记录：缓存边界 8/8（13.862 秒）、受影响 44/44（18.6 秒）、默认冒烟 8/8；架构/文档定向 28/29（10.419 秒），唯一失败为当时 R1418 完整安全全量欠账，现已由 R1420 闭环。当时最近真实全量为 R1403：5006/5006、557.302 秒，tree=`f44ace210cffd75885fa71c39ac3627f3c5ffaa4`，来源 common-dir `full-safe-receipts.json`。详见 [R1418](tasks_round/tasks_round_1418_result.md)。

R1420 最终验收：干净 master `4297564` 安全全量 5024 项、0 失败、437.376 秒，含架构 341 项；正式凭据 round=1420、tree=`8efa76a596ed682f2d3b57a1b2249553c5f9669b`，旧全量欠账已清零，凭据写入后轮次基线再验 5/5（0.325 秒）。缓存配置隔离 8/8、历史门禁样本隔离 7/7；首轮两个失败已闭环且原日志保留。收尾仅改文档，不冒称新树实测。详见 [R1420](tasks_round/tasks_round_1420_result.md)。

R1402 本轮实测：UI 路线图 §一 第 2 项（设计 token）末页迁移——`agent/prompt_optimizer.py` 10 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改 token（**零视觉变更**）＋行号平移同步（架构统一基数 第四项 175→176、覆盖率审计21 位点 173→174）；`test_token_boundary` 计数 16→6。定向 8/8、默认冒烟 8/8、架构 341/341。1402−1400=2<5 且未命中 §5，**不跑全量**（最近绿全量 R1401 `tree=60d4e23d…`）。提交内容 `8274dee`；报告／状态／接力 `0962173`。详见 [R1402](tasks_round/tasks_round_1402_result.md)。

R1401 本轮实测：UI 路线图 §一 第 2 项（设计 token）`desktop.py` 内联间距迁移——13 处 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改 token（**零视觉变更**；无新增 import、行数 7498 不变、无行号平移）；`test_token_boundary` `desktop.py` 计数 40→27。默认冒烟 8/8、架构 341/341。**命中 §5（启动路径，且 1401−1396=5）**：干净 master `o07-fullsafe-master` `--all --safe` 4983/4983、558.1 秒、0 红（凭据 tree=`60d4e23d…`＝`a8a0803:程序`，`last_full_safe_all_round` 1396→1400）。提交内容 `a8a0803`；报告／状态／接力 `71b7d3f`。详见 [R1401](tasks_round/tasks_round_1401_result.md)。

R1400 本轮实测：UI 路线图 §一 第 2 项（设计 token）第 3 批单页迁移——5 页 24 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）＋`keyframe_comfy.py` 1 处等值 `#ffffff→COLORS['background_card']` 改 token（**零视觉变更**）；`test_token_boundary` 计数 `keyframe_comfy.py` 36→25、`workflow_settings.py` 11→6、`white_model.py` 12→8、`native_assets.py` 9→6、`background_characters.py` 3→2、HEX `keyframe_comfy.py` 3→2。定向 168/168、默认冒烟 8/8、架构 341/341。1400−1396=4<5 且未命中 §5 升级条件，**不跑全量**（最近绿全量 R1399 `tree=250b6384…`）。提交内容 `e81df9c`；报告／状态／接力 `e0c8a75`。详见 [R1400](tasks_round/tasks_round_1400_result.md)。

R1399 本轮实测：UI 路线图 §一 第 2 项（设计 token）第 2 批单页迁移——4 页 21 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）＋`asset_detail.py` 1 处等值 `#ffffff→COLORS['background_card']` 改 token（**零视觉变更**）；`test_token_boundary` 计数 `asset_detail.py` 21→10、`prompt_window.py` 3→0、`qwen_setup.py` 9→6、`seedream_settings.py` 9→5、HEX `asset_detail.py` 21→20。行号平移：TODO注释快照 `asset_detail.py` 353→354、架构统一基数 第四项 `qwen_setup.py` 48→49／170→171。定向 50/50＋70/70、默认冒烟 8/8、架构 341/341（首次 2 红，同步后复验全绿，共 2 次）。**命中 §5 五轮（1399−1394=5）**：干净 master `o07-fullsafe-master` `--all --safe` 4983/4983、609.6 秒、0 红（凭据 tree=`250b6384…`＝`4ed81e9:程序`，`last_full_safe_all_round` 1394→1396）。提交内容 `4ed81e9`；报告／状态／接力 `d6dd313`。详见 [R1399](tasks_round/tasks_round_1399_result.md)。

R1396 本轮实测：UI 路线图 §一 第 2 项（设计 token）单页迁移——`asset_reference_images.py` 13 处内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改 token（`SPACING['md']`×11、`SPACING['xs']`×2），**零视觉变更**（取值相等且间距与调色板无关）；`test_token_boundary` 该文件数字间距 18→5。定向 `test_reference_images`＋`test_token_boundary` 26/26、默认冒烟 8/8、架构 341/341。1396−1394=2<5 且未命中 §5 升级条件，**不跑全量**。提交内容 `ac01f9f`；报告／状态／接力 `d5aeffc`。详见 [R1396](tasks_round/tasks_round_1396_result.md)。

R1395 本轮实测：出站 HTTP 收口（`platform_tools.open_https`；覆盖率审计26 清零）；定向 7/7、默认冒烟 8/8、架构 341/341。**1395−1390=5 命中 §5 五轮规则**：干净 master 工作树 `o07-fullsafe-master`（`git reset --hard master`→`d93993e`）跑 `run_selftests.py --all --safe` **4983 条、602.9 秒、0 文件有红**（凭据 tree=`886cfd07…`＝内容提交 `d93993e:程序`；`last_full_safe_all_round` 刷新为 1394）。`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 均无阈值抖动。提交内容 `d93993e`；报告／状态／接力 `0e5dd5d`。详见 [R1395](tasks_round/tasks_round_1395_result.md)。

R1394 本轮实测：agent 进程原语收口（`platform_tools.run_process`；覆盖率审计21 清零）；定向 7/7、默认冒烟 8/8、架构 `smoke_test.py --architecture` 341/341（数量不变，改既有门禁）。1394−1390=4<5 且未命中 §5 升级条件，**不跑全量**（最近绿全量 R1391 `tree=a8cfd2f0…`）。提交内容 `a966c41`；报告／状态／接力 `0c1e471`。详见 [R1394](tasks_round/tasks_round_1394_result.md)。

R1393 本轮实测：覆盖率审计棘轮递归化（`production_runtime_files`）；定向 7/7、默认冒烟 8/8、架构 `smoke_test.py --architecture` 341/341（数量不变，改既有门禁）。1393−1390=3<5 且未命中 §5 升级条件，**不跑全量**（最近绿全量 R1391 `tree=a8cfd2f0…`）。提交 `8f1a1fc`。详见 [R1393](tasks_round/tasks_round_1393_result.md)。

R1391 本轮实测：新增 `test_project_entry_boundary.py` 5/5；默认冒烟 8/8；架构 `smoke_test.py --architecture` 341/341（336→341，+5）。1391−1386=5 命中 §5 五轮规则 → 干净 master 工作树 `o07-fullsafe-master` `run_selftests.py --all --safe` 4983 条、546.4 秒、0 文件有红（凭据 round=1390、tree=a8cfd2f0…＝`37ed5bc:程序`；`last_full_safe_all_round` 刷新为 1390）。

R1390 本轮实测：§三 覆盖率门禁递归对齐（`_scan.production_files_recursive`）；定向 4 文件 8/8、默认冒烟 8/8、架构 `smoke_test.py --architecture` 336/336（数量不变，改既有门禁）。1390−1386=4<5 且未命中 §5 升级条件，**不跑全量**（最近绿全量 R1387 `tree=000477da…`）。提交 `fdb1daf`。详见 [R1390](tasks_round/tasks_round_1390_result.md)。

R1389 本轮实测：新增 `test_token_boundary.py` 5/5；默认冒烟 8/8；架构 `smoke_test.py --architecture` 336/336（331→336，+5）。1389−1386=3<5 且未命中 §5 升级条件（无启动路径／Tk 控件生命周期／删除语义／层级登记表改动），**不跑全量**（最近绿全量 R1387 `tree=000477da…`）。提交 `c8dbdb0`。详见 [R1389](tasks_round/tasks_round_1389_result.md)。

R1388 只读诊断实测：设计 token 内联视觉常量审计（269 个生产 .py）。默认冒烟 `smoke_test.py` 8/8（只读诊断 §5 默认不跑测试；此为该轮陈述基线的附加冒烟，不计验收）。**不跑全量**（距最近绿全量 R1387 `tree=000477da…`、`last_full_safe_all_round=1386` 仅 2 轮，且本轮无生产改动）。不改生产代码/测试/台账/路线图。提交 `7377586`。详见 [R1388](tasks_round/tasks_round_1388_result.md)。

R1387 实测：按钮门禁递归零容忍（`test_button_boundary` +2）；定向 25/25、默认冒烟 8/8、架构 `smoke_test.py --architecture` 331/331（329→331）。**1387−1382=5≥5 命中 §5 五轮规则**：干净 master 工作树 `o07-fullsafe-master`（`git reset --hard master`→`d5f597f`）跑 `run_selftests.py --all --safe` **4973 条、572.5 秒、0 文件有红**（凭据 round=1386、tree=`000477da…`＝内容提交 `d5f597f:程序`；`last_full_safe_all_round` 刷新为 1386）。`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 均无阈值抖动。提交内容 `d5f597f`；报告／状态／接力 `ec2320b`。详见 [R1387](tasks_round/tasks_round_1387_result.md)。

R1386 实测：`pet_bus.stage_label` 新入口＋阶段编号漂移纠正；定向 1275/1275、0 文件红、305.5 秒；默认冒烟 8/8；架构 `smoke_test.py --architecture` 329/329（326→329，+3 门禁）。路线图条目收口（§5）触发全量：干净 master 工作树 `o07-fullsafe-master`（`git reset --hard master`→`4cb02d3`）跑 `run_selftests.py --all --safe` **4971/4971、0 红、534.1 秒**（凭据 round=1382、tree=`d9aee73c…`＝内容提交 `4cb02d3:程序`；同一内容树不重跑第二次）。`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 均无阈值抖动。提交内容 `4cb02d3`；报告／状态／接力 `580d043`。详见 [R1386](tasks_round/tasks_round_1386_result.md)。

R1381 实测：`tests/architecture/test_dialog_boundary` 6/6（含新 canary）、定向 `-k "dialog prompt_window qwen tts_settings cloud_assets"` 24/24、默认冒烟 8/8、架构 `smoke_test.py --architecture` 326/326（原 325，+1）0 红。本轮只改架构门禁与文档、不改生产代码；1381−1380=1<5 且未命中 §5 升级条件（无启动路径／Tk 控件生命周期／删除语义／层级登记表改动），不跑全量；R1380 全量 4967/4967 为历史凭据（tree 不同不复用）。提交 `3ced47d`。详见 [R1381](tasks_round/tasks_round_1381_result.md)。

R1265 当前实测：受影响 458/458、冒烟 9/9；本轮架构首次 307/311，行号/轮次/周期四项问题修复后相关 10/10 复验通过。历史真实全量 R1264（干净 master a521730，4389/4389、413.396 秒）不覆盖本次实现；1265−1264=1，无升级项，不重复全量。完整证据见 tasks_round/tasks_round_1265_result.md。

R1253／R1255：制作锁修复定向 179/179、受影响 236/236、冒烟 9/9（默认 8/8）、架构 311/311、113.479 秒。生产实现 5b88c01，GUI 测试独立迁移 6ecb8e7 后另 1/1；均已同步主目录。全量未触发且未执行，R1251 为历史证据。Tk 非致命焦点告警及首次失败见报告。

R1251：模型切换隔离五项修复。干净 master 0084579 完整安全全量 4365/4365、597.524 秒，架构 311/311；执行器真实 round=1251、tree=8b48b1df35feda0afbd77fb5fedacb82da1b037a。关联 331/331、冒烟 9/9。首轮环境缺件及台账／夹具失败已闭环，见 R1249／R1251 报告。此后仅文档收尾，未实发 API、未重启。

R1248：关联 80/80、受影响冒烟 9/9（含默认 8/8）。首轮全量 1 条历史测试缺少发布器参数，用户授权后仅补齐注入，保留原断言，复测 3/3。干净 master 8512e06 正式安全全量（--jobs 4 --gui-jobs 2）4356/4356、585.006 秒，含架构 311/311；真实 round=1248、tree=37b32d6f6e54e581226fefeb92bbe91ce10761b4。此后仅文档收尾；主目录另一任务未提交修改不属于此凭据。

R1242：关联回归 199/199、115.7 秒，受影响冒烟 9/9（含默认 8/8），注释台账 2/2。首轮全量 10 条失败已闭环，相关复验 209/209、148/148。干净 master df9717d 正式安全全量（--jobs 4 --gui-jobs 2）4337/4337、634.517 秒，含架构 315/315；真实 round=1242、tree=264059cdc559997f5a19dba957ebccef671d33e5。此后仅文档收尾，见本轮报告。

R1213：干净 master 07d440c 正式全量 4302/4302、416.918 秒，含架构 311/311；执行器 round=1213、tree=807bfe5241ffb6e0e6fd48a57f3b1d5f7e8b5cf4。定向 145 条、默认 8/8、受影响冒烟 9/9；补齐隔离依赖后 61/61。最终收尾文档及用户脏树未同树全量；未实发 API、未重启。

R1212：受影响 192/192、默认 8/8、受影响冒烟 9/9、架构 311/311（104.715 秒）；核心 70/70、保存 34/34、取消/交付 12/12 有交集不累加。1212−1208=4，未触发全量升级；历史 R1208 非本轮同树凭据。实现 40f87ac，六项用户修改保持，未重启/实发 API。

R1208：干净 master fe4a923 正式安全全量 4291/4291、397.379 秒，含架构 311/311；执行器已写入 round=1208、tree=3831b1e0fe2e20cf1ea6c7b0b8afb9c881c3bff9。定向 111/111，位置登记修正后 72/72，取消 fixture 补齐后 73/73，默认冒烟 8/8、受影响冒烟 9/9。全量后发现共享缓存隔离细节，补丁先红后绿并定向 68/68；最终缓存补丁、文档树及含六项用户修改的主目录未同树全量。见 R1208 报告。

R1200/R1202：干净 e1f2d26 安全全量 4283/4283、539.0 秒（含架构 311/311），定向 129/129、默认冒烟 8/8、受影响冒烟 9/9；首次全量仅既有 SSE 架构登记行号漂移，修正后定向 71/71 并完整复验通过。后续干净 master 808a972 正式全量 4283/4283、511.725 秒，执行器已写入 R1202 凭据，tree=c4088b61e6cfeea289ff0cbd7dc9daca06628b38。原目录含用户六项修改，最终文档树及用户脏树未同树全量。

- R1198 本轮实测：干净实现基点 `445445f` 安全全量 4279/4279、559.7 秒、0 红（含架构 311/311）；定向 71/71、受影响冒烟 9/9、文档一致性 11/11。实现及审计已同步 master；全量不含六项用户未提交改动，分支未发布正式 master 凭据，历史仍 R1160。收尾仅文档，不冒称最终文档树同树全量。详见 [R1198](tasks_round/tasks_round_1198_result.md)。

- R1180 本轮实测：干净分支 `65649b0` 安全全量 `--gui-jobs 1` 4271/4271、582.2 秒（含架构 310/310）。首次默认并发 1 红，资产模块原断言复跑 18/18；定向 71/71、冒烟门禁 9/9。实现已同步 master；不含六项既有用户改动，分支不写正式 master 凭据，历史仍 R1160。收尾仅文档，不冒称最终文档树同树全量；未实发模型或重启。详见 R1180 报告。

- R1149 实测：模型池/工作流/模型管理 166/166，补充 Codex 路径优先级后定向 17/17；受影响冒烟 9/9（含默认 8/8）。架构 310 条首次 1 红，三处既有解码台账行号同步后失败模块 3/3（2.828 秒），未重复整套。实现 `8bd6241` 已合入；未运行真实 Claude Desktop 或验证登录/回复，历史安全全量 R1145 不代表本轮同树全量。

- R1140 当前实测：干净 master `947a3a7` 安全全量 4226/4226、501.415 秒（含架构）；凭据 round=1140、tree=`2b6e3b0819dda6756f30edb9c0a9dbdbb22118c2`、at=2026-10-08T16:14:45。附件 21/21、冒烟 9/9、入口 3/3；全量首跑两红先增量修绿再复验通过。收尾仅文档变化，不冒称同树全量；未调用外部模型。

- R1134 当前实测：干净 master `f2df26a` 全量 4214/4214、437.628 秒（含架构），受影响 140/140、21.7 秒、冒烟 9/9、默认 8/8。正式凭据 `round=1134`、`tree=a21c2baaaf8db6b3c924a047cc34c8e7b5eee209`、`at=2026-10-08T09:15:03`。收尾仅文档变化，不冒称最终文档树同树全量；真实外部生成和视觉验收未运行。

- R1127 当前实测：干净 master `66fffca` 全量 4187/4187、444.522 秒，含架构 309/309；默认 8/8、受影响 464/464、失败修复增量 59/59。执行器正式凭据 round=1127、tree=`f779114fa9a3d5429bffecbfc653814af11ae82d`；收尾仅文档变化，不冒称同树全量。阶段治理已同步，下一轮 1128。

- R1125 当前实测：干净分支 `c366345` 安全全量 4174/4174、420.9 秒（架构 309/309）；受影响定向 152/152、失败修复定向 26/26、默认冒烟 8/8、注册表 73。实现已快进同步 master；本次分支实跑未写入正式 master 全量凭据，历史 R1122 凭据保持原样。

- R1118 实跑：定向修绿 60/60、追加 14/14、受影响 9/9（含默认 8/8）；干净分支 884835c 全量 4157/4157、419.9 秒，含架构。分支全量不写 master 凭据，正式记录仍 R1115；后续仅文档收尾，不冒称文档树同树全量。

- R1115 实跑：定向 171/171、默认 8/8、受影响 9/9（96 用例）；注释快照行号同步后定向 6/6，最终干净 master 536ebcd 全量 4153/4153、397.524 秒，含架构，中央凭据 round=1115、tree=92d56dd4daa677db8553a9c939077cb4d53cf80a。收尾文档树变化不冒称同树全量。真实用户项目及外部模型未操作，未重启应用。

- R1113 实跑收尾：干净分支 dc8e922 完整安全回归 4148/4148、424.6 秒、0 红项（含架构）；失败闭环及语义专项 24/24、6.678 秒，默认 8/8。实现 412daae 已在 master，R1111 验收闭环；分支执行器不写 master 正式凭据，中央记录仍 R1110。未运行真实外部 Agent/API 端到端，未重启应用；文档收尾后的树不冒称同树全量。

- R1102 实跑：专项 22/22、相关/UI 365/365（200.1 秒）、架构 308/308（36.171 秒）、受影响冒烟 9/9、默认 8/8。旧回调测试桩补齐新方法且原断言全部保留。未改 Tk 生命周期/事件绑定，距 R1101 全量 1 轮，不触发全量；最近正式凭据仍 R1101，不冒称本轮树全量通过。
- R1101 实跑：定向/UI 360/360、独立架构 308/308、受影响冒烟 9/9、默认 8/8；首次全量的旧示例气泡断言冲突已按追加授权迁移，启动性能 14/14。e1179af 干净 master 安全全量 4128/4128、349.289 秒，中央 R1101 凭据已写入；收尾仅文档更新，不冒称文档更新树同树全量。

- R1100 本轮实测：定向 241/241、默认 8/8、受影响 9/9、独立架构 308/308；干净 master 检查点 `4a8d8f3` 全量 4124/4124、447.831 秒。中央真实凭据 round=1100、tree=`c8b8902486cad4ea3bec84d26368bda118cbc4f7`、at=2026-10-07T21:30:56；全量欠账闭环。随后仅回填文档，不冒称最终文档树同树全量；无真实项目/API/实机视觉验收，Tk 非失败警告见报告。新增 6 项测试，既有断言零删除零弱化。

- R1099 本轮实测：分支干净检查点 52c4ff0 安全全量 4118/4118、367.1 秒；定向 235/235，布局修复后 UI/内联 123/123、架构 308/308、默认 8/8，受影响 9/9。78aeef1 合入后仅文档收尾，生产代码/测试与该检查点相同。分支执行器不写主树全量凭据，common-dir 最近正式记录仍 R1097。Tk `greet/run` 非失败警告与未做实机视觉验收的限制见结果报告；旧表单测试获准删除/迁移，未弱化保留功能断言。

- R1097 实测：四项修复专项 29/29、默认冒烟 8/8、跟踪 Python/pyw AST 591/591；干净 master `76b8b77` 正式安全全量 4119/4119、390.132 秒，tree=`3a9db263bae14cd2b5971d0b1986fedf64498eec`，真实回执 round=1097、at=2026-10-07T18:06:30。其后仅回填文档，不冒称最终文档树同树全量；本次四项修复和分批简化目标完成，真实应用与真实用户项目未运行。

- R1088 实测：定向 168/168（59.2 秒）、默认冒烟 8/8、受影响 9/9、独立架构 309/309（23.8 秒），实现 `7c092a3`。未触发本轮全量，不将上一轮凭据冒称本轮验证。
- R1087 实测：定向 242/242、默认冒烟 8/8、受影响 9/9、独立架构 309/309；干净 master 检查点 `88eb04e` 全量 4075/4075、353.079 秒，tree=`7bfadad80296c3be43991a6aaf82646e4f44d41c`，真实凭据 round=1087、at=2026-10-07T07:44:15。详见 R1087 结果，不冒称后续文档树或 R1088 同树全量。

- R1085 实测：定向 115/115、失败项复测 23/23、默认冒烟 8/8、受影响 9/9、独立架构 309/309（30.4 秒）。检查点 `cd7cfae` 安全全量 4064/4064、348.967 秒，tree=`24cb94f0911cb0fc070e0cd52ad95c5d85ea1bad`，真实凭据 round=1085、at=2026-10-07T06:49:53。R1083 的 fcntl 闭包阻塞已消除；随后只归档文档与执行器生成的架构耗时元数据，不冒充最终文档树同树全量。

- R1068 实测：真实干净检查点 `1b36059` 安全全量 3994 条、0 个文件失败（333.662 秒），tree=`8466f0109fe30c54a31d1ea8890e5b05843553d6`，执行器凭据 round=1067。独立副本基线全量 3994 条通过；三个符号试删后的定向 90/90、冒烟 8/8、架构 309/309（120.944 秒）。两处凭据不混用，随后文档归档不冒充最终同树全量。
- R1066 实测：定向 40/40、受影响检查 9/9、冒烟 8/8；检查点 `e7f65b3` 安全全量 3991 条、0 失败（336.8 秒，含架构用例）；树 `8a93b15524b47c306b12ecb1cf5d2228327dcb12`。执行器按运行时最新报告记录 round=1065，未手改凭据；回填文档不冒充同树全量。
- R1065 实测：受影响检查 9/9、默认冒烟 8/8、独立架构 309/309（95.225 秒）；干净检查点 `fed586a` 安全全量 3988 条、0 个文件失败（333.9 秒），程序树 `e95eac4dbc3d49ca8a7c6ea8fd2d47ff3da0250c`。随后仅补本轮报告和状态，不冒充最终文档树的同树全量凭据。普通启动自动消息顺序已有回归，未以真实用户项目验收检查点恢复弹窗。
- R1058 历史实测：文档／轮次 15/15（0.332 秒）、新增链接／锚点 20 处通过、默认冒烟 8/8、独立架构 309/309（104.159 秒）；纯文档，未重复安全全量。
- R1057 历史实测：J16 删除后定向 711/711（166.1 秒）、冒烟 8/8、独立架构 309/309（101.609 秒），文档／轮次回归 15/15；未重复安全全量，下条 R1056 全量凭据仅代表其检查点。

- R1056 历史实测：删除前后定向均 203/203（40.0／38.7 秒）、冒烟 8/8、独立架构 309/309（104.334 秒）。截至 R1058 开工，最近安全全量为 R1056 干净 master 检查点 `70a25ad`，3973/3973、388.9 秒，tree=`67590ad058708133dbee5adc5c1614b39d9b0f29`；随后仅补报告、状态与人工队列，不冒充最终文档树全量凭据。R1054 假凭据审计及下列 R1034、更早条目均为各轮历史记录。
- R1034 历史实测：架构 301/301、109.237 秒；当轮安全全量受测提交 `509b6da`：3937/3937、334.510 秒，tree=`5113c0c2571b9cf256d4509cfff9a2f8f37f1f59`，不是当前最近全量；随后仅补报告/状态文档，不冒充当前文档树的全量凭据。C4 同树连续两遍达标的历史证据仍为 R1032 的 `acde93c`：3934/3934、341.614/341.134 秒，不能把 R1034 单次测量当作新的两遍证据。R1026 六项失败已在 R1027 清空；凭据以 common-dir 真实记录为准。
- R993 完整安全全量的历史记录为 3824/0、306.312 秒；是否可复用必须由 common-dir 的 `full-safe-receipts.json` 按内容树与有效期判定，不由本文授予通过。
- 下列 Round 403 及更早记录均为历史快照；测试触发规则只认 `AGENTS.md` §5。

- Round 403：经 `comfy_runtime.open_comfy()` 启动并读取 `http://127.0.0.1:8188/system_stats`；ComfyUI 0.37.0、RTX 4060 就绪，已保存的 Flux Klein、Qwen 编码器、Flux VAE 均在对应节点选项中。`run_selftests.py --safe --serial -k workflow keyframe_model_service stage_model_value keyframe_comfy` **95/95 通过**；默认 `smoke_test.py` **8/8 通过**。未提交生成任务。

- Round 402：复跑 `smoke_test.py --architecture` **31/31 通过**、默认 `smoke_test.py` **8/8 通过**；`AGENTS.md` 的入口基线已同步为架构 31/31、全量安全自检 3,059 条。历史 Round 182 的 14/14 与 2,942 条仍仅作为当时记录保留。

- Round 401：`tests.test_storage`、`tests.test_asset_resume`、`tests.architecture.test_recycle_service` **17/17 通过**；`smoke_test.py --architecture` **31/31 通过**；默认 `smoke_test.py` **8/8 通过**。

- Round 400：本机只读发现 Comfy Desktop 可执行文件；配置端点 `/system_stats` 返回 **HTTP 502**。`run_selftests.py --safe --serial -k workflow keyframe_model_service stage_model_value keyframe_comfy` **95/95 通过**；默认 `smoke_test.py` **8/8 通过**。

- Round 399：`smoke_test.py --architecture` **31/31 通过**；`run_selftests.py --safe --serial -k legacy_compat stage_completion_service platform_tools hash_backend` **26/26 通过**；默认 `smoke_test.py` **8/8 通过**。

- Round 398：新增原子写入边界架构门禁后，`smoke_test.py --architecture` **28/28 通过**；`run_selftests.py --safe --serial -k workflow force_quit model_pool model_secrets` **144/144 通过**；默认 `smoke_test.py` **8/8 通过**。

- Round 396：`run_selftests.py --all --safe` 覆盖 **137 个测试文件、3,059 条用例**，**788.2 秒、0 个失败文件**；默认 `smoke_test.py` **8/8 通过**。白模视频上传真机验收未经用户授权，未执行。

- Round 182 收尾：`run_selftests.py --all --safe --jobs 6` 覆盖 **115 个测试文件、2,942 条用例**，
  **831.3 秒、0 个失败文件**；完整输出：`维护记录/round182_closure_safe_all_20260927.out.log`。
  `smoke_test.py --architecture` **14/14 通过**、7.584 秒，覆盖删除网关、动态导入登记、层级、
  模型边界、循环依赖、路径权威、平台和阶段路径门禁。

- 历史快照：Round 404 默认冒烟 **8/8 通过**；Round 402 架构检查 **31/31 通过**，不代表当前树的结果。
- Round 17：项目文件落盘过滤回归 **49/49**、剧本页面文件表 UI 回归 **1/1**、默认冒烟 **8/8 通过**。
- Round 18：HOLLMWOOD 队列 2/2、剧本 API 14/14、三虎模式 7/7、默认冒烟 8/8 通过。完整 `test_pet_ui.py` 仍有剧本结构阶段插入前的旧断言（期待 storyboard 而非 script_structure），不作为本轮新增失败。
- Round 19：剧本文件三列独立紧凑排列、文件名去除目录前缀的 UI 回归 1/1，默认冒烟 8/8 通过。
- Round 20：TLS EOF 传输重试与四角色剧本失败回退回归 17/17，默认冒烟 8/8 通过。
- Round 21：剧本输入提示垂直居中与空闲滚动 UI 回归 2/2，默认冒烟 8/8 通过。
- Round 16：历史对话简报回归 **48/48**、工作流 **69/69**、API **14/14** 通过；默认冒烟 **8/8 通过**。
- Round 15：剧本准备文件表分类回归 **1/1 通过**，默认冒烟 **8/8 通过**。
- Round 14 定向：`test_api` **53/53 通过**；页面构建异常回归 **1/1 通过**。全量安全自检已按用户指示暂停，未可作为发布通过依据。
- 历史定向记录：Round 13 `test_skill_templates` + `test_sanhu_mode` 10/10 通过；Round 12 `test_skill_templates` 2/2、检查点恢复相关 `test_skills` 2/2 通过；Round 11 `test_sanhu_mode` 7/7、页面构建 1/1 通过。

## 已知阻塞与待办

R1265：用户授权四项技能保障已完成，无本轮功能待办。超过预算的技能组合会明确阻断，需用户减少选择；未实发外部 API／桌面应用，程序注入保障不等于模型绝对遵从。完成后停止，不自动执行下列历史任务。

- R1198 日报周报清理修复及其他生成文件机制扫描已完成，当前请求无阻塞。其他清理风险 J1～J8 仅诊断，见 [审计与测试计划](tasks_round/tasks_round_1198_cleanup_audit.md)；未执行真实项目清理，不自动扩展整改范围。回收不释放总磁盘空间，未重启应用。

- R1139 既有回归阻塞已在 R1140 闭环：旧按钮样式/剧本文案断言已同步用户批准行为，另补齐两页蓝色覆盖；干净 master 947a3a7 全量 4226/4226 通过。技能同步的真实模型创作验证仍未执行，不用自动化通过冒称外部模型行为。

本阶段一般范围锁定（2026-10-01 用户裁决）：只做入口统一、性能与缺陷修复；新功能先登记。Animatic 为用户后续明确授权的例外，见 R1134；此例外不授权其他新功能。

### 【已完成·R1134】新增 Animatic 分镜预演阶段（animatic）

- 授权变更：R1123 仅登记延期；用户后续明确授权新增阶段，并选择应用内部合成与旧目录只读、首次修改复制方案。R1134 完成自动化验收，历史登记保留在 R1123 报告。
- 目标位置：初步分镜 `storyboard` 之后、资产管理 `assets` 之前，不替换白模预演 `previs`。
- 阶段职责：参考图 + 分镜提示词经本地 ComfyUI 生成镜头预演草图，配临时 TTS／导入音频，应用内部合成 Animatic。SG-A/SG-B 约束进入及确认；未实跑外部生成与成片视觉验收。
- 参考图边界：将资产管理的参考图目录在职责上提前为跨阶段共享参考图目录，由分镜预演负责准备、资产管理复用；不物理移动用户数据。
- 资产提示词边界：资产提示词保留在资产管理，不移动到分镜预演。
- 生成边界：资产管理复用相同功能代码，走线上 API 正式生成资产图；分镜预演使用本地 ComfyUI 生成预演草图。
- 验收与边界：全量 4214/4214、默认 8/8；不移动用户数据，不生成正式资产或首帧。完成证据见 [R1134](tasks_round/tasks_round_1134_result.md)，历史登记见 [R1123](tasks_round/tasks_round_1123_result.md)。

### 【待办·显式推迟】会员订阅制（Mode A 软件授权）——开工前置决策清单

- 决定：软件授权制（入口闸门）；用户仍自带 API Key，不碰模型调用链。
- 定价：3 天试用／月 39／季 99／年 399。
- 状态：**显式推迟·非现在实现**，待“入口统一＋性能＋缺陷修复”阶段收尾后再立项。本待办只登记决策与前置项；现在不搭后端、不写登录或付款、不预留接口、不做任何实现。
- 开工前必须先定的 11 项决策：身份（设备／账号）、登录最小范围、试用时长（服务器时间权威，防改本地钟）、计费与自动续费代扣、授权判定的唯一入口位置、订阅凭据存储（禁走 DPAPI 机器绑定）、离线／验权失败宽限策略、验权网络出口（统一经 `platform_tools`）、订阅令牌不得入日志／任务 JSON（靠覆盖率审计 27）、付款资质（商户＋对公／ICP备案／托管收银台不碰卡号／PIPL）、反作弊与 DRM 容忍度。
- 两大先决架构约束：(1) **服务器权威**——本地“是否已付费”被改也不算数；桌面只缓存带签名、带过期时间的续验结论。(2) **试用时长以服务器时间为准**，防系统钟回拨或前调白嫖。
- 与当前阶段的依赖关系：覆盖率审计 21（平台适配）、26（模型路由）、27（密钥）是订阅未来应挂接的接缝；收尾三项即为订阅打地基。订阅闸门应落在统一的 L3 入口，不得内联散写。

UI 统一入口已存在且有多批历史迁移。R1031 的 4 处 tk.Button 候选已由 [R1041](tasks_round/tasks_round_1041_result.md) 完成迁移；50 个带字体/颜色标签是历史扫描候选，R1051 只完成资产详情的 5 处说明文字迁移，不能据此宣布全页面统一。架构第 3、4 项台账 pending 已为空，不再将其写作当前迁移主线。R1032 的“本次清单停止”是当时范围；后续 R1036 队列有独立授权与验收记录，不受该历史停止语句误导。

更新（R1376—R1380，UI 统一入口覆盖轮）：路线图 v1 中此前未收口的 4 项已按各自完成判据收口并**完成全量覆盖审计**——卡片容器（页面级承载区 `ttk.LabelFrame`→`ui_widgets.Card`，21 页已用 Card，其余为卡内小节／锁定几何阅读区／独立工具脚本豁免）、文字层级（说明→`DescriptionBlock`、状态→`ProgressLabel`、标题→`Tokens.Title.TLabel`，7 页门禁固化于 `tests/architecture/test_text_component_boundary.py`）、忙碌态（提交/取消/成功/失败/迟到结果全链路收口到 `BusyState.set_busy`，生产 `ttk.Progressbar.start/stop` 零容忍门禁）、文案与复制（复制失败固定术语＋递归生产扫描门禁）。R1380 命中 §5 五轮规则，干净 master 全量 4967/4967、0 红；架构 325/325。R1381 复核校正：**上述「其余项均未收口」为高估**——路线图其余待审计项多数早已由递归零容忍门禁收口（表格 `test_data_table_boundary` 固定 `{'desktop.py': 3}`，项目树为唯一语义例外；输入／下拉／提示／右键菜单／文件选择／快捷键／Tooltip／图标／滚动条／文案与复制／忙碌态 均为递归 `violations==[]`；弹窗由 R883／R922 收口，R1381 再把 `test_dialog_boundary` 门禁递归化）。**真正剩余**的只剩尚无专用门禁的项：设计 token 内联视觉常量（R1388 只读审计：业务页 111 处内联 hex／8 文件、213 处数字 padx/pady／19 文件、189 处数字字号尺寸候选／32 文件，且 ui_tokens 与 ui_theme 双调色板并存）、§三 覆盖率审计 7 项（R1390 裁定 6 项收口、R1391 收口第 4 项「项目进入路径」，7 项全部收口）。阶段显示已由 R1386 收口（`pet_bus.stage_label` 现算＋`test_stage_display_boundary` 编号一致性／位点冻结门禁）；按钮门禁已由 R1387 由「固定页清单」收紧为递归零容忍（全生产 269 模块 0 裸 `tk/ttk.Button`，架构 331/331）。按路线图各项「完成判据」逐页推进。文字层级旧页面为已登记 backlog。完成依据见 [R1376](tasks_round/tasks_round_1376_result.md)–[R1381](tasks_round/tasks_round_1381_result.md)，范围与判据以 `维护记录/UI统一入口路线图_v1.md` 为准。

### 【已完成·R1386】生产文案阶段编号漂移（R1382 只读审计 → R1386 修复轮收口）

- 现象：R1375（O48）已把用户可见「第N步」收口到 pet_bus.stage_step，但散落的「NN 阶段名」旧编号未同批处理；R1124 插入 animatic（第 04 步）后，资产起整体 +1／+2 偏移（资产 03→05、连贯性 04→06、定稿 05→07、首帧 06→08、白模 07→09、视频 08→10、配音 09→11、剪辑 10→12、质检 11→13）。
- 权威：pet_bus.STAGES（顺序即步号）＋pet_bus.STAGE_NAMES（显示名）＋desktop.PAGES 标签格式；阶段目录名见 stage_layout.STAGES。
- 命中（排除 stage_path_service.LEGACY_NUMBERED 旧目录兼容常量）：R1382 初报生产 14 文件 97 处、tests/ 19 文件 56 处；R1386 复核修正 1 处误报（animatic_service.py:1 的「L2 分镜预演」＝层级前缀 L2，非阶段步号），准确＝生产 13 文件 96 处。
- 用户可见优先：keyframe_batch.py:51/52/141/236、desktop.py:2484、desktop.py:7015/7058、pet_ui.py:2956/2959、stage_parallel.py:477/480/483/486/489、skill_tools.py 的 PAGES 说明列。
- 勿误改：stage_path_service.LEGACY_NUMBERED（旧目录只读兼容常量）、desktop.py:5180（01剧本准备）、desktop.py:5212（02剧本结构）。
- 收口判据（路线图 §二 第 15 项原文）：任何阶段名称展示均从权威表取值 → 修复轮须同时新增/扩展架构门禁（AST 扫生产字符串常量，排除 docstring 与 LEGACY）并同步更新 tests/ 里写死旧编号的 56 处断言。
- 状态：**已收口（R1386 修复轮 §3.2）**。`pet_bus.stage_label` 为「NN 阶段名」唯一权威；6 个展示位点改现算、注释／docstring 按权威序纠正；`test_stage_display_boundary.py` 新增 3 条门禁（编号一致性＋位点冻结＋导航序对齐），架构 326→329；定向 1275/1275、默认冒烟 8/8、干净 master 全量 4971/4971、0 红（tree=`d9aee73c`＝`4cb02d3:程序`）。见 [R1386](tasks_round/tasks_round_1386_result.md)。

### 【待办·已审计未实现】设计 token 内联视觉常量（R1388 只读审计）

- 现象：规则 34 要求 padx/pady、颜色、字号、圆角一律从 token 取值；实际业务页仍大量内联视觉常量，且无自动化门禁。
- 命中（269 个生产 .py，排除 tests／tasks_round／维护记录；权威＝ui_tokens.py／ui_theme.py／ui_widgets.py／ui_icons.py／skills 独立脚本）：① 内联 hex 业务页 **111 处/8 文件**（pet_ui.py 45、desktop.py 31、asset_detail.py 21、cell_hover.py 6、keyframe_comfy.py 3、app.py 2、storyboard_table_ui.py 2、previs_monitor.py 1）；② 数字 padx/pady **213 处/19 文件**（desktop 40、keyframe_comfy 36、asset_detail 21…）；③ 数字 font/wraplength/width/height 候选 **189 处/32 文件**（desktop 41、pet_settings_ui 18、pet_ui 18…；width/height 部分属布局非纯视觉）。
- **双调色板风险**：ui_tokens.py（14 hex）与 ui_theme.py（53 hex）各自硬编码，ui_theme.py **未** import ui_tokens；全生产仅 desktop.py import ui_theme，ui_tokens 被 14 个模块 import。同一 hex 多点重复 → 改色易漂移。
- 现状：tests/architecture 无 token 专用门禁（仅 test_scrollbar_theme_boundary.py）。
- 收口判据（路线图 §一 第 2 项原文「页面是否仍内联视觉常量待审计」）：页面视觉常量从 token 取值 ＋ 棘轮门禁冻结（只减不增）。
- 状态：已审计；**R1389 已加棘轮门禁** `tests/architecture/test_token_boundary.py`（内联 hex 与数字 padx/pady 按文件「只减不增」，新增文件即违规；架构 336/336）。**迁移仍待做**：先统一调色板（`ui_theme` 复用 `ui_tokens`，可能改视觉须先确认），再逐页迁 hex；padx/pady 与字号按单页粒度另批。**R1396／R1399 起**按「值恰等于 token」的可证明零视觉变更子集、单页粒度推进（R1396 `asset_reference_images.py` 数字间距 18→5；R1399 `asset_detail.py`／`prompt_window.py`／`qwen_setup.py`／`seedream_settings.py` 共 21 处间距＋1 处等值色；R1400 五页 24 处间距＋1 处等值色；R1401 `desktop.py` 13 处间距；R1402 `agent/prompt_optimizer.py` 10 处（累计 81 处）。**决策-free 子集至此全部迁完**：全站内联标量 `padx/pady` 只剩非 token 值与 0 值间距。再推进必须先有调色板决议——hex（含 `desktop.py` 31 处）、103 处旧调色板值、非 token 间距值、旧页面文字层级均依赖它。见 [R1388](tasks_round/tasks_round_1388_result.md)／[R1389](tasks_round/tasks_round_1389_result.md)。

### 【已收口·R1391】项目进入路径覆盖门禁（R1390 §三 裁定 → R1391 收口）

- 现象：路线图 v1 §三 第 4 项「项目选择／切换」（权威＝`DesktopStartupController`／`desktop_settings_service`）缺一条架构覆盖门禁断言「所有项目进入路径必经控制器」。
- 现状证据：`desktop.py` 已统一经 `DesktopStartupController`（410/415）；功能级测试 `test_ui_edges`／`test_timers`／`test_desktop_startup_perf`＋`test_project_context_boundary`（project_context 仅 L3 构造）。
- 收口判据（路线图 §三 第 4 项原文「所有项目进入路径可由同一控制器与设置服务审计」）：新增覆盖门禁（desktop 项目进入相关方法不得绕过 `startup_controller`）并证明扫描为空。
- 状态：**R1391 已收口**——新增 `tests/architecture/test_project_entry_boundary.py`（5 条）冻结项目进入入口集合、断言首帧首次选择必经 `DesktopStartupController`、当天选择委托 `desktop_settings_service`；架构 336→341、全量 4983/4983。见 [R1391](tasks_round/tasks_round_1391_result.md)。

### 【已收口·R1393】覆盖率审计棘轮口径递归化（R1390 §三 后续）

- 现象：R1390 只把删除／事件总线／阶段完成三类门禁升为递归；覆盖率审计棘轮仍走 `production_files()`（仅根目录），对 `agent/`（被 30+ 产品模块导入的运行时子包）失明。
- 实现（**不改生产代码**）：`tests/architecture/_scan.py` 新增 `NON_PRODUCT_PARTS`＋`production_runtime_files()`（递归再排除 skills／scripts／reference／outputs／附加工具，239 个运行时模块）；`test_coverage_audit_ratchet.scan()` 默认范围改它、台账键改相对路径 `_key()`；`维护记录/架构统一基数.json` 覆盖率审计21／26 各 +2 pending（count 21→2、26→2；26 baseline_pending 1→2）；判据文档第 21／26 行真候选 0→2。
- 新暴露真候选（pending 待裁定）：`agent/core.py:173`／`agent/prompt_optimizer.py:172`（进程）、`agent/core.py:189/208`（网络）。
- 验证：定向 7/7、默认冒烟 8/8、架构 341/341；1393−1390=3<5 且未命中 §5 升级条件，不跑全量。见 [R1393](tasks_round/tasks_round_1393_result.md)。

### 【已收口·R1394／R1395】agent 包进程原语与出站 HTTP 真候选

- 范围＝R1393 新暴露的 4 条 pending：`agent/core.py:173`、`agent/prompt_optimizer.py:172`（subprocess）；`agent/core.py:189/208`（urllib）。
- R1394 已收口 2 处 subprocess：`agent/core.py` `command()` 改经 `platform_tools.run_process`（惰性 import、移除模块级 `import subprocess`）；`agent/prompt_optimizer.py` MCP 桥子进程同改（模块级 import，保留 `subprocess` 供 `TimeoutExpired`／`SubprocessError`）。行为与异常类型不变；台账 `覆盖率审计21` 两条 pending→migrated、count 2→0，`第四项` `json.loads` 行号平移（core 13→12、prompt_optimizer 174→175）；判据第 21 项真候选 2→0。
- R1395 已收口 2 处 HTTPS：`platform_tools` 新增唯一出站 HTTP 入口 `open_https(url,*,timeout=60,data=None,headers=None)`，`agent/core.py` `request()`／`download()` 改经它（错误分类、密钥脱敏、HTTPS 强制、`geturl()` 重定向校验、1GB 上限、原子发布不变）。裁定：两处均为应用自身资产 I/O（参考图／云端视频下载）非模型路由，且 `download()` 依赖 `agent.core` 原子发布权威不能外移 → 只把出站调用收口到宿主适配层。台账 `覆盖率审计26` 两条 pending→migrated、count 2→0；判据第 26 项真候选 2→0。
- 结果：**覆盖率审计 21／26 真候选全部清零**，双向棘轮相等（再现裸 `subprocess.run`／`urllib.request.urlopen` 会被立即拦下）；占位类型 20／24／25 无真候选。见 [R1394](tasks_round/tasks_round_1394_result.md)／[R1395](tasks_round/tasks_round_1395_result.md)。
- 另：secret sink（覆盖率审计 27）仍为根目录口径，是否同批递归化待评估。

### 项目优化清单（R1058 事实校正）

以下是当前待办的优先级索引，不新增执行授权；每轮只处理一类任务。优先级是建议顺序，不代表未验证项已被认定为缺陷。

| 优先级 / 状态 | 项目 | 下一步与完成边界 |
| --- | --- | --- |
| 已完成 | 三虎聊天瞬时关闭、动画吞单击 | R1034 已分离动画取消与退出清理；新增 3 条回归，全量 3937/3937。部署后的阅读体验仍需重启旧进程确认，不重新列为待开发功能。 |
| 已完成本次审计/核验 | 依赖与历史名称、后台生命周期、文档事实、C4 | R1027–R1032 证据保留；不等于全页面 UI 或全部技术债清零，不重复迁移已采用服务。 |
| 隔离场景已验收；真实环境边界保留 | 启动、同日续开、项目改名认领、幽灵条目 | [R1043](tasks_round/tasks_round_1043_result.md) 验证空项目取消恢复，[R1044](tasks_round/tasks_round_1044_result.md) 验证同日续开，[R1048](tasks_round/tasks_round_1048_result.md) 验证改名认领；[R1050](tasks_round/tasks_round_1050_result.md) 以隐藏 Tk／服务集成验证幽灵登记同步，不是新增实机视觉验收。真实项目、旧运行实例和三虎重启阅读体验未据此关闭。 |
| 已完成 / 不重复立项 | 4 处 tk.Button 统一入口 | [R1040](tasks_round/tasks_round_1040_result.md) 完成图标适配，[R1041](tasks_round/tasks_round_1041_result.md) 完成 3 模块 4 处迁移及别名门禁；原行号仅为 R1035 历史定位，不再作为当前待迁移清单。 |
| 已完成 / 已入门禁 | 覆盖率审计棘轮递归化（产品运行时子包） | [R1393](tasks_round/tasks_round_1393_result.md) 把 `test_coverage_audit_ratchet` 扫描范围由根目录改产品运行时口径（239 模块），覆盖率审计21／26 各 +2 pending；[R1394](tasks_round/tasks_round_1394_result.md)／[R1395](tasks_round/tasks_round_1395_result.md) 已把新暴露的 4 条 agent 真候选全部收口（进程→`platform_tools.run_process`、出站→`platform_tools.open_https`），覆盖率审计21／26 各清零。 |
| P2 / 部分完成，余项待分类 | 文字层级、Card/token、焦点与忙碌反馈 | [R1051](tasks_round/tasks_round_1051_result.md) 完成资产详情 5 处普通说明；[R1052](tasks_round/tasks_round_1052_result.md) 仅完成 Busy／焦点覆盖矩阵，不代表缺口已修。标题、状态色、窄格文字及后续交互修复仍需独立范围，不批量机械替换。 |
| P2 / 持续守护 | 性能、服务契约与上下文覆盖 | 保留现行棘轮和同条件性能验证；新增实际服务再纳入，不因历史名称重复造模块或迁移。 |
| 条件阻塞 | 白模视频真实上传验收 | 等待用户指定镜头和授权发送素材；不自行上传。 |
| 条件阻塞 | P3-2 兼容 facade 退役 | 先查生产调用方及兼容窗口；既有台账淘汰日 2027-03-31，未满足条件不删除。 |
| 显式推迟 | 会员订阅、完整分段流水线方案 3b | 保留原前置决策和需求触发条件；当前不新增用户可见功能。 |

下一项以[优化待办队列](维护记录/优化待办队列.md)的最高优先级未完成项为准；条件项未满足不得勾选。J18 完成后是 J19 的只读职责边界诊断，不重新执行已完成的按钮迁移。本节不新增真实项目操作或上传授权。

UI 待办见 `维护记录/UI统一入口路线图_v1.md`。

性能基准（路线图第 18 项）：R776 已冻结统一归档、同条件中位趋势阈值和共享绝对上限；后续性能轮只可在同条件样本上比较，严禁以冷/热缓存或项目路径差异掩盖回归。

缺陷普查台账 `维护记录/缺陷台账_20261001.md` 保留 R744 时点记录；不能把其中旧“未关闭”直接当作现状。后续授权范围内的启动取消、改名认领和幽灵登记验收见上表 R1043／R1048／R1050；真实用户环境的剩余边界仍保留，本轮不修改原台账或追认历史验收。

回收站恢复入口已有整批／单条／旧 `files` 清单兼容、冲突零移动及越界拒绝的回归覆盖。R770 当时的 `_diag_winprobe.py` 全量阻塞不再是当前状态：R1029 干净提交 66539c3 安全全量 3934/3934。此事实只证明当前受测版本，不追认 R770 或历史缺口轮次验收。

0. 架构统一第 1、2 项已解冻，第 3、4 项台账 pending 均为 0。现行结果采用方 26 个、只读/既有豁免 34 个，范围待审计为空；上下文采用方 22 个、豁免 8 个、7 个未实体化历史名称保留独立审计记录，pending 为空。`storyboard_edit_service` 已采用四字段结果，不能重复列为“下一批迁移”。R1028 只完成历史职责索引，不冒充迁移；完整范围由 `维护记录/架构统一基数.json` 与门禁约束。后续如出现新增实际服务，仍按每轮最多 3 个 service 同步调用方、测试及棘轮，不为清空数字重复改代码。
1. R182 的可执行拆分项仅余 P3-2（facade 退役治理）：P0-1/P0-2 已完成，P0-3 已由 R589–R593 完成；P1-1 至 P1-7、P2-1 至 P2-5、P3-1 均已逐项关闭。当前五个 facade 仍各有生产调用方，且统一淘汰日为 2027-03-31；在任一 facade 零调用或兼容窗口到期前不得删除。旧项目只读迁移的用户可见失败提示尚未有获批交互契约，不能擅自新增。详见 `tasks_round/tasks_round_547_result.md`、`tasks_round/tasks_round_568_result.md` 与 `tasks_round/tasks_round_593_result.md`。R182 以外的全页面响应式布局和删除入口统一是独立专项，不纳入 R182 拆分债务。
2. 白模视频上传真机验收仍未做：需用户指定已采用且已生成预演视频的镜头，并授权向万相/Seedance 发送素材；程序不会擅自上传用户素材。
3. P1 启动白屏用户侧复验：R536 已以真实 Tk 首屏覆盖“无当前项目首页未安排 Canvas 布局”的根因，但无法替代用户重启当前已运行实例后的环境验收。若重启后仍白屏，须保留启动时刻、是否自动打开今日项目及截图，按该新证据诊断；不得把 R523/R527/R535 的局部性能结论当作已解决证明。
4. 流水线代码级分段编排（方案3b）：将剧本准备拆为 岗位1-2（桌面引擎任务）→ Gate A 确认门禁 → 岗位3（程序调用 `hollmwood_roles.run`，API 链）→ 岗位4-8（桌面引擎接力）→ Gate B。前置条件：新增 L3 分段控制器并接 `stage_handler_registry.start()` 唯一入口；中间产物路径经 `stage_path_service` 登记；CLI→API→CLI 两跳的上下文预算需 `workflow_context_budget` 新策略；确认暂停复用 `confirm_gates` 既有机制。触发条件：API 用户需要完整流水线成为真实需求时再立项。
同日续开已完成项（不再列为待执行）：[R1044](tasks_round/tasks_round_1044_result.md) 在隔离正式启动器中完成正常退出→同日重开→01 剧本准备→02/01 切页→正常退出。该证据关闭原第 5 项的隔离正式启动器复验，不涵盖真实项目、大项目、旧运行实例或精确启动耗时；未经另行授权不操作真实项目。

## R504 阻塞归类与整改路线

历史快照：下表及紧随的测试迁移计划描述 R504–R507 当时的安排，不是当前执行顺序，也不授权重新实施密钥迁移。R182 剩余项与当前阻塞见[当前待办](#已知阻塞与待办)；表内“结构治理待办”不得覆盖后续完成证据。

| 优先级 | 分类 | 阻塞条件 | 最小整改闭环 | 完成判据 |
| --- | --- | --- | --- | --- |
| P0 | 已完成（R505） | 新写入已改 DPAPI，旧程序明文文件已受控迁移清理 | 仅保留历史会话的只读兼容 | 保存、读取、迁移失败回滚、云视频取钥及实迁检查均通过 |
| P1 | 已完成（R506） | `responses` 分支现按原生请求/响应格式处理 | 仅提取 `output_text`，保留空文本和错误的真实语义 | 协议专项、架构门禁、安全全量和默认冒烟均通过 |
| P2 | 已完成（R507） | 云视频凭据默认不回填且输入框保持掩码 | 显式查看仅短暂生效，到期后清空；只在新输入时替换 | Tk 无头测试验证默认掩码、无回填、显式显示与自动重新掩码 |
| P3 | 结构治理待办 | R182 清单仍未逐项关闭 | 按既有专项一项一轮，不与上述安全修复混改 | 每项有边界测试和状态记录 |

R504 当时的整改顺序为：P0 密钥迁移 → P1 Responses 协议 → P2 界面掩码 → P3 既有结构专项。P0—P2 在 R505–R507 完成；“进入 P3”仅指当时阶段，不是当前指令。

## R504 测试迁移计划

以下为历史计划，保留追溯；不是本轮测试命令或新增任务。当前验证规则唯一来源为 AGENTS.md §5。

1. 不移动现有测试文件：本次发现属于缺失契约覆盖，不是测试目录组织问题；继续遵守“新测试只放 `tests/`”。
2. 为 P0 新增独立的凭据迁移回归：使用临时目录与假保护器，覆盖旧 `.env` 发现、加密迁移、原子替换失败、旧明文清理和不得回显；禁止读取或使用真实 `private/.env`。
3. 为 P1 在 `tests/test_model_pool.py` 或新增 `tests/test_model_router_responses.py` 固化真实 HTTP JSON fixture；现有 `choices` 桩保留作 Chat 兼容覆盖，不得冒充 Responses 覆盖。
4. 为 P2 在既有云视频测试模块补 UI 状态断言；若 Tk 生命周期使其不稳定，先将“Entry 配置/回填决策”提取为无 Tk 纯函数再测试，不能降低断言或跳过。
5. 迁移与修复完成后依次运行定向测试、默认冒烟、架构门禁；P0/P1 跨模块变更收口时再运行 `run_selftests.py --all --safe`，并记录总数、耗时、失败模块和密钥脱敏检查结果。

## 最近完成

Round 390 及更早的逐轮完成记录已原文迁至 [状态历史归档](维护记录/状态历史归档.md)；当前最新完成项与验证结果见文首轮次头、[验证基线](#验证基线)及[优化队列](维护记录/优化待办队列.md)。


R1609：新增 usage_overview.estimate_scenario，按场景用量乘费率，缺费率／币种／版本时不给金额也不补零；场景矩阵与公式见 维护记录/成本估算与场景矩阵_20261016.md。

R1608：新增 agent.core.save_file（按块复制、摘要与长度校验、失败不覆盖旧成果），collect_download_inbox 改用它并包在发布事务内，大媒体收回不再整份进内存。

R1607：新增 native_asset_codec.seedream_provenance，首帧 Seedream 与资产云图两条路径的每次状态写入都带 provenance（提示词摘要、逐参考图摘要、模型与采样参数、载荷结构版本），不含密钥与图片字节；覆盖矩阵见 维护记录/多模态溯源覆盖矩阵_20261016.md。

R1606：剧本页 open_path／context_menu 两个外部 UI 能力改为实例注入 ScriptPageServices，Desktop 在组合入口装配默认服务，独立页面测试不再初始化 Desktop。引用注入定向7项、注释快照2项通过；架构345项与默认冒烟接续复验。仅两产品模块，未改业务状态与阶段权威；其余页面跨页依赖见 architecture.md 的 R1606 节，不声称全桌面解耦。

R1538：启用金额上限时，在项目锁内检查根目录及cloud_video旧任务和会话台账；未纳入总账或状态损坏则发送前阻断，已入账/明确not_submitted不阻断，不修改历史、不推测费用。定向46条及冒烟8项通过，证据.git/r1535-tests.log、r1535-smoke.log。历史费用迁移与对账入口仍待实现，P0-3保持待验收。

R1541：费用核对入口完成，账单金额/币种/核对人/凭据摘要和修订历史落盘；已核对费用防迟到回执覆盖，汇总分列估算和账单金额。定向47条、补强2条与金额最终2条通过，冒烟8项通过。R1538安全全量5238条通过（不含本轮新代码）。继续旧会话费用导入及批量预估，P0-3待真实验收。
