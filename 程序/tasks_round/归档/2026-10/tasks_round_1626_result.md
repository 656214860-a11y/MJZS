# R1626 辅助依赖清单与解释器版本策略（Q12）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round/tasks_round_1610_result.md) J 第三批 Q12）。
- 三基线：默认冒烟 **8/8**（R1625 实测）；架构门禁 **356 项**；全量安全全量 **R1624 绿**（502 秒、0 红、凭据 round 1624）。
- 欠账：本轮只改 `程序/runbook.md`（`.md` 非源码），**不是源码轮**，计数不变。

## 前提核对：R1610 那两句话的真实含义

R1610 只写「登记辅助依赖清单与解释器版本策略（alpha → 稳定版迁移计划）」。核原始证据时发现两处按字面写就会写错：

1. **「解释器缺模块」不是 alpha 的缺陷，是有意裁剪**。本会话实测 `import trace`／`import symtable`／`import sqlite3`
   都失败，看起来像 alpha 构建不全。核 `tests/test_stdlib_closure.py` 才知道：第 34 期从 `运行环境\Python\Lib`
   剪掉了 **58 个**标准库模块（`PRUNED` 清单），并且有两道静态闸——①从 `启动漫剧制作助手.pyw` 出发的 import 闭包
   必须逐层解析到盘上（函数体里的 import 也解析，唯一放行 Blender 宿主里的 `bpy`）；②被裁模块不许再 import、
   盘上也不许悄悄出现。所以文档必须写成「缺＝可能是有意裁剪，动它要同步清单与门禁」，而不是「alpha 不稳定」。
2. **「辅助依赖」不是 Python 包**。`tests/architecture/test_static_hygiene.py` 写明本项目**零运行时依赖**；
   真正要登记的是外部程序（FFmpeg／ComfyUI／Blender／Claude Desktop／Codex／Claude Code／Qwen Code）与
   网络服务的密钥。清单的权威源是 `environment_check.py`（"环境自检"页就是它），不是 R1610 的话。

## 做了什么（`程序/runbook.md` §8／§9）

- **§8 辅助依赖清单**：逐项给「必需性／怎么找／缺了会怎样／权威源」，并点出密钥查找次序（环境变量 → 统一 `.env`
  → `private/.env`，不落库）与密钥名（`DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、`DASHSCOPE_API_KEY`／`QWEN_API_KEY`、
  `COMFY_API_KEY`、`TTS_API_KEY`）。另记一条易误判点：ComfyUI 的服务进程是它自己的 `.venv\Scripts\python.exe -s ComfyUI\main.py`，
  与本助手解释器无关，"强制关闭"按命令行特征认人。
- **§9 解释器版本策略与迁移计划**：现状（随附 3.15.0a2、AGENTS §1 钉路径、不用全局 Python）＋裁剪事实与两道闸
  ＋迁移计划（触发条件、前置基线、六步：并列安装稳定版 → 重跑闭包门禁并**重新决定裁剪清单** → 冒烟/架构/全量依次绿 →
  手工过 GUI 面 → 同步 AGENTS §1 与 `安装信息.json` → 旧版保留一个周期再删）＋风险（alpha API 变更、警告升硬错误、
  裁剪清单失效、`test_startup_budget` 对新解释器启动耗时敏感）＋红线（不为迁移引入第三方依赖、不把裁掉的模块悄悄放回）。
- 顺带把 §3 的全量耗时从"约 11 分钟"改成实测口径（约 8–11 分钟，R1624 实测 502 秒）。

## 验证

| 项 | 结果 |
| --- | --- |
| `tests.architecture.test_round_baselines` | OK（含轮次连续性与欠账账簿项） |
| `tests.test_line_endings` | OK（`.md` 必须 LF） |

文档轮不跑全量、不重复跑架构门禁（AGENTS §5 去重；架构门禁的最近一次真实绿证是 R1624 的后台全量，其中含架构项）。

## 诚实边界

- 迁移计划是**策略**，不是已执行的迁移：本轮没有在稳定版解释器上跑过任何用例，六步里第 2 步（重新决定裁剪清单）
  是迁移时最容易踩的地方，已单列。
- §8 的"怎么找"来自代码里的常量与查找次序（`integrations.comfy_executable`、`white_model_service.find_blender`、
  `workflow_settings.find_program`）；本机没有装 ComfyUI／Blender，未逐项实机验证。
- `PRUNED` 的 58 项与盘上状态由既有门禁保证，本轮未改动；`安装信息.json` 里的版本号（0.6-20260918）是安装时的记录，
  不代表当前程序版本。
- 本轮只改文档，未实机演练 runbook 与迁移步骤。

## 清单收口

R1610 J 的 Q1–Q12 至此全部落地（Q1／Q3 → R1611，Q2 → R1612，Q4 → R1613，Q5 → R1614，Q6 → R1615，Q7 → R1616，
Q8 → R1617，Q9 → R1618–R1623，Q10 → R1624，Q11 → R1625，Q12 → 本轮）。
