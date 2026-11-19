# R3574 — A10 第三批 ComfyUI 参考图依赖归位
<!-- round-evidence: {"commit_base": "b9bd28a6", "credential_hits": 0, "evidence_sha256": "7db780f5803ed5eb", "exit": 0, "failed": 0, "passed": 145, "round": 3574, "tests": "run_selftests.py -k test_batch_frames test_execution_deadline test_comfy test_http_client test_dynamic_import_registry test_no_circular_import test_layers test_http_boundary test_unification_ratchet test_static_hygiene"} -->

1. 类型为结构治理轮。基线 `b9bd28a6`，专用工作树 `f111`，分支 `codex/architecture-a10-batch-boundary`，生产改动 3 个模块。
2. 实测与失败集合见下文。
3. 三条已知越层边消除两条，直连 HTTP 存量白名单减少一项。安全全量欠账未在本轮结算。

## 范围与变更

按 A10 复核 A3/R3409、A6/R3415、A9-8/R3519、R3541、R3543、R3565 与机器凭据。领号 R3574。范围扫描发现 `comfy_service.py` 与 L1 企业车道重叠，`http_client.py` 与 L2 任务书车道重叠，批处理模块与 foundation 两个车道重叠。只在本专用树实现，合入前须逐块核对。

| 基线位置 | 实际职责 | 终态 |
| --- | --- | --- |
| `infra/comfy_service.py:133` | 生成节点探测图以检查所需节点和模型 | 改用同层 `build_reference_graph`，越层消失 |
| `infra/comfy_service.py:146` | 上传参考图并生成单次资产工作流 | 改用同层 `LocalComfyClient` 与图构造器，越层消失 |
| `infra/cloud_assets.py:70` | 构建云资产图前上传本地参考图 | 导入仍存在。继续修改将触及第 4 个生产模块 |

`batch_frames_tool` 仍负责批处理与回执恢复，保留 `graph`、`Client` 和独立启动入口。`infra/comfy_service.py` 提供图构造。`infra/http_client.py` 承接本机上传、请求和响应解码，保留禁止代理和跳转、异常文案、读取上限、超时预算。连接仍由原调用路径发起。

## 验证

先执行边界红测和断连行为测试。边界列出原 `comfy_service.py:133` 和 `:146`，断连测试基线通过并固定单次请求、错误传播语义。

- 终态专项 145/145，包含批处理部分失败续跑、回执恢复、截止时间、上传断连、静态与动态环、上下层边界、直连 HTTP 和 JSON 棘轮。共享本机传输沿用单次 `open`，原批处理回执查询仍由原入口驱动。
- 默认冒烟 9/9，含 8 个业务检查与隐藏桌面探针。首跑定向回归因专用树缺少 FFmpeg 报错，随后复用随附 FFmpeg，通过测试进程 PATH 提供。三个固定技能包按仓库锁定 commit 检出并核对 tree hash。
- `smoke_test.py --affected batch_frames comfy_service http_client cloud_assets` 首次重跑等待共享 GUI 令牌超过 900 秒。令牌释放后在隐藏桌面重跑，542/542，通过 9 项、失败 0 项，覆盖云资产、画幅、原生资产、首帧、视频和 UI 路径。
- 首版结构验证发现 JSON 解码落在 `comfy_service.py` 会形成新棘轮项。将解码跟随本机请求迁到 HTTP 权威模块，再删除已无调用点的原棘轮条目，未新增豁免。
- 原行覆盖目标 115/115，83/662 模块有行覆盖。分支覆盖保留原 91 组目标，并加入已有批处理和执行期限测试。1775 条执行，1773 条通过、2 条跳过。94 个计量模块均达到原下限，1535/2737 个决策点双结果覆盖；`http_client.py` 实测 75.0%，原下限 58.0%。两份快照按实测刷新。

## 完整架构比较

R3565 在同一源码起点 `b9bd28a6` 实测 599/602，失败集合为性能历史文件缺失、随附 Python 环境包超出白名单、功能分支轮次连续性。本树从共享工作区只读复制了 Git 忽略的性能历史缓存，并核对字节哈希，专项已转绿。状态页提交门禁要求仅 master 更新，本分支保留继承的轮次头，留待授权的合并轮同步。

终态完整架构 601/603，400.346 秒，退出 1。较 R3565 无新增失败，`test_performance_history_is_declared_as_historical_only` 转绿。剩余 `test_site_packages_whitelist` 检出随附环境多出的 `annotated-types`、`pydantic`、`pydantic-core`、`typing-extensions`、`typing-inspection`，`test_round_number_continuous` 检出功能树继承的状态页轮次 3409。按规则保留 `R3574-FAIL` 检查点。标准机器凭据见 [R3574.json](evidence/R3574.json)。

## 交接

剩余 `infra/cloud_assets.py:70` 可改用 `infra.http_client.LocalComfyClient`。将云资产和画幅测试的上传替身跟随实际消费者，复验引用顺序、路径校验、上传失败和请求次数。更新 A9-8 生产消费者精确台账并扫描严格门禁剩余集合。此交接仅记录范围。
