# R1248 修复结果：Anthropic 原生剧本截断识别

- 类型：修复轮（含全量基线验证）。中央唯一入口领取 R1248；本任务无对应队列 ID，不占用 R1247。
- 测试：新增 4 条测试修复前 16 个子场景失败，修复后 4/4；关联回归 80/80、6.1 秒，受影响冒烟 9/9（含默认 8/8）。完整安全全量及其架构门禁待执行，未宣称通过。
- 欠账：历史正式全量 R1242；本轮触发五轮周期，需真实全量凭据闭环。

## 根因与修改

Anthropic Messages 的 stop_reason 未进入 ModelAdapter.response_meta.finish_reason，HOLLMWOOD 又只拒绝 length，导致 max_tokens 的部分正文被当作成功结果继续审核。普通原生工具对话也未检查截断，可能进入自动保存。

仅修改 model_router.py、hollmwood_roles.py、writing_api.py：保留原生 stop_reason；四角色同时拒绝 length/max_tokens 并报告真实原因；普通原生分支在工具执行及采用前返回明确失败。原生 /v1/messages、独立 system、x-api-key、输出额度及既有导演空正文重试保持不变，不切换到 OpenAI 兼容协议。

新增 tests/test_anthropic_script_truncation.py，经真实适配器和本地假传输验证十类角色、正常完成对照、普通回复不保存、演员截断不发布。未削弱任何已有断言。架构 JSON 内存解码登记仅随插入同步 writing_api.py:362→367，分类和豁免理由不变。

## 验证与边界

- `run_selftests.py -k anthropic_script_truncation`：修复前 4 条、16 个失败子场景；修复后 4/4、0.8 秒。
- `smoke_test.py --affected model_router hollmwood_roles writing_api anthropic_script_truncation`：80/80、6.1 秒；含等待 GUI 令牌的门禁总耗时 73 秒；冒烟 9/9。
- 不读取或修改用户密钥、模型配置和已有剧本；未实发 API、未重启、未 push。
- 当前为实现检查点，全量尚未完成；提交哈希于收尾补记。

[TASK_IN_PROGRESS]
