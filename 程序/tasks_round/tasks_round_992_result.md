# R992 结果：WIP 领取守卫与行尾声明

- 本轮继续认领 `reliability-loss-guard`，完成 WIP 前置和行尾归一声明；阶段端到端探针的 SG-02 至 SG-05 真机覆盖仍待后续收口，队列项保持 claimed。
- 三项基线：定向 `tests.test_round_claim tests.architecture.test_round_baselines` 17/0；默认冒烟 8/8；架构门禁 279/0。R991 最终全量 receipt 仍为 3821/0、296.517 秒；本轮内容树变更后将在队列总项收口时刷新。

## 交付

- `round_claim.py next` 在通过 detached 检查后再检查 `git status --porcelain`；存在未提交变更时拒绝领取，并提示 `git switch -c codex/wip-R<轮次>`，避免脏树跨轮写入同一文件。
- 临时仓库 CLI 回归覆盖了已提交工作树可领取与脏树拒绝，计数器不会在拒绝路径分配轮次。
- 新增根目录 `.gitattributes`：文本统一声明，`.cmd` 固定 CRLF，常见图像、音频与视频为 binary；未执行 renormalize，也未批量改写文件。
- `程序/AGENTS.md` 同步 WIP 规则：跨文件改动达到 50 行时，先提交或建立 WIP 分支。

## 边界

- 未改生产模块、用户项目、`程序/data`、`程序/private`、日志或运行数据；未新增 `.bak_*`。
- 提交哈希：待本结果最小暂存后填写。
