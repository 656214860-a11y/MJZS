# R1063 死代码静态诊断

## A 结论

REPORT READY。完成静态诊断，未执行死代码删除。0 项 SAFE TO REMOVE、3 项 REVIEW、25 项 KEEP。

## B 范围

程序已跟踪源码、测试及维护脚本；补充核查已跟踪 Markdown 引用。不读取用户项目数据、private、配置、日志。扫描器以白名单 walker 运行，不是无边界递归。

## C 证据

完整报告：[CODE-ROT-REPORT](../../outputs/code-rot-cleaner/R1063/CODE-ROT-REPORT.md)。同目录包含 analysis.json、review.json、cleanup-plan.csv。扫描 562 个源码文件、123183 行；自动统计汇总仅含原始 25 个整文件候选，追加的 3 个符号单独计数。

## D 候选

| ID | 文件:行号 / 符号 | 调用方扫描 | 潜在删除量 |
|---|---|---|---|
| CRT-026 | idea_chat.py:459 / project_document_kind | 精确符号仅定义，未发现调用或字符串引用 | 25 行 / 1349 字节 |
| CRT-027 | projects.py:316 / Projects.remove_internal_links | 同上；delete 走 recycle_paths | 19 行 / 1107 字节 |
| CRT-028 | workflow_process_registry.py:70 / cancel_process_slot_request | 精确符号仅定义，未发现调用或字符串引用 | 10 行 / 334 字节 |

字节按 UTF-8、LF 归一化片段计，不是实际已释放空间。仅提议删除函数，不提议删除模块。

## E 保留项

动态导入、Blender 模板、测试 canary、共享测试常量、维护 CLI、附加工具入口均保留；逐项理由见 review.json。无入站 import 不等于无用途。

## F 修改边界

仅生成报告证据及更新状态页顶部轮次。未修改生产 .py、测试、配置或用户数据；未删除任何文件。

## G 验证

本轮只做静态检查；未运行定向测试、smoke 或架构门禁。R1062 的 34/34、8/8、309/309 和全量凭据仅属历史结果，不能当作本轮删除验证。

## H 风险

三个公开符号可能存在外部或动态使用；受排除目录不纳入无引用结论。projects.py 中共享导入 remove_project_link_node 仍有调用，必须保留。

## I 权限阶段

code-rot-cleaner 要求先报告、批准副本验证，再逐候选批准真实清理。本轮停在报告阶段，不将一般清理请求解释成精确删除批准。

## J 整改路线

批准 CRT-026～028 临时副本验证 → 按完整报告中的三条命令建立副本基线 → 仅删除三个符号 → 对比回归 → 呈现结果及残余风险 → 再申请真实源码清理批准。不得使用整文件删除证明器删除这三个承载模块。

## K 测试迁移计划

不迁移、不删除测试、不弱化断言。副本验证拟覆盖 idea_chat、projects、workflow_process_registry、默认 smoke 和架构门禁；测试夹具若依赖受保护数据即停止，不复制用户数据。

## L 元数据与提交

中央任务 R1063-CODE-ROT-REPORT，owner codex-code-rot；本报告完成后状态页当前轮次 1064，最新报告 1063。提交前状态：尚未提交；最终提交回执以 Git 中 `R1063: 归档死代码候选与验证提案` 为准（不在提交内容内自填其尚不存在的哈希）。

## M 收尾

诊断完成，真实清理未执行、验证未批准。无需回收任何用户可见文件；未触及 logs、episode、writing、private 或配置。
