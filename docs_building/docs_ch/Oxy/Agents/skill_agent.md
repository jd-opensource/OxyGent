
## 概述

`SkillAgent` 是 OxyGent 框架中的“技能增强智能体”。它的核心职责不是“执行技能脚本”，而是：

1. **发现技能（metadata-only）**：扫描技能目录并只加载 `name/description` 等轻量元数据。
2. **激活技能（system-driven）**：通过 **用户显式 `/skill-name ...`** 或 **selector（额外一次 LLM 选择）** 决定是否激活技能。
3. **注入上下文（prompt injection）**：激活后将 `SKILL.md` 的正文（以及可选 resources）作为上下文注入到 `${additional_prompt}`，让后续 LLM/工具调用在技能约束下继续执行。

> 重要：本实现 **不允许模型直接调用 `Skill` 工具**（`SkillTool` 会阻止 `invocation_source=model`），避免“模型自发开技能”。

同时，为了让官方 Codex 风格的技能（例如 `skill-creator`、`agent-browser`）更“开箱即用”，`SkillAgent` **默认启用 `shell_tools`**（提供 `run_shell_command`），用于执行技能工作流中描述的本地 CLI 命令。

> 提醒：**不建议关闭 `shell_tools`**。大量 skills 的工作流都依赖“执行本地命令”这一步（例如 `agent-browser` 需要调用本地 CLI），如果关闭，SkillAgent 往往只能注入指引但无法落地执行，导致 **大概率无法正常使用**。


## 本次更新概览（新增能力）

这一节用“用户视角”概括 SkillAgent 带来的新能力；如果你需要二次开发或排查问题，可以把它当作索引再跳到后面的实现细节。

1. **技能“可发现、可按需加载”**：只扫描技能元数据（name/description），需要时再加载 `SKILL.md` 正文与资源（progressive disclosure），减少无谓的上下文开销。
2. **两种激活方式**：
   - **手动激活**：用户通过 `/<skill-name> [arguments]` 明确使用某个技能。
   - **自动激活（可选）**：系统通过 selector（额外一次 LLM 选择）在候选技能中选择最多一个并激活。
3. **更安全的“脚本执行”通道（可选）**：提供 `run_skill_script`，只允许运行对应 skill 的 `scripts/` 目录下脚本，并对扩展名做白名单限制。
4. **开箱即用的内置技能**：内置 preset skills（例如 `skill-creator`），无需手工拷贝即可使用；同时保持同名覆盖规则，方便用户自定义版本优先。
5. **配套 Demo / 单测与稳定性改进**：提供对话式示例与测试覆盖，并修复若干与运行环境/测试稳定性相关的问题。


## SkillAgent 能做什么

1. **让用户通过统一的“技能目录 + 手动指令”使用技能**：`/<skill-name> [arguments]`
2. **让系统通过 selector 自动选择（最多一个）技能并激活**（可开关）
3. **将技能正文/资源作为上下文注入**，使后续对话/工具调用遵循技能工作流
4. **把选中/激活信息写入 `OxyResponse.extra`**，便于日志与 UI 展示
5. **默认可调用 `run_shell_command` 执行本地 CLI 命令**：便于按技能工作流落地（例如 `agent-browser` 需要执行命令行工具）


## SkillAgent 的实现细节（关键流程）

### 1）MAS 侧：SkillRegistry + SkillTool wiring

在 `MAS.init()` 中：

- 若 `mas.skill_registry` 为空：创建 `SkillRegistry(auto_discover=True)`
- 若 MAS 未注册名为 `Skill` 的 tool：注册 `SkillTool()`
- 若已存在 `SkillTool`：通过 `set_registry()` 绑定 registry

因此在正常 MAS 启动时：

- `oxy_request.mas.skill_registry` 总是可用（如果初始化成功）
- `SkillTool` 可以通过 `oxy_request.mas.skill_registry` 找到 registry


### 2）SkillAgent：在 `_before_execute()` 激活并注入

`SkillAgent` 继承 `ReActAgent`，但技能逻辑主要发生在 **执行前 hook**：

1. `await super()._before_execute()`：让 `LocalAgent` 先把 `tools_description`、基础 `additional_prompt` 等准备好
2. 注入“技能目录”（metadata-only）：追加到 `oxy_request.arguments["additional_prompt"]`
3. **手动激活优先**：若用户 query 满足 `/skill-name ...`：
   - 调用 `Skill` 工具：`invocation_source="user"`
   - 把 `SkillTool` 返回的注入文本追加到 `additional_prompt`
   - 将 `query` 重写为“arguments 部分”（避免 LLM 继续看到 `/skill-name`）
4. 若未手动激活且 `enable_selector=True`：
   - 调用 `select_skill(...)`（metadata-only）得到 `{selected_skill, confidence, reason}`
   - 置信度达阈值后调用 `Skill` 工具：`invocation_source="selector"`
   - 将注入文本追加到 `additional_prompt`

并在 `_after_execute()` 将以下字段回填到响应里：

- `OxyResponse.extra["skill_selection"]`
- `OxyResponse.extra["skill_activation"]`


### 3）SkillTool：只负责“加载 + 注入”，不执行技能任务

`SkillTool` 的行为：

- 通过 registry 按需加载技能全文（progressive disclosure）
- 生成注入内容：`SkillContent.to_context_injection()`（包含 `[SKILL ACTIVATED: name]` 标记）
- 替换 `$ARGUMENTS`（若提供 arguments）
- 严格限制调用源：
  - `invocation_source=model`：直接 `SKIPPED`
  - `disable-model-invocation=true`：阻止 selector 激活
  - `user-invocable=false`：阻止用户 `/skill-name` 手动激活

返回：

- `output`：注入字符串
- `extra.environment_modifications`：当前支持解析 `allowed_tools/model/timeout`（由 skill frontmatter 提供）

> 说明：本版本 SkillAgent 主要使用“注入 prompt”，`environment_modifications` 目前仅透出在 `extra`，未对 agent 运行时做强制应用。


## 方案 B：执行 Skill 自带脚本（新增 `run_skill_script` Tool）

`SkillAgent/SkillTool` 仍然只负责“发现/激活/注入”，**不自动执行** skill 的 `scripts/`。为了让官方 `skill-creator` 这类 skill 能“按 Codex 方式”落地创建技能，本仓库新增了一个 **Skill 感知且有安全边界** 的 Tool：

- Tool Hub：`skill_tools`
- Tool：`run_skill_script`

### 行为与安全边界

1. 通过 `SkillRegistry.get_skill(skill_name)` 解析出 `SKILL.md` 路径，得到 skill 根目录 `base_dir`。
2. 只允许执行 `base_dir/scripts/` 下的文件（禁止 `..` 路径逃逸）。
3. 支持的脚本类型（白名单）：`.py` / `.sh` / `.zsh`。
4. 对 `init_skill.py --path <dir>` 这类“输出目录参数”为相对路径的场景，会将 `<dir>` 统一按**进程启动目录（通常是项目根目录）**解析，避免在 skill 目录内产生“套娃路径”。

### 示例：用 `skill-creator` 创建 skill

用户输入（手动激活 skill）：

```text
/skill-creator init hello-skill --path .claude/skills
```

随后 agent 在 skill 指引下调用：

```json
{
  "tool_name": "run_skill_script",
  "arguments": {
    "skill_name": "skill-creator",
    "script_relpath": "init_skill.py",
    "args": ["hello-skill", "--path", ".claude/skills"]
  }
}
```


## Preset skill：内置 `skill-creator`

为满足“无需手工拷贝即可直接使用官方 agent skills”的诉求，本仓库将官方 `skill-creator` 作为 **preset skill** 内置：

- 位置：`oxygent/preset_skills/skill-creator/`
- 发现：`SkillRegistry.DEFAULT_SKILL_DIRS` 会自动包含该目录（最低优先级）

### 同名 skill 的覆盖优先级（Codex/Claude Code 规则）

当多个目录下存在同名 skill 时，**项目（project-local）优先级最高**，其次才是个人（personal），最后才是内置 preset。

默认从低到高的覆盖顺序为：

1. `oxygent/preset_skills/`（最低）
2. `~/.oxygent/skills/`
3. `~/.claude/skills/`
4. `.oxygent/skills/`
5. `.claude/skills/`（最高）

因此：如果你在项目里提供了 `.claude/skills/skill-creator`（或 `.oxygent/skills/skill-creator`），将覆盖 `~/.claude/skills` / `~/.oxygent/skills` 里的同名 skill，以及内置 preset 版本。

## 缓存与目录设计

这部分说明 `SkillAgent`/`SkillTool` 的缓存与目录解析策略，避免把它误解为“磁盘缓存”。

### 1）目录解析策略

- **默认模式（未配置 `skill_dirs`）**：使用 MAS 全局 `SkillRegistry.DEFAULT_SKILL_DIRS`，优先级从低到高为：
  1. `oxygent/preset_skills/`
  2. `~/.oxygent/skills/`
  3. `~/.claude/skills/`
  4. `.oxygent/skills/`
  5. `.claude/skills/`
- **按 agent 隔离模式（配置 `skill_dirs`）**：`SkillAgent` 仅从该 agent 的绝对路径目录列表发现 skill，不再读取默认目录链。
- **空目录行为**：目录存在即可通过初始化；空目录表示“当前无可用 skill”，不会自动回退默认目录。

### 2）缓存层级（均为进程内内存缓存）

| 层级 | 位置 | Key | 内容 | 作用域 |
|---|---|---|---|---|
| 元数据索引 | `SkillRegistry.metadata_index` | `skill_name` | `name/description/skill_path` 等 metadata | 单个 `SkillRegistry` 实例 |
| 技能全文缓存 | `SkillRegistry._content_cache` | `skill_name` | 解析后的 `SkillContent`（含 resources） | 单个 `SkillRegistry` 实例 |
| Agent scoped registry 缓存 | `SkillAgent._scoped_skill_registry` + `_normalized_skill_dirs` | 归一化后的目录列表 | `SkillRegistry` 实例 | 单个 `SkillAgent` 实例 |
| Tool scoped registry 缓存 | `SkillTool._scoped_registry_cache` | `tuple(normalized_skill_dirs)` | `SkillRegistry` 实例 | 进程级（`SkillTool` 类级） |

> 以上缓存都在内存中，不会写入 `cache_dir/` 或其它磁盘目录。

### 3）生命周期与失效策略

- `SkillRegistry`：
  - `discover_all()`：重建 metadata 索引（不加载全文）。
  - `load_full_content()`：首次加载技能全文后写入 `_content_cache`。
  - `reload()`：清空 `_content_cache` 并重新 discover。
- `SkillAgent` scoped 缓存：
  - 首次使用或 `init()` 时按 `skill_dirs` 构建。
  - 当 `skill_dirs` 发生变化时，会按新目录重建 scoped registry。
- `SkillTool` scoped 缓存：
  - 相同目录 tuple 会复用同一 `SkillRegistry`（减少重复 discover）。
  - 默认无 TTL；进程重启后自然清空。
  - 如开发态需要手动清理，可执行 `SkillTool._scoped_registry_cache.clear()`。

### 4）设计取舍

- **性能**：通过 metadata-only + 按需全文加载，避免把所有 `SKILL.md` 一次性塞入上下文。
- **隔离**：`skill_dirs` 让不同 `SkillAgent` 在同一 MAS 内可使用不同技能集合。
- **一致性**：同名冲突在同一 registry 内遵循“后发现覆盖先发现”规则，目录优先级可预测。


## 手动激活语法

- 格式：`/<skill-name> [arguments]`
- skill-name：`[a-zA-Z0-9][a-zA-Z0-9_\-]{0,127}`
- `//...` 会被当作普通文本（用于转义）

示例：

```text
/skill-creator init hello-skill --path .oxygent/skills
```


## Selector 自动激活（metadata-only）

当 `enable_selector=True` 且没有手动激活时：

- selector 会把“用户 query + 候选 skills（name: description）”发给 LLM
- 期望返回 **严格 JSON**：

```json
{
  "selected_skill": "<name>" | null,
  "confidence": 0.0,
  "reason": "..."
}
```

- 低于 `selector_min_confidence` 时不激活技能


## 参数配置

`SkillAgent` 关键参数：

| 参数 | 类型 | 默认值 | 说明 |
|---|---:|---:|---|
| `enable_skill_catalog` | bool | `True` | 是否注入“可用技能目录（metadata-only）” |
| `skill_catalog_max_entries` | int | `50` | 注入技能条目上限（0 表示不截断） |
| `enable_selector` | bool | `True` | 是否启用 selector 自动激活 |
| `selector_max_candidates` | int | `30` | 送入 selector 的候选技能数 |
| `selector_min_confidence` | float | `0.6` | 自动激活阈值 |
| `selector_llm_model` | str\|None | `None` | selector 用的 LLM，默认用 agent 的 `llm_model` |
| `enable_shell_tools` | bool | `True` | 是否默认启用 `shell_tools`（`run_shell_command`），用于执行技能工作流中的本地命令；如需关闭可设为 `False`，或通过 `except_tools` 禁用具体命令 |
| `skill_dirs` | list[str]\|None | `None` | 可选的“agent 级技能目录白名单”（绝对路径）。配置后仅从这些目录发现技能；未配置时沿用 MAS 全局 `SkillRegistry` 默认规则 |

### `skill_dirs` 行为说明（按 agent 隔离）

- **未配置 `skill_dirs`**：行为不变，继续使用 MAS 全局 registry（默认 `.claude/.oxygent + preset` 规则）。
- **配置 `skill_dirs`**：仅使用该 agent 的目录列表发现技能，不再读取默认目录。
- **严格校验**：每个目录必须是绝对路径、必须存在且为目录；否则在初始化时抛错并阻止启动。
- **空目录允许**：目录存在即可通过初始化；如果目录中暂无 skill，后续表现为“该 agent 当前无可用 skill”。

示例（同一 MAS 中隔离两个 SkillAgent）：

```python
oxy.SkillAgent(
    name="agent_a",
    llm_model="default_llm",
    skill_dirs=["/abs/path/to/skills/a"],
)

oxy.SkillAgent(
    name="agent_b",
    llm_model="default_llm",
    skill_dirs=["/abs/path/to/skills/b"],
)
```


## 使用示例

### 1）命令行对话式 Demo

```bash
python examples/agents/demo_skill_agent.py \
  --agent-a-skill-dir /abs/path/to/skills/a \
  --agent-b-skill-dir /abs/path/to/skills/b
```

### 1.1）skill-creator + agent-browser Demo（推荐）

```bash
python examples/agents/demo_skill_creator.py
```

### 2）Web 对话（可选）

```bash
python examples/agents/demo_skill_agent.py \
  --agent-a-skill-dir /abs/path/to/skills/a \
  --agent-b-skill-dir /abs/path/to/skills/b \
  --web
```

### 3）环境变量

如果希望启用 selector（需要可用的 LLM）：

- `DEFAULT_LLM_BASE_URL`
- `DEFAULT_LLM_MODEL_NAME`
- （可选）`DEFAULT_LLM_API_KEY`


## 常见问题

### Q1：为什么模型输出里出现 `tool_name: "skill-creator"`？

Skill 是“注入上下文”，不是 MAS 里可调用的 tool。为了避免模型把 skill 当 tool，本仓库的约束是：

- Skill 激活只能通过系统调用 `Skill` tool
- Demo 里也增加了 prompt 约束：**Never use a skill name as tool_name**

### Q2：为什么会提示 skill 重名覆盖？

`SkillRegistry` 的搜索路径有优先级：**项目（project-local）覆盖个人（personal）**，同级目录下“后面的覆盖前面的”。

默认优先级见上文「同名 skill 的覆盖优先级」。

### Q3：如何查看当前有哪些 skills？

建议使用显式命令：`list skills`。

这类问题本质是“**列出 metadata**”，不是“激活某个 skill”。在未做专门处理时，可能出现：

1. **模型倾向于调用 Tool**：它看到 toolset 里存在 `Skill`，会尝试用它来“列出技能”，但 `Skill` 设计上需要 `name`，并且模型调用也会被拦截（`SKIPPED`），最终容易输出含糊答案。
2. **Prompt 依从性/截断**：即使已经注入了“技能目录”，模型也可能忽略该段（尤其在上下文很长时）。
3. **实际未使用 SkillAgent**：如果 master agent 不是 `SkillAgent`，就不会有 catalog 注入与相关拦截逻辑。

当前实现：

- 用 `/<skill-name> ...` 明确激活。
- 用 `list skills`：`SkillAgent` 会直接从 `SkillRegistry` 的 metadata 生成用户可读的 skills 列表（不加载全文）。
