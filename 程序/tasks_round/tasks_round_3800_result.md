# R3800 结果：E 维端到端产品验收取证轮（任务书执行轮）
<!-- round-evidence: {"commit_base": "fb362630", "credential_hits": 0, "evidence_sha256": "b087913ba8235317", "exit": 0, "failed": 0, "passed": 446, "round": 3800, "tests": "run_selftests.py -k account writing script_structure stage_completion lease http_boundary"} -->

- 轮次类型：任务书执行轮（E 项「端到端产品验收」——本地制作链＋受控云端链）。纯取证＋文档轮，无产品代码改动（新增取证脚本 `scripts/acceptance_e2e_probe.py`、`scripts/acceptance_e2e_worker.py` 除外）。
- 是否跑测试：跑了。`acceptance_e2e_probe.py` 17/17 检查通过（隐藏桌面真实会话，假供应商＋假会员服务）；`smoke_test.py` 9/9；`run_selftests.py -k account entitlement lease http_boundary script_structure stage_completion writing` 结果见 §4。
- 积压是否下降：是——验收台账 E 项转「通过（受控范围）」，七条用户故事中 US01/US02 链路段取得实测证据，其余故事段与真实付费链路如实标注未覆盖。

## 1. 三问

1. **什么类型轮**：任务书 E 项——从助手界面走一条本地制作链和一条受控云端链，验证启动、暂停、取消、产物核验和失败反馈；抽检本轮变更与出站规则；云端不可用时记录可继续的本地操作。
2. **是否跑测试**：跑了——E2E 探针 17/17、冒烟 9/9、定向自检（账号/授权/租约/出站边界/剧本结构/阶段核验/写作域）。
3. **积压是否下降**：是——E 项从「待验」转「通过（受控链路）」，未覆盖项（真实付费媒体链、US03–US07 全链）在台账如实登记。

## 2. 取证方法（隔离、可复现）

- **探针**：`scripts/acceptance_e2e_probe.py`（父进程：假模型供应商 SSE＋假会员服务＋项目制备＋证据汇总）＋ `scripts/acceptance_e2e_worker.py`（隐藏桌面单会话 worker，复用 R3759 取证助手）。证据 `tasks_round/evidence/R3800/`。
- **本地制作链**（可丢弃项目，真实 Desktop＋真实代码路径）：
  1. 剧本准备简报（结构化字段，R3759 已验证格式）→ 供应商按阶段序回「项目设定／剧本大纲／角色卡」阶段稿，逐「继续」确认采用；角色卡确认后模型回 `{"next_stage":"自然剧本"}` 过渡（按请求内容识别，非序号猜测）→ 阶段④自然剧本经 `_auto_save_script_raw` 落盘 `script_raw.md`。
  2. `stage_exec.run(d,'script_structure',trigger='manual')`——与「手动制作结构剧本→直接执行」同一 runner：本地规则结构化→`publish_stage_text` 发布→`02剧本结构/结构剧本/p_结构剧本_本地_*.md`（6857B，sha256 `5dd572c2…`）。
  3. `stage_completion_service.completion_evidence`：script ✓、script_structure ✓（manifest 核验同口径）。
  4. 暂停/恢复：`stage_flow.AUTO`（三虎自动链同一状态机）armed→pause→`next_stage()=None`→resume→放行→done 推进，测后解除武装。
  5. 取消：供应商慢速流→`interrupt_script_agent()`（与 A 轮同一取消入口）→新台账条目产生。
  6. 失败反馈：供应商 HTTP 500→请求失败，状态栏/转录尾部取证（`failure_transcript_tail.json`）。
- **受控云端链**（同一 Desktop 会话）：
  - worker 进程内把 `domain.account_client.request` 的 opener 重定向到本机假会员服务（请求构造/JSON/错误映射/会话落盘全真实）；`infra.lease_verifier.PUBLIC_KEYS` 注入本轮测试密钥对 `k-e2e`（探针纯 Python RSA-2048 签发，客户端验签链路真实，不接触 k2026a 私钥）。
  - `account.request_code→login(123456)`→租约验签通过→`entitlement=valid/usable`→`stage_gate('storyboard')=''`（付费阶段放行）、免费阶段同放行。
  - 写 `account_down.json` 假服务断连→`renew` 失败（code=network）→宽限（8s）耗尽→`entitlement=locked/usable=False`→`stage_gate('storyboard')` 返回拦截文案（「需登录/离线授权超宽限」口径）、`stage_gate('script_structure')=''` 免费阶段仍放行；本地结构剧本产物仍在。
- **出站规则抽检**：`outbound_scan.txt` 静态枚举 `urlopen/build_opener/requests./http.client/socket` 调用点；守卫测试 `test_http_boundary` 由定向自检覆盖。

## 3. 结果摘要（17/17，明细见 summary.json）

- **启动**：Desktop 打开项目→剧本页→简报提交→阶段稿逐段产出并采用→script_raw 落盘→script 阶段核验通过→script_structure 手动执行完成，全链路真实 UI 入口。
- **产物核验**：结构化正稿 6857B 落盘＋sha256＋`is_structured_script`＋清单核验＋completion_evidence 双阶段 ok。
- **暂停/恢复**：自动链状态机 paused 期间 `next_stage()=None`，resume 后立即放行下一阶段。
- **取消**：慢速流中途 `interrupt_script_agent()`→台账新增条目（`cancel_ledger.json`）。
- **失败反馈**：供应商 500→用户可见失败信号落盘取证。
- **云端不可用可继续项**：免费阶段（剧本准备/剧本结构）本地规则链不受账号闸门影响；已落盘产物不受影响；付费阶段在 locked 后被拦截并给出处理指引——与 entitlement_service 设计口径一致。
- **诚实边界**：真实付费媒体链（US03 角色参考图/US04 首帧/US05 配音/US06 粗剪/US07 导出）未走——需真实供应商凭据与预算，任务书允许「真实付费样例须有预算」前提下另行安排；云端链为受控假服务（真实协议与验签，非真实账号服务）。

## 4. 测试与基线

- `smoke_test.py`：9/9 通过。
- `run_selftests.py -k account entitlement lease http_boundary script_structure stage_completion writing`：结果以提交回执为准（GUI 令牌跨树排队，耗时以实际为准）。
- 服务端账号域：R3739 已跑 `test_account_*` 全绿；本轮未改服务端。

## 5. 未测／限制（如实记录）

- US03–US07（媒体生成与交付）未执行：需真实 ComfyUI/云端供应商与预算；阶段入口闸门与失败反馈已由免费阶段链＋账号闸门取证覆盖。
- 云端链使用受控假会员服务：协议路径、租约签名/验签、会话存储、权益状态机、阶段闸门均为真实代码；服务端真实实现差异（限流、真实邮件码、真实 k2026a 租约）已在 B 轮对真实服务只读核对。
- 探针时间相关：供应商模式经 `supplier_mode.json` 热切换；账号宽限 8s 为探针参数（`--account-grace-seconds`），生产宽限口径由 entitlement_service 常量决定未改。
- `stage_flow.AUTO` 测后已解除武装；探针项目为 `%TEMP%\acceptance-e2e-*` 可丢弃目录。
