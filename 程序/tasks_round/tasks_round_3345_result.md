# R3345 — 工作树复用随包 FFmpeg 与缺失解码器边界修复
<!-- round-evidence: {"commit_base": "b0a3bcd9", "credential_hits": 0, "evidence_sha256": "b249395344042e3b", "exit": 0, "failed": 0, "passed": 43, "round": 3345, "tests": "run_selftests.py -k ffmpeg_runtime platform_tools"} -->

## 三问

1. **本轮类型**：§3.2 修复轮。按地基任务书全量失败闭环，修复工作树中FFmpeg定位为空及图片校验把空路径交给subprocess的根因；未改图片有效性断言。
2. **测试及三个基线**：新行为先红后绿，9项测试由5个失败事件转为9/9；首轮官方定向66/66、0 skip；默认冒烟9/9；平台工具官方affected34/34、0 skip；静态和规模15/15。架构532项／212.075秒，仅1 FAIL：`platform_tools.py`分支决策点快照133≠当前135。原九文件失败簇的消费者回归实扩20文件／73单元，**828项／867.5秒／0红／0 skip／exit0**。未运行安全全量，不宣当前全树绿色。
3. **欠账少了吗**：工作树可以找到已授权随包解释器相邻的真实FFmpeg，合成PNG已真实解码；缺失解码器改为可操作错误且不启动进程。共享分支账本须由lead整合后按真实目标统一测量；本轮不手写covered、不抬floor、不宣全量欠账清零。

## 本轮执行契约（任务书V2 §12）

| 字段 | 本轮事实 |
|---|---|
| 目标 | 无本地运行环境的工作树仍可使用确证随包解释器的FFmpeg；不存在解码器时明确拒绝而非None参数TypeError |
| 范围 | `contract/platform_tools.py::_bundled_tool`；`domain/keyframe_evidence.py::image_facts`；新 `tests/test_ffmpeg_runtime.py`；本结果及自动机器证据 |
| 前置 | owner已交付master `b0a3bcd9`；lead独立创建本工作树，原 `foundation-hardening` R3344同步正在测试，因此本轮绝不写原树 |
| owner／车道 | 新子会话 `round-ffmpeg-runtime`；分支 `codex/foundation-ffmpeg-runtime`；独立全局领号R3345 |
| 起点 | `b0a3bcd9`，开工branch正确、工作树及索引为空、无MERGE_HEAD |
| 授权来源 | 地基任务书测试通过后的合并目标、固定2eb60233全量17红的真实堆栈及lead范围委派；计划在common-dir `foundation-runtime-fix-plan.md`／`foundation-full-failure-plan.md` |
| 验收 | 配置／本地随包优先；只在 `运行环境/Python` 确证布局查相邻ffmpeg；一般Python不得误认；缺工具不启动进程；真实PNG的sha/尺寸正确，坏IDAT和截断PNG仍拒绝 |
| 风险 | 当前解释器来自另一个相同随包布局时可能使用其真实FFmpeg；仅固定目录检查且文件必须存在，不信任任意parent.parent；没有全局PATH改写、目录扫描或运行资源复制 |
| 回滚 | 对本轮提交执行 `git revert <本轮hash>`；不会改随包二进制、用户配置、项目文件或其他工作树，不需恢复用户数据 |

## 根因与最小改动

固定失败HEAD `2eb60233` 中，`platform_tools`仅查询当前checkout的 `运行环境/ffmpeg/bin`、PATH和fallback。CI `.wt/ci`、功能工作树均无该未入库目录，PATH未命中，而主安装确有FFmpeg和FFprobe；`keyframe_evidence.image_facts()`把None交给subprocess造成TypeError。

- 复用现有工具路径唯一入口，不新增模块。仍以显式配置、本地随包目录优先；仅当 `Path(sys.executable).resolve()` 的父目录名为Python（大小写不敏感）、祖父名为运行环境时，增加相邻 `ffmpeg/bin` 候选。真实文件不存在继续既有PATH/cache/fallback逻辑。无盘符硬编码、递归搜索、全局PATH修改、symlink或巨大runtime拷贝。
- `platform_tools.py`自然980→985行（净增5）；不移除旧空白、不抬规模阈值。
- `image_facts()`在启动解码进程前增加两行缺失判定：未找到FFmpeg时抛中文可操作ValueError。没有泛catch TypeError装作成功，也不把缺失情况写入成功缓存。

开工fresh scope核验：L0/L2候选文件无分支独有diff；L2 `platform_tools`虽暂存M，但index blob等于采样master、unstaged为空，属于incoming，不是独有修改。本轮只改自身隔离树，不触L2整合现场或其独有 `keyframe_lifecycle_service/stage_execution_service`。

## 红绿与真实验证

所有命令使用 `D:/漫剧制作助手/运行环境/Python/python.exe -B`，工作目录为本工作树程序。日志在common-dir，不把运行日志纳入Git。

| 检查 | 真实结果 |
|---|---|
| 改前 `-m unittest tests.test_ffmpeg_runtime -v` | 9 tests，5 failure events，exit1；确证解释器回退未生效、缺解码器提示错误、实际工作树tool为None |
| 最小修后同命令 | 9/9，0.144秒，exit0；包含真实随包FFmpeg对16×9合成PNG解码及sha／尺寸断言 |
| 官方 `run_selftests.py -k ffmpeg_runtime test_context keyframe_evidence` | 实际5文件／6工作单元／66项，3.3秒，0红文件、0 skip；原关键帧证据13项（含坏IDAT、截断PNG拒绝）通过 |
| `smoke_test.py` | 9通过／0失败，隐藏桌面probe可用 |
| `smoke_test.py --affected platform_tools` | 实际 `test_platform_tools` 34项，1.3秒，0红、0 skip；outer为10检查（默认8快速＋probe＋affected） |
| `-m unittest tests.architecture.test_module_size_ratchet tests.test_static_names tests.architecture.test_static_hygiene` | 15/15，9.816秒，exit0；平台模块985行 |
| 原九文件解码失败簇官方定向 | 实际扩展20测试文件／73单元，**828项／867.5秒／0红文件／0 skip／exit0**；batch15、keyframe分组14/16/1、evidence13、lifecycle9、req_s08 19、file_origin16、stage_gate5及全部pet_ui／stage_parallel工作单元通过。按正常GUI队列等待后取得令牌，未抢锁、取消或重复启动。日志仍含若干Tk `invalid command name ... after script` 清理提示，未隐去 |
| `smoke_test.py --architecture` | 532项／212.075秒／1FAIL，其他531通过；唯一失败为branch快照 `platform_tools.py 133 != 135`，需真实重测，未改共享基线 |
| 新测试局部分支度量 | `branch_coverage_report.py tests.test_ffmpeg_runtime --json <common-dir>/R3345-directed-branch.json --quiet` exit0、tests_ok=true；platform_tools仅7/135，明确只新测试定向覆盖，不能用作完整总账本 |
| 正式机器定向 | 正常 `round_evidence.py 3345 -k ffmpeg_runtime platform_tools` 实跑43项／0失败／exit0，凭据扫描0命中，`commit_base=b0a3bcd9`；只支持其指定范围，不代表完整架构绿 |
| 差异检查 | `git diff --check` 无输出；范围仅两生产文件及独立测试／结果／证据 |
| 安全全量 | 未运行。历史master b0全量于13:00:14 exit1有19红，它不是本修复分支测试结果，不据文件名扩修或宣绿 |

局部branch JSON SHA256：`b7325e079354245c3ba4c6a43e3c84eee3880e00a8a45addb76727a2880b11b7`，targets仅 `tests.test_ffmpeg_runtime`。不可并入完整账本冒充全目标覆盖。

日志SHA256：
- 改前红 `R3345-red.log`：`e53c3404239df56feedece941b09b5967350566c2155a5a8c3e0497d5edb97f6`。
- 新行为绿 `R3345-green.log`：`1ceecc46a32056dbd3abc7e2f8177c3a51be25a4b8390b03540fb3dd587faa0e`。
- 首轮定向 `R3345-targeted.log`：`72e25b6061339fe038cb525240c9808937a296727f896aacdaf26def00d15e88`。
- 默认冒烟 `R3345-smoke.log`：`5ce6e31a15604fa018d5796bc616b982d17a8a8e64a0ca15b3f2ec5edbc904ad`。
- 静态／规模 `R3345-static.log`：`cfa4f3e429639cbb5716a84c9e461ef2b37fced2fdaa91442f7f2ff10de6896c`。
- 架构 `R3345-architecture.log`：`cbc6e945cda6a1bcf68ed74918fa4e384ac5ec1a5be3605c3ba7f25001e21176`。

## 测试环境资源恢复

本工作树新建后固定公共gitlink为空：从既有common-dir归档恢复commit `1a43ae5a019d157eb3d45ad73e800081cb127763`，先校验其tree `d9a208042147179768f0a24dc54bdfbd5374a9e9`；只解压完整固定跟踪内容，不改变gitlink索引。ignored历史基准从主安装同路径复制，未纳管。本轮没有复制真实配置、用户项目或运行二进制，没有把资源缺失当代码回归。

## 四态与提交

| 状态 | 本轮结论 |
|---|---|
| 已实现 | 两处根因修复与9项行为测试已写入本隔离树 |
| 已验证 | 新行为、真实解码、原关键帧坏图校验、工具优先级、默认冒烟及静态通过；九簇扩展消费者828项全过；完整架构因真实新增决策点快照未刷新而未绿 |
| 已合入 | 只准备提交本独立分支，待lead整合；未改原foundation-hardening树或master |
| 已发布 | 否；未push、未更改真实随包环境、配置或用户项目 |

最终消费者完整inner日志已保全为common-dir `R3345-nine-consumers-inner.log`，9787字节，SHA256 `ce5e6b4aadc5800f58dbe607547043da53ae9340fb4fe8d4ff71dddb98ac9bcc`；绝对路径复制后读回与原日志字节相同。一次接续脚本曾把程序目录下证据路径误写为 `程序/tasks_round/...`，读取即FileNotFoundError、未写任何文件；已更正为当前目录相对路径并正常保存非敏感接续，未影响测试、源码或结果。

本轮按lead授权保存范围明确的源码检查点；定向证据43项真实通过，不代表架构532项全绿。共享账本由lead整合所有变更后按真实全目标刷新，不能手写covered或放宽floor；在此之前不标任务书完成。提交自身hash由交付消息返回，不为补hash追加覆盖证据的文档链。
