# R4407 结果：S04-AUDIO-TRACKS 分镜预演三轨临时声音（REQ-S04-74~77）
<!-- round-evidence: {"commit_base": "150768b0f", "credential_hits": 0, "evidence_sha256": "0031960e3c0a00cf", "exit": 0, "failed": 0, "passed": 24, "round": 4407, "tests": "run_selftests.py -k animatic_audio animatic_timeline"} -->

- 轮次类型（§3）：3.1 功能轮（新增 L2 模块 `domain/animatic_audio.py` 与 `edit_service.render_mixed_audio`）。
- 测试跑了吗：跑了定向与架构门禁，均绿；三个基线——默认冒烟本轮未跑（工作树未合入 master，验收按任务书两条命令）；架构门禁 708 条全绿；定向 24 条全绿；覆盖率基线已用工具机械刷新（133/684）。
- 欠账少了吗：零新增同层 L2 边、零新增登记项；参数棘轮未抬高。

## 缺陷复现方式（先红）

预演声音只有单轨 `assemble_image_timeline(audio)` 入口（domain/edit_service.py:66-102），没有「声音/对白、声音/整轨、声音/音乐」三轨语义：无逐镜 dialogue→临时 TTS 幂等生成、无对白超长告警、无整轨优先、无 -12dB 音乐混音命令拼装。REQ-S04-74~77（docs/stages/S04_分镜预演.md:67-70，现为 ⬜，本卡禁止改该文件，未翻 ✅）要求的能力整体缺失。

改前跑 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k animatic_audio animatic_timeline`，红 2 个文件共 3 条（原文摘要）：

```
### test_animatic_audio（1 条红）
ModuleNotFoundError: No module named 'domain.animatic_audio'

### test_animatic_timeline（2 条红）
ImportError: cannot import name 'render_mixed_audio' from 'domain.edit_service' (…\程序\domain\edit_service.py)
（test_req_s04_74_76_mixed_audio_runs_injected_command_in_scratch_area 与
  test_req_s04_76_mixed_audio_requires_l3_injected_command 两条，原因相同）
```

红的原因即卡面缺陷：`domain.animatic_audio` 不存在、`edit_service.render_mixed_audio` 不存在。（首次试跑还曾因测试文件自身 `b'…台词…'` 非 ASCII 字节字面量在 collection 期 SyntaxError 失败 1 条，修正字面量写法后转为上述缺陷红。）

## 改动位置（文件:行号）

- `domain/animatic_audio.py`（新建，1-145）：纯 L2、零同层 import。`SUBDIRS` 三轨目录；`dialogue_text` 归一（列表滤空「。」连接、dict 取 text/line）；`plan` 整轨优先/逐镜 TTS/静音三模式；`shot_tts` 文件名 `<shot_id>_temp_<sig>.mp3` 幂等复用、`tts-previs:` request_id；`detect_overlong` 0.1 秒容差告警不截断；`build_audio_mix_command` adelay 放置 + volume=-12dB + amix + apad + `-t` 截齐，全空走 anullsrc。
- `domain/edit_service.py:117-130`：新增 `render_mixed_audio`，混音命令由 L3 经 `mix_command` 注入（与 `assemble_image_timeline` 零耦合；原签名与 4 命令行为未动）。
- `tests/test_animatic_audio.py`（新建）：19 条，覆盖卡面全部边界例子（空输入 silent+anullsrc、幂等复用/0 字节重合成、整轨优先、-12dB 与 `-t`、超长告警与容差、多句列表归一）。
- `tests/test_animatic_timeline.py:53-83`：`MixedAudioRenderTests` 2 条（注入命令透传并执行、未注入拒跑）；旧 3 条断言原样保留。
- `tests/architecture/_layers.py:46`：`_register(2, …, "animatic_audio", …)`。
- `维护记录/架构统一基数.json`：第一项 `entity_paths` 加 `"animatic_audio": "domain/animatic_audio.py"`，`exempt_items` 加 `"animatic_audio"`，`exempt_count` 57→58。
- `维护记录/覆盖率基线.json`：scripts/coverage_report.py 原 15 目标机械刷新（tests_ok=true，133/684）。
- `runbook.md` §11：模块数 683→684、未触达 550→551（181、183、186 行）。

## 签名与卡面接口契约的一处偏差及理由

复杂度棘轮 `test_complexity_ratchet` 参数上限为 7（kwonly 全计），首次架构门禁红：`animatic_audio.py::shot_tts 8 个参数 > 上限 7`、`edit_service.py::render_mixed_audio 8 个参数 > 上限 7`。收拢方式：`shot_tts` 尾部 `project/persistent` 收进 `**options`（persistent 默认 True 不变）；`render_mixed_audio` 三个轨道参数收进 `**tracks` 透传给注入的 mix_command。调用方写法与卡面契约逐字一致（仍写 `project=…, persistent=…, full_track=…, dialogue_clips=…, music=…`），仅签名聚合位置不同。

## 验收命令输出尾部（原文）

命令一 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k animatic_audio animatic_timeline`（目录 程序，退出码 0）：

```
跑 2 个测试文件 / 2 路工作单元（8 路并行）
  test_animatic_audio           19 条     0.0 秒
  test_animatic_timeline         5 条     0.0 秒

共 24 条用例，0.7 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过

ALL TESTS PASSED
```

命令二 `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（目录 程序，退出码 0）：

```
----------------------------------------------------------------------
Ran 708 tests in 251.663s

✅ 架构治理测试：tests/architecture
OK
```

覆盖率刷新 `..\..\..\..\运行环境\Python\python.exe -B scripts\coverage_report.py <原15目标> --json 维护记录/覆盖率基线.json`：退出码 0，尾部 `模块被覆盖：133/684；目标用例：全通过`。

## 没有验证的地方

- 未跑真实 ffmpeg/ffprobe 进程：混音命令只断言拼装形态（adelay/volume/amix/apad/-t/anullsrc），真实转码结果未验证。
- L3 消费方（animatic_service 的 build_bundle、桌面页导入整轨/音乐入口、对白超长告警上屏）不在本卡允许文件内，未接线；`plan/detect_overlong` 的产物路径约定待 L3 轮次落地。
- 未跑默认冒烟与全量 `--all --safe`（非本卡验收项）。

## 卡外发现（只记录，不顺手修）

- `docs/stages/S04_分镜预演.md` 已含 REQ-S04-74~77 与 DES-S04-21（现为 ⬜）；本卡禁止改该文件，未翻 ✅。
- `animatic_service.build_bundle`（domain/animatic_service.py:117-202）仍是单音频入口，逐镜 TTS 需后续 L3 轮次改走 `plan`＋`render_mixed_audio`。
