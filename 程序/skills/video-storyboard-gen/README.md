# video-storyboard-gen

[![CI](https://github.com/anyhui/video-storyboard-gen-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/anyhui/video-storyboard-gen-skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

面向中文视频创作的可复用 Agent Skill：把主题、文案或创意整理为可执行的故事结构、逐镜分镜表，并按需生成即梦/Seedance 等 AI 视频提示词。核心交付不依赖网络或付费 API。

## 特性

- 剧情、广告、带货、宣传场景的结构与时间分配
- 带时间码、景别/角度、画面动作、运镜、声音和转场的分镜契约
- 人物、产品、空间、色调与素材引用的连续性检查
- 健康声明、合成媒体、品牌、肖像和素材授权边界
- 渐进式参考资料，主技能文件保持聚焦
- 确定性 Python CLI，支持 Markdown、稳定 JSON 和 UTF-8 文件输出
- stdlib-only 测试与仓库发布校验，无外部服务

## 兼容性

- Hermes Agent Skills
- Claude/Claude Code Skills
- CLI：Python 3.10+，仅使用标准库

不同宿主对 Skill frontmatter 的扩展字段支持可能不同；本仓库只使用通用字段。

## 安装

将仓库克隆或复制到宿主的 skills 目录，保持 `SKILL.md`、`references/` 和 `scripts/` 相对位置不变。例如：

```bash
git clone https://github.com/anyhui/video-storyboard-gen-skill.git
```

具体 skills 目录和启用方式以 Hermes 或 Claude 当前文档为准。本技能无需安装 Python 依赖。

## 使用

在 Agent 中直接描述需求：

```text
为“山城早餐”做一支30秒、9:16的抖音广告分镜，突出清晨烟火气；需要逐镜声音设计和Seedance提示词。
```

确定性 CLI 适合生成可继续编辑的结构化脚手架：

```bash
python3 scripts/storyboard_gen.py generate "山城早餐" \
  --type 广告 \
  --duration 30 \
  --subject "本地早餐文化" \
  --platform 抖音
```

输出稳定 JSON 或 UTF-8 文件：

```bash
python3 scripts/storyboard_gen.py generate "山城早餐" --duration 30 --format json
python3 scripts/storyboard_gen.py generate "山城早餐" --duration 30 --output storyboard.md
python3 scripts/storyboard_gen.py reference --format json
```

CLI 不调用生成式模型，只提供确定性的分镜骨架；Agent 工作流负责创意细化、事实核验与安全检查。

## 示例

- [恩施藤茶分镜脚本](examples/恩施藤茶分镜脚本.md)：90 秒剧情化产品内容，已避免未经证实的医疗功效表达。
- [AI 视频提示词指南](references/ai-video-guide.md)：素材引用、时间段提示词、镜头与约束词用法。

## 目录

```text
.
├── SKILL.md                 # Agent 入口与精确输出契约
├── references/              # 按需加载的创作与安全细节
├── scripts/
│   ├── storyboard_gen.py    # 确定性 Markdown/JSON CLI
│   └── validate_repo.py     # 发布完整性校验
├── evals/evals.json         # 代表性技能评估用例
├── examples/                # 人工编写示例
└── tests/                   # unittest 测试
```

## 验证

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_repo.py
python3 -m compileall -q scripts tests
python3 scripts/storyboard_gen.py generate "冒烟测试" --duration 12 --format json
```

CI 在仍受上游支持的 Python 版本上运行相同的标准库检查，不使用付费 API。

## 限制

- 平台模型、参数和审核规则会变化，请以平台当前文档为准。
- 约束词不能保证生成结果稳定，长视频通常需要拆段生成并人工检查连续性。
- 输出是创作初稿，不替代法律、医疗、广告合规或版权意见。
- CLI 生成的是通用骨架，不会自动理解品牌资料或生成成片。

## 参与贡献

开发流程见 [CONTRIBUTING.md](CONTRIBUTING.md)，安全问题见 [SECURITY.md](SECURITY.md)，版本记录见 [CHANGELOG.md](CHANGELOG.md)。仓库作者原创的代码与文档采用 [MIT License](LICENSE)；第三方名称、商标、素材及引用内容仍归其各自权利人所有，不因收录于本仓库而获得 MIT 授权。
