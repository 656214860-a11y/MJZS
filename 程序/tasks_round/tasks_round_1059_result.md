# R1059：J19 三虎聊天交互职责边界只读诊断

1. 本轮为结构治理轮（只读诊断），来源 R1036 J19／OPT-09；选定一个职责并冻结测试，不实施拆分。
2. 默认冒烟 8/8、架构 309/309（101.237 秒）实测通过。主干三轮计数触发的一次安全全量 3973/3973、384.586 秒通过，凭据对应固定检查点 9d4790e，不沿用历史绿色冒充本轮。
3. project_status.md 正文欠账不变；本轮只消除“尚无职责提案／测试清单”的诊断缺口，不宣称修复产品或完成重构。

## A. 授权与范围

只新增本报告、同步状态页轮次头、完成后勾选人工队列 J19；中央认领经既有入口。禁止修改生产代码、测试、配置、用户数据与历史结果。未使用 computer-use。codebase-design 用于接口与状态归属判断，tech-writer 用于证据及未覆盖边界留痕；技能中的删除旧测试建议不适用，遵守项目禁止删测试／弱化断言的约束。

## B. 基线与认领

起点 master `8056e4f2245334c13b55d6b6dbf916da90f43cd4`，工作区干净。中央 next 分配 1059，R1036-J19／codex-j19 认领；WIP 分支 codex/wip-R1059。默认冒烟基线 8，架构基线 309。最近历史安全全量 R1056 3973/3973，不是本轮结果。

## C. 选定职责与理由

候选：Pet 的聊天交互会话协调——单／双击消歧、显式开关、心跳守护关闭、退出取消。不是拆整个 pet_ui，也不是重做 R182 已完成的文本、几何、形状或尾巴计算拆分。行数不构成性能问题证据，本轮不声称提速。

选择依据：同一会话的入口分布在菜单、Canvas、心跳和 Destroy；R1034 曾修复动画重排误用退出清理。以一个 Module 隐藏事件顺序与待执行点击的所有权，才可能获得 Depth 和 Locality；机械搬函数、将整个 Pet 传给新文件并不能达标。

## D. 当前依赖与调用方

定位以起点源码为准；扫描根目录生产 Python AST 的方法属性引用，并阅读真实绑定、心跳和宿主退出；这不是对动态反射或第三方扩展零调用的证明。

| 输入／所有者 | 当前链路及定位 | 不可越界职责 |
| --- | --- | --- |
| Canvas | pet_ui.py:4288 单击、:4289 双击 → :4608 pet_click／:4669 double_click | Tk 事件绑定留在 L4 Pet |
| 菜单 | pet_ui.py:1272 click → open_chat | 原意图、菜单文案与阶段命令不迁移 |
| 动画 | pet_ui.py:4218 _schedule → :4231 _cancel_animation_timer | 只撤动画帧；不能取消点击或关闭聊天 |
| 心跳 | pet_ui.py:1181 drain、:1184 modal guard、:1185 away guard | 保留现有顺序和唯一心跳，不新增周期计时器 |
| 退出 | desktop.py:2018 → Pet.stop；pet_ui.py:4601、:4605 两个 Destroy 绑定 | child Destroy 过滤、重复关闭与调度清理不改变 |
| 云窗 | pet_ui.py:3068 懒建 Cloud；pet_cloud.py:527 show、:575 close | 布局、阅读时长、淡入淡出、定位重试、回复与转播仍归 Cloud |

根目录 AST 对选定的 11 个方法名（pet_click、flip_chat、cancel_click、double_click、open_chat、close_chat、toggle_chat、guard_chat_grab、guard_cloud_away、chat_drain、cloud_visible）的属性命中均在 pet_ui.py；其中 cloud_visible 另供 :1226、:2549、:2620、:2978、:3390、:3750、:4700 查询。故不能删兼容门面或把调用方改为到处 import 新模块。Cloud 还反向持有 Pet 并消费 attending、chat_task、answer_offer、run_plan 等；本轮不移动这些业务依赖，也不宣称已消除双向对象引用。

## E. 状态所有权与行为冻结

| 状态 | 现状 | 提案约束 |
| --- | --- | --- |
| _click_at | Pet :916 初始化、:4616 排队、:4636／:4659 清除 | 协调 Module 唯一拥有；主线程调度，双击先取消单击 |
| chat | :906 初始化；:3796 打开后置引用；:3808 显式关闭清除 | 与 Cloud.visible 不等价，保留原可观察语义 |
| _cloud | :907／:3072；一次懒建、反复复用 | 实例、Tk 控件、记录仍由 Pet／Cloud 持有，不复制会话 |
| visible／shape | Cloud 管理，Pet :4622 查询 | 贴纸与聊天形态不可合并；只查询，不维护第二份布尔值 |
| _timer | 动画独有 | 不进入聊天协调 Module |
| _mute_until | Pet :932／:4646；多个播报消费者 | 继续归播报策略，单击关闭只调用既有 mute，不复制静默策略 |

open_chat 保留主窗恢复→懒建→show(pinned=True, SHAPE_CLOUD)→记录问候→状态提示；失败时沿用 None、errors 与 notice／speak。双击是“打开”而非“切换”；flip_chat 按实际可见性切换并在关闭时 mute，toggle_chat 按 chat 引用切换，不能在重构中偷偷统一。守护关闭返回布尔值；drain 失败记错误并返回 0。

stop 目前直接调用 Cloud.close，而 close_chat 另有错误捕获和 chat 清空；退出绑定还会调用 close_chat。不能把二者等同替换而改变异常、顺序和返回值。Cloud.close 撤销渲染、位置、hold、fade、hint，再裁剪记录及渐隐；这些资源仍归 Cloud。

## F. 建议的 Seam 与 Interface（未批准、未实现）

优先评估无 Tk 的聊天交互协调 Module，由 Pet 装配。Interface 按实际行为保留 request_single、open、close、guard、cancel_pending 五种操作；双击通过取消待单击后 open 表达。guard 接收已计算的 modal／attending，不负责系统前台探测。退出取消与普通关闭的不同语义必须作为显式契约冻结，而非隐含在一个万能 stop 中。

依赖为两个局部可替代 Adapter：调度器（生产 Tk after／after_cancel，测试可控时钟队列）与视图动作（生产沿用 Pet／Cloud 的展示、关闭、可见性及提示，测试内存替身）。调度失败后的立即执行回退、Tcl 取消失败处理保持原样；不开线程、不访问磁盘或网络。所有 Tk 操作依旧在 UI 主线程。

Pet 对外方法与返回值保持兼容；新 Module 不 import pet_ui／pet_cloud，不接收整个 desktop 或 Pet，不替代 stage_handler_registry。chat_drain、chat_hello／chat_task、show_main、mute 以及 Cloud 自己的显示计时不在第一批迁移内。若为这些依赖新增大量透传方法、复制状态或制造循环委托，停止拆分，保留现有实现；Depth 必须由多个入口共享消歧和取消规则证明，不能以文件变短验收。

## G. 已确认事实与待验证风险

1. pet_ui.py:4602 仍称 stop 会被 _schedule 反复调用，与 :4223 已改为 _cancel_animation_timer 不符；是过时注释，不是当前动画仍关闭聊天的证据。留待获批执行轮就地校正。
2. Pet.chat、Cloud.visible、shape 和 pending click 各有独立语义；这是状态分离事实，不直接认定为 bug。
3. 现有真实 Tk 回归覆盖动画不关闭聊天、保留单击和退出撤销；未来需补调度抛错、取消抛错、连续重复单击、子控件 Destroy、退出时云窗关闭异常与迟到回调的特征测试，先记录当前行为再决定是否另立修复轮，不能在重构中改变错误语义。
4. 本轮无用户故障复现、堆栈或新录屏；属于结构提案，不伪造崩溃证据或宣称重启后的视觉体验已验收。

## H. 冻结测试清单

冻结源为上述起点提交的 `tests/test_pet_ui.py`，Git blob `78f40261b05c595da6152d1061e6344249d183c4`，原文件 SHA256 `a6a8743d3bec6243153895a36be7b83e79dc323bab9005db440bca04a4b75201`。下表完整选中每个类的全部 test_* 方法，不只是抽样：

| 完整 ID 前缀 tests.test_pet_ui. | 数量 | 重点保护 |
| --- | ---: | --- |
| AnimationTests | 9 | 动画不关聊天、保留待单击、stop 清理 |
| CloudTests | 37 | 单例记录、失败提示、父窗销毁、阅读计时及幂等关闭 |
| PetClickTests | 6 | 单击双向切换、等待双击、双击取消；菜单与猫爪原断言保留 |
| SingleDialogTests | 2 | 播报不替换聊天、重复打开同一实例 |
| PageAskTests | 7 | 当前页问候与任务交接、不清旧记录 |
| ForegroundTests | 24 | 手动开窗不受自动播报闸门影响、离开守护与回来恢复 |
| CloudCloseTests | 12 | 关闭按钮、Escape、贴纸关闭 |
| ChatUnderModalTests | 3 | modal 关闭、无 modal 保持、释放后补播 |

共 100 个静态方法 ID。重建方式：从冻结 blob 用 AST 选取上表类的 test_* 方法，拼接 `tests.test_pet_ui.<类>.<方法>`，全局排序、LF 分隔并带末尾 LF；SHA256 为 `279a6376b42d43d8290923de378edc3136eed64709b919c8dc8a67cb6ebf7a4d`。这是可复核的精确集合，不是“约 100 条”或测试通过声明。

关键 ID 包括 AnimationTests.test_animation_frames_do_not_close_open_chat、test_animation_frames_preserve_pending_single_click、test_stop_still_closes_chat_and_cancels_pending_click；PetClickTests.test_a_single_click_waits_for_the_double_click、test_a_double_click_cancels_the_pending_menu；CloudTests.test_closing_the_main_window_takes_the_cloud_with_it、test_a_cloud_that_cannot_build_is_recorded_not_raised。完整归属由冻结集合决定，不以本文缩写作为新测试 ID。

## I. 本轮验证与安全

随附 Python -B 执行默认 `smoke_test.py` 8/8、`smoke_test.py --architecture` 309/309（101.237 秒），退出码均为 0；架构与起点 309 持平，包含文档／轮次检查。1059−1056=3，test_round_baselines 在 master 实际要求当前树全量凭据，因此固定干净 master 检查点后只运行一次 `run_selftests.py --all --safe`；不再重复 100 条／宠物整文件定向，不修改门禁绕过计数。测试由既有安全执行器隔离，不启动真实项目或清理日志。

该次全量退出 0，3973 条用例、0 个失败文件；common-dir 实际凭据 round=1059、seconds=384.586、at=2026-10-05T03:34:13、tree=5368f077408c6cc51dadad9aaf90cbcfd793bf03。对应干净 master 检查点 9d4790e，运行期间未编辑文件；后续仅回填报告、轮次头与人工队列，不冒称最终文档树已经全量受测。

## J. 整改路线

J19 到本报告的只读提案与冻结清单为止，不等于批准拆模块。后续须明确批准本报告 F/K 后，才开独立执行轮：先补 G3 特征测试；再只迁移交互协调、不动业务／Cloud 布局；生产模块最多 3 个（建议 pet_ui＋一个新协调模块，Cloud 暂不改），同步实际层级登记及架构描述，不新增反向依赖。若状态／依赖无法收敛，提交“不拆”的证据而非硬造浅层门面。

验收：既有调用方不扩大，Pet 入口／返回值／错误与先后顺序不变；动画与聊天计时隔离；单例与记录保留；原 100 个 ID 不丢不弱化。用户可见行为若有意改变，另立修复轮，不伪称等价迁移。队列下一项 J20 是条件守护，无新增实际服务或性能变更时不得为勾选而执行。

## K. 测试迁移计划

本轮零迁移、零删改测试。未来生产迁移轮先运行冻结 100 条并补 G3 特征覆盖，再跑完整 test_pet_ui 及实际受影响调用方；默认冒烟与完整架构门禁必须通过。因涉及 Tk 生命周期／事件处理，按 AGENTS §5 升级一次固定检查点安全全量，不以小集合代替。

test_pet_ui／test_ui_edges 的组织拆分必须另开测试搬家轮：列旧完整 ID→新完整 ID 一一映射，数量集合守恒、无双份、无新 skip，保留 fixture／断言／临时项目隔离；同步执行器收集、增量关联、Tk 工作池和资源释放。生产拆分需要的 mock 点／导入变更按规则说明“因契约变更，断言未动”。本次只冻结上述 100 条重点集，未授权拆整个大测试文件；test_ui_edges 保持原状。

## L. 收尾与回滚

最终文档回填后，文档／轮次定向检查 15/15（0.307 秒），git diff --check 通过；中央 J19 认领已完成，round-claim validate 为 0 错误、1 条既有 architecture-unfreeze-1-2 租约时间警告，本轮未改动该项。

已提交检查点 9d4790e（R1059: 固定J19职责诊断与测试清单检查点）。收尾仅暂存本报告、状态轮次头与人工队列，按显式白名单和凭据形态扫描提交；最终提交回执以 Git 的 `R1059: 完成J19职责边界诊断与测试冻结` 为准，不 push。撤销文档使用 git revert；本轮没有生产变更需要回滚。状态 N=1060、最新报告 M=1059。

## M. 自审

自审通过：三项基线实测通过；只读源码与既有测试，改动仅本报告和获准轮次元数据；未拆模块、未读取真实 private/、episode/、writing/、配置或密钥，未删任何文件。诊断完成不冒充重构完成，后续执行仍须单独批准。
