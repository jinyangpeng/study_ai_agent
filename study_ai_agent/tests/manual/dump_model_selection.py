"""当前模型选择状态一览"""
import os
import sys
from pathlib import Path

# 把项目根加进 sys.path（conftest.py 在 pytest 跑时会自动加，但裸跑脚本不会）
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from src.core.model_factory import model_factory
from src.core.config import agent_config

print("=" * 60)
print("当前模型选择状态")
print("=" * 60)

print()
print("【1】环境变量中的 key")
keys = ["QIANFAN_API_KEY", "ZAI_API_KEY", "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY"]
for k in keys:
    v = os.environ.get(k, "")
    label = ("set(len=" + str(len(v)) + ")") if v else "<empty>"
    status = "OK " if v else "   "
    print(f"  {status} {k:24s} = {label}")

print()
print("【2】agent_config 优先级和模型名")
for name in ["qianfan", "zhipuai", "deepseek", "qwen"]:
    cfg = getattr(agent_config, name, None)
    if cfg is None:
        print(f"  {name:10s} = <not configured>")
    else:
        print(f"  {name:10s} priority={cfg.priority}  model_name={cfg.model_name!r}")

print()
print("【3】strategy 配置")
print(f"  AGENT_STRATEGY env = {os.environ.get('AGENT_STRATEGY', '<not set>')!r}")
print(f"  config.strategy    = {agent_config.strategy!r}")

print()
print("【4】ModelFactory 实际可用供应商")
print(f"  _available_providers = {model_factory._available_providers}")

print()
print("【5】_select_provider() 选中谁")
selected = model_factory._select_provider()
print(f"  -> {selected!r}")

print()
print("【6】选中的供应商的具体 ModelConfig")
if selected:
    cfg = getattr(agent_config, selected, None)
    print(f"  priority   = {cfg.priority}")
    print(f"  model_name = {cfg.model_name!r}")

print()
print("【7】create_model() 实际返回的 chat model 详情")
model, name = model_factory.create_model()
print(f"  provider = {name}")
print(f"  model    = {model!r}")
print(f"  class    = {type(model).__module__}.{type(model).__name__}")
print(f"  streaming= {getattr(model, 'streaming', None)}")
print(f"  base_url = {getattr(model, 'base_url', None) or getattr(model, 'openai_api_base', None)}")
print(f"  model_name = {getattr(model, 'model_name', None)}")
