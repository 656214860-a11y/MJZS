# R443 结构治理轮结果

## 范围

- 来源：R418 整改路线 J3/K 的分镜文件面板服务边界。
- 仅迁移定稿查看指针的偏好持久化；未改变分镜预览、正文编辑、阶段启动、白模上传或主界面“齿轮 → 设置”入口。

## 改动

- `storyboard_selection.remember_final_view()` 成为定稿查看路径的无 Tk 持久化入口：拒绝项目外路径、原子写入相对路径并保留其他项目偏好。
- `storyboard_files.show_final()` 的选择回调改为委托该入口；既有编辑正文保存仍保持原职责和行为。
- 新增服务行为测试与仅约束 `choose()` 回调的静态门禁；首次门禁发现并精确排除了同一页面内独立的正文编辑保存，未弱化该编辑路径。
- `architecture.md`、`AGENTS.md`、项目状态与报告已同步；架构测试清单为 31 文件、55 项。

## 验证

- `python -m unittest tests.test_storyboard_final_selection tests.architecture.test_storyboard_final_selection_boundary`：3/3 通过。
- `python smoke_test.py --architecture`：55/55 通过。
- `python smoke_test.py`：8/8 通过。
- 全量安全自检未在本轮执行；最新可用全量基线仍为 R439 的 3,116/3,116。

## 自审与结束检查

- 通过：仅变更该面板的一个偏好写入边界及必要测试、文档、状态和报告。
- 通过：服务无 Tk 依赖；未改用户项目数据、外部生成或上传路径，也未影响设置入口。
- 本轮为结构治理轮；默认与架构基线通过，项目已接续至 R444。已知阻塞数未减少，统一阶段写入总项与白模授权仍待后续轮次。
