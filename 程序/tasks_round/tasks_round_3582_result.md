# R3582 — A10 第四批云资产参考图上传依赖归位
<!-- round-evidence: {"commit_base": "f090d54f", "credential_hits": 0, "evidence_sha256": "ff8e417fd3766201", "exit": 0, "failed": 0, "passed": 157, "round": 3582, "tests": "run_selftests.py -k test_aspect_ratio_priority test_native_run test_http_client test_batch_frames test_execution_deadline test_layers test_no_circular_import test_http_boundary test_dynamic_import_registry test_unification_ratchet test_static_hygiene"} -->

1. 结构治理轮。起点 `f090d54f`，工作树 `e83f`，分支 `codex/architecture-a10-cloud-upload`。生产模块改动 1 个。
2. 默认冒烟 8/8，另有隐藏桌面探针通过。专项 157/157。完整架构与其余验证见下文。
3. A9-8 记录的三条 L1 → 批处理边已全部清零。安全全量未运行，中央凭据没有该基线程序树的记录，本轮未结算全量欠账。

## 范围和行为

领号 R3582，中央队列无匹配项。范围扫描发现架构文档与若干活跃车道重叠，工具审计测试与 A9/A10 车道重叠，画幅测试与 L2 车道重叠。合入时须逐块核对。变更落在专用工作树。

| R3519 证据中的原边 | 当前状态 |
| --- | --- |
| `infra/comfy_service.py:133 → batch_frames_tool/batch_frames.py` | R3574 移除节点探测依赖 |
| `infra/comfy_service.py:146 → batch_frames_tool/batch_frames.py` | R3574 移除参考图工作流依赖 |
| `infra/cloud_assets.py:70 → batch_frames_tool/batch_frames.py` | R3582 改用同层 `infra.http_client.LocalComfyClient` |

云资产图引用的图片仍提交给本机 ComfyUI 的 `/upload/image`。原批处理 `Client` 从同一个客户端继承上传实现。切换后每张图仍发送一次请求，沿用 multipart 请求头、无 Authorization 头、超时、响应解码和错误传播。云账户密钥读取、参考图路径校验、节点连接和画幅优先级沿用现有流程。上传没有第二个实现或网络写入点。

## 验证

- 改码前边界红测唯一失败为 `AssertionError: [('cloud_assets.py', 70, 'batch_frames_tool')] != []`。断连和成功解码测试在基线通过。改码后覆盖一次 POST、30 秒默认超时、断连的 `ValueError` 传播、无第二次请求，以及多个参考图的响应名、角色与顺序。
- 专项 157/157。包含批处理续跑、原生资产、上传与截止时间、精确工具消费者、静态与动态环、分层、HTTP 和 JSON 棘轮。严格工具审计只剩既有的 8 条发行开发文件、2 条发行生成数据和 2 条开发入口拒绝，越层集合为空。
- 默认冒烟 9/9，含 8 项业务检查与内置的 `gui_hidden.py --probe`。专用树通过只读来源使用随附解释器和 FFmpeg，补齐三个技能包固定提交并核对树哈希。
- 受影响回归 `smoke_test.py --affected batch_frames comfy_service http_client cloud_assets` 首跑 544/545。唯一失败是 `test_api_cache_usage.py:207` 在固定技能包就位前找不到 `sd-decision-engine/SKILL.md`。补齐后串行复跑失败模块 15/15，受影响用例逐项有通过记录。首跑 Tk 用例在隐藏桌面执行。
- 行覆盖目标 115/115，83/662 个模块有行覆盖，与 R3574 口径相同，11 个核心路径的实测结果均达到既有下限。
- 分支覆盖保留 R3574 的目标并追加画幅与上传用例，隐藏桌面执行 1781 条，1779 条通过、2 条登记跳过。94 个模块全部达到现有下限，1543/2737 个决策点双结果覆盖，`http_client.py` 实测 80.0%。覆盖率阈值和仓库快照保留原值。

## 完整架构比较

终态完整架构 601/603，404.240 秒，退出 1。对照本轮起点 R3574 的终态 601/603，失败项无增减。

| 失败项 | R3582 实测 |
| --- | --- |
| `DependencyWhitelistTests.test_site_packages_whitelist` | 随附解释器的 purelib 仍有 `annotated-types`、`pydantic`、`pydantic-core`、`typing-extensions`、`typing-inspection` |
| `RoundBaselineTests.test_round_number_continuous` | 本树继承状态页轮次 3409，最新结果轮次 3582，期望 3583。状态页按规则只能在主干同步 |

首轮架构启动后继续编辑，扫描过程中读到了变化中的文件，因此比较使用 R3574 的有效历史实测与本轮终态完整实测。

按规则通过 `dev.py commit` 保存 `R3582-FAIL` 检查点。实际提交哈希由 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_3582_result.md` 定位。机器凭据使用已完成的绿色专项输出及暂存范围凭据扫描生成，见 [R3582.json](evidence/R3582.json)。

## 交接

A10 剩余 ASR 独立协议工作沿用 R3519 的实际分发和进程闭包证据。待接续核对 stdio JSON-Lines 版本协商、客户端和服务端读取边界，以及安装进程的独立消息边界，回归取消、停止超时和退出。关联 A15 的发行拒绝已在 R3519 留档。本轮范围止于云资产上传边。
