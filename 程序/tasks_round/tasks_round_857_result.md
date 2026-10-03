# R857 结果：阶段配置面板按工作流程重排并删除全局默认模型

## 界面与入口

- 阶段配置按“预设 → 统筹 SKILL → 由谁执行 → 怎么执行 → 技能说明 → 本页专属 → 底部动作条”重排；确认按钮迁至底部并改为“确认并关闭”。
- 说明区继续使用剩余空间布局，并预留底部动作条高度，窗口缩放时不会覆盖确认区。
- 恢复“新增 SKILL”受控导入：仅在用户显式选择文件后复制进阶段注册目录、强制扫描并刷新说明；恢复“恢复默认”入口，确认后只复位当前阶段模型与 SKILL，不改统筹或制作锁。

## 模型契约

- 删除程序级全局默认模型的 UI、配置 API、执行上下文和路由回退，模型覆盖现为“单次 > 项目”。
- 原 `配置/SKILL/全局模型.json` 已经 `storage_maintenance.recycle_paths()` 移入可恢复回收站，未直接删除。
- 契约断言相应更新：删除全局模型 API/上下文断言，路由只验证两级回退；另外将注册表基数同步为当前已登记的 71 项（剧本阶段 5 项）。

## 验证

- `run_selftests.py --safe -k skills ui_edges manual_plan manual_gate video_ui aspect stage_config model_router stage_execution`：385/385 通过，0 红（236.5 秒）。
- `run_selftests.py --safe -k workspace maintenance force_quit`：53/53 通过，0 红。
- `test_asset_gating`：17/17 通过；`smoke_test.py --architecture` 已完成。
- 完整 `run_selftests.py --all --safe` 在本机 Tk 子进程组合执行至 `test_asset_gating` 时停滞，未产生可接受的全量通过汇总；因此未推进 `last_full_safe_all_round`，后续需在干净桌面会话复跑。

## 注意

- 界面重排需要重启应用后生效；本机桌面自动化未暴露应用窗口，故未取得剧本与视频窗口截图，需在干净桌面会话复核“本页专属”和底部确认条。
