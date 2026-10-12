# R1374：O47 关键真实链路集成测试（配置→请求→响应→采用→下游）

类型：验证/基线轮（§3.10；本项「验证／建议」→ 为关键真实链路补集成测试，不改业务逻辑）。承接 R1267 清单 O47（O01—O46 已完成）。中央轮次 1374（`.git/round-counter.json` 的 `last_claimed=1374`）。本轮 1374 − last_full_safe_all_round(1373) = 1 < 5，无五轮欠账；改动未命中 §5（只新增测试文件，无启动路径、无 Tk 控件生命周期、无删除语义、未改 `tests/architecture/_layers.py`）。

## 三个必答
- 本轮类型：验证/基线轮。
- 测试：新增 `tests/test_critical_chains.py` 17/17；定向 `-k critical_chains recycle audio_import stage_completion delivery_import script_contract stage_flow` 187/187；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；均 0 红。
- 欠账：O47 关闭，清单剩 O48；1374 − 1373 = 1 < 5，无五轮欠账；未命中 §5，收口跑一次干净 master 全量（结果见「全量判定」）。

## 目标（R1267 清单 O47）
- 依据：历史有数千条全量测试及定向回归，但最新树没有对应全量凭据；R1267 当时也未运行真实 API、CLI/桌面往返及完整成片链路。
- 建议：分层建立配置→请求快照→实际发送→响应保全→阶段采用→下游成果的集成测试；媒体链路用可重复小样本，加失败注入、断电恢复、跨集隔离和干净安装。真实付费服务单独受控抽样，不默认每轮全量调用。
- 验收：优先覆盖 O01–O12/O38/O39；行为断言替代易漂移的固定行号定位，但不得弱化契约断言。

## 实现（四条真实链路 + 两条门禁，17 条用例）
无生产代码改动；只新增 `tests/test_critical_chains.py`。全部使用合成数据与注入的传输／发布器，不调用真实付费 API、不依赖 Tk 界面；断言只依赖公开行为与不变量。

1. 链路 A：回收站安全语义（O38/O39，`RecycleChainTests` 5 条）
   - 写前计划→逐项移动→提交：`recycle_paths` 两项后原位置清空、批次清单 `state=committed`、`read_recycle_batch` 逐项只有 `source`/`recycle_path`、`restore_recycle_batch` 复原且字节一致。
   - **失败注入**：patch `move_planned` 第 2 次抛 `OSError` → 整批回滚（`state=rolled_back`）、两文件都在原位、字节不变、异常重抛。
   - `version_retention` 六类保留原因：未结算/未知→`unsettled`、锁定→`locked`、进成片来源（按 `(镜头,版本)` 或 `(镜头,sha256)`）→`edit_source`、已验收→`approved`、最新→`latest`、未过保留期→`fresh`、可回收→空串。
   - `edit_source_versions` 从 `13质检交付/导出成片` 的 `edit_bundle.json` 读出被引用的 `(镜头,版本)` 与 `(镜头,sha256)`。
   - `clean_project` 只处理「下载根下且含 `config.json`」的项目，且回收（写 `committed` 批次）而不永久删除。
2. 链路 B：模型请求链（`ModelRequestChainTests` 5 条）
   - 实际发送：URL＝`base_url + /chat/completions`、头 `Authorization: Bearer …`、payload `{model, messages, max_tokens}`（system 前缀在最前）、**密钥不出现在 payload**。
   - 响应保全：`response_meta` 白名单（requested_model/wire_api/response_id/finish_reason/response_shape/message_fields/reasoning_fields/reasoning_lengths/content_length）。
   - 用量：`usage_of` 把 `prompt_cache_hit_tokens` 映射成 `cached_tokens`；`Ledger.record/hit_rate/flash_share` 按 token 与条目口径复算。
   - 诊断：`model_diagnostics.record` 落 `model_diagnostics/`，磁盘 JSON **不含任何正文**（提示词、响应正文、推理正文都不落盘），只留长度、形状与用量。
   - 超时：注入抛 `TimeoutError` 的传输返回 `ok=False`／`error_class=timeout`／空 text／status 0，不抛异常。
3. 链路 C：导入→发布→阶段采用→完成证据（O02/O03，`ImportToCompletionChainTests` 3 条）
   - `import_audio` 把文件发布到 `11配音与字幕/音频/<名>_<uuid6>.wav`，**源文件保留**；导入本身**不构成完成证据**；`prepare_media_completion` 得到 `pending_review` 且仍不完成；`confirm_media_completion` 后才 `completion_evidence` 真。
   - 非对白音轨（`kind=bgm`）不能顶替对白完成（明确报错）。
   - `import_delivery_master` 把成片发布到交付阶段目录，源文件保留。
4. 链路 D：剧本→结构→分镜下游（`ScriptToStoryboardChainTests` 2 条）
   - 自然剧本经 `write_structured_script` 由本地规则（未调用模型）生成结构稿到 `02剧本结构/结构剧本`，`is_structured_script` 与 `verified_stage_output('script_structure')` 为真，自然剧本**原样保留**。
   - `completion_evidence('storyboard')`：已采用但无镜头不算完成；换成含镜头的采用分镜后才算完成。
5. 门禁 O04（`VideoReworkGateTests` 1 条）：`video_task_state.submission_block_reason` 只放行「首次提交／已失败重试／已下载且显式 `revise`」，已下载未标 revise 与未决（unknown/running/queued）都拦。
6. 门禁 O05/O06（`KeyframeGateTests` 1 条）：`stage_parallel.frames_ready` 对未配置／已删除／越界／缺失／空文件／损坏 PNG 六类逐镜给原因，`ok=False`、`started=True`，不会漏成「首帧都在」。

## 契约变化
- 无生产契约变化（纯测试轮）；新增测试只断言既有公开行为，未放宽任何断言。
- 记录两条本轮实测的既有契约事实（供后续勿误判）：①`completion_evidence` 对 `script`/`script_structure`/`storyboard` 返回的 `detail` 是固定的「未找到」文案，完成判据只能看 `ok` 布尔；②`stage_parallel.frames_ready` 在「一个可用帧都没有、且 `keyframe` 阶段未跑过」时按既有的「上游还没做先不拦」返回 `ok=True`，因此首帧门禁用例必须包含至少一个真实非空帧文件才会走到拦截分支。

## 测试
- 新增 `tests/test_critical_chains.py` 17 条（上列 A5+B5+C3+D2+O04 1+O05/O06 1）。
- 定向 `-k critical_chains recycle audio_import stage_completion delivery_import script_contract stage_flow` **187/187、0 红**（含既有 `test_recycle_*`／`test_audio_import_service`／`test_stage_completion_service`／`test_delivery_import_service`／`test_script_contract`／`test_stage_flow`，证明新增测试与既有回归无冲突）。
- 架构 `--layer architecture --all` **312/312**（与基线一致，只增不减；未新增架构测试，故未改 §5 清单）。
- 默认冒烟 `smoke_test.py` **8/8**。
- 未新增 `skipTest`，未改 `tests/architecture/_layers.py`。

## 边界
- 真实付费服务**不实测**（O47 明确「单独受控抽样、默认不实测」）；模型链用注入传输，覆盖「配置→请求→响应→保全」但不发真实请求。
- 断电解恢复用「写前计划＋失败注入」覆盖（链路 A），未做真实进程 kill；跨集隔离与干净安装在 O07/O29/O45 等专项已有各自回归，本文件不重复。
- **未覆盖** O01、O07–O12 的专项行为（未结算资产保留、白模身份、预理路由、资产确认事务、确认内容绑定、TTS 缓存身份等）：本轮没有改动这些模块的生产代码，也不声称本文件替代它们的验收；`tests/test_critical_chains.py` 只补「跨模块关键链路」的集成证据。
- 断言均以行为与不变量为准，不锚定易漂移的行号；`completion_evidence` 的 `detail` 文案只在 `ok=False` 时有意义，故 D 链只断言 `ok`。

## 全量判定
- 待收尾补记。

## 提交
- 待收尾补记。

