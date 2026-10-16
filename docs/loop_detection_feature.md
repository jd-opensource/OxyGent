# ReAct Agent 工具调用循环检测 — 功能说明

| 项目 | 内容 |
|------|------|
| **功能名称** | Loop Detection for ReAct Agents |
| **所属模块** | `oxygent.utils.loop_detector` / `oxygent.utils.loop_signatures` |
| **接入点** | `oxygent.oxy.agents.ReActAgent`（及其子类 `SkillAgent` / `RagAgent`）|
| **版本** | feature-loopdetection-20261014 |
| **状态** | 已完成单测与端到端验证，待合入 |

---

## 目录

1. [一句话概括](#1-一句话概括)
2. [要解决的问题](#2-要解决的问题)
3. [功能全貌](#3-功能全貌)
4. [四种循环模式](#4-四种循环模式)
5. [三种处理模式](#5-三种处理模式)
6. [两层输出签名机制](#6-两层输出签名机制)
7. [使用方式](#7-使用方式)
8. [工作原理](#8-工作原理)
9. [与现有系统的关系](#9-与现有系统的关系)
10. [扩展与定制](#10-扩展与定制)
11. [设计取舍](#11-设计取舍)
12. [FAQ](#12-faq)

---

## 1. 一句话概括

> **自动识别 ReAct Agent 的工具调用死循环，可配置为静默、告警或立即终止，默认关闭，对现有用户零影响。**

---

## 2. 要解决的问题

### 2.1 现状痛点

OxyGent 的 `ReActAgent` 以 `max_react_rounds`（默认 16）为唯一兜底 —— 只要 agent 没返回最终答案就一直循环。但现实中大量场景是 LLM **陷入了无效循环**：

- **工具报错 → LLM 看不懂 → 用相同参数再调 → 再报错**（头铁硬刚）
- **同一个 query 查到空结果 → LLM 不死心 → 换个 query → 还是空**（换皮循环）
- **权限/网络被拒 → LLM 以为是参数问题 → 反复换参数**（永久阻断仍重试）
- **A 工具 → B 工具 → A 工具 → B 工具**（钟摆震荡）

这些场景的共同特征：
1. **一定会跑满 `max_react_rounds` 才停**，烧 10 倍以上 LLM 调用
2. **最终返回的答案往往是胡编**（LLM 在上下文窗口耗尽后编一个结论糊弄）
3. **工具侧的流控/配额被白白消耗**（相同参数反复调同一个工具）
4. **用户等待 30 秒+**，体验极差

### 2.2 本功能的价值

| 维度 | 改进前 | 改进后 |
|------|-------|-------|
| LLM 调用次数 | 跑满 max_react_rounds（10-16 次）| 3 次触发后立即停 |
| 响应时间 | 5-30 秒 | 1-2 秒 |
| 工具调用次数 | 跑满 max_react_rounds | 3 次触发后立即停 |
| 用户体验 | 等很久拿一个胡诌答案 | 快速拿到 "请换个问法" 的明确提示 |
| 问题可观测 | 需翻完整轮次日志才能看出循环 | 一条 WARN 日志 `Loop detected: {...}` |

---

## 3. 功能全貌

```
┌─────────────────────────────────────────────────────────────┐
│                   ReActAgent._execute()                     │
│                                                              │
│   ┌──────────────────────────────────────────────────┐      │
│   │ 每一轮循环：                                     │      │
│   │   1. LLM 生成 tool_call                          │      │
│   │   2. 执行工具 → 拿到结果                         │      │
│   │   3. 写入 react_memory                           │      │
│   │   4. 【本次新增】调用 detect_loop(...)  ←────────┼──┐   │
│   │        - 读 shared_data 里的历史 trace           │  │   │
│   │        - 跑 4 个检测器                           │  │   │
│   │        - 命中 → 按配置的模式处理                 │  │   │
│   └──────────────────────────────────────────────────┘  │   │
│                                                          │   │
└──────────────────────────────────────────────────────────┼───┘
                                                           │
                              ┌────────────────────────────┼───┐
                              │  oxygent/utils/            │   │
                              │  ├── loop_detector.py  ◄───┘   │
                              │  │   • 4 个检测器              │
                              │  │   • trace 缓冲区（上限 6）  │
                              │  │   • 提示模板                │
                              │  │                             │
                              │  └── loop_signatures.py        │
                              │      • Layer 1 hash 兜底       │
                              │      • Layer 2 @register       │
                              │      • 阈值表 / 良性签名       │
                              └────────────────────────────────┘
```

### 3.1 核心能力清单

| 能力 | 组件 | 说明 |
|------|------|------|
| 识别"同参重调" | `_detect_repeat` | 连续 N 次完全相同参数 |
| 识别"报错硬刚" | `_detect_error_retry` | 工具报错后同参再调 |
| 识别"换皮循环" | `_detect_repeat_by_output` | 换参数但结果类别一致 |
| 识别"钟摆震荡" | `_detect_cycle` | ABAB / ABCABC 周期 |
| 输出降噪 | Layer 1 签名 | 剥除时间戳 / UUID / trace_id |
| 自定义归类 | Layer 2 签名 | 装饰器注册语义分类 |
| 静默跳过 | `disabled` 模式 | 默认，零开销 |
| 告警 + 自救 | `warn` 模式 | 注入系统提示让 LLM 自救 |
| 立即终止 | `block` 模式 | 返回 fallback 消息 |
| 诊断留痕 | `shared_data` | 命中后保留 `_loop_detected` 结构 |

---

## 4. 四种循环模式

### 4.1 error_retry（头铁硬刚）

**触发条件**: 上一步工具报错，当前步用**完全相同参数**再调。

**典型场景**:
```
step 1: curl(url="http://xxx")        → Error: timeout
step 2: curl(url="http://xxx")        → 触发 error_retry
```

**为什么要立即拦**: 参数没变，网络环境没变，结果几乎必然再次报错。

### 4.2 repeat（单曲循环）

**触发条件**: 连续 3 次（默认阈值）用**完全相同参数**调同一工具。

**典型场景**:
```
step 1: search(q="量子隧穿")  → "No matching results"
step 2: search(q="量子隧穿")  → "No matching results"
step 3: search(q="量子隧穿")  → 触发 repeat
```

**为什么阈值是 3**: 允许正常的"查一次没有，稍微换一下再查一次"（2 次不触发），但第 3 次相同参数就不合理了。

### 4.3 repeat_by_output（换皮循环）

**触发条件**: 换参数但结果**语义类别一致** N 次（阈值按签名类别可配）。

**典型场景**:
```
step 1: curl(url="http://a") → "403 Permission Denied"  → sig=permanent_block
step 2: curl(url="http://b") → "403 Permission Denied"  → sig=permanent_block（阈值=2）
                                                         → 触发 repeat_by_output
```

**依赖**: 需要工具通过 `@register_signature` 注册自定义签名；未注册时降级为 Layer 1 hash，只能抓完全一致输出。

**为什么需要**: `curl` 调不同 URL 都被同一个 proxy 拒掉 → fingerprint 不同，Layer 1 hash 不同，普通 `repeat` 抓不到。签名让"同类错误"坍缩成一个类别。

### 4.4 cycle（钟摆震荡）

**触发条件**: 最近 4 步（或 6 步）的指纹序列呈现 ABAB / ABCABC 模式。

**典型场景**:
```
step 1: list_files()      ← A
step 2: read_file(f1)     ← B
step 3: list_files()      ← A
step 4: read_file(f1)     ← B  → 触发 cycle（周期 2）
```

**为什么需要**: `repeat` 只能抓单工具循环，钟摆是多工具循环。

---

## 5. 三种处理模式

通过 `ReActAgent.loop_detection_mode` 配置：

### 5.1 `disabled`（默认）

```python
loop_detection_mode="disabled"
```

**行为**: 完全跳过检测器，不读取 `shared_data`，不写 trace。

**何时用**: 现有用户升级后无需任何改动 —— 这是默认值，保证**零破坏性变更**。

### 5.2 `warn`（告警 + 自救）

```python
loop_detection_mode="warn"
```

**行为**:
1. 日志打印 `WARNING - Loop detected: {...}`
2. 向 `react_memory` 注入一条**面向 LLM 的系统提示**，告诉它检测到了什么循环，建议它换策略
3. **继续执行**后续 react 轮次

**何时用**: 开发/调试期，或希望给 LLM 一次自救机会的生产场景。

**注入提示示例**（type=repeat 时）:
> `[System] You have called 'search' with identical arguments multiple times. The result will not change. Stop repeating; switch strategy or give the final answer.`

### 5.3 `block`（立即终止）

```python
loop_detection_mode="block"
loop_fallback_message="已检测到工具调用循环，请换一种问法。"
```

**行为**:
1. 日志打印 `WARNING - Loop detected: {...}`
2. **立即终止** ReAct 循环
3. 返回 `OxyResponse(output=loop_fallback_message, extra={..., "loop_detected": {...}})`

**何时用**: 生产环境，希望快速止损、给用户明确反馈。`extra.loop_detected` 可被上游消费做监控/告警。

---

## 6. 两层输出签名机制

签名把工具的输出归类成一个短字符串（如 `"ok"` / `"empty"` / `"permanent_block:auth"`），用于 `repeat_by_output` 和 `cycle` 的输出维度检测。

### 6.1 Layer 1：默认 hash 兜底

**没注册签名的工具自动走这里**。流程：

1. 对工具返回文本做噪声剥除（见下表）
2. 取 MD5 前 12 位
3. 前缀 `h:` 便于日志中区分

**剥除的噪声模式**:
| 噪声类型 | 示例 | 替换为 |
|---------|-----|-------|
| ISO/RFC 时间戳 | `2026-10-14T12:30:00Z` | `<TS>` |
| UUID | `3a7f9b2c-...` | `<UUID>` |
| 32-64 位 hex | `abc123...` (MD5/SHA/trace_id) | `<HEX>` |
| HTTP Date | `Mon, 14 Oct 2026 ...` | `<HTTPDATE>` |
| Python 内存地址 | `at 0x7f...` | `at 0x<ADDR>` |
| 键控 id | `trace_id="xxx"` / `requestId: xxx` | `<ID>` |

**优点**: 零配置、能抓到"每次返回完全一样"的循环。
**局限**: 抓不到"每次返回不同文本但语义是同类错误"的循环。

### 6.2 Layer 2：工具自定义签名

**适用于需要语义归类的工具**。用装饰器注册：

```python
from oxygent.utils.loop_signatures import register_signature

@register_signature("search_api")
def _search_signature(result, args):
    if "403" in result or "Permission denied" in result:
        return "permanent_block:auth"   # 阈值 2，快速拦截
    if "500" in result or "Internal Error" in result:
        return "biz_fail"                # 阈值 3，允许重试
    if "no results" in result.lower():
        return "empty"                   # 阈值 3
    return "ok"                          # 良性，不触发检测
```

**优先级**: Detector 优先用 Layer 2；函数抛异常或返回空值时降级到 Layer 1。

### 6.3 内置阈值与良性签名

**阈值表**（连续 N 次相同签名触发）:

| 签名前缀 | 阈值 | 语义 |
|---------|-----|------|
| `auth_err` | 2 | 鉴权失败，快速拦截 |
| `permanent_block` | 2 | 永久阻断（网络/策略）|
| `client_error` | 3 | 请求构造错，LLM 可自救 |
| `biz_fail` | 3 | 业务软失败，允许重试 |
| `no_progress` | 2 | 探索无进展 |
| `empty` | 3 | 查无结果 |
| `denied` | 3 | 拒绝 |
| （默认） | 3 | 其他签名 |

**良性签名**（永不触发 `repeat_by_output`）: `ok`, `progress`
- 执行成功 / 有新进展的调用，连续出现是正常的

---

## 7. 使用方式

### 7.1 最简用法

```python
from oxygent import oxy

agent = oxy.ReActAgent(
    name="my_agent",
    llm_model="my_llm",
    tools=["search"],
    loop_detection_mode="block",   # ← 加这一行即可
)
```

### 7.2 自定义 fallback 消息

```python
agent = oxy.ReActAgent(
    name="my_agent",
    llm_model="my_llm",
    tools=["search"],
    loop_detection_mode="block",
    loop_fallback_message=(
        "抱歉，我在尝试回答这个问题时陷入了循环。"
        "请换一种描述方式，或拆分成更具体的子问题。"
    ),
)
```

### 7.3 warn 模式（允许 LLM 自救）

```python
agent = oxy.ReActAgent(
    name="my_agent",
    llm_model="my_llm",
    tools=["search"],
    loop_detection_mode="warn",
    max_react_rounds=16,  # warn 模式下继续跑，建议配合 max_react_rounds 兜底
)
```

### 7.4 为工具注册语义签名

```python
# tools/my_api.py
from oxygent.utils.loop_signatures import register_signature

def my_api_tool(url: str) -> str:
    # ... 实际逻辑 ...
    return response_text

@register_signature("my_api_tool")
def _my_api_signature(result, args):
    if "permission" in result.lower():
        return "permanent_block:auth"
    if "timeout" in result.lower():
        return "client_error"
    return "ok"
```

**然后在 agent 中正常使用即可**，检测器会自动调用注册的签名函数。

### 7.5 监控 / 告警集成

```python
# 在 block 模式下，响应里会带诊断信息
resp = await mas.chat_with_agent(payload={"query": "..."})
loop_info = resp.extra.get("loop_detected")
if loop_info:
    # 发送到监控系统
    send_metric("agent.loop_detected", tags={
        "type": loop_info["type"],
        "tool_name": loop_info["tool_name"],
    })
```

---

## 8. 工作原理

### 8.1 整体流程

```
┌─ ReActAgent._execute() 每轮 ─────────────────────────────────────┐
│                                                                   │
│  1. LLM.call(messages=[...])                                      │
│  2. parse_llm_response() → {tool_name, arguments}                 │
│  3. await oxy_request.call(tool_name, arguments)                  │
│  4. react_memory.add_message(...)  ← 结果写入 memory              │
│                                                                   │
│  5. ┌─ 本次新增 ─────────────────────────────────────────┐       │
│     │ if loop_detection_mode != "disabled":              │       │
│     │     loop_info = detect_loop(                       │       │
│     │         shared_data=oxy_request.shared_data,       │       │
│     │         tool_calls=本轮 tool_calls,                 │       │
│     │         tool_results=本轮 tool_results,             │       │
│     │         current_round=i,                           │       │
│     │     )                                              │       │
│     │     if loop_info:                                  │       │
│     │         logger.warning(...)                        │       │
│     │         if mode == "block":                        │       │
│     │             return fallback_response               │       │
│     │         else:  # warn                              │       │
│     │             inject_system_hint(react_memory)        │       │
│     └────────────────────────────────────────────────────┘       │
│                                                                   │
│  6. 继续下一轮                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### 8.2 detect_loop 内部

```
detect_loop(shared_data, tool_calls, tool_results, current_round)
    │
    ├─ 如果已经检测到循环 → 直接返回（幂等）
    │
    ├─ 把本轮 tool_call → trace entry：
    │    - fingerprint = MD5(tool_name + sorted(arguments))[:12]
    │    - output_sig = compute_signature(tool_name, result, args)
    │    - is_error = 关键字匹配 OR 签名前缀归为 error
    │
    ├─ trace 缓冲区上限 6（够抓周期 3 的 cycle）
    │
    ├─ 按优先级跑 4 个检测器（命中即停）:
    │    1. _detect_error_retry   （2 步窗口，最快）
    │    2. _detect_repeat         （3 步窗口）
    │    3. _detect_repeat_by_output
    │    4. _detect_cycle          （4-6 步窗口）
    │
    └─ 命中 → 写 shared_data["_loop_detected"] = {...}
```

### 8.3 为什么把 trace 存在 shared_data

`OxyRequest.shared_data` 是 OxyGent 原生就有的"请求级共享字典"（oxy.py:161），生命周期与请求一致，天然满足：
- 跨轮次保留（同一个请求内所有 react 轮共享）
- 跨 agent 隔离（不同请求不互相污染）
- 请求结束自动回收（不泄漏）

无需引入新的状态管理机制。

### 8.4 为什么用指纹而不是直接存参数

- 存指纹：固定 12 字节，长 trace 也只占 ~100 字节
- 存参数原文：参数可能是大 JSON，长 trace 会撑爆上下文
- 指纹是 MD5 的前 12 位，碰撞概率可忽略

---

## 9. 与现有系统的关系

### 9.1 继承链

```
ReActAgent（本次改动）
  ├── SkillAgent    — 继承，自动获得循环检测能力
  └── RagAgent      — 继承，自动获得循环检测能力
```

**改一处，三处生效**。

### 9.2 与 max_react_rounds 的关系

- `max_react_rounds` 是**硬上限**（防止无限循环的最后防线）
- 循环检测是**早停机制**（在上限之前主动识别无效循环）
- 两者**互补**：有检测的情况下，max_react_rounds 可以配置更大的值，给合理推理更多空间

### 9.3 与 trust_mode 的关系

`trust_mode=True` 时第一次工具返回就直接返回，根本不会多轮调用 → 循环检测不会触发，无冲突。

### 9.4 与现有日志 / trace 系统的关系

- 日志按 OxyGent 现有习惯打到 `logger.warning`，带 `trace_id` / `node_id` extra 字段
- 循环信息写入 `shared_data["_loop_detected"]`，可被下游 agent 消费
- `block` 模式的 `OxyResponse.extra` 带 `loop_detected` 结构，上游可用于告警

---

## 10. 扩展与定制

### 10.1 调整检测阈值

当前阈值在 `oxygent/utils/loop_signatures.py:_SIGNATURE_THRESHOLDS` 字典里，直接改即可：

```python
_SIGNATURE_THRESHOLDS: dict[str, int] = {
    "auth_err": 2,         # 想更严格 → 改 1
    "permanent_block": 2,
    "client_error": 3,     # 想更宽松 → 改 5
    ...
}
```

### 10.2 添加新的检测模式

在 `loop_detector.py` 新增 `_detect_xxx` 函数，然后加入 `detect_loop` 的优先级链：

```python
detected = (
    _detect_error_retry(trace)
    or _detect_repeat(trace)
    or _detect_repeat_by_output(trace)
    or _detect_cycle(trace)
    or _detect_xxx(trace)   # ← 新增
)
```

### 10.3 自定义 fallback 行为

目前 `block` 模式返回固定消息。如需转交给其他 agent，可在 `_execute()` 的循环处理块里扩展：

```python
if self.loop_detection_mode == "block":
    # 示例：转交给 chat_agent 做兜底
    fallback_resp = await oxy_request.call(
        callee="chat_agent",
        arguments={"query": f"用户问题陷入循环，原问题：{oxy_request.get_query()}"},
    )
    return OxyResponse(state=OxyState.COMPLETED, output=fallback_resp.output, ...)
```

### 10.4 为特定工具豁免检测

参考 superassistant 的做法，在 `loop_detector.py` 加白名单：

```python
_EXEMPT_TOOLS = {
    "mode_switch",       # 模式切换类工具，天然可能多次调用
    "set_variable",      # 状态设置类
}
```

然后在 `detect_loop` 遍历时跳过：

```python
if tool_name in _EXEMPT_TOOLS:
    continue
```

（本次开源版未加这个白名单，保持通用；需要可在业务层扩展）

---

## 11. 设计取舍

### 11.1 为什么默认 disabled

**最小惊讶原则**：开源框架升级不应改变默认行为。用户主动启用意味着他认同"宁可拒绝也不要死循环"的权衡。

### 11.2 为什么 trace 上限 6

- 周期 3 的 cycle 检测需要 6 步窗口（`period * 2`）
- 更长的窗口对检测精度收益递减，但内存占用线性增加
- 实测 6 够抓绝大多数生产场景

### 11.3 为什么 block 返回固定文本而不是让 LLM 总结

**可预测性**：
- 固定文本：用户/上游系统能准确判断"这是循环中断"，不需解析 LLM 自由文本
- LLM 总结：又调一次 LLM，又多等 1-3 秒，而且可能产出低质量内容

需要 LLM 总结的，可通过 `warn` 模式让 LLM 自救，或业务层接 `extra.loop_detected` 转交。

### 11.4 为什么签名机制分两层

- Layer 1 零配置通用兜底 → **80% 场景够用**
- Layer 2 工具级精细控制 → **解决 Layer 1 抓不到的换皮循环**
- 两层互不耦合，用户按需启用

### 11.5 为什么不是中间件 / Hook

OxyGent 当前 `ReActAgent._execute()` 没有标准 Hook 机制。本次移植选择最小改动路径 —— 直接在 `_execute()` 内加检测点，而非引入全新的 Hook 架构。如果后续 OxyGent 要抽象 Hook，可以把这块逻辑迁过去。

---

## 12. FAQ

**Q1: 开启检测会不会误伤正常重试？**
A: 几乎不会。
- `repeat` 阈值 3，允许"查无 → 换参 → 查无 → 换参 → 查有"的正常流程
- `error_retry` 要求上一步显式报错，正常重试会先调整参数
- 真正担心的话用 `warn` 模式，LLM 可继续执行

**Q2: 签名函数抛异常会怎样？**
A: 自动降级到 Layer 1 hash，不影响主循环。参见 `test_classifier_exception_falls_back_to_hash` 测试。

**Q3: shared_data 的 trace 会不会被持久化到 ES？**
A: `shared_data` 是请求级内存字典，请求结束即释放，不入库。

**Q4: 如何在生产环境打开，但只收集数据不中断？**
A: 用 `warn` 模式 + 监控消费 `shared_data["_loop_detection_trace"]`，拿到循环分布后再决定要不要切 `block`。

**Q5: 自定义签名怎么测试？**
A: 签名函数是纯函数，可独立单测，不需要拉起 agent。参考 `tests/unittest/test_loop_detector.py:test_classifier_exception_falls_back_to_hash`。

**Q6: 支持异步工具吗？**
A: 支持。检测器只看 tool_call 和 tool_result，与工具是同步/异步无关。

**Q7: 和 `max_react_rounds` 冲突吗？**
A: 不冲突，互补。`max_react_rounds` 是硬上限，检测器是早停。启用检测后可适当调大 `max_react_rounds`。

**Q8: 新工具一定要注册签名吗？**
A: 不是。默认 Layer 1 hash 足够抓"同参 / 同输出"的循环；只有需要抓"换参但同类错"的循环时才需要注册。

---

## 附录 A：关键文件索引

| 文件 | 行数 | 职责 |
|------|-----|------|
| `oxygent/utils/loop_detector.py` | 285 | 4 个检测器 + 提示构造 + 轨迹管理 |
| `oxygent/utils/loop_signatures.py` | 173 | Layer 1 hash + Layer 2 装饰器 + 阈值表 |
| `oxygent/oxy/agents/react_agent.py` | +47 | 2 个 Field + `_execute` 内调用点 |
| `tests/unittest/test_loop_detector.py` | 198 | 16 项单测 |
| `examples/agents/demo_loop_detection.py` | 78 | 端到端 Web demo |

## 附录 B：相关文档

- 测试报告：`docs/loop_detection_test_report.md`
- 参考实现：`/Users/yangyalong6/super-assistant/oxygent/utils/loop_detector.py`（内部项目，含业务耦合，本次开源版已裁剪）
