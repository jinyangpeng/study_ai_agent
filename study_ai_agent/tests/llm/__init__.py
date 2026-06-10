"""LLM provider 集成测试。

需要：
* 至少一家供应商的 API key（从 ``.env`` 自动加载）
* 联网

``conftest.py`` 把项目根加进了 ``sys.path``，所以 ``from src.providers import ...``
可以直接用。
"""
