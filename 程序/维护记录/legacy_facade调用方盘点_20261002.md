# legacy facade 调用方盘点（C3）

淘汰日维持 **2027-03-31**；本报告不执行退役。

| Facade | 生产调用模块 | 清零路线 |
| --- | --- | --- |
| `resolved_storyboard_alias` | `engine.py` | 将别名解析收敛到分镜路径服务，保留同等回归后移除门面调用。 |
| `canonical_stage_name` | `confirm_gates.py` | 由阶段注册表提供规范名称转换。 |
| `optional_workflow_model_name` | `local_previs.py` | 由模型配置服务直接提供预览模型名。 |
| `optional_model_identity` | `idea_chat.py` | 由模型池/身份服务直接解析。 |
| `optional_asset_counts` | `pet_ui.py` | 由资产状态服务提供只读汇总。 |

五项均有生产调用方，当前没有“零调用者可退役候选”。每项完成官方替代服务、调用方迁移与回归测试后，才能登记候选；实际删除属红档，须在淘汰日和独立授权后执行。
