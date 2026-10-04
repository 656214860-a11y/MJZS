# R1009：idea_chat 项目上下文收敛

- `idea_chat` 的项目根入口统一改为只接受 L3 构造的 `ProjectContext`，路径解析均从 `context.root` 取得。
- `Desktop` 与 `writing_api` 经 `stage_execution_service.project_context()` 注入上下文，保留既有聊天网关与发布器职责。
- 路线图第二项将 `idea_chat` 从待办移入已迁移模块；其余待办保持不变。

## 验证

```powershell
Set-Location 程序
$env:PYTHONPATH = (Join-Path (Get-Location) 'tests')
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -m unittest test_idea_chat.SavingTests architecture.test_project_context_boundary
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -m unittest test_ui_edges.BriefTintTests.test_the_users_own_words_show_up_on_the_display architecture.test_project_context_boundary
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -m py_compile idea_chat.py desktop.py writing_api.py
```

上述定向验证共 52 项通过。完整 `test_idea_chat` 在本机执行至最后一个既有 Tk 用例时超过 30 秒工具时限；此前 70 余项均通过，未将该超时计为通过。
