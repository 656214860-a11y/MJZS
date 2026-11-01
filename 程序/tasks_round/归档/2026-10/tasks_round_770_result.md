# R770 结果｜恢复入口补全

## 轮次结论

本轮为修复轮，补的是删除确认文案已经承诺、但除分镜链外没有 UI 调用方的“回收站可恢复”能力。

实现与定向验证通过；完整安全全量未验收，原因是工作区既有、未追踪的顶层诊断文件 `_diag_winprobe.py` 未登记到 `tests/architecture/_layers.py`，触发层级完整性门禁。本轮未为使门禁变绿而修改、登记或删除该文件，故全量基线保持 R769。

## 交付

- `storage_maintenance.read_recycle_batch()` 只读兼容 `items` 与早期 `files` 清单；仍由既有 `restore_recycle_batch()` 承担实际恢复、越界检查、冲突零移动与回滚。
- 新增无 Tk 的 `recycle_recovery_service` 与 `recycle_recovery_controller`：只列当前项目回收站和项目库回收站的合法批次／可恢复条目；不新建清单格式或第二套回收语义。
- `desktop.py` 的项目首页、项目选择窗口及项目右键菜单均接入“恢复回收站内容…”。页面可查看批次、原位置、原因与条目，并可整批或单条恢复。
- 删除确认文案改为指向真实“恢复回收站内容…”入口，消除“可在维护工具中恢复”的空承诺。

## 沙箱回归

全部测试只用临时目录，未读取或改写真实用户项目／回收内容：

| 项目 | 结果 |
| --- | --- |
| 列批次及清单元数据 | 通过 |
| 整批恢复 | 通过 |
| 单条恢复且不连带其余条目 | 通过 |
| 目标已存在时零移动 | 通过 |
| 越界批次拒绝 | 通过 |
| 早期 `files` 清单兼容 | 通过 |
| 项目内／项目库双根汇总 | 通过 |

## 验证

| 命令 | 结果 |
| --- | --- |
| `python smoke_test.py` | 8/8 通过 |
| `python smoke_test.py --affected storage_maintenance storyboard_recycle` | 9/9 通过 |
| `python run_selftests.py -k recycle storage --safe` | 26 条／0 红 |
| `python smoke_test.py --architecture` | 139/139 通过（在既有诊断文件出现前执行） |
| `python run_selftests.py --all --safe` | 3,511 条、913.4 秒；1 个文件红：`architecture.test_layers` 的 `_diag_winprobe.py` 未登记 |

本轮号 `770 - 741 = 29 >= 3`，按要求已运行完整安全全量；因上述外部工作区门禁红灯，`维护记录/测试分层基线.json` 的 `last_full_safe_all_round` 不推进。

## 后续

先由该诊断文件的所有者决定：将其移出运行期顶层、纳入明确外围工具白名单，或按实际职责登记层级；完成后重新运行完整安全全量，方可关闭 R770 验收。

## Git

- 已提交：是（用户明确授权“可以入库”后完成首次提交）。
- Commit hash：`c00a5f8`（`chore: 初始化版本控制，排除用户数据与密钥`）。
- 未执行 `git push`。
