# R2208 Comfy 密钥：新保存的密钥不再被旧环境变量盖过（修复轮；含 J9 结论）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 05 的 J8；J9 经核对无需改码，结论见下。

## 基线
分支 `codex/wip-R2208`，自 R2202。

## 轮次类型／三套基线／债务
修复轮；台账与分层无变化。

## 改动
- 缺陷：`cloud_assets.get_key()` 先读同名环境变量 `COMFY_API_KEY`，再读统一密钥库，旧环境变量会盖过用户刚在「云模型设置」保存的新密钥。
- 修复：取钥次序改为「统一取钥链（`model_pool.named_key` ≡ `credential`：本机 DPAPI → .env → 环境变量）→ 同名环境变量兜底 → 老安装本机加密文件（只读兼容）」。`_unified_key` 仍经 `model_pool.named_key`，该函数本就是 `credential` 的薄包装，所以不另开读取路径。

## J9 结论（不改码）
- `tts_api.unified_key`、`speech_api`、`seedream_api`、`qwen_setup`、`cloud_video_service` 取钥都经 `model_pool.named_key`，即同一条 `credential` 链，来源顺序已一致，无需再改。
- `api_endpoints.configured_key` 是 `credential` 自己调用的最底层读取（`.env` 文件／DPAPI／环境变量按配置分支），反向委托会形成导入环，其注释已写明；不动。

## 新增测试
`tests/test_api.py::CloudAssetsTests`：先写失败用例 `test_a_newly_saved_key_beats_a_stale_environment_variable`，改前输出 `AssertionError: 'sk-stale' != 'sk-fresh'`；改后通过；另加 `test_unified_key_reads_the_model_pool_chain`。既有取钥用例断言未动。

## 测试
`run_selftests.py -k test_api asset_batch_window native_assets cloud_video model_pool tts`：ALL TESTS PASSED。未做：真机在已有旧环境变量的机器上保存新密钥的目视验证。

## 回滚
`git revert` 本轮提交。

## 下一步
J10–J12（候选 04）。
