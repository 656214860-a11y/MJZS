# R1200 修复轮：剧本准备模型输出额度与截断判定

- 类型：修复轮（含全量基线验证），承接 R1199 的只读诊断和用户“修复”授权。
- 测试：定向 129/129；默认冒烟 8/8；受影响冒烟 9/9。最终安全全量 4283/4283，539.0 秒（含架构 311/311）。
- 状态欠账：本轮修复不扩展历史清理 J1～J8；主目录正式全量凭据历史仍为 R1160，不将隔离分支实测冒充 master 同树验收。
- 提交：实现 2592ea8；既有架构位置登记 e1f2d26；最终归档提交由 Git 回执索引。

## 根因与修复

R1199 已证实：HTTP 200 不代表完成。writer_revision 在 completion_tokens=8192、finish_reason=length 时没有可见正文；更早的导演计划同样 length，但旧代码见到非空正文就放行。

1. hollmwood_roles：仅已知 deepseek-v4-flash / deepseek-v4-pro 的四角色、审核与修订请求采用 32768 输出上限；其他型号原有 4096/8192 不变。输出上限覆盖推理和正文，不保证每次生成均能完成。
2. finish_reason=length 一律不能作为有效角色成果，不因正文非空或包含 APPROVED 放行。不增加截断重试；既有导演空正文最多补发一次、创作角色只请求一次仍保留。
3. 空正文错误保留安全响应元数据；额度耗尽明确展示 max_tokens 与 length。修正创作角色明明未补发却标记 retried_once=true 的错误诊断。日志和界面错误不输出推理正文。
4. model_pool → model_router 的 SSE 路径保留真实 finish_reason；演员流式输出也能识别截断，失败稿不发布为正式剧本。

官方参数依据：[DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/) 与 [官方 Crush 配置示例](https://api-docs.deepseek.com/quick_start/agent_integrations/crush/)；后者为 V4 Flash/Pro 给出 32768 的默认输出配置。本轮不改用户模型名、思考开关、供应商配置或密钥。

## 断言变更登记

- 原 test_content_roles_use_8192_and_empty_response_is_not_retried 改名为 test_other_models_keep_8192_and_empty_response_has_budget_diagnostics：保留单次请求和原额度断言，新增 length、max_tokens、未补发标记和私有内容不泄漏断言。
- 新增 V4 导演/创作修订/审核/演员预算检查；新增非空截断拒绝与不补发检查。
- 新增真实 SSE 字节 fixture → HTTP 解析 → adapter 结束原因透传检查。
- 新增 writing_api 演员流式截断集成检查：返回失败、停止继续审核、正式剧本发布器未被调用。
- 未修改 ROLE_ORDER、MAX_REVISIONS、run 串行接力、SKILL、brief 契约或既有审核往返次数。

## 实际验证

- 测试先行：新增 3 条测试在原实现产生 9 个子场景失败，确认预算不足、截断放行和 SSE 丢失结束原因。
- 定向：run_selftests.py -k hollmwood model_router_diagnostics model_pool writing_api，129/129，1.9 秒。
- smoke_test.py：8/8；smoke_test.py --affected hollmwood_roles model_pool model_router：9/9。
- 新增写入边界测试初次使用了不存在的 mock 目标；改为现有 _write_script_raw 后定向全部通过，没有更改生产写入边界或降低断言。
- 首次安全全量：4283 条，546.5 秒，仅架构统一棘轮 1 处失败；model_pool.py 既有 SSE JSON 解析从 582 行移到 583 行，登记表只同步行号，未改变豁免理由、数量或门禁断言。随后先定向复验失败项及角色/接口相关测试 71/71 通过，3.2 秒。
- 最终安全全量：干净 e1f2d26 执行 run_selftests.py --all --safe --gui-jobs 1，4283/4283、539.0 秒、exit=0，含架构 311/311。程序树 750b261fa3d5faae980b6e35391dd8d8df26d02a；分支实测，不生成 master 正式凭据。
- 临时验证日志位于系统 TEMP 的 R1200-*.log，不新增项目运行日志。

## 自审与限制

- 本轮范围：3 个既有生产模块、3 个既有测试文件、既有架构登记的一处行号及必要结果/状态/接力文档，无越界依赖。
- 同类复核：非空导演/审核/创作截断与演员流式路径均覆盖；其他模型参数保持原口径。
- 实际计费取决于生成 token；提高上限可能增加极端请求耗时和费用，不是每次固定消耗 32768。180 秒调用超时不变，未新增无限重试。
- 未实发付费 API、未重启真实应用、未改用户项目数据。需下次应用重新加载代码后以实际调用确认服务端生成结果；测试不承诺模型永不截断。
- 用户六项原改动在合入时逐项哈希核对；最终文档树和含用户改动的主目录不冒称同树全量。
- 自审：通过。根因修复、适用验证、范围与同类截断边界均已核验；run 函数 AST 与修复前一致。

[TASK_COMPLETE]
