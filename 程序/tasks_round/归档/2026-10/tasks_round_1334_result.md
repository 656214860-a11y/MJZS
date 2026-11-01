# R1334：O12 TTS 批次冻结配置与缓存身份

类型：功能轮（§3.1），承接 R1267 清单 O12（O01—O11 已完成）。中央轮次 1334。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 49/49（`tts`）、关联 115/115（`ui_edges`）、架构相关 12/12、默认冒烟 8/8，全 0 红。
- 欠账：O12 关闭，清单剩 O13—O48；本轮号 1334 − 上次绿全量 1330 = 4 < 5，且改动不命中 §5 升级条件，按用户 2026-10-12 指令本轮不跑全量。

## 问题
- 逐句签名的比较字段只有 `shot_id／text／voice／speed`（`line_done`），`build_lines` 也不带模型或服务商——换了模型／换了 endpoint 之后，旧成品仍被判成「这一句已经好了」，直接沿用旧语音。
- `synthesize` 每次合成时重新 `read_settings()`：长批次中途改了设置，同一批里前面几句按旧配置、后面几句按新配置，混用两套。
- 整段配音的指纹只有 text／model／voice，没有服务商端点：同一个模型 ID 在两个服务商上会被当成同一份缓存。
- `line_done` 只判「文件在不在」，截断或损坏的成品也算已生成；批次记录里也没有留下这一批用的是哪套配置。

## 实现
- `request_identity(settings, voice, speed)`：一次请求的身份（**不含密钥**）= 服务商端点＋模型唯一 ID＋音色＋语速（本客户端唯一发出去的采样参数）。`build_lines(..., settings=)` 把身份写进每一句，`LINE_IDENTITY_FIELDS` 一并进入 `line_done` 的比较与 `batch_signature` 的哈希。
- `freeze_settings(lines, settings)`：开批时冻结有效配置——清单里已经写死的端点／模型优先，清单没有才读当前设置；`run_lines` 用冻结值构造默认合成器，中途改设置不影响这一批。
- `synthesize(..., settings=None)`：允许调用方传入配置（默认仍读当前设置）。
- `script_signature(text, settings)` 加入 `endpoint`：换服务商即换指纹。
- `publish_line` 记 `bytes`＋`sha256`，`line_done` 沿用前复核摘要（旧清单没记摘要时退回「文件非空」），损坏或空文件会被重新合成；`reusable_full_track` 也要求整段音频非空。
- `批次.json` 增记 `identity`（端点、模型、逐句用到的音色与语速），只记身份不记密钥。
- L4 `desktop.generate_tts_per_line` 把 `tts_settings` 传给 `build_lines`（夹具跟随新签名补 `**_kwargs`，断言未改）。

## 验证
- 新增 `tests/test_tts.py::TtsBatchIdentityTests` 6 条：`build_lines` 记身份；长批次中途改设置两句都用开批时冻结的配置；换模型／换端点都判成另一份缓存（`resume_folder` 失配、`pending_lines` 指向重做）；截断与空文件都不续用；旧清单没摘要时文件非空即沿用、空文件不沿用；密钥不进指纹／清单／批次记录，批次记录带上身份。
- 定向 `-k tts` 49/49、0 红；`-k tts audio animatic subtitle` 全绿；关联 `-k ui_edges` 115/115、0 红（`test_per_line_tts_asks_before_paying`、`test_whole_script_tts_reuses_unchanged_audio` 都过）；架构相关 `-k unification_ratchet json_io_boundary layers tts_publication_boundary todo_comment_snapshot` 12/12、0 红；默认冒烟 8/8。
- 台账无变化：`tts_api.py` 只用 `json.dumps`，不在 `json.loads` 台账里；本轮未增删架构测试。

## 风险与边界
- 升级后第一次跑逐句配音：旧批次记录没有端点／模型，`batch_signature` 会变，旧批次目录不会被复用，会重新合成一次（正确但会多花一次钱）；已写成成品的音频文件不删。
- 同理，整段配音指纹新增 endpoint 后，旧 `整段配音.json` 不再命中，会重新合成一次。
- 摘要校验只能发现「文件被换过或写坏」（sha256 对不上、空文件），不能证明音频解码正常、也不是内容审核；真正的技术核验仍属媒体校验线（O03／O18）。
- `freeze_settings` 在清单里出现两个不同端点／模型时不能冻结，退回显式传入或当前设置；这种「一单混两套」的清单本来就该在生成清单时就避免。
- 未重启应用、未实发 TTS 付费请求；单元与静态验证不等于真实扣费与听感验收。

[TASK_COMPLETE] 批次开批冻结配置、逐句与整段缓存身份含端点／模型／音色／语速、沿用前复核输出摘要；中途改设置不混用、换模型或服务商失效旧缓存、损坏音频不续用，且密钥不入签名与清单；定向 49/49、关联 115/115、架构 12/12、默认冒烟 8/8，0 红。
