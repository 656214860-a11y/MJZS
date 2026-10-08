# R1164：排除新建项目的默认占位分镜

- 类型：§3 修复轮，用户要求定位并修复删除自然剧本后的成果计数。
- 测试：默认冒烟 8/8；受影响 9 文件、63 用例通过（冒烟含门禁 9/9）。完整架构本轮未跑；完整安全回归未触发，历史凭据 R1160，不代表当前树全量通过。
- 欠账：关闭本次占位分镜误计数；既有范围外待办不变。

## 根因与改动

只读核验发现残留 JSON 与 Projects.create 自动创建的默认单镜头种子完全一致。发送每次重新 snapshot，并非删除后的缓存。catalog 只要求 shots 非空，导致默认“待编写”镜头被算作分镜成果。

storyboard_catalog_service 以保守的完整默认镜头特征识别未编辑种子，不依赖文件名或自然剧本数量；排除成果目录与发送统计。真实或已编辑镜头继续计数。不删除文件、不改变项目初始化和实际分镜的删除规则。

## 实际验证与失败闭环

- 新增 Projects.create → 创建自然剧本 → 删除自然剧本 → snapshot/continuation_instruction 回归；同时验证文件字节不变，编辑镜头后重新计入。
- 首次测试定位文件用了迁移后命名，fixture 未命中；改为实际 JSON 后，在分镜应为空断言稳定复现失败，实施修复后通过。
- unittest：test_context、test_storyboard_current_source、test_storyboard_final_selection、test_projects，共 33/33。
- 初次 affected 使用生产模块名未匹配测试，门禁拒绝；改用 context、storyboard_current_source、storyboard_final_selection、projects，9 文件 63/63，通过。单独 run_selftests -k storyboard_catalog_service 命中 0，不作为验证凭据。
- 修复代码只读核验当前用户项目，scripts/storyboards/assets 均为 0；未写入项目数据，未真实发送模型请求。
- git diff --check 通过。自审：1 个生产服务和 1 个回归测试文件；未跨层、未改启动/Tk 生命周期/删除语义，R1164-R1160=4，不触发全量。

## 交付

已提交 ed0e7aa（`R1164: 排除默认占位分镜的成果计数`），fast-forward 同步 master。6 项既有用户改动逐文件 SHA256/删除状态保持不变。主目录 context 23/23，实际项目只读统计再次确认为 0/0/0。运行中的应用需重启加载；历史消息保留原文，新发送按实时统计生成。未 push。
