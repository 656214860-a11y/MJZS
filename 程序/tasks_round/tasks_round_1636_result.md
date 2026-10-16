# R1636 网络面清单补全与 §4 复核（联调/测试 T12／T13 收尾）

- 编号说明：中央领取号 1636，提交号与状态页一致。
- 本轮类型：§3.10 验证/基线轮（只改文档，不改代码与测试）。
- 测试跑了吗？跑了。轮次基线＋行尾共 21 项。未跑全量：本轮非源码轮，全量欠账仍为 2／8（门禁线 8）。

## 交付

1. 说明/联调测试出口基线.md §5：补登**第二个**本地回环监听面——随附 skill 资产 skills/09白模预演SKILL/create-blender-story-video/assets/render-monitor-dashboard/server.py:849 自带的监控面板。
2. 复核 §4（缺陷台账 A 级 3 条挂账的守护用例索引）与源台账 维护记录/缺陷台账_20261001.md 的“待实机复验”条目：一致，无需改动，故本轮只动 §5。
3. 复核 §5 与 §6 T13 口径：previs_monitor 回环预览页的登记与代码一致，未改。

## 实测结论（只读核验）

- 全仓监听面共 2 处：previs_monitor.py:130（登记为 T13）与本轮补登的 skill 资产 server.py:849。
- 该 server 的加固事实：--host 默认 127.0.0.1 且非回环 host 在启动前直接拒绝；只答 GET 且仅固定只读端点（/、/index.html、/render-monitor-demo/、/render-monitor-demo/index.html、/healthz、/api/status、/api/latest-frame）；POST 与 HEAD 返回 405；只读白名单内的 index.html 与已校验预览帧，不做任意路径文件服务（无路径穿越面）；设 nosniff／no-referrer／X-Frame-Options DENY 与 CSP 头。
- 产品代码不启动它：全仓仅该文件自引用，无其他引用点；属随附工具资产，归入供应链面。

## 未决与界限

- 阶段4 清单仅剩 T13（回环预览页无鉴权）待用户裁决；本轮不代裁决、不改 previs_monitor.py。
- 未跑全量；最近真实同树全量仍是 R1624（13dea0a，502 秒、0 红）。