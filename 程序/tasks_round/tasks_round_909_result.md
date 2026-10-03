# R909 B 线改名项目认领链核验

- `Projects.claim_reconciled()` 先校验项目库一级目录，再在一个事务中更新登记表、项目 `config.json` 的 `episode_dir` / `episode_file`、本地 `projects.json` 与 `cloud_video/*/config.json` 的活路径；失败会逐文件回滚。
- 重新扫描只会自动认领唯一候选目录；多个候选保留给界面明确确认，回收站目录不会被列为候选。
- 侧栏的重新查找入口会在成功后刷新项目树并选中新路径；桌面记忆的项目路径与旧版分镜面板路径也有独立回归覆盖。

验证：`python -m unittest tests.test_project_rename_reconcile -v`，6/0；`python run_selftests.py --safe -k core`，125/0。
