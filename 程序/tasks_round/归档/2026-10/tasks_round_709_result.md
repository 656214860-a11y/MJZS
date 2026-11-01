# R709 结构治理轮（执行）结果：JSON 读写入口首批收口

来源：`架构模块接口统一.txt` 第一批第 4 项。范围限定为白模预演进度 JSON；未修改业务语义、UI 或用户项目数据。

## 完成内容

- `previs_progress_service.status_value()` 改由 L1 `file_cache.read_json()` 读取正式进度文件，不再自行 `read_text()`／`json.loads()`。
- `publish()` 继续只经 `agent.core.save_text()` 原子发布；其成功后的 `file_cache.published()` 事件会淘汰旧缓存。
- 新增缓存失效回归和 JSON I/O 架构门禁，固化“L2 读走缓存、写走原子服务”的边界；未改变进度状态映射和容错回退。

## 验证

| 基线 | 结果 |
| --- | --- |
| 定向单元（进度状态 + JSON 门禁） | 8 条 / 0 红 |
| 受影响冒烟 | 9/9 |
| 默认冒烟 | 8/8 |
| 架构门禁 | 108/108 |
| 完整安全全量 | 3,417 条 / 0 红 / 768.5 秒 |

完整安全全量日志：`维护记录/r709_json_io_safe_all.log`。

## 后续

JSON 读写统一仍是逐服务迁移项；其他 L2/L3 JSON 路径留待独立轮次审计，不以本轮单点迁移宣告全库完成。

`[TASK_COMPLETE]`
