# 诊断报告：残留 SKILL 无法删除（R3276）

> 日期：2026-11-18　｜　轮次：R3276（只读诊断轮）
> 症状：① `设置→SKILL管理` 删不掉 `程序\skills\00全流程SKILL\AIGC创作全流程`；② 拆分出的 `pipeline-*` skill 也删不掉。
> 本文为只读诊断产物，不含代码改动。行号基于 master `8317c4cc`（R3258）实测。

---

## 一、结论先行：这是三个独立缺陷叠加，不是「内置只读」一条规则

| # | 缺陷 | 症状 | 根因位置 |
| --- | --- | --- | --- |
| **D1** | 非阶段目录对 SKILL 管理完全不可见 | `AIGC创作全流程` 在管理列表里根本不存在，没有删除按钮 | `orchestrator/skill_registry.py:494` `_stage_directories()` |
| **D2** | 内置层三面封死：不能删、不能禁、不能藏 | `pipeline-*` 在列表里，但删除/禁用按钮均被拦 | `pet_skills_manage.py:303`、`:411`；`ui/skill_lifecycle_service.py:91`、`:331` |
| **D3** | `AIGC创作全流程` 是无映射的孤儿 gitlink | 即使删掉目录，git 索引仍保留 submodule 记录，`git status` 持续报错 | git index `160000 1a43ae5a...`；`.gitmodules` 不存在 |

**D1 与 D2 的关系**：两者都表现为「删不掉」，但机制完全不同。D1 是「看不见 → 无从操作」，D2 是「看得见 → 被规则拦住」。上一轮修复只处理了 D2 的一半（确认内置不可删），对 D1 没有任何作用——**这正是用户被困住的真实原因**。

---

## 二、D1：非阶段目录不进注册表（实测证据）

### 2.1 机制

`orchestrator/skill_registry.py:494-502`：

```python
def _stage_directories(self, root=None):
    """只返回 SKILL 根目录下直接对应 01—13 的目录，不猜测其他资料目录。"""
    root = self.root if root is None else root
    entries = sorted(root.iterdir(), key=lambda path: str(path))
    return tuple(path for path in entries
                 if path.is_dir() and stage_from_path(path / '__stage_probe__'))
```

`stage_from_path`（`orchestrator/skill_project_layer.py:27-36`）从路径中匹配 `^(\d{2})` 并在 `STAGE_DIRECTORY_IDS`（`01`–`13`）里查表。`00` 不在表内 → 返回空串 → 该目录被 `_stage_directories()` 过滤掉。

`_package_sources`（`:580-599`）虽然会扫描阶段目录下的一层子目录找包，但**前提是那个父目录先被 `_stage_directories()` 接纳**。`00全流程SKILL` 不在其中，所以它下面的三个包一个都进不来。

### 2.2 实测

```
注册表看到的阶段目录：01 剧本准备SKILL … 13质检交付（共 13 个，全部 builtin）
00全流程SKILL in stage dirs? False
AIGC 目录在磁盘上存在? True

注册表 total: 73
contains AIGC? False
contains sd-? False
contains short-drama-director? False
contains pipeline-? 13
```

### 2.3 影响面：不止 AIGC 一个

`程序\skills\` 根下**同样不可见**的还有 5 个目录：

| 目录 | 子项数 | 是否被 git 跟踪 |
| --- | --- | --- |
| `imagegen` | 6 | — |
| `short-drama-storyboard` | 6 | — |
| `storyboard-image-prompts` | 4 | 在 `skills-lock.json` 里登记 |
| `templates` | 14 | — |
| `video-storyboard-gen` | 14 | — |

加上 `00全流程SKILL` 下的 `AIGC创作全流程`、`cinematic-director`、`jingju-skills`，共 **8 个目录 / 3 个包组**对 SKILL 管理不可见。

### 2.4 设计意图是明确的，不是疏漏

`_stage_directories` 的 docstring 写着「不猜测其他资料目录」；`_package_sources` 写着「永远不递归枚举包内子 SKILL」；`stage_from_path` 写着「非阶段资料目录不作猜测」。这三处注释表明「排除非阶段目录」是**有意设计**，目的是防止阶段配置的下拉选项被资料包污染。

所以修复不能简单改成「扫描 everything」——那会破坏这个设计意图。需要的是**另一条受控通道**。

---

## 三、D2：内置层三面封死（实测证据）

### 3.1 三个拦截点

| 操作 | 位置 | 原文 |
| --- | --- | --- |
| 删除（UI 预检） | `pet_skills_manage.py:303` | `if getattr(skill, 'layer', '') == 'builtin': hint.set('内置 SKILL 只读，不能删除；要换行为请用用户层同名覆盖。')` |
| 删除（服务端） | `ui/skill_lifecycle_service.py:331` | `raise skill_import_service.ImportBlocked('内置 SKILL 只读，不能删除')` |
| **禁用** | `pet_skills_manage.py:411` | `hint.set('内置 SKILL 只读，不能禁用；要换行为请用用户层同名覆盖。')` |
| **禁用（服务端）** | `ui/skill_lifecycle_service.py:91-92` | `if entry['layer'] == 'builtin': raise skill_import_service.ImportBlocked('内置 SKILL 只读，不能禁用')` |

**注意第 3、4 行**：内置层连「禁用」都被拦。而禁用机制本身已经完备——

`ui/skill_lifecycle_service.py:85-96` 的 `set_skill_disabled()` 把条目登记进 `data/skills/disabled_skills.json`，文件保留、`getAll()` 滤除。这个能力**对用户层和项目层工作正常**，只差内置层的一行判断。

### 3.2 用户层覆盖这条路走不通

三处提示都建议「要换行为请用用户层同名覆盖」。但覆盖只能**替换行为**，不能**消除干扰**：

- 用户层同名 skill 会遮蔽内置版（`scan()` 的 `:766` 有影子告警），列表里仍然显示一条。
- 用户真正要的是「列表里别再出现它」，覆盖做不到。

### 3.3 没有任何测试锁定这些拦截

全仓搜索「内置 SKILL 只读」只命中 4 处生产代码，**测试里 0 处**。`tests/` 下搜索「不能删除」只命中两处与本议题无关的断言（分镜文件、编辑框）。**改动这条规则不会撞断现有断言。**

---

## 四、D3：孤儿 gitlink（决定性发现）

### 4.1 实测

```
$ git ls-files -s '程序/skills/00全流程SKILL/AIGC创作全流程'
160000 1a43ae5a019d157eb3d45ad73e800081cb127763 0  ...
```

`160000` ＝ gitlink ＝ submodule 记录。但：

| 检查项 | 结果 |
| --- | --- |
| `.gitmodules` 是否存在 | **不存在**（`Test-Path` False） |
| `.git/modules/` 内容 | **空** |
| 该目录内是否有 `.git` | **没有** |
| `git submodule status` | 报错 `fatal: no submodule mapping found in .gitmodules for path '程序/reference/HoLLMwood'` |

即：git 索引声称「这里是个子仓库」，但子仓库的一切元数据都已丢失。**这是一个孤儿 gitlink。**

### 4.2 同样形态的还有 3 个

```
160000 3ef9f995... 程序/reference/HoLLMwood                              （.git 存在）
160000 1a43ae5a... 程序/skills/00全流程SKILL/AIGC创作全流程              （.git 不存在）
160000 6c3d7399... 程序/skills/01 剧本准备SKILL/剧本锻造                  （.git 存在）
160000 357d1348... 程序/skills/01 剧本准备SKILL/编剧技能集                （.git 存在）
```

### 4.3 为什么删目录不够

实测 `storage_maintenance.recycle_paths()` 对该目录**工作正常**（临时目录验证：`status: moved`，回收记录完整）。回收站不背这个锅。

问题在 git 层：`recycle_paths` 移走的是**文件系统内容**，git 索引里的 gitlink 记录**不受影响**。后果：

- `git status` 持续报 `no submodule mapping found`
- `git checkout` / `git restore` 可能把目录重新检出
- 用户会反复遇到「删了又回来」

**所以 D3 必须在 git 索引层处理，UI 修复无法覆盖。**

---

## 五、Q10 澄清后的架构事实：13 个子技能没有 stage

用户说明：`00` 是总包放「整个流程的项目级 skill」，`01-13` 是「阶段 skill 的位置」，用户选择单独安装在哪个阶段，都通过同一输入框调用。

实测 `AIGC创作全流程` 下的子技能结构：

| 项 | 实测 |
| --- | --- |
| 含 `SKILL.md` 的子目录 | **13 个**（非 14——`assets` 只有资源图片，无 `SKILL.md`） |
| 名单 | `sd-asset-engine`、`sd-combat-engine`、`sd-decision-engine`、`sd-feed-engine`、`sd-jieshuo-engine`、`sd-overseas-engine`、`sd-qc-engine`、`sd-real-engine`、`sd-recon-engine`、`sd-script-engine`、`sd-storyboard-engine`、`sd-xuanhuan-engine`、`short-drama-director` |
| **frontmatter 的 `stage` 字段** | **13 个全部为空**（`stage=(none)`） |
| 对比 `pipeline-*` | 13 个全部有 `stage`（`剧本准备`／`剧本结构`／`初步分镜`…） |

**这是安装流程的关键阻塞**：`plan_import(source, target_dir, stage, registry)` 的 `target_dir` 必须来自阶段目录，而 13 个子技能没有 `stage` 就无法映射到 `01-13` 任何一档。

**另注**：根目录 `README.md` 的版本说明写「1 总控 + 12 子技能」，实测是 13 个子目录含 `SKILL.md`——README 自身计数与实物不符（12 `sd-*-engine` + 1 `short-drama-director` = 13）。

---

## 六、根因链总结

```
用户点「删除」
   │
   ├─ 若目标在 00全流程SKILL 下（AIGC 包）
   │     └─ D1：不在 _stage_directories() → 不在注册表 → UI 列表里没有这一行
   │            → 没有删除按钮 → 死路
   │
   └─ 若目标是 01-13 下的 pipeline-*
         └─ D2：layer == 'builtin' → 删除被拦（:303 / :331）
                → 禁用也被拦（:411 / :91）→ 死路

即使绕过以上两条手工删了目录：
   └─ D3：git 索引保留 160000 gitlink，.gitmodules 不存在
          → git status 报错 / 可能被重新检出 → 「删了又回来」
```

**上一轮修复的误判**：「内置 skill 不让删除是正确逻辑」这句话本身对**删除**成立（内置随程序分发，删了升级会回来），但它被当成了**全部结论**，于是既没给禁用开口，也没人发现 D1 和 D3 这两个真正的死路。

---

## 七、修复方向（详见任务书）

| 缺陷 | 方向 | 改动量 |
| --- | --- | --- |
| D1 | 新增「残留包管理」受控通道，不改 `_stage_directories` 的严格语义 | 中（新增 L2 服务 + L4 入口） |
| D2 | 放开内置层的**禁用**，删除仍禁止 | 小（去掉 2 处判断） |
| D3 | 用户授权后清理 gitlink 索引记录 | 小但需授权 |

**不引入任何新第三方依赖**：禁用机制（`disabled_skills.json` + `set_disabled`）、回收站（`recycle_paths`）、包发现（`_package_source`）三项能力均已存在。缺的是策略接线，不是轮子。

---

## 八、证据索引

| 结论 | 取证方式 |
| --- | --- |
| `00全流程SKILL` 被排除 | `python -c "default_registry(Path('.'))._stage_directories()"` 实测输出 13 个阶段目录，无 00 |
| AIGC 不在注册表 | `getAll()` 73 项，`contains AIGC? False` |
| 13 个子技能无 stage | 逐目录读 `SKILL.md` frontmatter |
| 内置删除被拦 | 读 `pet_skills_manage.py:303`、`skill_lifecycle_service.py:331` |
| 内置禁用被拦 | 读 `pet_skills_manage.py:411`、`skill_lifecycle_service.py:91` |
| 禁用机制已完备 | 读 `skill_lifecycle_service.py:85-96` |
| 无测试锁定该规则 | `grep '内置 SKILL 只读'` 全仓 → 仅 4 处生产代码，tests 0 处 |
| 孤儿 gitlink | `git ls-files -s` → `160000`；`.gitmodules` 不存在；`.git/modules` 空 |
| 4 个 gitlink | `git ls-files -s \| Select-String '^160000'` |
| `recycle_paths` 对该类目录有效 | 临时目录构造 + 实跑，`status: moved` |
| `git submodule status` 已报错 | 实跑，`fatal: no submodule mapping found` |

**未运行**：冒烟、架构门禁、全量——本文为只读诊断产物，按 `AGENTS.md` §3.5 不跑测试。
