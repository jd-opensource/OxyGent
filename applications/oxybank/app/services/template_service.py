from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import httpx

from app.storage.es_client import ESClient

logger = logging.getLogger("oxybank.template_service")


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------

# Templates are global: any bank can use any template. Historical data may still have
# per-bank bank_id values on template docs; treat that field as a tag, not a filter.
# Newly-created user templates are stored under bank_id="_global"; built-ins are under
# bank_id="_builtin". Nothing in the query path filters by bank_id anymore.
_GLOBAL_BANK_ID = "_global"
_BUILTIN_BANK_ID = "_builtin"


def create_template(
    es: ESClient,
    bank_id: str,
    data: dict,
    user: str,
) -> dict:
    """Create a global template. `bank_id` is accepted for API-compatibility with the
    URL scheme (`/banks/{bank}/templates`) but ignored — templates are not bank-scoped.
    Enforces global name uniqueness so sys_template can safely reference templates by name.
    """
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Template name is required")

    existing = _find_template_by_name(es, name)
    if existing is not None:
        raise ValueError(f"A template named '{name}' already exists")

    template_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "bank_id": _GLOBAL_BANK_ID,
        "name": name,
        "description": data.get("description", ""),
        "editable_fields": data.get("editable_fields", []),
        "field_constraints": data.get("field_constraints", {}),
        "layout": data.get("layout", {}),
        "created_by": user,
        "created_at": now,
        "updated_at": now,
    }

    es.index_doc("templates", doc, doc_id=template_id, refresh=True)
    doc["id"] = template_id
    return doc


def _find_template_by_name(es: ESClient, name: str) -> dict | None:
    """Look up a template by exact name across the global pool.
    Returns the first match if any (name uniqueness is enforced on create/update)."""
    result = es.search(
        "templates",
        query={"match_phrase": {"name": name}},
        size=5,
    )
    items = result.get("items", [])
    # Prefer non-orphan matches on the off chance duplicates snuck in historically.
    exact = [t for t in items if t.get("name") == name]
    return exact[0] if exact else (items[0] if items else None)


def list_templates(es: ESClient, bank_id: str) -> list[dict]:
    """List all templates. `bank_id` accepted for URL compatibility but ignored —
    every bank sees the same global template pool."""
    result = es.search(
        "templates",
        query=None,
        size=10000,
    )
    return result.get("items", [])


def get_template(es: ESClient, bank_id: str, template_id: str) -> dict | None:
    """Get a single template by ID or by name from the global pool.

    Resolution order:
    1) Direct doc lookup by ID (fast path).
    2) If not found, search by exact name.

    `bank_id` accepted for URL compatibility but ignored — templates are global.
    """
    # Fast path: ID lookup
    doc = es.get_doc("templates", template_id)
    if doc is not None:
        return doc

    # Fallback: name lookup
    return _find_template_by_name(es, template_id)


def update_template(es: ESClient, template_id: str, data: dict) -> dict | None:
    """Update a template. If the name is changing, enforce global uniqueness."""
    if "name" in data and data.get("name"):
        new_name = str(data["name"]).strip()
        current = es.get_doc("templates", template_id)
        if current and current.get("name") != new_name:
            existing = _find_template_by_name(es, new_name)
            if existing is not None and existing.get("id") != template_id:
                raise ValueError(f"A template named '{new_name}' already exists")
        data["name"] = new_name
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    es.update_doc("templates", template_id, data, refresh=True)
    return es.get_doc("templates", template_id)


def delete_template(es: ESClient, bank_id: str, template_id: str) -> bool:
    """Delete a template. Built-in templates cannot be deleted; user-created templates
    are global (any admin can remove them). `bank_id` is accepted for URL compatibility
    but not used for ownership checks."""
    doc = es.get_doc("templates", template_id)
    if doc is None:
        return False
    if doc.get("is_builtin") or doc.get("bank_id") == _BUILTIN_BANK_ID:
        raise ValueError("Built-in templates cannot be deleted")
    return es.delete_doc("templates", template_id, refresh=True)


# ---------------------------------------------------------------------------
# LLM Chat (SSE streaming)
# ---------------------------------------------------------------------------

TEMPLATE_SYSTEM_PROMPT = """你是一个标注模板设计助手。用户会描述他们需要什么样的标注模板，你需要生成一个标准格式的标注模板JSON。

模板JSON格式如下：
```json
{
  "name": "模板名称",
  "description": "模板描述",
  "editable_fields": ["field1", "field2"],
  "field_constraints": {
    "field1": {
      "type": "radio",
      "options": ["选项1", "选项2"],
      "required": true
    },
    "field2": {
      "type": "textarea",
      "placeholder": "请输入...",
      "show_when": {"field1": "选项2"}
    }
  },
  "layout": {
    "sections": [
      {"title": "数据内容", "fields": ["data_field1", "data_field2"], "readonly": true},
      {"title": "标注区域", "fields": ["field1", "field2"]}
    ]
  }
}
```

field_constraints支持的type:
- "radio": 单选按钮，需要options数组
- "select": 下拉选择，需要options数组
- "textarea": 多行文本框，可设置placeholder
- "text": 单行文本框（默认）

特殊字段:
- show_when: 条件显示，如 {"field1": "选项2"} 表示当field1的值为"选项2"时才显示该字段
- required: 标记必填

layout.sections中:
- readonly: true 的section里的字段只展示不可编辑
- 非readonly的section里的字段可编辑

以下是两个内置模板示例供参考（name 是模板的唯一标识，请为你生成的模板挑选一个简短、语义明确、全局唯一的英文/拼音字符串作为 name）：

示例1 - QA标注模板 (name: "builtin_qa"):
```json
{
  "name": "builtin_qa",
  "description": "Label whether the answer is satisfactory, and why not if it isn't",
  "editable_fields": ["is_satisfied", "reason"],
  "field_constraints": {
    "is_satisfied": {"type": "radio", "options": ["Satisfied", "Unsatisfied"], "required": true},
    "reason": {"type": "textarea", "placeholder": "Why is the answer unsatisfactory?", "show_when": {"is_satisfied": "Unsatisfied"}}
  },
  "layout": {
    "sections": [
      {"title": "QA Content", "fields": ["query", "answer"], "readonly": true},
      {"title": "Annotation", "fields": ["is_satisfied", "reason"]}
    ]
  }
}
```

示例2 - 业务域标注模板 (name: "builtin_business"):
```json
{
  "name": "builtin_business",
  "description": "Label the business domain the document belongs to",
  "editable_fields": ["business"],
  "field_constraints": {
    "business": {"type": "radio", "options": ["Home Appliances", "Consumer Electronics", "Apparel", "Food & Beverage", "Home & Building", "Maternity & Baby", "Beauty & Personal Care", "Health & Medical", "Sports & Outdoors", "Auto Accessories"], "required": true}
  },
  "layout": {
    "sections": [
      {"title": "Document Content", "fields": ["sys_chunk"], "readonly": true},
      {"title": "Business Domain", "fields": ["business"]}
    ]
  }
}
```

请务必用 ```json ``` 代码块包裹返回的JSON，方便系统解析。"""


async def llm_chat(
    config: Any,
    messages: list[dict],
    bank_schema: list[dict] | None = None,
    current_template: dict | None = None,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted chunks."""
    llm_cfg = config.llm
    url = llm_cfg.base_url.rstrip('/')
    if '/chat/completions' not in url:
        url += '/chat/completions'

    sys_messages = [{"role": "system", "content": TEMPLATE_SYSTEM_PROMPT}]
    if bank_schema:
        schema_desc = json.dumps(bank_schema, ensure_ascii=False)
        sys_messages.append({
            "role": "system",
            "content": (
                "当前 Bank 的 Schema 字段定义如下（这是用户实际拥有的字段列表）：\n"
                f"{schema_desc}\n\n"
                "字段 type 的含义与在模板中的用法参考：\n"
                "- text：长文本，通常是需要标注员阅读的原始内容 → 放在 readonly section 展示，不放进 editable_fields\n"
                "- string / keyword：短文本或类别值，可能是元数据（如来源、分类），也可能是待填写的标签 → 视用户描述决定放展示区还是标注区\n"
                "- integer / float：数值，通常是打分/评级字段 → 若是标注结果，用 select/radio 约束取值范围\n"
                "- sys_chunk：文档切分产生的文本块，等同于长 text，必须放 readonly 展示\n\n"
                "另外，样本里可能还带有 sys_ 开头的系统字段（sys_status/sys_executor/sys_create_time 等），"
                "这些是平台自动维护的元数据，不要放进 editable_fields 或 layout.sections，模板不关心它们。\n\n"
                "重要约束：\n"
                "1) layout.sections 里引用的字段、editable_fields、field_constraints 涉及的字段必须都来自上面 Schema 列表；\n"
                "2) 不要杜撰不存在的字段名；\n"
                "3) 如果标注结果需要一个新字段来存放，请在 editable_fields 里明确列出该字段名，并给出合理的字段约束。"
            ),
        })

    if current_template:
        # Give the AI the template the user is currently editing so follow-up messages
        # like "add a field for confidence" or "change the options" iterate on it
        # rather than generating a whole new template.
        tpl_desc = json.dumps(current_template, ensure_ascii=False, indent=2)
        sys_messages.append({
            "role": "system",
            "content": (
                "用户当前正在编辑的模板如下（这是本轮对话的起点）：\n"
                f"```json\n{tpl_desc}\n```\n\n"
                "接下来的用户消息通常是**在此模板基础上做修改**（比如新增/删除字段、调整选项、"
                "改变布局等）。请仅返回修改后的完整模板 JSON，保持未提及部分不变。"
                "如果用户明确说要从零重新做，才忽略这个起点。"
            ),
        })

    payload = {
        "model": llm_cfg.model,
        "messages": sys_messages + messages,
        "stream": True,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {llm_cfg.api_key}",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                if data_str.strip() == "[DONE]":
                    yield "data: [DONE]\n\n"
                    return
                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            chunk = json.dumps({"choices": [{"delta": {"content": content}}]})
                            yield f"data: {chunk}\n\n"
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


# ---------------------------------------------------------------------------
# Template test/apply
# ---------------------------------------------------------------------------

def test_template(template: dict, sample_data: dict) -> dict:
    """Apply a template to sample data and return the result.

    Validates that only editable_fields defined in the template are modified.

    Parameters
    ----------
    template : dict
        The template definition with editable_fields and field_constraints.
    sample_data : dict
        The sample data to apply the template to.

    Returns
    -------
    dict
        The resulting sample data with template applied (only editable fields
        may differ from input).
    """
    editable_fields: list[str] = template.get("editable_fields", [])
    field_constraints: dict = template.get("field_constraints", {})

    result = dict(sample_data)

    # Apply field constraints (defaults, formatting, etc.)
    for field_name in editable_fields:
        constraints = field_constraints.get(field_name, {})
        if not constraints:
            continue

        # Apply default value if field is empty
        default_value = constraints.get("default")
        if default_value is not None and not result.get(field_name):
            result[field_name] = default_value

        # Apply allowed values constraint (enum validation)
        allowed_values = constraints.get("allowed_values")
        if allowed_values and result.get(field_name):
            if result[field_name] not in allowed_values:
                # Reset to default or leave unchanged
                if default_value is not None:
                    result[field_name] = default_value

    # Validate: ensure non-editable fields are not modified
    for key in result:
        if key not in editable_fields and key in sample_data:
            result[key] = sample_data[key]

    return result
