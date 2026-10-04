# R1010：keyframe_batch 项目上下文收敛

- 首帧任务书 `image_prompt()` 改为只接收 L3 注入的 `ProjectContext`，仍只处理调用方给出的分镜源与输出清单。
- `stage_execution_service.keyframe_image_prompt()` 统一构造上下文；L4 `keyframe_import` 不再直传项目根路径。
- 第二项将 `keyframe_batch` 从待办移入 adopters。

## 验证

```powershell
Set-Location 程序
$env:PYTHONPATH = (Join-Path (Get-Location) 'tests')
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -m unittest test_keyframe architecture.test_keyframe_batch_json_boundary architecture.test_project_context_boundary
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -m py_compile keyframe_batch.py keyframe_import.py stage_execution_service.py
```

## 提交凭据

- 实现提交：`a365cb5`
