# R584 修复轮结果：自动定稿发布失败

## 结果

修复自动定稿的实际生产失败：`storyboard_final.finalize()` 在发布定稿文件前抛出 `NameError: name 'json' is not defined`，导致工作稿未进入回收站。

## 根因与修复

- 精确复现：`tests.test_ui_edges.UiEdgeTests.test_auto_final_switch_generates_final_and_retires_working_json` 在定稿文件不存在处失败；状态栏原文为“自动定稿未完成：name 'json' is not defined”。
- 根因：`storyboard_final.py` 使用 `json.dumps()`／`json.loads()` 进行定稿文本校验，但模块未导入标准库 `json`。
- 修复：仅在 `storyboard_final.py` 的标准库 import 中补充 `json`。原有统一阶段发布、内容校验、原子替换、别名更新和 `storage_maintenance.recycle_paths()` 回收路径均未改变。

## 改动文件

- `storyboard_final.py`：+1 个标准库导入。

## 验证

| 范围 | 结果 |
| --- | --- |
| 自动定稿／工作稿回收精确回归 | 1/1 通过 |
| `python smoke_test.py` | 8/8 通过 |

## 后续

本项消除了完整 `ui_edges` 第 7 分组中的自动定稿失败；其余失败簇继续按“生产缺陷优先、接口迁移测试次之”逐项处理。
