from pathlib import Path
import re
root=Path(r'D:\漫剧制作助手\.agents\worktrees\account-design-consolidation')
p=root/'程序/docs/specs/07_业务域规格.md'
original=p.read_text(encoding='utf-8')
old=(root/'程序/说明/账户会员云端设计.md').read_text(encoding='utf-8')
# Preserve every non-account paragraph in 7.4–7.7; keep stable 7.1–7.8 anchors.
prefix='''# 07 业务域规格

本册覆盖会员订阅、登录认证、设置、素材授权与模型管理。

**账户与会员的唯一设计权威是本册 [§7.9](#79-账户与会员完整设计)。** 需求事实见 [产品需求规格](../requirements/产品需求规格.md)，决策理由见 [ADR](../adr/README.md)，历史来源与逐项冲突处置见 [账户设计条款迁移映射](../records/账户设计条款迁移映射.md)。旧账户设计与立项清单只作迁移来源，不再构成另一份现行权威。

## 7.1 域划分

| 域 | 职责 | 权威章节 |
|---|---|---|
| 会员订阅 | 试用、付费、租约、兑换码与退款登记 | 本册 §7.9 |
| 登录认证 | 邮箱验证码、口令、会话与设备绑定 | 本册 §7.9 |
| 设置 | 全局配置、桌面偏好 | 本册 §7.4 |
| 素材授权 | 溯源、许可与商用门控 | 本册 §7.5 |
| 模型管理 | 模型池、密钥、可用性探针 | 本册 §7.6、ADR-0011 |

## 7.2 会员订阅

本节保留既有导航锚点。产品价格、费用分离、授权闸门、兑换码与退款的完整条款统一见 [§7.9](#79-账户与会员完整设计)，不在此重复正文。

## 7.3 登录认证

本节保留既有导航锚点。身份、API、租约、设备、注销与隐私的完整条款统一见 [§7.9](#79-账户与会员完整设计)。

'''
mid=original[original.index('## 7.4 设置'):original.index('## 7.8 未决事项')]
mid=mid.replace('`说明/生成服务失败处理契约.md`','[生成服务失败处理契约](../contracts/生成服务失败处理契约.md)')
end='''## 7.8 未决事项

账户、计费与部署的待决项统一见 [§7.9.10](#7910-决策状态与未决事项)，保留原 D／Q 编号；本节只保留导航锚点。

## 7.9 账户与会员完整设计

### 7.9.0 权威、状态与核对范围

本章承接原《账户登录与会员订阅 — 设计文档（首期）》全部十节实质条款，并吸收立项清单 D1–D16、D11b、Q1–Q8。需求、设计与实现分别判定：**需求事实**指用户确认的产品约束；**已接受设计**指已接受 ADR 或明确设计裁决；**现有实现**仅指本轮读取源码可定位的能力；**未实现设计**指契约候选或缺少实现／验收凭据；**历史结论**保留追溯且不得作当前承诺。状态可并存，代码不自动覆盖需求。本章合并本身不授权实现功能。

R3832 在基点 `b860721f` 静态核对客户端 `domain/account_client.py`，及独立服务端仓库 `D:\\漫剧服务端` 的 `app/main.py`，仅为公开 API 入出参与必要处理读取 `app/service.py`、`app/providers.py`、`app/lease.py`；未读取私密配置，未联网、未复验测试服、GUI、备份恢复或支付。以下“现有实现”均为该范围的静态证据，不等于端到端验收通过。部署状态、法律与资质结论不得由历史记录或工程源码自证。

'''
body=old[old.index('## 1 范围'):]
# Stable heading conversion, including originally nested 7.1/9.1.
body=re.sub(r'^### (\d+)\.(\d+) (.+)$',lambda m:f'#### 7.9.{m[1]}.{m[2]} {m[3]}',body,flags=re.M)
body=re.sub(r'^## (\d+) (.+)$',lambda m:f'### 7.9.{m[1]} {m[2]}',body,flags=re.M)
# Internal references are scoped to this new chapter.
body=re.sub(r'§(\d+)\.(\d+)',r'§7.9.\1.\2',body)
body=re.sub(r'§(\d+)(?![\d.])',r'§7.9.\1',body)
# Restore non-account AGENTS references accidentally swept by numeric conversion.
body=body.replace('AGENTS §7.9.', 'AGENTS §').replace('AGENTS.md` §7.9.', 'AGENTS.md` §')
body=body.replace('AGENTS §3.8','runbook §15 可靠性').replace('AGENTS §2.3 规则 13','AGENTS §2.2 事件权威')
body=body.replace('以上模块名是设计命名，实现前须先搜已有入口再确认（AGENTS §2.5 规则 28），特别是网络出口只经 `platform_tools`。','以上为分层设计命名，实现须先搜已有入口。现有账户 HTTP 消费者经 `platform_tools.open_https`；新增 JSON API 遵守当前 AGENTS 出站权威，不把历史出口命名推广为通用例外。')
body=body.replace('| 首期只有试用；支付期接入后沿用 |','| 试用与兑换码会员已存在；另预留 `auto_renew`（默认关闭）、`channel`（默认 `redeem`，另预留 `wechat`／`alipay`），支付接入验收后才启用 |')
body=body.replace('| 首期只有 `email`；邮箱统一小写并去掉 `+标签` |','| 首期只有 `email`；邮箱统一小写并去掉 `+标签` |')
body=body.replace('### 7.9.3 服务端\n','### 7.9.3 服务端\n\n以下十张表是原设计核心数据模型，保留全部字段，**不是当前完整数据库清单**。API 已增加的字段／表在本节补充；未核对全部迁移与数据库实例。\n')
body=body.replace('| `GET /v1/meta` |', '| `GET /v1/meta` |')
body=body.replace('- 所有时间字段为 UTC 秒级时间戳；服务端响应带 `server_time`。','- 所有时间字段采用 UTC 秒级时间戳。原设计要求响应带 `server_time`，现有实现并非每个端点都返回，必须按下方实返字段表消费，不补造字段。')
body=body.replace('#### 7.9.3.3 技术选型、数据库与迁移', '''#### 7.9.3.2a 当前公开接口核对补充

上述接口均可在服务端 `app/main.py` 定位；客户端 `domain/account_client.py` 除退款登记／查询外均有对应包装，另有 `GET /v1/providers`。退款服务端路由已存在，**该客户端文件尚无退款包装**，不能据此宣称退款 UI 已验收。`GET /healthz` 为健康检查，返回 `{ok}`。

| 接口组 | 本轮核对的实返字段／约束 |
|---|---|
| meta | `{api_version, min_client_version, server_time, kids, features}`；现有 `features=[password]` |
| code／reset／logout／delete-cancel | 成功 `{ok:true}`；code 不返回 `server_time`；注册邮件重复提示是枚举防护的一项明确例外 |
| verify／register／password/login | `{refresh_token,user{id,is_new,has_password},lease,state,server_time}`；verify 同样收 `privacy_version` |
| password change | `{ok,has_password}`；当前客户端带 `old_password` 时才入参 |
| renew | `{refresh_token,lease,state,server_time}`；`device_id` 是客户端设备指纹值，服务端与登记哈希比较 |
| me | `{id,email,status,created_at,subscription{state,plan,trial_ends_at,period_end},devices{active,max},has_password}`；**无外层 `user`、无 `server_time`**，取代旧表“`/v1/me` 的 user”表述 |
| devices／unbind | 列表 `{devices:[{id,name,os,first_seen,last_seen,current}],max,unbind_left,next_unbind_at,server_time}`；解绑 `{ok,unbind_left}` |
| delete-request | `{ok,deletion_at,server_time}` |
| export | `{exported_at,account{id,status,created_at},consents{age_confirmed_at,tos_version,privacy_version},identities:[{kind,value,verified_at}],devices:[{id,name,os,first_seen,last_seen,unbound_at}],subscription{plan,status,trial_started_at,trial_ends_at,period_end},redemptions:[{plan,days,redeemed_at}]}` |
| refund POST／GET | POST Bearer＋`{code,reason}`，reason 去首尾空白且必填；返 `{id,redeem_code_id,reason,requested_at}`；GET 返 `{requests:[上述申请字段]}`；错误 400 `refund_reason_required`／`refund_code_invalid`，同码只一份申请 |
| providers | Bearer；`{enabled,providers:[{id,name,base_url,models,invite_url,note}],relay_sites}`；关闭时两列表空，付费会员才带 `relay_sites`（模型／价格／余额展示，不含上游地址与凭据） |

请求模型长度上限为：email 320、验证码 12、设备 `id/name/os` 各 64、协议版本各 32、refresh_token 128、password／old_password 128、兑换码 64、退款 reason 1–500；这是**请求解析上限**，口令业务强度仍为 8–64 且含字母与数字。`device.name/os`、协议版本默认空，`age_confirmed` 默认 false，`purpose` 默认 login。客户端邮箱本地校验另限 254；与服务端解析上限不同，尚未统一。设备表 API 实际还使用 `os`，会话轮换使用 `replaced_by/replaced_at`；旧十表关键字段并非穷举。新增 `refund_request` 由公开返回可定位其 `id/user_id/redeem_code_id/reason/requested_at`；线路／开关见 §7.9.7。

共用错误：400 `invalid_request`（请求模型不合法）、`client_version_required`（缺／错版本头）、`invalid_email`、`invalid_device`、`age_confirmation_required`、`terms_required`、`code_invalid`；401 `session_invalid`；403 `account_banned`／`account_pending_deletion`；409 `device_limit`；429 `too_many_requests`；426 `client_too_old`。各接口专有错误保留在前表。客户端网络失败码 `network`、无法解析响应 `bad_response` 是本机结果，不是服务端业务码。原设计错误体 `{code,message,retry_after?}` 保留，限流可带 `Retry-After`。除 `/v1/meta` 与 `/healthz` 外均校验 `X-Client-Version`。

**未实现设计**：原07的默认中转站计量上报要求（项目哈希、阶段、模型、供应商请求 ID、计费单位、状态、时间戳；不得含提示词、剧本、素材、路径原文或 API Key）保留为隐私上限与候选需求，**`POST /v1/metering` 在本轮两端路由／消费者均不存在**，不能列作已实现。自建 API 不由软件收费、不上报，只入本地用量台账。官方推荐第三方线路费用另计，当前不等于软件代收、代理或额度系统。具体授权、去重、重试、扣减与结算须另定再实现。

#### 7.9.3.3 技术选型、数据库与迁移''')
body=body.replace('#### 7.9.3.4 部署\n','#### 7.9.3.4 部署\n\n以下云厂商、节点、证书、域名、邮件与备份记载为**历史部署记录／运维设计**，本轮未核验在线状态，不是当前上线、备案或恢复验收凭据。公网与邮件合规须由负责人另行确认。\n')
body=body.replace('- **管理后台（R1900）**', '- **管理后台（R1900 历史方案，已被后述鉴权后台方案取代）**')
body=body.replace('**管理后台（R1900）**','**管理后台（R1900 历史方案，已被后述鉴权后台方案取代）**')
body=body.replace('本机生成，存 `session.json`','机器稳定标识的加盐哈希，回退种子独立保存')
body=body.replace('（见立项前清单 §7.9.5）','（见 §7.9.8 的前提重估）')
body=body.replace('- 验证码暴力枚举、同邮箱／同 IP 刷接口、枚举邮箱是否已注册，均被限流且不泄露存在性。','- 验证码暴力枚举、同邮箱／同 IP 刷接口须限流；login/reset 不泄露存在性。register 已注册返回 `email_registered` 是明确产品例外，须按 IP 限流并验收，不得宣称所有接口均不泄露。')
body=body.replace('| P3 | 中转站适配器与分成（待办，见 §7.9.7） | 待与中转站沟通后另定 |','| P3 | 原“中转站适配器与分成”已收窄为推荐线路预设（见 §7.9.7），不做 Key 池／代理转售 | 预设接口与按需卡片有历史实现记录；返佣、推广与计量仍待确认 |')
body=body.replace('### 7.9.10 未决事项（实现前须定）', '### 7.9.10 决策状态与未决事项')
body=body[:body.index('### 7.9.10 决策状态与未决事项')]+'''### 7.9.10 决策状态与未决事项

#### 7.9.10.1 当前产品事实与历史取代

| 项 | 当前约束与依据 |
|---|---|
| 价格／试用 | **需求事实**：3 天免费试用，不含 API 额度；月 19／季 49／年 189 元，只含应用使用权（折合约 19／16.3／15.75 元每月）。原设计与 D7 的月 39／季 99／年 399 **已被用户新价格取代**，不得继续当待确认现价。API 费用用户另付；旧07引用的 `console.supergpt.dev/models` 仅是历史第三方价目入口，单价未在本轮核验，不作固定费率承诺。 |
| 免费／收费边界 | **已接受设计＋现有实现**：免费范围是 `pet_bus.STAGES` 前两个阶段键（剧本准备／剧本结构），从初步分镜起为收费阶段；侧栏按收费阶段键拦截，缺省阶段与非阶段工具页放行。原07把“初步分镜、所有已成功产物导出”一并视为免费，与旧完整设计及现实现有冲突：前者更正为前两阶段；**查看与本地读取仍放行，质检交付导出原设计要求受闸门约束，其具体导出消费者本轮未验，不能泛化为全部导出免费或全部已实现拦截**。若需求要改此边界须另记裁决。 |
| 原07待修 M-1／M-2／M-3 | 原明文 `GATE_ENFORCED`、单点时钟、退款无据是**历史缺陷**。当前静态证据：授权由验签租约判定（`domain/entitlement_service.py`）、双基线／MAC 存储（`infra/account_store.py`，ADR-0007/0008/0009）、服务端退款申请与唯一申请约束（ADR-0010）。不再保留为未经复核的当前 P0/P1；也不宣称客户端防绕过成为安全边界或退款 UI 已验收。 |
| 代码／责任历史 | R1886 接受 SQLite WAL 与 FastAPI，旧设计说“前两阶段免费”；R1890 独立服务端仓库、main、不推远端，P0 骨架实现记录；R1894 由当时主会话负责服务端、账户会话负责桌面 P1/P2、P2 测试服部署记录均仅为历史归属与进度，不能代替本轮验收。 |
| 售卖与官网 | **已接受设计（R1900 用户裁决）**：首页不写试用、价格与购买，收款与售卖说明只放爱发电店铺；管理后台不作普通公网产品入口。旧“只有 SSH 隧道、无独立登录”后台被后述用户名＋口令＋TOTP 方案取代；本轮未核验 8433 的真实暴露及认证配置，须运维复核，不能同时把两种部署方式当现行事实。 |
| 兑换天数／未来支付 | **已接受设计＋现有实现**：暂无营业执照的历史背景下先经爱发电／淘宝发卡，monthly 30／quarterly 90／yearly 365 天；输入兑换码入口已是客户端设计。以后具备主体与商户资质再接微信／支付宝官方商户；不自动续费代扣。 |

#### 7.9.10.2 D 决策台账

立项清单是 R1644 历史投影，不是整体批准；下表逐 ID 保留问题范围与当前判定，不能把工程可做替代法律、经营或验收结论。

| ID／原标题 | 当前判定 | 对应条款／仍待事项 |
|---|---|---|
| D1 身份基线 | 已接受设计＋现有实现 | 账号制、每账号3台、自助解绑；30天2次配额、设备会话吊销见 §7.9.3.2、§7.9.4.4、§7.9.5.3。 |
| D2 账号来源 | 部分已定 | 自建邮箱验证码＋口令已存在（R2022）；短信／微信仅预留，MFA未实现，见 §7.9.1、§7.9.3.2。 |
| D3 最小信息集 | 已接受设计 | 邮箱、设备／IP哈希、年龄及协议确认；不收身份证，不上传项目素材，见 §7.9.6。 |
| D4 未成年人 | 设计已定、法务未定 | 18岁声明与服务端记录；声明非法律保护，用户协议／隐私政策专业审阅仍待，不能标“合规完成”。 |
| D5 注销与数据导出 | 设计及公开接口已存在，留存待复核 | 7天冷静期、撤销、导出、试用哈希与90天审计留存；支付账单另议，见 §7.9.3.2、§7.9.6。 |
| D6 授权模型 | 已接受设计＋现有实现 | 软件使用权、统一入口闸门、前两阶段免费；导出消费者验收差异见 §7.9.10.1。 |
| D7 定价与试用 | 已定且取代历史价格 | 3天、19／49／189；不含API额度，见 §7.9.10.1；39／99／399不再有效。 |
| D8 服务器权威 | 已接受设计＋现有实现 | 签名、期限、会话吊销；客户端加固只是门槛，见 §7.9.4、ADR-0007。 |
| D9 试用计时 | 已接受设计＋现有实现 | 服务器时间、试用到期封顶、签名时钟＋双基线＋300秒容差；实际对抗验收本轮未跑。 |
| D10 凭据存储 | 已接受设计＋现有实现 | 订阅凭据禁DPAPI机器绑定；DPAPI仅保护MAC密钥，与模型Key分路径；旧无MAC会话重登，见 §7.9.5.3、ADR-0008。 |
| D11 付款资质与合规 | 部分已定、外部前提未定 | 兑换码＋人工退款已定；商户／对公／备案／PIPL／财税留存与对账需负责人及法务确认；不碰卡号，见 §7.9.6、§7.9.9.1。 |
| D11b 离线与宽限 | 当前设计已定、调整未定 | 租约7天＋宽限3天，试用封顶；到期保留免费阶段与本地读取；真实反馈后是否调整待定，见 §7.9.4.3。 |
| D12 云端职责边界 | 已接受设计 | 只鉴权与订阅，不代理模型、不保管用户Key、不做子Key池或转售，见 §7.9.1、§7.9.7。 |
| D13 项目数据是否上云 | 已接受设计 | 项目／素材留本地，无同步或云备份；云端不获本机删除权，见 §7.9.1、§7.9.6。 |
| D14 数据库与迁移 | 选型已定、演练未在本轮核验 | SQLite WAL、编号SQL／回滚、每日备份；OSS历史待开桶，恢复凭据与PostgreSQL可移植性须验，见 §7.9.3.3。 |
| D15 服务端部署与发布 | 部分已定、上线验收未定 | 独立依赖、版本协商已存在；节点、备案、SPF／DKIM、灰度、发布回滚仍需真实凭据，见 §7.9.3.4、§7.9.9。 |
| D16 可观测与限流 | 部分实现、SLO未定 | 发码／口令／解绑／兑换限流、哈希脱敏、90天审计已有设计；服务端延迟／可用性SLO、灰度聚合阈值未定，见 §7.9.3.2、§7.9.8。 |

#### 7.9.10.3 Q 讨论问题与未决清单

| ID／原问题 | 判定 | 结论／剩余工作 |
|---|---|---|
| Q1（D12）云端职责边界 | 已答复 | 只鉴权订阅，不代理模型。 |
| Q2（D13）项目数据是否上云 | 已答复 | 不上云。 |
| Q3（D2／D3）账号来源与最小信息 | 已答复并后续扩展 | 邮箱验证码首期，后加口令；其余身份未实现。 |
| Q4（D6／D7）授权与定价 | 后续已定，边界有验收差异 | 软件授权、3天与19／49／189；导出边界见 §7.9.10.1，不沿用旧价格。 |
| Q5（D12＋D11）谁垫服务成本／是否含额度 | 部分已定 | 软件费不含模型额度，用户Key自付；推荐线路不代理，返佣、单价、结算周期与任何软件计量扣减映射仍未定，不能推导平台垫资。 |
| Q6（D1）设备数与解绑 | 已答复 | 3台、每30天2次解绑，见接口配额。 |
| Q7（D5）注销导出与留存 | 已答复、部分留存待验 | 7天冷静期、账号导出、试用哈希／90天审计；支付订单财税留存另定。 |
| Q8（D11）付款资质与备案负责人／时间 | 未完成 | 首期绕开在线商户而用发卡；经营主体、商户、ICP备案、法务与完成时间仍由负责人给证据，工程不能自证。 |

仍未决：7＋3天是否调整；推荐线路选择／上游服务条款与转售风险复核、邀请返佣比例／是否终身绑定／结算方式；备案与邮件SPF／DKIM；OSS私有桶与上传／恢复演练；服务端延迟／可用性SLO、灰度观察／回滚阈值；默认中转计量候选及额度扣减映射。短信／微信和多因素未实现。旧价格待确认项已被取代，不再列未决。
'''
# Insert retained prelaunch constraints and candidate verification without reviving historic authority.
body=body.replace('### 7.9.8 安全清单（实现时逐项对抗测试）','''### 7.9.8 安全清单（实现时逐项对抗测试）

立项历史的桌面前提（单机单用户、裁剪解释器、零桌面数据库与无本机入站面）不能推广成云端现状。云端可有独立数据库／依赖／鉴权入站，桌面仍不新增监听；本机用户可见删除遵守回收权威，云端不获本机文件权威；令牌与密钥禁止进入日志／任务JSON／错误上报。后台网络不得阻塞Tk，生命周期取消与迟到结果须丢弃。

前提重估与验收候选仍需逐项留证：阶段4 T12 原“单机无账号／支付”N/A 不再充分，须补越权／支付／注入／外泄；T13 回环无鉴权“接受”须在账号面重估；阶段5 U13 的多租户SLO／迁移回滚／灰度由N/A转适用，U1/U6/U11/U12优先；阶段4 T6/T7 本地性能口径不覆盖服务端。计费不变量为分项求和等于总额、不负额、币种隔离、退款扣费对称（未来支付期验收）；迁移前向／回滚／失败恢复／旧数据兼容、灰度授权失败率／错误率／成本与回滚演练、隐私／导出／注销与资质法务确认均不可由本次文本合并宣称通过。
''')
body=body.replace('#### 7.9.7.1 管理后台已有能力（`https://<服务器>:8433`，用户名＋口令＋TOTP）','#### 7.9.7.1 管理后台历史实现记录（`https://<服务器>:8433`，用户名＋口令＋TOTP）\n\n此为旧文档记载的后续方案，取代 §7.9.3.4 的“SSH即管理员、无单独登录”方案；本轮未核对后台代码与部署，不将其记为已验证上线。')
# Current protocol correction remains traceable rather than asserting old wrong response structure.
body=body.replace('`/v1/me` 与登录结果的 `user` 带 `has_password`','登录结果的 `user`、`/v1/me` 顶层带 `has_password`')
body=body.replace('不实现）。','不实现）。')
p.write_text(prefix+mid+end+body,encoding='utf-8')
print('wrote',p,'lines',len(p.read_text(encoding='utf-8').splitlines()))
