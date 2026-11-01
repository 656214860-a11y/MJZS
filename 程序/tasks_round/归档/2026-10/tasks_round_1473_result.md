# R1473 结果
> 说明：本轮在车道分支 `codex/wip-R1454` 开发，号源已被并行任务占用，合并时正式记为 R1473。验收复测（真实项目「摄影侠」副本，真实 load 路径，心跳法，各 3 次）：进入 02 阶段最大冻结 master 约 2.7 秒×5 次（累计约 10 秒）→ 本改动 150–230 ms；进入 03 阶段最大 126–241 ms → 94–169 ms。代价：02 页正文改为不自动换行并加横向滚动条。验收测试 ui_edges、core、startup_perf、page_cache 全部通过。
- 本轮类型：修复轮（性能）。
- 测试跑了吗：定向 267 条/212.8 秒，266 无失败、1 条新增测试失败；修正视口操作后仅复跑该条，1 条/18.931 秒 OK。未跑全量或 gate。
- 欠账变化：02 多秒冻结已消除；03 不变差验收未通过；新增记录 09 默认成果目录权限探测阻塞。

## 根因与修复
- `desktop.py:5306` 两个正文 Text 的中文自动换行触发 Tcl 内部重排；堆栈停在 `Misc.update()`。
- 同一副本单变量对照：word 最大 2736 ms；char 2467 ms；none 129 ms；仅替换正文为空短文 141 ms（其余控件不变）。
- 基线 Python 建页 57.1 ms；正文 insert 两次共 1.3 ms；fit 五次共 4.3 ms；update_idletasks 十次共 137.3 ms；02 无 Text.index 调用。
- 另一基线建页 58.9 ms、insert 共 2.8 ms、fit 共 5.6 ms、idle 共 113.5 ms；不是正文读入或整文 index 测量造成秒级冻结。
- Label/其余布局未单独拆计时；保留它们的空正文对照最大 141 ms，只能作为排除主要瓶颈的证据。
- 两框改为 wrap=none，各加横向滚动条；全文、编辑、撤销、保存与门禁逻辑保留。长行需要横向滚动。
- `test_ui_edges.py:1230` 加入长中文行，断言全文、不换行、横向滚动条双向连接及两框独立滚动，保留原编辑/恢复/保存断言。

## 心跳验收（ms；三次中位数）
| 阶段 | 修复前最大 | 修复后最大 | 修复前累计 >60 | 修复后累计 >60 |
| --- | ---: | ---: | ---: | ---: |
| 02 | 2736 | 188 | 11257 | 188 |
| 03 | 134 | 188 | 341 | 415 |
- 02 达到 <300 / <800 阈值；03 有小幅回退，不能标记“不变差”通过。
- 02 三次前最大/累计：2681/11037、2736/11268、2774/11257；后：191/191、188/188、173/173。
- 03 三次前最大/累计：129/230、173/399、134/341；后：188/462、191/415、174/413。
- 环境：Windows 11 26100，指定 Python 3.15.0a2，Tcl/Tk 8.6.15；10 ms after 心跳，Desktop.load → 02 → 03，同副本、同 pump 时长，串行测量。
- 证据：`.probe_tmp/gap.py`、before2/base2/base3.log、after1/after2/after3.log；首轮基线尚无 Python 方法计时，其心跳与加载路径相同。
- 原项目 `05资产管理` 读取被 WinError 5 拒绝；统一使用 `.probe_tmp/gap-4mke79xu/proj` 的可读取副本，缺该目录，不能冒充完整真实项目验收。

## 04–13 单次巡检
- 04–08 最大（仅 >60 ms 间隔）：0、213、126、74、134 ms；0 表示无 >60 ms 间隔。
- 默认路径的 09 阻塞超过 150 秒，采样落在 `file_cache.py:219 probe_writable → tempfile.mkstemp`；未完成的心跳不能记成 0 ms 通过。
- 通过 MANJU_WHITE_MODEL_WORKSPACE 指向工作树内临时目录后，09–13 最大：134、155、279、168、0 ms；全部 <300 ms。
- 证据：pages.log、pages_bounded.log、pages_remaining.log；09–13 是中断后重新 load 的续测，非完整连续一轮。

## 测试与边界
- 实际命令：指定 Python `-u -B .probe_tmp/run_targeted.py --serial --gui-wait 0 -k test_core test_desktop_startup_perf test_page_cache test_ui_edges`。
- 包装器调用 `run_selftests.main`；缓存/令牌/临时目录定向 `.probe_tmp/`，先只读检查共享 GUI 令牌，无测试断言改写；白模临时目录同上。
- 包装器启动曾因 Windows spawn 入口保护缺失及遗留令牌等待中断，未执行测试用例；修正后仅执行一次完整定向集合。
- 新增用例首次未将长行滚入视口，横向范围为 0；补充 see(end-1c)，未弱化断言；增量命令：指定 Python `-B -m unittest test_ui_edges.UiEdgeTests.test_script_structure_page_shows_source_and_output_in_separate_boxes`（PYTHONPATH=程序;程序/tests），输出 OK。
- `git diff --check --ignore-submodules` 通过；测试中的既有 Tk after/speak 回调警告未形成额外失败。详细结果见 `.probe_tmp/targeted.log`、`retest.log`。
- 未提交、合并、推送、切分支、领取轮次或修改 project_status；未删除项目文件。
- 未完成：完整原项目权限恢复后的复验、03 不变差、09 默认成果目录同步权限探测修复；本轮不标记 TASK_COMPLETE。
