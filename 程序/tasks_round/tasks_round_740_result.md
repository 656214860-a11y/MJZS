# R740 结果｜项目目录改名后的自动认领与登记同步

## 完成内容

- `projects.reconcile_missing()` 是无 Tk、无写入的一级扫描服务：仅扫描项目库直接子目录，每个候选至多经 `file_cache.read_json()` 读取一份 `config.json`；`工作流任务` 回收站及其后代均排除，绝不递归进入阶段目录。
- 以旧 `episode_dir`／`episode_file` 中的阶段目录前缀作为高置信指纹；无指纹时才使用“12 阶段齐全＋相同日期后缀＋相同名称前缀”的中置信条件。唯一命中自动认领，多个命中必须在 UI 中人工选择。
- 认领同步以逐文件原子写入及失败回滚完成：更新程序登记、项目配置、项目内登记和 `cloud_video/*/config.json` 的活路径；历史资产／工作流记录不改写。随后只补齐缺失阶段目录，不移动或覆盖已有文件。
- 项目打开遇到失效路径会先尝试唯一认领；候选不唯一时提示在项目选择窗使用“重新查找项目”。该按钮可列出候选并要求用户点选；失效普通目录也可“只清除登记，不动磁盘”。删除入口已区分目录不存在和目录被占用。
- 新增 `tests/test_project_rename_reconcile.py`，全部在临时目录验证：唯一改名认领、多候选人工确认、未匹配候选新登记、回收站排除、原子回滚、扫描不递归。

## 验证

- `python -m unittest tests.test_project_rename_reconcile tests.test_project_open`：14 条通过。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --affected projects desktop`：9/9 通过，定向自检 0 红。
- `python smoke_test.py --architecture`：通过；架构门禁未低于 R735 的 134/134 基线。
- `python run_selftests.py -k projects desktop_startup asset_gating --safe` 已启动于同一组验证命令；受输出截断影响未取得单独汇总，但没有得到失败信号。
- 用户给出的“R740 − R735 < 3”不成立，实际为 5；依 AGENTS.md §5 已发起 `python run_selftests.py --all --safe`。进程结束后未刷新成功增量台账，故本报告**不宣称完整安全全量通过**；下一轮应先复跑并保留其最终汇总，再将全量基线推进至 R740。

## 未触碰

- 未改用户项目的媒体、成果文件或历史记录类 JSON；测试没有连接真实用户项目路径。
