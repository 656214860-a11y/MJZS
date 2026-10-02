# R790 结果｜结构治理轮：架构统一第 3、4 项第二批

## 交付

- 迁移 `idea_chat.py`：L2 不再直接使用 `agent.core` 或裸 `json.loads` 读写聊天记录、简报与回收记录；所有正式读写均要求 L3 注入的网关，缺少网关明确抛出错误。
- `stage_execution_service.idea_chat_gateway()` 是唯一的 L3 装配点，提供缓存读取与原子 JSON／文本发布；`desktop.py` 仅取得并传递该网关，不承载落盘决策。
- 保持既有路径、数据格式、聊天／简报授权语义和回滚行为。测试中的直接调用同样通过真实 L3 网关；另有回归确认未注入调用被拒绝。
- 同步棘轮台账：第 3 项 `idea_chat.py` 六项改为 `migrated`，pending **56 → 50**；第 4 项三项改为 `migrated`，pending **24 → 21**。因新增 L3 函数导致的既有 `stage_execution_service.py` 行号漂移已只更新定位坐标，处置状态不变。

## 进度

本轮遵循用户指定的第二批；下一批为 `asset_batch_service.py`＋`asset_batch_lifecycle.py`。剩余量按文件聚集度而非点数机械折算轮次：第 3 项还剩 50 项、第 4 项还剩 21 项，后续每轮仍限定 2–3 个模块，直至两个独立扫描集合清空。

## 验证

| 检查 | 结果 |
| --- | --- |
| `python smoke_test.py` | 8/8 通过 |
| `python smoke_test.py --affected idea_chat stage_execution_service desktop` | 9/9 通过 |
| `python run_selftests.py -k "idea_chat unification_ratchet" --safe` | 81 条／0 红 |
| `python smoke_test.py --architecture` | 156/156，通过 |

`R790 - last_full_safe_all_round(R788) = 2 < 3`，且本轮未触及 Tk 生命周期或层级登记表；按 AGENTS.md §5 不跑完整安全全量，`last_full_safe_all_round` 保持 R788。

## Git

- 本轮未暂存、未提交、未推送。
- 建议提交信息：`refactor(idea-chat): 注入统一读写网关`。
