# R1002 创意附件项目上下文迁移

## 已完成

- 创意附件归档、已入库列表与对话引用均改为消费 L3 注入的 `ProjectContext`。
- 附档目录统一从 `context.stage_resolver('script')` 获得，不再由 L2 接收裸项目根路径。
- 对话控制器和桌面引用菜单改经 `stage_execution_service` 的 L3 门面。
- 第二项台账将 `idea_attachments` 从待办移至 adopters。

## 验证

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_idea_attachments tests.test_idea_chat_controller tests.architecture.test_idea_attachment_publication_boundary tests.architecture.test_project_context_boundary`
- 结果：21 tests passed。

## 未完成

- 路线图第二项仍有 14 个现行服务待迁移或审计；全量门禁尚未执行完成。

## 提交凭据

- 实现提交：`4959216`。
