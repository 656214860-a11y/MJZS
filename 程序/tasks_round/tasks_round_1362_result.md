# R1362：O37「测试连接成功」与完整工作流支持分开

类型：功能轮（§3.1；本项为「事实／验证」→ 实现＋回归）。承接 R1267 清单 O37（O01—O36 已完成）。中央轮次 1362（在干净 master 工作树 o07-fullsafe-master 领取）。本轮 1362 − 1361 = 1 < 5，未命中五轮欠账，也未命中 §5 全量升级条件（未改启动路径／Tk 控件生命周期／删除语义／层级登记表），按 2026-10-12 验证策略本轮不跑全量。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 -k model_pool pet_models model_router model_diagnostics pet_ui token_saver request_ledger model_probe_layers 771 条（1 红为主树本地未跟踪用户配置所致，见「边界」）、新增 tests/test_model_probe_layers.py 16/16、-k pet_settings copy_rules line_endings skip_hygiene model_probe_layers model_pool（2 红同为主树既有环境项：未跟踪配置的桌面模型标签＋主树 desktop.py 行尾）、架构门禁 --layer architecture --all 312/312、默认冒烟 smoke_test.py 8/8、默认增量运行 1 红（同一环境项）。
- 欠账：O37 关闭，清单剩 O38—O48；1362 − last_full_safe_all_round(1361) = 1 < 5，本轮不欠全量，未命中 §5，无需复用 7 日凭据。

## 目标（R1267 清单 O37）
- 证据：model_pool.py 用最小 ping（PROBE_TOKENS=16）判断响应 ok；该结果不能证明长文本、流式、中断、工具或阶段文档都可用。
- 建议：配置页分展示连通性、协议、模型 ID、能力声明和最近完整任务结果；CLI／API／桌面分别检查，不自动探测产生大量费用；第三方标签不应替代实际请求模型标识。
- 验收：伪兼容协议、仅 reasoning 无正文、流式中断、超长输出、模型切换均有针对性检查；真实服务用用户选择的小样本验证，并记录配置版本。

## 实现（model_pool.py，L1）
- 新增分层常量：PROBE_DIMENSIONS（connectivity／protocol／model_id／capabilities／full_task 五维）、PROBE_DIMENSION_LABELS、PROBE_FULL_TASK_STATE＝「未验证」、PROBE_FULL_TASK_NOTE、PROBE_WIRE_FIELDS（各协议一次可用响应该有的字段）、VERIFY_TOKENS＝64、SAMPLE_PROMPT、TASK_TRUNCATED（length／max_tokens／max_output_tokens）、HEALTH_KEY＝「model_health」。
- 新增 config_version（协议·地址·模型 ID·密钥名的当前生效身份，不含密钥值）、request_spec（测试连接与小样本验证共用同一份地址／请求体／请求头拼法）、body_signals（只取响应形状、服务端 model、是否有正文与推理字段，绝不带正文）、_full_task_check、classify（把一次结果拆成五维：连通／协议／模型标识／能力声明／完整任务，未联通时不谎报协议或完整任务）、probe_summary、health／health_of／record_health。
- probe()：改经共享 request_spec 发最小请求，返回体在原有 ok／status／error／model／url／ms／usage_note 之外追加 config_version／signals／checks／summary／full_task；最小请求的「完整任务」一维恒为「未验证」，不进绿灯。原有键与「连接成功，延迟 N ms」语义不变。
- 新增 verify_sample()：用户点名才发一次真实短请求（SAMPLE_PROMPT，max_tokens＝VERIFY_TOKENS），按 full=True 判完整任务——正文为空（如仅推理）判失败、finish_reason 属截断判失败、error 含取消／中断判「流式／请求被中断」、服务端 model 与请求不一致在模型标识一维标异常；返回含 config_version／content_length／finish_reason／checks。

## 实现（pet_models_ui.py，L4）
- 新增 probe_breakdown（把探测结果按五维分行＋配置版本＋最近完整任务）、verify_line（跑一次小样本验证并把结果经 record_health 落到该模型名下）；probe_line 保留「连接成功，延迟 N ms」那句，其后追加同一份分层说明；probe_all 的提示改成逐条分行。
- 模型配置页在「测试连接」旁新增「小样本验证」按钮：只在「默认模型」选中的那一条上发一次请求（AUTO 或池里没有该条时只提示、不发送），不批量、不自动，避免产生大量费用；页面 seam 增加 probe_sample。

## 契约变化与同步
- probe 返回体为纯追加（checks／summary／config_version／signals／full_task）；既有断言（ok／status／ms／url／error／usage_note）不受影响。
- tests/architecture/test_unification_ratchet.py 第四项以「文件:行号」记身份，本轮 model_pool.py 新增函数使既有豁免项（裸 json.loads，非文件读取）由 576→808、613→845 位移，同步更新 程序/维护记录/架构统一基数.json；未新增裸 json.loads、未改扫描集合。
- 未新增顶层模块，tests/architecture/_layers.py 未动，层级登记表未变。

## 验证
- 新增 tests/test_model_probe_layers.py 16 条：五维分层且最小探测的完整任务恒「未验证」；伪兼容协议（200 但无该协议字段）标协议异常；仅 reasoning 无正文在能力声明标异常、小样本验证的完整任务判失败；超长输出（finish_reason=length）判「截断」；流式中断（请求已取消）判「中断」；服务端换模型在模型标识标异常、一致则通过；死端点不谎报协议／完整任务；Anthropic messages 形状算协议兼容；config_version 含协议／地址／模型 ID／密钥名；verify_sample 只发一次真实短请求（样本提示＋VERIFY_TOKENS）并带 config_version；record_health／health_of／health 往返且多模型互不覆盖；probe_breakdown 列全五维＋配置版本＋最近完整任务；probe_line 仍含「连接成功，延迟」。
- 定向 -k model_pool pet_models model_router model_diagnostics pet_ui token_saver request_ledger model_probe_layers 共 771 条，1 红：test_model_pool.RecordTests.test_desktop_options_are_marked_only_when_the_shared_probe_cannot_find_them（主树未跟踪 程序/配置/宠物/配置.json 的 claude-desktop 记录带一个本机不存在的 program 路径，desktop_model_label 追加「（未安装）」；同一 HEAD 干净工作树该用例绿，既有环境项）。
- -k pet_settings copy_rules line_endings skip_hygiene model_probe_layers model_pool：copy_rules／pet_settings／skip_hygiene／model_probe_layers 全绿；2 红同为主树环境项——上述桌面模型标签，及 test_line_endings 的 desktop.py（主树工作树 LF，属性钉 CRLF；干净工作树绿）。
- 架构门禁 --layer architecture --all 312/312（0 红）；默认冒烟 smoke_test.py 8/8；默认增量运行 1 红（同一桌面模型标签环境项）。

## 边界
- 「连接成功」与「完整工作流可用」彻底分开：最小请求（测试连接）只证明连通与鉴权，完整任务一维恒「未验证」；只有用户点「小样本验证」发一次真实短请求才判完整任务。
- 小样本验证仍是单次短请求，不覆盖长文本上限、真实流式通道、工具调用与阶段文档级负载；这些留待后续路线图条目，本轮不假装覆盖。
- body_signals 只取元数据（形状／长度／字段名／服务端 model），不保存或回传正文与密钥，沿用「诊断不存正文」口径。
- 不新增自动探测；不新增 skipTest／裸 json.loads／L2 直写／动态导入；未命中 §5。

## 全量判定（本轮不跑的依据）
- 1362 − last_full_safe_all_round(1361) = 1 < 5，未命中五轮欠账；本轮改动未触及启动路径、Tk 控件生命周期（销毁／重建）、删除语义（storage_maintenance.py）、层级登记表（tests/architecture/_layers.py），不触发 §5 升级条件。
- 复用检查：.git/full-safe-receipts.json 现含 round=1361、tree=3e20f7c4b6a743ce8718878c15163c8cb1a8afec 的绿全量，但本轮不需要全量，故不涉及复用；本轮全量为 0 次。
- 无阈值抖动项（test_desktop_startup_perf／test_perf_baseline）出现，无需定向复测。
