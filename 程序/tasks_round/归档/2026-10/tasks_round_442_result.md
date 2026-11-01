# R442 结构治理轮结果

## 范围

- 来源：R418 整改路线 J3/K 的资产批处理面板服务边界。
- 仅收敛 `asset_batch.py` 的批量设置持久化；未触及阶段启动、白模上传或主界面“齿轮 → 设置”入口。

## 改动

- 新增 `asset_batch_settings_service.py`：统一读取、合并并原子保存 `ui_settings.json` 中的 `asset_batch` 子配置；删除模型时只更新隐藏标记和匹配的已保存模型，不影响 ComfyUI 本地文件或其他项目偏好。
- `asset_batch.py` 的保存设置、开始生成保存、Skill 路径保存和删除模型均委托该服务；Tk 控件、确认框、异步模型检测与用户提示仍留在 UI。
- 新增服务行为测试及 UI→服务静态边界门禁；测试因接口迁移同步新增，既有断言未弱化。
- `architecture.md` 与 `AGENTS.md` 已登记 L2 职责、30 份架构测试和 54 项基线；`project_status.md` 已接续至 R443。

## 验证

- `python -m unittest tests.test_asset_batch_settings_service tests.architecture.test_asset_batch_settings_boundary`：4/4 通过。
- `python smoke_test.py --architecture`：54/54 通过。
- `python smoke_test.py`：8/8 通过。
- 全量安全自检未在本轮执行；最新可用全量基线仍为 R439 的 3,116/3,116。

## 自审

- 通过：变更仅覆盖资产批量设置服务边界及必要的文档、测试、状态和报告。
- 通过：未引入 Tk 依赖到服务层，未改动用户项目数据、外部生成或上传路径。
- 通过：默认冒烟及架构门禁达到并更新当前基线。

## 三项结束检查

1. 本轮是结构治理轮。
2. 已运行服务定向、架构和默认冒烟；本轮三项基线中默认 8/8、架构 54/54 通过，全量沿用 R439 的 3,116/3,116 历史通过结果。
3. `project_status.md` 的已知阻塞条目数未减少；统一阶段写入总项和白模真机授权仍待后续处理。
