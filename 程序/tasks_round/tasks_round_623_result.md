# R623 外部桌面应用绑定普查（只读诊断轮）

## 开头三问（AGENTS.md 第 7 节）

- 本轮是功能轮还是整理轮？只读诊断轮；不实施解绑或功能调整。
- 测试跑了吗？三个基线过了吗？未跑。此次只读取源码、测试和既有报告，不产生代码变更，故未把基线当作本轮验收。
- `project_status.md` 的欠账少了吗？没有；本轮仅形成证据，不消化欠账。

编号自检：`tasks_round/` 已有连续 R603–R622，R623 不存在；因此新增本报告，未覆盖既有结果。

## 范围和方法

检索范围为运行源码、启动脚本和 `tests/` 中的 `CODEX_HOME`、`.codex`、`codex`、`chatgpt`、`claude`、桌面程序路径、环境变量、进程名和注册表访问。文档、SKILL 正文和纯显示文案中出现的产品名不算“探测或依赖”。结论先行：**没有“外部桌面应用不存在即整个助手不能启动”的全局硬依赖；存在若干按用户显式选择才生效的功能级硬依赖。**

## A. 硬依赖（功能级；不影响应用本体启动）

|位置与调用场景|原始代码片段|失败行为与影响|
|---|---|---|
|[workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:371) `find_program()`；阶段配置解析、后台/交互执行前|`found=shutil.which(engine+'.exe')`<br>`if engine=='codex':`<br>` choices=list((Path(os.environ.get('LOCALAPPDATA',''))/'OpenAI/Codex/bin').glob('*/codex.exe'))`<br>`else: native=Path.home()/'.local/bin/claude.exe`<br>`raise ValueError('未找到 '+ENGINES[engine]+' 命令行程序…')`|选了 Codex 或 Claude Desktop 且未手工指定有效 `.exe` 时，抛可读 `ValueError`；阶段不能启动，但 UI/其它 API 或引擎不受影响。Codex 的私有安装目录是动态 `%LOCALAPPDATA%\OpenAI\Codex\bin`，Claude 是 `~/.local/bin/claude.exe`。|
|[workflow_engines.py](D:/漫剧制作助手/程序/workflow_engines.py:62) `background_command()`；后台阶段执行|`exe=find_program(config)`<br>`if config['engine']=='codex': args=[exe,'exec',...]`<br>`else: args=[exe,'-p','--output-format','json',...]`|继承 `find_program()` 的受控异常；只阻断该桌面引擎的后台阶段。|
|[workflow_engines.py](D:/漫剧制作助手/程序/workflow_engines.py:146) `launch_interactive()`；“交给本机 Agent”阶段执行|`exe=find_program(config)`<br>`if config['engine']=='codex': from codex_tasks import prepare_task`<br>`... persisted=bool(session and any((Path.home()/'.claude/projects').glob('*/'+session+'.jsonl')))`|Codex/Claude 启动文件不存在时该交互流程报错；进程启动型 `OSError` 时仅在配置了兼容 API 回退时改走 Qwen，否则报“本机 Agent 无法启动；未配置…API 回退”。Claude 私有会话目录不存在只令 `persisted=False`，从新会话启动，并非错误。|
|[codex_tasks.py](D:/漫剧制作助手/程序/codex_tasks.py:36) `RPC.__enter__()`；Codex 任务创建/RPC|`exe=shutil.which('codex')`<br>`paths=list((Path(os.environ.get('LOCALAPPDATA',''))/'OpenAI/Codex/bin').glob('*/codex.exe'))`<br>`if not exe:raise ValueError('未找到Codex程序，请先安装并打开Codex')`|Codex 任务书/RPC功能无法运行，受控 `ValueError`。调用点为上表 `launch_interactive()` 的 Codex 分支；不影响其它阶段。|
|[qwen_adapter.py](D:/漫剧制作助手/程序/qwen_adapter.py:11) `command()`；选择 Qwen 时|`root=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'qwen-code/qwen-code'`<br>`node=root/'node/node.exe'; entry=root/'lib/cli-entry.js'`<br>`found=shutil.which('qwen.exe')`<br>`raise ValueError('未找到 Qwen Code…')`|Qwen Code 不存在时，选择它的阶段无法启动，给出受控安装/选择程序提示；不是 Codex/ChatGPT/Claude 目录。|
|[comfy_runtime.py](D:/漫剧制作助手/程序/comfy_runtime.py:11) `executable()/open_comfy()`；用户主动打开本机 ComfyUI|`r'C:\Program Files\Comfy Desktop\Comfy Desktop.exe'`<br>`Path(os.environ.get('LOCALAPPDATA',''))/'Programs/ComfyUI/ComfyUI.exe'`<br>`if exe is None: raise ValueError('未找到本地 ComfyUI 桌面程序…')`|只阻断“桌面打开 ComfyUI”这项本机生成辅助功能；抛受控错误。|
|[previs_automation.py](D:/漫剧制作助手/程序/previs_automation.py:71) 经 [white_model_service.py](D:/漫剧制作助手/程序/white_model_service.py:70) `find_blender()`；白模预演|`call_config['program']=find_program(call_config)`<br>`if not wm.find_blender(refresh=True):raise ValueError('未找到本地 Blender')`<br>`choices = [Path('E:/Blender/blender.exe'), Path('D:/Blender/blender.exe')]`<br>`found = shutil.which('blender')`|找不到 Blender 时，白模自动化入口报“未找到本地 Blender”；正常剧本、阶段配置和非白模功能不受影响。另有 [native_apps.py](D:/漫剧制作助手/程序/native_apps.py:73) 用 `tasklist ... blender.exe` 仅探测 Blender 窗口。|
|[integrations.py](D:/漫剧制作助手/程序/integrations.py:12) `skill_file()`；遗留 Codex 已安装技能读取 API|`home=Path(skill_home) if skill_home else Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills'`<br>`if not path.is_file():raise ValueError('未找到Codex已安装技能：'+str(path))`|直接调用会因 `CODEX_HOME/skills/<目录>/SKILL.md` 不存在而抛受控错误。代码检索显示生产 `.py` 中无 `skill_file(` 调用，只有定义；因此它目前不是运行主路径依赖。|

## B. 软探测、可选集成和逻辑标识

|位置与调用场景|原始代码片段|探测失败行为；外部不存在的影响|
|---|---|---|
|[model_pool.py](D:/漫剧制作助手/程序/model_pool.py:63)、[model_pool.py](D:/漫剧制作助手/程序/model_pool.py:105)、[model_pool.py](D:/漫剧制作助手/程序/model_pool.py:223)；模型池/阶段配置|`DESKTOP_ENGINES = {'chatgpt-desktop': 'codex', 'claude-desktop': 'claude'}`<br>`def desktop_engine(model_id): return DESKTOP_ENGINES.get(...)`<br>`桌面 Agent 是内建调用目标…不能…消失。`|这里不检查安装状态，仅把逻辑模型 ID 映射为引擎。因此所有机器都显示这两个可选项；真正选择后才进入 A 的 `find_program()`。|
|[workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:320)；读取当前阶段配置|`engine = model_pool.desktop_engine(selected)`<br>`return engine, find_program({'engine': engine, 'program': profile['program']})`|对桌面模型调用程序定位；`KeyError, ValueError` 分支返回空程序而非让读配置崩溃。实际执行才给用户错误。|
|[engine_probe.py](D:/漫剧制作助手/程序/engine_probe.py:50)、[engine_probe.py](D:/漫剧制作助手/程序/engine_probe.py:179)；手动“引擎真机验证”|`found=which(engine+'.exe')`<br>`.../'OpenAI'/'Codex'/'bin'...`<br>`native=home/'.local/bin/claude.exe'`<br>`return any((home/'.claude'/'projects').glob('*/'+session+'.jsonl'))`|探测不到返回 `None`/`not-installed` 和尝试路径，不影响应用；只影响维护诊断结果。|
|[codex_paste.py](D:/漫剧制作助手/程序/codex_paste.py:10) 与 [codex_paste.ps1](D:/漫剧制作助手/程序/codex_paste.ps1:26)、:129；把内容粘入已开的 Codex/ChatGPT Desktop|`if($process.ProcessName -eq 'ChatGPT'){ return $path -match ...'OpenAI\.Codex_.../app/ChatGPT\.exe$' }`<br>`return $process.ProcessName -eq 'Codex' -and $path -match ...`<br>`$deadline=[DateTime]::UtcNow.AddSeconds(15)`|仅接受已运行、路径经校验的 ChatGPT（OpenAI.Codex 包）或 Codex 进程；15 秒未定位返回 `ok:false`：“未找到可确认的 Codex 消息输入框；本次内容已复制，可手动粘贴。”不冻结主程序、不强制安装。|
|[token_saver.py](D:/漫剧制作助手/程序/token_saver.py:510)、:544、:560；宠物设置里的 Codex Token 节省配置|`env=os.environ.get('CODEX_HOME'); return Path(env) if env else Path.home()/'.codex'`<br>`def deliver_global(values=None, home=None):`<br>`def scan(project=None, home=None, environ=None):`|这是用户主动“写/扫描 Codex 配置”的可选功能，`CODEX_HOME` 缺失时使用 `~/.codex`。不会在应用启动或阶段候选中读取；即使未安装 Codex，也可创建/读取配置文件，不能证明客户端存在。|
|[pet_settings_ui.py](D:/漫剧制作助手/程序/pet_settings_ui.py:相关 Token 设置写入入口)；设置页|`token_saver.deliver_global(read(), home=getattr(pet,'codex_home',None))`|只由用户保存全局 Codex 设定时触发；文件系统错误显示反馈，不影响其它设置。|
|[integrations.py](D:/漫剧制作助手/程序/integrations.py:22)、[desktop.py](D:/漫剧制作助手/程序/desktop.py:4704)；自动/手动拉起 Comfy|`if exe is None:`<br>` if silent: self.status.set('没找到 ComfyUI 桌面程序，本次不启动…'); return False`|自动链路静默降级，手动链路给文件选择器；不需要 ComfyUI 就不会缺功能。|
|[native_apps.py](D:/漫剧制作助手/程序/native_apps.py:30)、:58；关闭 Comfy 进程|`Get-CimInstance Win32_Process ... 'ComfyUI'`<br>`['taskkill', '/IM', image, '/F', '/T']`|按 ComfyUI 命令行/映像名采样和结束，仅本机 Comfy 管理功能使用；未发现时无进程可关。|
|[desktop.py](D:/漫剧制作助手/程序/desktop.py:5924)；启动剪映（非 AI，仍是外部桌面应用）|`local/'JianyingPro/JianyingPro.exe'`<br>`...glob('*/JianyingPro.exe')`<br>`raise ValueError('未自动找到剪映专业版…')`|外部剪辑器不存在时仅“启动剪映”失败，有受控提示。|

### 注册表、环境变量、私有路径的负面证据

- 全项目 `winreg/HKCU/HKLM` 命中只在 [platform_tools.py](D:/漫剧制作助手/程序/platform_tools.py:14) 的可选 `windows_registry()` 和 [pet_ui.py](D:/漫剧制作助手/程序/pet_ui.py:768) 的本助手开机自启 `HKCU\\...\\Run`。没有 Codex、ChatGPT、Claude、Comfy、Qwen、Blender 或剪映的注册表探测。
- 阶段 SKILL 注册表不再碰外部目录：`skill_registry.py` 没有 `CODEX_HOME`、`.codex`、`ChatGPT` 或 `Claude` 命中。R622 已使预设技能候选固定于程序内置 `skills/`；该结论与本轮源码检索一致。
- 没有发现 `chatgpt-desktop` 或 `claude-desktop` 的私有目录探测；两者在 `model_pool.py` 中只是逻辑 ID。ChatGPT Desktop 的唯一进程/可执行路径校验是 `codex_paste.ps1` 的可选自动粘贴。

## C. 外部不存在时的分类判断

1. **应用级硬依赖：无。** 应用启动、阶段配置候选、项目配置读取和 API 模型路径不会因为未安装 Codex/ChatGPT Desktop/Claude Desktop 而失败。
2. **功能级硬依赖：有。** 用户明确选中 Codex、Claude、Qwen、Comfy、Blender、剪映对应功能时，缺少该程序会阻断该动作；都以 `ValueError` 或状态提示暴露，未见未捕获的启动链崩溃。
3. **软探测：** `engine_probe`、Claude 会话历史检查、Comfy 静默启动、Codex 自动粘贴和模型池逻辑 ID 都是可缺失的。唯有“桌面引擎优先”这种配置选择会把后续执行导向功能级硬依赖，并非自动安装探测造成。

## D. 测试中的外部应用存在性依赖

**没有测试依赖真实 Codex、ChatGPT Desktop、Claude Desktop、ComfyUI、Qwen、Blender 或剪映已安装。** 逐项证据如下；它们用临时目录、注入函数或模拟可执行文件验证契约。

|测试位置|断言/做法|是否隐式要求真实桌面应用|
|---|---|---|
|[tests/test_core.py](D:/漫剧制作助手/程序/tests/test_core.py:825) 与 [tests/test_skills.py](D:/漫剧制作助手/程序/tests/test_skills.py:1195)|`mock.patch.dict(os.environ, {'CODEX_HOME': td})`；断言预设/`flow_skill_choices()` 忽略它，且路径不含 `.codex`。|否；恰好防止外部 Codex 目录成为候选来源。|
|[tests/test_engine_probe.py](D:/漫剧制作助手/程序/tests/test_engine_probe.py:55)、:172、:246|临时 `claude.exe/codex.exe`、注入 `which`/runner/home，临时 `.claude/projects`。|否；测试的是找不到时的 `not-installed` 和路径契约。|
|[tests/test_workflow.py](D:/漫剧制作助手/程序/tests/test_workflow.py:678)、:707、:824|以 lambda/patch 返回 `C:/Apps/codex.exe` 或抛 `ValueError('not installed')`，并用项目临时 `codex.exe`。|否；覆盖桌面优先和缺失回退，未启动真实客户端。|
|[tests/test_model_pool.py](D:/漫剧制作助手/程序/tests/test_model_pool.py:83)|断言池含 `chatgpt-desktop`、`claude-desktop`，及 `status(...) == (True,'桌面 Agent')`。|否；要求逻辑项存在，并不检查安装状态。若将来改成隐藏未安装项，此测试应随产品契约更新。|
|[tests/test_pet_ui.py](D:/漫剧制作助手/程序/tests/test_pet_ui.py:3039)、[tests/test_pet_settings.py](D:/漫剧制作助手/程序/tests/test_pet_settings.py:441)|断言两个逻辑模型存在、旧“打开 ChatGPT 桌面”按钮不存在。|否；UI/配置契约，不启动或探测外部软件。|
|[tests/test_token_saver.py](D:/漫剧制作助手/程序/tests/test_token_saver.py:548)、:555、:731|设置临时 `CODEX_HOME`，断言写入临时 `.codex/config.toml`。|否；测试的是可选 Codex 配置文件写入。它是对 Codex 配置格式的显式耦合，不是对已安装客户端的隐式依赖。|
|[tests/test_previs_monitor.py](D:/漫剧制作助手/程序/tests/test_previs_monitor.py:254) 及预演测试|stub `find_program` 为 `codex.exe`，Blender/本机进程均为替身。|否。|
|[smoke_test.py](D:/漫剧制作助手/程序/smoke_test.py:330)、:393、:405|静态检查引擎验证台账、Claude 入口、`chatgpt-desktop/claude-desktop` 映射。|否；检查源码/维护记录字段，不检查本机安装。|

## E. 结论：绑定清单与风险

- 需优先治理的真实环境耦合是 `workflow_settings.find_program()`、`codex_tasks.RPC` 和 `workflow_engines.launch_interactive()`：它们决定已选桌面阶段是否可执行。若产品目标是“没有任何外部客户端也应完整执行”，需要为各桌面阶段给出明确 API/本地替代契约，而不是仅删除路径探测。
- `token_saver` 的 `CODEX_HOME` 是独立的“配置 Codex”功能，和阶段 SKILL 扫描已解耦。删除它会减少 Codex 绑定，但会改变用户主动配置 Codex 的能力。
- `codex_paste.ps1` 严格验证进程名和 WindowsApps 包路径是安全边界；若保留自动粘贴，不能为“兼容”而放宽为任意 ChatGPT 进程。

## J. 整改路线（本轮不实施）

1. **先收敛阶段执行的自动外部优先（影响：`workflow_settings.py`、`workflow_engines.py`、模型池和阶段设置测试）。** 将桌面模型保留为用户显式选择项；读取配置时不自动把 API 模型升级到本机 Codex。对缺程序统一显示可选动作：“选择 exe / 改用 API / 取消”。影响面是已配置 `chatgpt-desktop`、`claude-desktop` 的项目，不应改写其用户数据。
2. **再决定 Codex 专属功能的产品边界（影响：`codex_tasks.py`、`codex_paste.py/.ps1`、`token_saver.py`、宠物设置）。** 若目标是不依赖 Codex，隐藏或拆出“创建 Codex 任务/粘贴到 Codex/写 Codex 全局配置”；若仍保留，明确标为可选集成并保持当前受控失败。`token_saver` 不应与阶段 SKILL 候选混合。
3. **独立治理其它外部桌面工具（影响：Comfy、Qwen、Blender、剪映各自适配器）。** 保留当前“显式启动时才要求安装”的行为；补充统一能力状态而不要在启动时扫描全部程序。这样避免新的机器差异和启动性能损失。
4. **不动的安全边界：** 保留 `codex_paste.ps1` 的进程路径白名单，保留注册表仅用于本助手自启动；两者不是 SKILL 扫描来源。

## K. 测试计划

1. 为阶段配置补回归：在 `CODEX_HOME` 指向临时含技能目录的情况下，断言 `flow_skill_choices()` 仍只有程序 `skills/`，并断言 `skill_registry` 不读取外部根。
2. 为 `find_program()` 和 `launch_interactive()` 补参数化测试：PATH、`%LOCALAPPDATA%`、`~/.local/bin` 全部缺失时，Codex/Claude/Qwen 分别给出受控错误；配置 API fallback 时仅验证回退分支，不启动真实 CLI。
3. 保留并加强 `codex_paste` 的离线契约测试：不存在匹配进程必须在有限超时后返回失败和手工粘贴文案；不得以真实 ChatGPT 进程作为测试前置。
4. 为 Comfy/Blender/剪映补“未安装”测试，断言静默路径返回 `False` 或受控 `ValueError`，并验证不写用户配置。
5. 若执行 J-2 的拆分，更新 `tests/test_token_saver.py` 以临时目录验证可选配置功能，删除任何要求默认页面展示 Codex 专属入口的断言；不删除 API 模型或内置阶段配置测试。

## 自审

- 本轮未修改任何 `.py`、测试、配置、用户数据或既有结果文件；仅新增本报告。
- 报告中每个运行时绑定条目均给出源码文件:行号和原始片段；未把文档/提示词中的名称误列为运行依赖。
- 未启动 GUI、未访问或写入任何外部应用私有目录，也未执行外部桌面程序。
