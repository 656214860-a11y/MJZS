# R462 结构治理：字幕导出发布边界

## A. 轮次类型与范围

按 `tasks_round/tasks_round_461_result.md` 的 E2 执行一个最小正式成果写入收敛：仅处理字幕 SRT 与对白脚本导出。

## B. 现状证据

`desktop.py` 的两个导出动作曾直接组合字幕行、创建阶段文件名并调用写入函数；二者属于配音与字幕阶段的正式用户成果。

## C. 方案

新增无界面 `subtitle_export_service`：接收项目根、剧集与角色资产，调用既有时间轴计算和阶段路径服务，原子发布 SRT 或对白脚本；`desktop.py` 仅委托服务并显示原有估算状态。

## D. 变更文件

- `subtitle_export_service.py`：SRT、对白脚本的受控阶段目录发布。
- `desktop.py`：两处导出入口改为服务委托。
- `tests/test_subtitle_export_service.py`：服务行为及 UI→服务静态边界。
- `architecture.md`：登记 L2 服务与已验证发布边界。
- `project_status.md`：登记本轮完成状态。

## E. 保持不变

文件命名、UTF-8 BOM 编码、无对白时的错误、估算状态提示、角色显示名与字幕阶段目录均保持原口径；未调用网络、上传、白模或 TTS。

## F. 验证

- `python -m unittest tests.test_subtitle_export_service tests.test_subtitles`：36/36 通过。
- `python smoke_test.py --architecture`：64/64 通过。
- `python smoke_test.py`：8/8 通过。
- `python run_selftests.py --all --safe`：3,161/3,161 通过，742.9 秒，0 个失败文件。

## G. 风险与回滚

服务仍使用既有原子 `save_text()`；异常时不覆盖既有成果。若需回滚，只将两个 UI 委托恢复为原逻辑即可，未迁移用户数据。

## H. 数据与安全

未读取或修改用户项目数据，未输出密钥，未执行外部请求。

## I. 完成判定

R461 的 E2 最小闭环已完成；优化清单总体仍有未完成项。

## J. 整改路线

下一轮继续扫描一个剩余正式成果直写或用户可见删除入口，只做单一闭环，并补服务与静态边界测试。

## K. 测试迁移计划

新增测试位于 `tests/`；未搬迁或重复创建测试模块。

## L. 关键约束

不改用户项目成果，不扩展到其他导出、删除或白模上传；白模真机上传仍必须等待用户对具体素材的明确授权。

## M. 下一步

继续 R461 的 E2/E3：扫描下一处单一的正式成果直写或删除入口，按风险和可验证性选择最小闭环。
