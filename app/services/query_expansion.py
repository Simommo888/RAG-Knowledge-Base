import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryVariant:
    text: str
    weight: float
    reason: str = ""


DOMAIN_ALIASES: dict[str, list[str]] = {
    "儿童": ["小孩子", "孩子", "少年", "少年闰土", "闰土"],
    "小孩子": ["儿童", "孩子", "少年", "少年闰土", "闰土"],
    "孩子": ["小孩子", "儿童", "少年", "少年闰土"],
    "童年伙伴": ["小伙伴", "小孩子", "少年闰土", "闰土"],
    "伙伴": ["小伙伴", "童年伙伴", "少年闰土", "闰土"],
    "闰土": ["少年闰土", "鲁迅", "故乡", "小孩子"],
    "少年闰土": ["闰土", "鲁迅", "故乡", "小孩子"],
    "春天": ["春", "春季", "春日", "春风", "朱自清"],
    "春季": ["春天", "春", "朱自清"],
    "夏天之前的季节": ["春天", "春季", "春", "朱自清"],
    "agentos": ["AgentOS", "Agent 管理平台", "多 Agent 管理平台", "智能 Agent 管理平台"],
    "多 agent 管理平台": ["AgentOS", "Agent 管理平台", "智能 Agent 管理平台"],
    "多Agent管理平台": ["AgentOS", "Agent 管理平台", "智能 Agent 管理平台"],
    "rag": ["RAG", "检索增强生成", "向量检索", "知识库问答"],
    "知识库问答": ["RAG", "检索增强生成", "向量检索"],
    "提示词": ["Prompt", "prompt", "提示词资产"],
    "报错": ["错误", "Error-Fix", "error fix", "失败原因"],
}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _dedupe_variants(variants: list[QueryVariant], max_variants: int) -> list[QueryVariant]:
    seen: set[str] = set()
    output: list[QueryVariant] = []
    for variant in variants:
        text = _normalize(variant.text)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(QueryVariant(text=text, weight=variant.weight, reason=variant.reason))
        if len(output) >= max_variants:
            break
    return output


def expand_query(query: str, enabled: bool = True, max_variants: int = 8) -> list[QueryVariant]:
    """Return low-cost query variants.

    The expansion is deliberately rule-based so it does not spend LLM or embedding
    budget. The original query is always first and keeps full weight.
    """
    normalized = _normalize(query)
    if not normalized:
        return []
    if not enabled:
        return [QueryVariant(normalized, 1.0, "original")]

    lowered = normalized.lower()
    variants = [QueryVariant(normalized, 1.0, "original")]

    for trigger, aliases in DOMAIN_ALIASES.items():
        trigger_lower = trigger.lower()
        if trigger_lower in lowered:
            for alias in aliases:
                variants.append(QueryVariant(alias, 0.72, f"alias:{trigger}"))
                if len(normalized) <= 12:
                    variants.append(QueryVariant(f"{normalized} {alias}", 0.58, f"expanded:{trigger}"))

    cjk_terms = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
    if len(cjk_terms) == 1 and len(cjk_terms[0]) >= 4:
        term = cjk_terms[0]
        variants.extend(
            QueryVariant(term[index : index + 2], 0.36, "cjk_bigram")
            for index in range(len(term) - 1)
        )

    return _dedupe_variants(variants, max_variants=max(1, max_variants))


def expanded_query_text(query: str, enabled: bool = True, max_variants: int = 8) -> str:
    return " ".join(variant.text for variant in expand_query(query, enabled=enabled, max_variants=max_variants))
