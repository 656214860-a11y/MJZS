# 第 162 轮：资产续跑台账测试迁移

## 改动

- 审计发现 `test_hash_backend.py` 是有意扫描全项目并启动子进程的集成用例，因此未迁移，避免改变其扫描边界。
- 将纯临时项目的 `test_asset_resume.py` 实现迁入 `tests/test_asset_resume.py`，根目录保留兼容入口。

## 验证

- 续跑台账用例只在 `TemporaryDirectory` 下创建最小项目和工作流目录；不访问用户项目、网络或 Provider。
- `python test_asset_resume.py`：8 条通过。
- `python -m unittest tests.test_asset_resume`：8 条通过。
- `python run_selftests.py --serial -k test_asset_resume`：8 条通过，增量台账刷新。

## 风险与下一步

- 覆盖跨重启重试、次数上限、成功项移除、空轮清理及损坏台账容错。
- 继续优先迁移纯逻辑用例；保留需要全项目扫描或真实子进程语义的集成级用例在根目录，待统一测试发现策略完成后再处理。
