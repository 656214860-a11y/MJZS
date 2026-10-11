# R1248 修复结果：Anthropic 原生剧本截断识别

- 类型：修复轮（含全量基线验证）。中央唯一入口领取 R1248；本任务无对应队列 ID，不占用 R1247。
- 测试：新增 4 条测试修复前 16 个子场景失败，修复后 4/4；关联回归 80/80、6.1 秒，受影响冒烟 9/9（含默认 8/8）。完整安全全量 4356 条、500.4 秒，1 条既有测试报错，未通过。
- 欠账：历史正式全量 R1242；本轮触发五轮周期，需真实全量凭据闭环。

## 根因与修改

Anthropic Messages 的 stop_reason 未进入 ModelAdapter.response_meta.finish_reason，HOLLMWOOD 又只拒绝 length，导致 max_tokens 的部分正文被当作成功结果继续审核。普通原生工具对话也未检查截断，可能进入自动保存。

仅修改 model_router.py、hollmwood_roles.py、writing_api.py：保留原生 stop_reason；四角色同时拒绝 length/max_tokens 并报告真实原因；普通原生分支在工具执行及采用前返回明确失败。原生 /v1/messages、独立 system、x-api-key、输出额度及既有导演空正文重试保持不变，不切换到 OpenAI 兼容协议。

新增 tests/test_anthropic_script_truncation.py，经真实适配器和本地假传输验证十类角色、正常完成对照、普通回复不保存、演员截断不发布。未削弱任何已有断言。架构 JSON 内存解码登记仅随插入同步 writing_api.py:362→367，分类和豁免理由不变。

## 验证与边界

- `run_selftests.py -k anthropic_script_truncation`：修复前 4 条、16 个失败子场景；修复后 4/4、0.8 秒。
- `smoke_test.py --affected model_router hollmwood_roles writing_api anthropic_script_truncation`：80/80、6.1 秒；含等待 GUI 令牌的门禁总耗时 73 秒；冒烟 9/9。
- 不读取或修改用户密钥、模型配置和已有剧本；未实发 API、未重启、未 push。
- 实现提交 `47f743f`，已同步主目录；状态检查点 `668c2cd`。
- 干净 master `668c2cd` 执行 `run_selftests.py --all --safe --jobs 4 --gui-jobs 2`：4356 条、500.4 秒；架构 311 项无失败；`test_script_agent_delivery_assembly.test_enabled_api_still_uses_roles_run_with_rhythm_and_rules` 报错。日志未报告跳过；Tk after 回调警告单独保留，不能视作失败闭环。
- 失败原因：测试第 94 行调用 `writing_api.reply` 未注入发布器，R1244 增加正式发布后 `_save_formal_script` 调用 `None`，触发 `TypeError: 'NoneType' object is not callable`。独立运行该测试文件 3 条仍有同一处报错。原断言未改，未用成功凭据替代本轮失败。
- 日志：`%TEMP%/r1248-full.log`、`%TEMP%/r1248-assembly.log`。完整测试使用 `%TEMP%/r1248-native-fullsafe`，不包含主目录另一任务的未提交改动。已恢复本地引用仓库及忽略的性能基线文件，无网络 API 调用。
- 自审：原生协议及预算不变；截断前置阻断工具执行/发布；真实适配器假传输覆盖正常与截断分支；只暂存本轮文件，保留另一任务改动。
- 阻塞：已按 AGENTS.md §8.6 请求授权，待允许后仅补齐既有测试发布器注入，保留全部原断言，复测并重新完成全量。当前任务尚未完成，正式成功全量仍为历史 R1242。

[TASK_BLOCKED]
