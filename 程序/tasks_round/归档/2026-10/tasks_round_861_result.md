# R861 结果｜缩略图后台不可用时不阻塞 UI

缩略图后台 worker 不可用时，旧回退会在 Tk 当前回调同步解整张原图并写缓存；大图可能卡住滚动或页面切换。现该分支保留既有文字占位并返回空值，不在 UI 线程解码；worker 恢复或下次打开时再自然补图。

验证：`tests/test_asset_thumbs.py` 21 条／0 红，故障注入将 `_WORKER_BAD` 固定为真并令 `_build_here` 被调用即失败，断言当前拍返回空、无待处理任务且未写缓存；`tests.architecture.test_round_baselines` 4 条／0 红；默认 `smoke_test.py` 8/8 通过。

`[TASK_COMPLETE]`：缩略图后台不可用时的 UI 同步整图解码路径已移除。
