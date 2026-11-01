# R1458 可靠性轮：标准库可用性门禁与启动失败日志（优化清单第 4 项）

1. **本轮类型？** 可靠性轮。新增一个测试，改启动入口失败分支的日志写法；不改业务逻辑。
2. **测试与基线？** 新增 `tests/test_stdlib_imports_available.py`（1 项）与 `test_app_logging.py` 增 1 项，均通过；默认冒烟与 `--architecture` 结果见提交前最后一次运行。
3. **是否欠账？** 启动入口再次改动，仍属 §5 风险路径，由 post-commit 后台全量补跑。

## 事实

- 根目录 `启动错误.log` 为 9 月 25 日 `colorsys` 缺失的残留；`.pyw` 失败分支用 `write_text` 覆盖，反复失败只留最后一次，且无时间／版本，无法判断是否过期。
- 随附 `运行环境\Python\Lib` 是裁剪版（不在 git 中）。当前生产代码所有标准库 import 经 find_spec 均可解析，`colorsys` 已不再被引用。

## 改动

- `tests/test_stdlib_imports_available.py`：用随附解释器 AST 扫描 `程序/*.py` 与 `agent/**` 的全部 import（含函数内），标准库名必须 find_spec 得到；try/except ImportError 内的可选导入豁免。以后有人引入裁剪掉的库，在开发机就红。
- `启动漫剧制作助手.pyw`：失败日志改为追加，带时间、版本、Python 版本头，保留最近约 64KB。
- `test_app_logging.py`：断言入口不再覆盖写。

## 提交

已提交，见 git log 标题 `R1458:`。
