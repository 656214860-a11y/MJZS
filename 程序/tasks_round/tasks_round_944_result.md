# R944 修复轮：并行回归超时集合访问

队列：C4-full-suite-shard。当前未完成，尚需完整两轮验收。

根因：concurrent.futures.wait 返回 Future 集合，run_units 对其调用 values 导致 AttributeError，在终止工作进程前进入等待式 shutdown。

修复：通过 pending 映射取得未完成单元，复用该列表生成超时失败记录。新增行为测试覆盖超时分支，没有修改既有断言。

验证：执行器 29/29；默认冒烟 8/8；真实 ProcessPoolExecutor 提交 30 秒 sleep，在 1 秒超时配置下 1.02 秒返回失败记录并退出。架构门禁和全量本轮尚未验证，不引用为通过。

提交：本报告随 R944 修复提交，提交号由 Git 历史记录。
