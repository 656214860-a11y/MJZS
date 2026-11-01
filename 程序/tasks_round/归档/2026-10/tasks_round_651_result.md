# R651｜结构治理轮：日志维护架构边界

## 开工三问与验证档位

1. 本轮是结构治理轮：只处理全量自检中 `log_maintenance.py` 的受控后台进程与受控日志删除边界。
2. 该模块只维护程序自有 `logs/` 与 `维护记录/`，不遍历或修改用户项目；`Popen` 用于退出后非阻塞清理，`unlink` 仅用于已判定的受管日志。
3. 修复目标是将该既有受控模块登记为后台与删除边界权威，不改变实际清理策略。

本轮改动涉及 3 个模块，按分级规则执行默认冒烟 + 架构门禁，跳过全量，理由：只调整 2 个架构边界测试及 L1 分层登记，未触及启动路径、用户数据格式、L0 契约或删除路径。

## 改动文件清单

- `tests/architecture/test_platform_process_boundary.py`：将既有受控后台维护模块 `log_maintenance` 登记入后台进程边界。
- `tests/architecture/test_recycle_service.py`：将该模块登记入受控日志删除权威集合。
- `tests/architecture/_layers.py`：将该模块登记为 L1 基础设施层。
- `project_status.md`：轮次台账推进至 R652，和本报告连续。

未改动任何用户数据、项目资产、用户项目目录或清理策略。

## 验证原始输出片段

### 定点架构回归

命令：`D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B -m unittest tests.architecture.test_platform_process_boundary tests.architecture.test_recycle_service`

```text
...
----------------------------------------------------------------------
Ran 3 tests in 4.617s

OK
```

### 默认冒烟

命令：`D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B smoke_test.py`

```text
通过：8 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮
```

### 架构门禁

命令：`D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B smoke_test.py --architecture`

```text
test_direct_popen_is_limited_to_platform_or_background_boundaries ... ok
test_physical_removal_is_recycle_or_tempfile_owned ... ok
test_round_number_continuous ... ok
```

架构门禁进程正常结束；本轮新增登记覆盖的两条边界断言通过。

## J 后续

- `architecture.md` 的模块说明未逐项列举全部 L1 基础设施模块；如需文档枚举补齐，应另开文档治理轮，避免扩大本轮范围。

## 自审

是：只登记 `log_maintenance` 的后台进程、受控删除与分层归属，未顺手修复其他全量自检失败项。
