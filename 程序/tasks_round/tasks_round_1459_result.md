# R1459 可靠性轮：静默吞异常留痕与棘轮（优化清单第 1 项）

1. **本轮类型？** 可靠性轮（同类改动批量成轮：110 处 `except Exception: pass`）。语义不变，只在原地把 `pass` 换成 `app_logging.swallowed()`。
2. **测试与基线？** 新增 `tests/architecture/test_silent_exception_ratchet.py`（3 项）、`test_app_logging.py` 增 2 项；默认冒烟 8/8；架构 343 项首次 2 红（TODO 快照与统一基数中的行号因新增 import 行漂移），重映射行号后复验通过；全量见提交前最后一次运行。断言未动。
3. **是否欠账？** 不新增；剩余窄异常（TclError、queue.Empty、OSError 等 161 处静默处理）属预期控制流，未动。

## 事实

- 生产代码共 271 处单语句 `except …: pass`，其中最宽的 `except Exception: pass` 为 110 处（desktop.py 15、pet_cloud.py 17、cell_hover.py 12 等），出错后没有任何痕迹。

## 改动

- `app_logging.swallowed(note)`：在 except 块内调用，仍吞掉异常，但记录“文件:行 已忽略 异常类型: 消息”；同位置同类型只记第 1 次及每 100 次，防止 UI 高频路径刷屏；自身不抛异常。
- 脱敏正则收归 `app_logging.redact`（唯一实现），`diagnostic_capture` 改为复用；崩溃落盘改由入口注入 `crash_sink`，`app_logging` 不依赖诊断层，基础模块可安全导入。
- 32 个生产模块共 110 处替换并补 `import app_logging`（豁免：`app_logging.py` 自身、`run_selftests.py`、`smoke_test.py`、`agent/`）。
- 棘轮：新增 `except Exception: pass` 即红，登记表只允许下降；`AGENTS.md` 门禁清单同步登记。
- 行号基线：`架构统一基数.json` 第四项 7 条、`TODO注释快照` 1 条仅做行号平移，内容与处置未改。

## 提交

已提交，见 git log 标题 `R1459:`。
