"""验证 skill 拼错策略名时会在 import 时 fail-fast（不等到运行时）。"""
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.skills.base_skill import BaseSkill

# 1) 拼对的情况：import 时不抛
class GoodSkill(BaseSkill):
    id = "good"
    name = "拼对"
    description = "ok"
    strategy = "react"

print("[OK] GoodSkill imports without error")
print("   strategy =", GoodSkill().strategy)

# 2) 拼错：class 定义时就该抛
try:
    class BadSkill(BaseSkill):
        id = "bad"
        name = "拼错"
        description = "should fail"
        strategy = "reactt"  # 故意拼错

    print("[FAIL] should have raised ValueError at class definition")
    sys.exit(1)
except ValueError as e:
    print("[OK] fail-fast triggered at class definition:")
    print("   ", e)

# 3) 拼完全乱写的名字
try:
    class NonsenseSkill(BaseSkill):
        id = "nonsense"
        name = "乱写"
        description = "should fail"
        strategy = "tree-of-thoughts"  # 没注册的策略

    print("[FAIL] should have raised ValueError at class definition")
    sys.exit(1)
except ValueError as e:
    print("[OK] fail-fast triggered for unknown strategy:")
    print("   ", e)
