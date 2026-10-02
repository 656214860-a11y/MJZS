# R759 结果｜修复轮：旧目录归位失败反馈

## 结论

已修复旧目录归位的静默失败。`Desktop.adopt_legacy_layout()` 的目录联接服务发生文件系统错误时，仍返回空字典并不阻塞项目使用，但现在明确提示“旧目录未归入新架构：…；请稍后重试。”。

## 根因与证据

- `desktop.py:3405-3421` 原先捕获 `stage_layout.adopt_legacy()` 的异常后直接返回 `{}`；页面保留原有状态，无法区分没有旧目录与归位操作失败。
- 新增 `tests/test_stage_wiring.py` 故障注入：令 `stage_layout.adopt_legacy()` 抛出 `OSError('目录联接不可用')`。旧实现状态不含“旧目录未归入新架构”，测试失败；修复后保持非阻塞返回并提供可行动状态。
- 未移动、覆盖、删除任何旧目录或用户项目文件；目录联接与历史路径权威语义不变。

## 验证

- `python -m unittest tests.test_stage_wiring.LayoutWiringTests.test_ensure_stage_layout_failure_is_visible_without_blocking tests.test_stage_wiring.LayoutWiringTests.test_legacy_adoption_failure_is_visible_without_blocking tests.test_legacy_adoption_service`：3 条／0 红。
- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected desktop stage_layout legacy_adoption_service`：9/9，定向安全自检 35 条／0 红／8.5 秒。
- `python smoke_test.py --architecture`：138 条／0 红。
- `759 - last_full_safe_all_round(758) = 1 < 3`，未触发完整安全全量。

## J. 整改路线

继续按缺陷台账以故障注入逐项确认 UI／项目维护的静默失败；历史归位日志写入失败与异步模型同步应先区分是否会造成用户误判，再决定可见降级或语义化上抛。启动首屏、改名认领与主界面幽灵条目仍保留实机复验挂账。

## K. 测试迁移计划

`tests/test_stage_wiring.py` 继续以临时项目和服务 mock 覆盖目录补齐／归位两条维护链：成功路径检查目录语义，失败路径检查非阻塞返回及状态可见。任何链接能力依赖仍保留平台前置说明，不把环境 skip 伪装为功能覆盖。
