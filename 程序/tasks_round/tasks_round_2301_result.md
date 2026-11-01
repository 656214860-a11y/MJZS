# R2301 结果：项目目录 .env 密钥迁进加密存储后停读（功能轮）

## 三问
- 做了什么：新增 `model_secrets.import_env_keys`：项目目录／程序目录／`private/.env` 的密钥第一次被读取时一次性迁进 `private/密钥/*.dpapi`，只补缺、不覆盖同名加密密钥、不删 `.env` 文件；在 `private/env_imported.json` 记路径与条数（不含密钥），此后连文件都不再打开。`api_endpoints.configured_key` 与 `cloud_video_service.saved_provider_key` 的明文读取改为「迁移＋读加密存储」；云视频仍按主机绑定（只认与该主机匹配的 .env 迁过的那把）。
- 为什么：明文 `.env` 不再作为运行期读取源，密钥只在加密存储里。
- 没做／已知取舍：全局加密存储按变量名存，两个项目 `.env` 里同名但值不同的密钥，先迁入的生效；迁移后在 `.env` 里改值不再生效，需在模型管理里改。未跑全量。

## 红绿
- 红：`tests/test_env_key_import.py` 依赖 `model_secrets.IMPORT_MARKER`／`import_env_keys`，改前这两个名字不存在。
- 绿：`run_selftests.py -k model_pool env_key_import test_api cloud_video integration pet_llm unification` 全过；`smoke_test.py --architecture` 415 例改后仅一项裸 `json.loads` 登记债务已改用 `agent.core.read_json/save` 消除，复跑 unification 过。
- 测试夹具（断言值未动）：`test_api.ConfiguredKeyTests`、`test_cloud_video` 的旧会话用例、`test_integration` 整模块改用 `tests/secret_store_support.isolate_secret_store`，把加密存储隔到临时目录，避免写进真实 `private/`；`test_model_pool` 的 `.env`→`private/.env` 用例第二段改用另一个变量名（同名已迁入加密存储，按新规则不回读），并 `mkdir(exist_ok=True)`。

## 基线
- 凭据扫描：本轮未写入或输出任何真实密钥；测试只用假值。
- 全量：未跑，欠账按 AGENTS.md §5 计数。
