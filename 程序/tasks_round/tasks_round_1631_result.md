# R1631 适配器请求形状对照与出站素材白名单（阶段4 T5＋T11）

- 本轮类型：§3.2 修复轮（两个适配器请求形状缺陷）＋测试基线。
- 测试：新用例定向 12/12；适配器与路由相关 33/33；模型池／用量／诊断等 175/175；默认冒烟 8/8；架构门禁 356/356（均本轮实测）。
- 欠账：本轮改了生产源码（`model_router.py`），按 §5 计入源码轮次（+1）。

## 交付

新增 `tests/test_outbound_request_contract.py`（12 用例）：

- `RequestShapeTests`（7，T5）：四个内置适配器对**同一逻辑请求**的认证头（Anthropic 用 `x-api-key` 且不带 Authorization，其余用 `Bearer`）；system 前缀落点（messages 协议放顶层，其余放 `messages[0]`）；无 system 时不加前缀；`max_tokens` 与 `temperature` 只在显式给出时出现；三个 OpenAI 兼容适配器的请求体逐字段一致（只允许 `model` 值不同）；端点＝声明的 base_url ＋协议路径；以及“发出去的请求必须就是 `payload()`／`headers()` 的产物”。
- `OutboundMaterialTests`（5，T11）：非参考模式只送本次声明的首帧（base64 解码须逐字节等于该文件）；载荷键集合固定且不在本地留副本；项目里 `.env` 诱饵的字节不出现在请求体；非图片与 >20MB 被拒；参考模式只带声明过的参考图且类型顺序固定；`shot_assets.image_url` 的类型／大小闸。

## 关键发现（本轮修掉的两个真实缺陷）

1. `model_router.DeepSeekAdapter.headers()` **忽略注入的 key**：它直接走 `pet_llm.headers(config, program)`，而同类的 `credential()`／`available()` 认注入的 key →“界面说这个模型能用”与“实际发出去用哪把钥匙”分叉。修法：`if self.key` 时用注入的 key 组头，其余保持原路径（保住 pet_llm 的 DPAPI／`.env`／环境变量三级来源）。影响面：生产只在 `model_router.py:468` 构造且不传 key，属**潜在缺陷**（当前用户路径未触发），但同一写法在池化／测试调用里会静默用错钥匙。
2. `model_router.ModelAdapter.payload()` 在 `wire_api='messages'`（Anthropic 原生）分支**丢掉 `temperature`**：chat／responses 分支都会带上，只有 messages 分支转给 `token_saver.anthropic_payload` 时漏了。修法：显式给出 `temperature` 时补进 messages 请求体。

同类缺陷扫描（修复轮必查）：全仓只有 base 与 DeepSeek 两处 `headers()` 覆盖；PoolAdapter 继承 base 且 `credential()` 认注入 key——无同类未修。

## 未做

- 未跑全量；未联网；未实机；未改其它适配器（cloud_video／comfy／volcengine 不在 T5 表内）。
- T11 只覆盖视频首帧／参考图这条出站链路；TTS 音频与云资产上传的出站白名单仍未覆盖（T11 剩余）。

## 自审（§4.2）

1. 满足验收标准：是（T5 请求形状对照、T11 出站素材白名单各建立用例，并修掉发现的映射缺陷）。
2. 范围外文件：仅 `model_router.py`（缺陷本体）与新测试文件。
3. 验证：定向 12/12、相关 208 项、默认冒烟 8/8、架构门禁 356/356 均为本轮实测；未跑全量。
4. 新引入问题：无。

## 提交

master 提交（hash 见 `git log --grep="R1631"`）。