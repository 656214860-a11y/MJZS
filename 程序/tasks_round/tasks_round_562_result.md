# R562｜结构治理轮（子场景：执行）

## 来源与执行项

- 来源：`tasks_round/tasks_round_547_result.md` J 节。
- 执行：P2-2——将尚未覆盖的分镜 JSON／资产预览接入按需、分片和可取消的读取协议，复用已有哈希缓存。

## 完成结果

- `storyboard_files.show_final()` 对超过既有 512 KiB 阈值的定稿 JSON 改为只在用户选中时后台读取。选择偏好仍由 `FinalStoryboardController.choose(..., load=False)` 立即经既有边界写入；独立控制器在工作线程读取，主线程仅接收当前页面代次的结果。
- 定稿文本用既有 `script_preview_service.preview_chunks()` 按空闲帧、每帧最多两块（约 64 KiB）写入 `Text`；换选、列表刷新或页面销毁会失效并撤销待轮询/待提交回调。短 JSON 仍即时加载，页面最终内容、导航和编辑语义不变。
- `FinalStoryboardController.apply_preview()` 只接收已读取的预览并更新无 Tk 的导航状态；`choose()` 新增兼容的 `load=False`，默认调用路径和对外行为不变。
- 资产详情的正典板、状态变体与行内预览不再把缩略图请求挂在长期存活的窗口，而是挂在各自页面控件。`asset_thumbs` 已有的 `_alive(master)` 队列检查会在页面销毁时丢弃未消费任务，继续复用既有路径/mtime 哈希磁盘缓存，不改缓存格式或图像内容。
- 修复 `smoke_test.py --affected storyboard_files` 与 `--affected asset_detail` 的测试别名，避免定向门禁出现“0 个匹配测试”。

## 改动文件

| 文件 | 变更 |
| --- | --- |
| `storyboard_final_controller.py` | 增加后台预览结果接收点，并保留选择持久化的默认加载契约。 |
| `storyboard_files.py` | 大 JSON 按需后台读取、页面代次取消、Tk 空闲分片渲染。 |
| `asset_detail.py` | 缩略图请求绑定页面控件，以复用既有任务失活取消。 |
| `smoke_test.py` | 补齐两个受影响模块的既有测试映射。 |
| `tests/test_storyboard_final_controller.py` | 覆盖后台预览接收和“先持久化、后读取”分支。 |
| `architecture.md`、`project_status.md` | 同步读取/缓存边界、轮次和债务状态。 |

应用代码仅改动 3 个模块，符合“每次最多改 3 个模块”约束。

## 验证

- `python -B -m unittest tests.test_storyboard_final_controller tests.test_file_cache tests.test_final_viewer`：39/39 通过。
- `python -B smoke_test.py --affected storyboard_files`：3 个测试文件、38 条用例通过。
- `python -B smoke_test.py`：默认冒烟 8/8 通过。
- `python -B smoke_test.py --architecture`：架构门禁 98/98 通过。

## 债务状态与自审

- P2-2 已完成；R182 可执行拆分债务由 7 项减至 6 项。P0-3 的既有二进制成果发布/分层阻塞不变。
- 通过：未改变分层、文件格式、缓存格式、用户数据或页面最终预览内容；未新增产品功能；无新增架构红点。
