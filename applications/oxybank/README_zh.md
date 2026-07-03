# OxyBank

一个轻量级的**数据标注与检索平台**，专为构建 AI 训练 / RAG 数据集设计。OxyBank 将 Elasticsearch（结构化检索）与 Vearch（向量相似度检索）结合，让一个"数据库"（Bank）既能做传统的关键词/过滤查询，又能做语义检索 —— 同时为人工标注员（和标注 Agent）提供一个整洁的工作台来管理数据。

内置 FastAPI 后端、基于 jQuery 的单页前端、JWT 鉴权、每个 Bank 独立的检索接口、AI 辅助的模板设计器，以及可插拔的标注 Agent 框架。

**English version**: see [README.md](README.md)

---

## 核心特性

- **Bank（数据银行）** —— 数据容器，附带用户自定义的字段 schema。内置 5 种场景模板（QA / 记忆 / 客服 FAQ / 知识库 / 产品目录），也可以完全自定义。
- **双存储检索** —— Elasticsearch 负责结构化过滤 / 全文；Vearch 负责向量相似度。任何字段都能标记为向量字段，原生支持多向量联合检索。
- **自定义检索接口** —— 每个 Bank 可配置多个检索接口，每个接口就是一份 mini API 定义（条件字段、匹配模式、输出字段）。
- **标注工作台** —— 样本列表 + 进度条 + 动态状态过滤 + 模板驱动的表单（radio / select / textarea / 条件显示）+ 上一条 / 下一条导航 + 版本历史。
- **全局模板池** —— 标注模板全局共享（不与 Bank 绑定）；每个样本通过 `sys_template` 引用一个模板名。
- **AI 模板设计助手** —— 用自然语言描述你要的模板，LLM 会读取当前 Bank 的 schema 生成模板 JSON。
- **标注 Agent** —— 注册外部 HTTP 服务，当样本 `sys_status` 变为指定值时自动触发。异步、超时可控，有完整执行日志。
- **文档导入** —— 支持 `.txt / .md / .pdf / .docx`（启用 `sys_chunk` 时自动切分）和 `.csv / .xlsx`（每行一条 sample）。
- **中英双语** —— 前端所有页面双语覆盖，切换语言即时生效。

---

## 环境要求

- Python 3.10+
- Elasticsearch 7.x（必需）
- Vearch 3.3.x（仅当有 Bank 使用向量检索时需要）
- Triton（或 OpenAI 兼容）Embedding 服务（仅向量检索需要）
- OpenAI 兼容的 chat-completions 服务（仅 AI 模板设计 / 标注 Agent 调用需要）

---

## 项目结构

```
OxyBank/
├── app/              # FastAPI 后端（routers / services / storage / auth）
├── web/              # 前端（静态 HTML/CSS/JS + jQuery）
├── deployment/       # Dockerfile + 启动脚本
├── config.json       # 运行时配置（见下文）
├── requirements.txt  # Python 依赖
└── run.py            # 启动入口（拉起 uvicorn）
```

后端代码直接放在 `app/` 下 —— 没有额外的 `backend/` 外壳目录。

---

## 快速开始

### 1. 装依赖

```bash
pip install -r requirements.txt
```

### 2. 修改配置指向你自己的基础设施

`config.json` **按环境分层**。启动时 loader 先套 `default` 段作为公共默认值，再用当前环境的同名段做**深度合并**覆盖。当前环境由环境变量 `OXYBANK_ENV` 决定（默认 `development`）。环境段里没写的字段自动继承 `default` 里的值。

**合并规则**是**深度合并**：`production.es` 只覆盖它列出的字段（比如 `hosts / user / password`），`index_prefix / timeout` 仍然从 `default.es` 继承。设了个未知环境值时会回退到只用 `default`。

- `auth.enabled: false` —— 所有请求都以匿名管理员身份进入。本地开发方便，**生产环境务必改成 true 并换掉 `secret_key`**。
- 只有确实要用向量检索 / AI 功能时才需要填 `vearch / triton / llm`，其他部分照常工作。

### 3. 启动服务

```bash
# 本地开发 —— OXYBANK_ENV 默认就是 development
python run.py

# 线上部署 —— 用 config.json 里的 production 段
OXYBANK_ENV=production python run.py
```

Docker 部署时在容器里设环境变量：

```dockerfile
ENV OXYBANK_ENV=production
```

默认监听 `http://0.0.0.0:8080`（API 和前端都从这一个端口出）。

首次启动会自动创建默认管理员账号 `admin / admin`（当 `auth.enabled` 曾经打开过、且用户表为空时）。登录后请到「用户管理」页改密码。

浏览器访问 `http://localhost:8080` 登录即可。

---

## 核心概念

### Bank

一个 Bank 是一个数据集容器，包含：

- 一份 **schema**（用户定义的字段列表，类型可选 `text` / `keyword` / `integer` / `float` / `string`）
- 可选的 **`sys_chunk` 字段** —— 想上传文档并自动切 chunk 时勾选（配合向量检索）
- 一个或多个 **检索接口**（下面详说）
- 若有字段用向量模式，还需指定 **embedding backend**

在「Bank 管理」页新建。选一个**场景模板**能拿到合理的初始 schema，也可以选「自定义」自己配。

### 系统字段（`sys_*`）

每个样本除了用户自定义字段外，还带一组平台管理的系统字段。大部分你不需要手动写 —— 平台会自动设置和推进。用户自定义字段（在 Bank schema 里定义的）跟这些字段并排存在。

**身份类（自动分配，不要动）**

| 字段 | 用途 |
|---|---|
| `sys_sample_id` | 样本 UUID，创建后不变 |
| `sys_document_id` | 样本所属文档的 UUID（一个文档对应多个样本） |
| `sys_create_time` / `sys_update_time` | 时间戳（UTC ISO 8601） |

**工作流类 —— 平时会用到的**

| 字段 | 用途 |
|---|---|
| `sys_status` | 工作流状态。规范英文取值：`Imported`、`To Assign`、`Assigned`、`To Annotate`、`Annotated`、`Rejected`、`Published`、`Ignored`；也支持任意自定义值。驱动标注 Agent 的触发。 |
| `sys_template` | 该样本使用的标注模板。接受模板 UUID 或 name（推荐用 name） |
| `sys_executor` | 分配到的标注员用户名 |
| `sys_priority` | 标注工作台里的排序优先级（整数，越小越靠前） |
| `sys_overview` | 简短摘要（样本列表里展示） |
| `sys_remarks` | 自由备注（比如驳回原因） |
| `sys_chunk` | 文档切分后的文本块。仅当 Bank 创建时勾选「启用文档切分」才有。**这是唯一支持向量检索的 sys_ 字段。** |

**状态流转辅助字段（自动维护，只读语义）**

| 字段 | 用途 |
|---|---|
| `sys_next_status` / `sys_next_template` / `sys_next_executor` | 样本下次保存时要推进到的状态。由标注 Agent 的输出写入，样本更新接口消费后自动清空。 |
| `sys_prev_status` / `sys_prev_template` / `sys_prev_executor` | 样本最近一次更新前的状态。**每次写入样本时自动 snapshot**（无论人工修改还是 Agent 写入）—— 标注页面「驳回」按钮就是用这几个字段把样本恢复到上一个状态。不要手动写。 |

### 检索模式

定义检索接口时，每个字段可选：

- `exact` —— 完全相等（ES `term`）
- `in` —— 值在列表中（ES `terms`）
- `fuzzy` —— 全文模糊匹配（ES `match`，带 fuzziness）
- `vector` —— 把查询文本 embedding 后，与该字段的 `{field}_vector` 列做相似度排序

一个接口可以配置多个 `vector` 字段，Vearch 会把多列距离求和后排序。

### 标注模板

模板定义标注表单（哪些字段可编辑、单选选项、条件显示等）。**全局共享** —— 任何 Bank 都能使用任何模板。通过 `name`（全局唯一）或 UUID 引用。

内置两个：
- `builtin_qa` —— 针对 `query` + `answer`，标注是否满意 + 可选原因
- `builtin_business` —— 针对 `sys_chunk`，标注所属业务域（radio）

在「标注模板」页可以新增：手写 JSON，或用 AI 设计助手（描述需求 → 生成 JSON → 微调保存）。

### 标注 Agent

在「Agent 管理」页注册一个外部服务：
- **服务 URL**（一个 POST 接口，收样本、返修改）
- **触发状态**（一个或多个 `sys_status` 值）

当样本进入任一触发状态时，OxyBank 会异步调用 Agent。Agent 的返回会作为样本更新写回，走同一条状态事件管道 —— 因此 Agent 可以**链式触发**（一个 Agent 的输出触发下一个 Agent）。

### 存储分工

- **Elasticsearch** —— 权威存储，每条样本的所有字段都在这里。
- **Vearch** —— 精简副本：向量列 + 被检索接口引用的 filter 字段。只有至少一个向量字段非空的样本才会写入 Vearch。

前端把这一层对用户透明。检索接口、deposit、样本更新都会自动保持两处数据同步，日常使用不需要手工调什么"重建索引"接口。

---

## 典型工作流

### A. 上传数据并标注

1. **建 Bank** —— 选一个场景模板（如 QA）或自定义 schema。
2. **上传数据** —— 到「数据管理」页，拖入 `.csv` / `.xlsx`（列名要跟 schema 对得上）或 `.pdf` / `.docx` / `.txt` / `.md`（若启用 `sys_chunk`，文件会自动切 chunk）。
3. **打开标注工作台** —— 按状态过滤，点某条样本 → 填表 → 保存。表单由该样本 `sys_template` 引用的模板驱动。
4. **可选：注册标注 Agent** —— 自动化部分流程，比如"状态变 `To Annotate` 时，调我的 LLM 起草一版标注"。
5. **查数据** —— 到「API 测试」页看自动生成的检索接口，复制 curl / Python 代码集成到业务代码里。

### B. 项目进行中新增检索接口

1. 「Bank 管理」→ 编辑 Bank → 添加检索接口。定义条件（字段 + 模式）和输出字段。
2. 新接口立即出现在「API 测试」页上。若新增了向量字段，现有样本会在后台自动回填到向量索引，无需手工触发。

### C. 集成到 LLM 应用

调用 `GET /api/banks/{bank}/list_banks`（或点「API 测试」页上的按钮）—— 返回一份 JSON 格式的工具描述，大多数 Agent 框架（LangChain、OxyGent SDK 等）能直接消费。

---

## 前端页面

| 页面 | 用途 |
|---|---|
| **Bank 管理** | 创建 / 查看 / 删除 Bank |
| **数据管理** | 上传文档，浏览编辑样本 |
| **标注工作台** | 逐样本标注（标注员登录后默认进这个页面） |
| **Agent 管理** | 注册标注 Agent、查看流程图、查执行日志 |
| **API 测试** | Bank 的检索 / 存储 API 的交互式文档 |
| **标注模板** | 管理标注模板（编辑 JSON、AI 辅助、真实样本预览） |
| **用户管理** | 用户 CRUD（仅管理员） |
| **系统配置** | 系统级配置（仅管理员） |
| **帮助** | 内置使用文档 |

标注员角色（`annotator`）只能看到「标注工作台」和「帮助」。

---

## API 路由地图

所有 API 前缀都是 `/api`：

| 分组 | 基础路径 |
|---|---|
| 认证 | `/api/auth/*` |
| Bank | `/api/banks` |
| 文档 | `/api/banks/{bank_name}/documents` |
| 样本 | `/api/banks/{bank_name}/samples` |
| 检索 | `/api/banks/{bank_name}/{api_id}/withdraw`，以及自动生成的 `withdraw` / `deposit` / `deposit_batch` / `list_banks`（挂在 `/api/banks/{bank_name}/` 下） |
| 模板 | `/api/banks/{bank_name}/templates`（模板其实是全局的，路径保留 bank 段仅为兼容） |
| Agent | `/api/banks/{bank_name}/agents` |
| 用户 | `/api/users` |
| 配置 | `/api/config` |

前端「API 测试」页会为当前 Bank 的每个检索接口生成动态文档（URL、参数、curl 代码、Python 代码、Try-it 面板）。

---

## 常见坑

- **PDF / DOCX 上传后整份文件变成了一条样本。** 建 Bank 时勾选 `has_sys_chunk`，才会自动切成多个 chunk。
- **CSV / XLSX 的列跟 schema 字段对不上。** 多余列会被忽略，缺失列变空 —— 表头名必须与 schema 字段名严格一致。
- **有 ES 数据但向量检索返回 0 条。** deposit 时向量字段为空（比如样本先入库、等 Agent 后补内容），Vearch 会跳过写入。等字段被后续填上（人工修改或 Agent 触发），会自动 upsert，无需手动干预。
- **`sys_template` 的值展示了错误的模板。** 模板解析先按 UUID 直查，找不到再按 name 全局查找 —— 值必须严格等于其中之一，空格 / 大小写会导致不匹配。
- **内置模板不能改。** 在「标注模板」页点「克隆」，得到一份可编辑副本再改。

---

## 开发

```bash
# 开发环境跟生产用同一条命令启动
python run.py
```

- 前端是纯 HTML/CSS/JS + jQuery，由 FastAPI 的静态挂载 `/css` `/js` 加上 `web/*.html` 的 catch-all 路由服务。**没有 build 步骤**，改了直接刷新。
- 后端默认不热重载（见 `run.py`）。改代码后需要重启。
- 前端在 `localStorage` 缓存 `oxybank-token` 和 `oxybank-user`。想强制重新登录，清掉这两个键。

### 扩展新的检索模式 / 状态 / 字段类型

- **新检索模式** —— 在 `app/services/retrieval_service.py` 里教会翻译成 ES 子句 + 相应的 Vearch filter（如需）；在 `web/js/banks.js` 的模式下拉里加选项。
- **规范状态** —— 加到 `web/js/agents.js` 的 `CANONICAL_STATUSES` 里，并在 `web/js/annotation.js` 的 `STATUS_COLOR_OVERRIDES` 里给它配色。后端不用改，`sys_status` 是自由字符串。
- **新字段类型** —— 若新类型需要 Vearch 单独一列，扩展 `app/services/bank_service.py::_build_vearch_properties`；在 `web/js/banks.js` 里让 schema 编辑器识别新类型。
