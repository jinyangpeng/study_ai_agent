import pathlib
p = pathlib.Path("src/core/strategies/reflection.py")
s = p.read_text(encoding="utf-8")
old = (
    '            system_prompt=_resolve_prompt(\n'
    '                skill,\n'
    '                "reflection_critique_prompt",\n'
    '                DEFAULT_REFLECTION_CRITIQUE_PROMPT,\n'
    '            ),\n'
    '            response_format=Critique,\n'
    '            tools=[],\n'
    '        )'
)
new = (
    '            system_prompt=_resolve_prompt(\n'
    '                skill,\n'
    '                "reflection_critique_prompt",\n'
    '                DEFAULT_REFLECTION_CRITIQUE_PROMPT,\n'
    '            ),\n'
    '            response_format=Critique,\n'
    '            tools=[],\n'
    '            middleware=build_skill_middleware(skill),\n'
    '        )'
)
assert old in s, "block not found"
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("[ok] reflection critique_node patched")