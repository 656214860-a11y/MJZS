# R775｜skip 卫生门禁（契约轮，A6）

## 结果

新增 `tests/skip_reasons.py`，将 29 个测试模块的 208 个 skip 收口为模块外的受控原因常量。每个常量均写明原因与恢复条件；分类为平台限制 205、缺外部程序 1、需实机复验 2，待修复缺陷为 **0**，故无待修复缺陷编号。

新增 `tests/architecture/test_skip_hygiene.py`，用 AST 扫描 `skipTest`、`skipIf`、`skipUnless` 与 unittest 装饰器：拒绝空理由、行内注释理由和未知常量；原因必须属于固定枚举并含恢复条件。`维护记录/skip台账.json` 按“文件／用例／序号”记录 208 项，门禁以源码集合和台账集合双向相等验证，且对待修复缺陷引用核验 `tasks_round/` 或缺陷台账中的实体。

未新增或删除 skip，未改产品代码，也未削弱既有断言。

## 验证

| 命令 | 结果 |
| --- | --- |
| `python -m unittest tests.architecture.test_skip_hygiene -v` | 3/3 通过 |
| `python smoke_test.py` | 8/8 通过 |
| `python smoke_test.py --architecture` | 143/143 通过（架构基线 140→143） |
| `python run_selftests.py -k skip_hygiene --safe` | 3 条／0 红 |
| `python run_selftests.py --all --safe` | 3,526 条；1 个文件有红 |

R775−R769=6，按规则强制执行完整安全全量。唯一红项是 `tests/test_perf_baseline.py:321`：300 行滚动中位 **163.9ms**（阈值 150ms，最慢 353.2ms）。这与 skip 卫生改动无关，故不伪造验收绿灯，`维护记录/测试分层基线.json` 的 `last_full_safe_all_round` 保持 **769**。

## 后续

需先单独诊断并修复／校准滚动性能基线，再重新运行完整安全全量；在此之前不得将本轮标记为完整安全验收通过。

## Git

本轮未提交；commit hash：无。
