# R1462 可靠性轮：模型调用结果计数、分发清单补全与分发自检（优化清单第 10、11 项）

1. **本轮类型？** 可靠性轮。
2. **测试与基线？** `test_app_logging.py` 增 1 项；新增 `tests/test_distribution_selfcheck.py`（2 项，含一次真实构建，约 10 秒）；`test_distribution_build`、`test_model_pool` 通过；默认冒烟与架构门禁见提交前运行。断言未动。
3. **是否欠账？** 改 `model_pool.py`（拆出 `_http_transport`，返回值不变），未触及启动入口、删除语义、层级表。

## 事实

- `distribution_build.py --build` 当前**直接拒绝构建**：开发目录里有 41 个文件不在《分发清单》中（本地 CI 脚本、开发文档、本机配置、`h3_launcher.pyw`、`reference/` 等），也就是说分发流程已经悄悄失效。
- 请求台账 `RequestLedger` 已覆盖按项目的 token／次数用量；缺的是进程级“调用结果分布”（成功、网络错误、限流、程序缺陷各多少次）。

## 改动

- 《分发清单》补全：保留 10 项（说明文档、内置模板、辅助脚本），排除 6 组（开发 CI／测试脚本、开发文档、本机状态与配置、个人 ComfyUI 启动器、参考仓库）。`--plan` 的“未决定”为 0。
- 新增 `scripts/distribution_selfcheck.py`：构建到系统临时目录 → 校验 → 用副本自带（裁剪版）解释器导入 `app_logging／diagnostic_capture／model_pool／desktop／app`，结束自动回收。测试 `test_distribution_selfcheck.py` 同时要求清单覆盖所有文件，新增文件忘了登记即红。
- `app_logging.count()`：事件计数，随 `logs/perf_metrics.json` 落盘；`model_pool.http_transport` 按结果种类（ok／network／bug／HTTP 状态类）计数，返回值与重试行为不变。

## 有意未做

- 不给 `http_transport` 加通用 429／5xx 重试：同一函数承载付费生成类请求，盲目重试存在重复计费风险，需要按调用种类区分幂等性后再做，属于独立决策。
- 升级回滚闭环（`reorganize_install.py` 加 `升级备份`）与随附 Python 3.15 预发布线的取舍：需要用户确认发布策略。
- 设置页展示“本周调用统计”属于 UI 新功能，数据已落盘，展示留待用户确认需求。

## 提交

已提交，见 git log 标题 `R1462:`。
