"""Verify each strategy node creates an agent with PII middleware attached."""
import sys
sys.path.insert(0, ".")
from langchain_core.messages import HumanMessage
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from unittest.mock import patch

# 拦截 create_agent 看是否传 middleware
captured = []
import langchain.agents as la
orig = la.create_agent
def spy(**kwargs):
    captured.append((kwargs.get("middleware"), kwargs.get("system_prompt", "")[:30] if kwargs.get("system_prompt") else "?"))
    return orig(**{k:v for k,v in kwargs.items() if k != "middleware"})

la.create_agent = spy
import src.core.strategies.p_e_r_a as p1
import src.core.strategies.reflection as p2
p1.la = la
p2.la = la

from src.skills import SKILL_REGISTRY
skill = SKILL_REGISTRY["research"]
fake = FakeListChatModel(responses=["ok"] * 100)

# 触发各 _make_*_node 静态方法
captured.clear()
p1.PerAStrategy._make_plan_node(skill, fake)
p1.PerAStrategy._make_execute_node(skill, fake)
p1.PerAStrategy._make_review_node(skill, fake)
print("p_e_r_a:")
for mw, sp in captured:
    n = len(mw) if mw else 0
    pii_n = sum(1 for m in mw if type(m).__name__ == "PIIMiddleware")
    print(f"  middleware count={n}  PIIMiddleware={pii_n}  system_prompt={sp!r}")

captured.clear()
p2.ReflectionStrategy._make_generate_node(skill, fake)
p2.ReflectionStrategy._make_critique_node(skill, fake)
p2.ReflectionStrategy._make_refine_node(skill, fake)
print("reflection:")
for mw, sp in captured:
    n = len(mw) if mw else 0
    pii_n = sum(1 for m in mw if type(m).__name__ == "PIIMiddleware")
    print(f"  middleware count={n}  PIIMiddleware={pii_n}  system_prompt={sp!r}")