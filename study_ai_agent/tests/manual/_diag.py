import sys
sys.path.insert(0, '.')
from src.core.middleware import BASE_MIDDLEWARES, SECURITY_MIDDLEWARES
print('SECURITY count:', len(SECURITY_MIDDLEWARES))
for m in SECURITY_MIDDLEWARES:
    t = getattr(m, 'pii_type', '?')
    s = getattr(m, 'strategy', '?')
    a = getattr(m, 'apply_to_input', '?')
    print(f'  - pii_type={t} strategy={s} apply_to_input={a}')
print()
print('BASE total:', len(BASE_MIDDLEWARES))
print('types:', [type(m).__name__ for m in BASE_MIDDLEWARES])
