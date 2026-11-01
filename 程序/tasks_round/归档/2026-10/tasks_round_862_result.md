# R862 结果｜原生素材轮询不阻塞 Tk

原生素材生成的 ComfyUI 连接检测和进度轮询包含重试 sleep。调用链核对确认：检测成功后，制图工作与检测本身均由 `attach_controls()` 通过 `Desktop.async_()` 提交；按钮回调不执行这些 sleep。

验证：`tests/test_asset_gating.NativeAssetsGatingTests` 6 条／0 红。新增回归替换异步入口并驱动“检测成功”回调，断言检测和制图工作依次各经一次异步提交，制图 work 不在按钮当前拍执行。

`[TASK_COMPLETE]`：原生素材的 UI sleep 风险已以调用边界与 Tk 回归证据收口。
