# R531 修复轮：左上角设置齿轮与标题对齐

## 轮次自检

1. 本轮是功能轮还是整理轮？修复轮；将“漫剧制作助手”右侧的设置齿轮下移至与标题文字水平对齐。
2. 测试跑了吗？三个基线过了吗？定向 Tk 接缝回归 1/1、默认冒烟 8/8、架构门禁 93/93 通过；历史全量安全基线仍为 3,230 条，未将其伪造为本轮结果。
3. `project_status.md` 欠账少了吗？已关闭顶部齿轮与标题未对齐的界面项；R182 结构专项与白模真机授权不在本轮范围。

## 根因与修复

设置齿轮为防止窄窗口裁切而放置在主窗口根层，其固定坐标仍是 `(138, 8)`。标题使用 16px 字体，而齿轮画布是 22px；两者按顶部对齐会造成视觉中心偏高。

- 将根层安全位调整为 `(138, 11)`，下移 3px，使齿轮与标题的文字中线对齐。
- 保留根层放置方式、横向位置、无障碍提示“设置”以及点击打开设置窗口的行为。
- 接缝回归同步更新为新布局契约；这是明确的界面位置变更，并未弱化点击、父容器或横向间距断言。

## 修改范围

- `desktop.py`
- `tests/test_pet_settings.py`
- `project_status.md`
- `tasks_round/tasks_round_531_result.md`

未修改用户项目数据、模型配置、密钥、阶段语义或后台任务逻辑。

## 验证

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest -v tests.test_pet_settings.DesktopGearSeamTests.test_the_gear_sits_next_to_the_title_without_a_sidebar_version_label`：1/1 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`：8/8 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --architecture`：93/93 通过。

## 自检复核

本轮只调整根层齿轮的纵向安全位，并已逐项核对设置入口仍可达、横向间距未变、窄窗口防裁切策略未变。界面改动需重启应用后生效。
