# 租户接入指南

RAG Center 是一个**检索中台**：`POST /rag/retrieve` 返回与问题相关的文档切片（chunk），答案生成在业务方完成。

## 开通流程

### 1. 创建租户

```bash
python scripts/create_tenant.py --id tenant_a --name "租户 A"
```

新建租户默认 **free** 档。

### 2. 调整套餐（可选）

```bash
python scripts/update_tenant_plan.py --tenant-id tenant_a --plan standard
python scripts/update_tenant_plan.py --tenant-id tenant_a --plan pro
```

| plan | 定位 |
|------|------|
| `free` | 体验 / PoC，新建默认 |
| `standard` | 生产可用，旧租户迁移档 |
| `pro` | 全功能 + 高配额 |

### 3. 创建 API Key

```bash
python scripts/create_api_key.py --tenant-id tenant_a --name "生产环境"
```

终端会输出 `plain key`（仅显示一次），后续请求放在 Header：

```bash
-H "Authorization: Bearer rk_live_你的key"
```

需要有效期时加 `--expires-days`（不传则永不过期）：

```bash
python scripts/create_api_key.py --tenant-id tenant_a --name "生产环境" --expires-days 90
```

### 4. 密钥生命周期（查看 / 吊销 / 轮换）

密钥只在平台侧管理，没有公开接口。创建时打印的 `key_prefix`（形如 `rk_a1b2`）就是后续定位用的标识。

```bash
# 查看该租户全部密钥：id / prefix / 备注 / 状态 / 有效期 / 创建时间
python scripts/revoke_api_key.py --tenant-id tenant_a --list

# 吊销（三选一定位：--key-id | --key-prefix | --name）
python scripts/revoke_api_key.py --tenant-id tenant_a --key-prefix rk_a1b2 --yes

# 轮换：吊销旧密钥并签发同名新密钥
python scripts/revoke_api_key.py --tenant-id tenant_a --name "生产环境" --rotate --yes
```

规则：

- 吊销 = 把 `api_keys.status` 改为 `revoked`，鉴权侧立即失效（`get_active_by_hash` 只认 `active` 且未过期）
- 重复吊销是**幂等 no-op**，不会报错
- `--key-prefix` 支持前缀匹配；命中多条会**拒绝执行并列出候选**，不会误伤
- 吊销租户**最后一把有效密钥**会被拒绝（防止锁死），需显式 `--force`，或用 `--rotate` 换发
- 删除类操作在非交互环境下必须显式传 `--yes`

### 5. 创建知识库并上传文档

见 [README](../README.md) 中的「创建知识库」「上传文档」示例。

---

## plan 三档对照

### 功能上限

| 项 | free | standard | pro |
|----|------|----------|-----|
| 允许的 retrieve profile | 仅 `speed` | `speed`、`balanced`、`custom` | 全部（含 `quality`） |
| hybrid | ❌ | ✅ | ✅ |
| rerank | ❌ | ❌ | ✅ |
| query_rewrite | ❌ | ❌ | ✅ |

### 配额

| 项 | free | standard | pro |
|----|------|----------|-----|
| 检索 QPS | 3 | 10 | 50 |
| 日检索量 | 500 | 5,000 | 100,000 |
| 最大知识库数 | 1 | 5 | 50 |
| 单次 retrieve 最多联查库数 | 1 | 3 | 5 |
| 单库最大文档数 | 30 | 200 | 5,000 |
| 最大并发索引 | 1 | 2 | 10 |

---

## retrieve profile 四档

**plan 管上限，profile 管本次检索策略。** profile 不进租户表，每次 retrieve 请求指定。

| profile | 说明 | 展开概要 |
|---------|------|----------|
| `speed` | 追求速度 | vector，`top_k=3`；关 rerank、rewrite |
| `balanced` | 均衡（**未传 profile 时默认**） | hybrid；关 rerank、rewrite |
| `quality` | 追求质量（仅 pro） | hybrid + rerank + rewrite |
| `custom` | 自定义 | 以请求里 `retrieval_options` 等为准，仍受 plan 约束 |

### curl 示例

**均衡（standard / pro 可用）：**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/rag/retrieve \
  -H "Authorization: Bearer rk_live_你的key" \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id": "<kb_id>",
    "user_id": "u1",
    "query": "退款几天内申请？",
    "profile": "balanced"
  }'
```

**追求质量（仅 pro）：**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/rag/retrieve \
  -H "Authorization: Bearer rk_live_你的key" \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id": "<kb_id>",
    "user_id": "u1",
    "query": "退款几天内申请？",
    "profile": "quality"
  }'
```

**自定义：**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/rag/retrieve \
  -H "Authorization: Bearer rk_live_你的key" \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id": "<kb_id>",
    "user_id": "u1",
    "query": "退款几天内申请？",
    "profile": "custom",
    "retrieval_options": { "mode": "hybrid", "vector_top_k": 15 },
    "rerank_options": { "enabled": false }
  }'
```

响应 `metadata.tenant_policy` 会返回本次 plan、profile 及实际生效参数。

响应 `metadata` 还包含 `log_id`、`trace_id`（Langfuse 启用时），用于关联检索反馈。

---

## 检索反馈

每次 `retrieve` 成功后，响应 `metadata` 带有：

| 字段 | 说明 |
|------|------|
| `log_id` | 本地检索记录 ID，建议与反馈一并提交 |
| `trace_id` | Langfuse trace ID；未启用 Langfuse 时为 `null` |

用户对检索结果打 **1～5 分**（5 为最好），可选备注，通过反馈 API 写入 Langfuse Score（`user_feedback`），与当次 trace 关联。运营可在 Langfuse 按 `user_feedback <= 2` 筛选低分 case 复盘。

### curl 示例

先 `retrieve`，记下 `metadata.trace_id` 与 `metadata.log_id`：

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/rag/feedback \
  -H "Authorization: Bearer rk_live_你的key" \
  -H "Content-Type: application/json" \
  -d '{
    "trace_id": "<trace_id>",
    "log_id": "<log_id>",
    "score": 2,
    "comment": "排第一的不是目标文档"
  }'
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `trace_id` | 是 | retrieve 返回的 Langfuse trace id |
| `log_id` | 建议 | 用于租户校验与对账 |
| `score` | 是 | 整数 1～5 |
| `comment` | 否 | 备注 |

调试台 `/retrieve` 在召回结果上方提供五星反馈条；`LANGFUSE_ENABLED=false` 时无法提交反馈。

---

## 离线测评

检索效果批量量化（RAGAS）与 golden set 约定见项目 [`eval/datasets/`](../eval/datasets/) 目录。

典型流程：

1. **导出低分 case**：`python scripts/export_eval_cases_from_langfuse.py --max-score 3 --kb-id <kb_id>`
2. **补 `ground_truth`**：从知识库文档摘 1～2 句关键话写入 JSON
3. **跑评测**：`python scripts/run_retrieval_eval.py --dataset eval/datasets/ecommerce_retrieval.json --api-key rk_live_...`

安装：`pip install -e ".[eval]"`。报告输出到 `eval/reports/`（已 gitignore）。

---

## plan 与 profile 的关系

```
租户 plan（脚本改）  →  能用多少、能开 hybrid/rerank 吗
retrieve profile（每次请求传）  →  本次检索策略
kb settings.synonyms（按知识库）  →  词表扩展，各 plan 均可配置
```

- 不传 `profile` 时，服务端默认 `balanced`
- free 租户只能传 `profile=speed`
- standard 传 `profile=quality` 或 custom 开 rerank → 拒绝
- 配额不够就 **升 plan**，不支持 per-tenant JSON 覆盖

---

## 错误码

| code | 含义 | 典型场景 |
|------|------|----------|
| `20010` | 未授权 | Key 无效或未传 |
| `20013` | 当前套餐不支持该功能 | free 传 balanced；standard 开 rerank |
| `20014` | 配额已用尽 | free 建第 2 个库；日检索量超限 |
| `20005` | 接口调用超限 | 秒级 QPS 超限 |
| `20020` | 反馈提交失败 | Langfuse 未启用或写入异常 |
| `20021` | 检索记录与 trace 不匹配 | `log_id` 与 `trace_id` 不一致或无权访问 |
| `20022` | 评分无效 | `score` 不在 1～5 |

---

## 旧租户迁移

数据库升级后，**升级前已存在的 tenant** 自动设为 `standard`；`tenant_demo` 为 `pro`。此后新建 tenant 默认 `free`。

升档不影响已有索引，只影响后续配额与 retrieve 能力边界。

---

## 调试台

本地前端 `npm run dev` 后：

- **列表页** `/knowledge-bases`：查看 plan Badge 与今日检索用量
- **检索页** `/retrieve`：四档 profile 选择器，按 plan 自动置灰；知识库 Checkbox 多选（来自 `GET /knowledge-bases/tree`），结果展示来源库 Badge
- **上传页** `/`：超配额时展示后端返回的 20014 文案

更多 API 说明见 [README](../README.md)。
