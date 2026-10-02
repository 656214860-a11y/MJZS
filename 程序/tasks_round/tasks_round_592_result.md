# R592 结构治理轮结果：P0-3 首帧与整包发布原语

## 改动文件

- `stage_execution_service.py`：新增 `publish_stage_bundle()`；关联成果必须整体通过校验、原子写入和索引更新，任一步失败都会恢复整包旧字节。
- `keyframe_lifecycle_service.py`：`replace_keyframe()` 增加可选发布器注入，维持旧首帧回收、失败恢复及镜头索引语义。
- `desktop.py`：首帧替换 UI 注入 `publish_stage_bytes()`。
- `tests/test_stage_execution_service.py`、`tests/test_keyframe_lifecycle_service.py`、`tests/architecture/test_keyframe_replace_boundary.py`：补齐整包回滚、首帧索引失败恢复和生产入口注入门禁。
- `architecture.md`、`project_status.md`：登记统一发布原语与进度。

## 迁移结果

首帧的正式写入已进入统一二进制发布入口。服务只接收外层传入的发布器，未反向导入 L3；旧帧仍先被回收。若 PNG 发布或镜头 JSON 索引更新失败，新帧会移除，旧帧与原镜头引用均恢复，因此阶段不会被错误视为完成。

`publish_stage_bundle()` 是给关联多文件成果使用的统一原子发布原语；本轮只建立其行为和回归，R593 将其接入视频提示生产路径。

## 验证

- `python -m unittest tests.test_stage_execution_service tests.test_keyframe_lifecycle_service`：12/12 通过。
- `python smoke_test.py --affected keyframe_lifecycle_service`：通过（定向 7/7）。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：101/101 通过。

## 债务状态

P0-3 尚待视频提示关联成果接入整包入口；本轮不提前关闭该条目。
