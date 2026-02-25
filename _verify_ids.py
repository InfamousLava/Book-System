"""Verify all HTML files have properly quoted MongoDB IDs"""
import os, re

files = [
    'static/store/index.html',
    'static/store/catalog.html', 
    'static/store/product.html',
    'static/store/checkout.html',
    'static/admin/inventory.html',
    'static/admin/orders.html',
    'static/admin/sales.html',
    'static/admin/settings.html',
    'static/admin/staff.html',
    'static/admin/dashboard.html',
    'static/shipping/dashboard.html',
    'static/inventory/manage.html',
    'static/customer/login.html',
    'static/customer/register.html',
    'static/customer/dashboard.html',
    'static/cashier/pos.html',
]

print('=== CHECKING FOR UNQUOTED IDs (BROKEN) ===')
broken = 0
for f in files:
    if not os.path.exists(f):
        continue
    with open(f, 'r', encoding='utf-8') as fh:
        lines = fh.readlines()
    for i, line in enumerate(lines, 1):
        # Find onclick with unquoted ${...id}
        # Pattern: onclick="func(${expr.id})" but NOT onclick="func('${expr.id}')"
        matches = re.findall(r"onclick=\"[^\"]*?\((\$\{[^}]+\.id\})[,\)]", line)
        for m in matches:
            # Check if it's already quoted
            idx = line.index(m)
            before = line[idx-1] if idx > 0 else ''
            if before != "'":
                print(f'  BROKEN {f}:{i} -> {m}')
                broken += 1

print(f'\nTotal BROKEN: {broken}')

print('\n=== CHECKING FOR STRICT === WITHOUT String() ===')
strict_issues = 0
for f in files:
    if not os.path.exists(f):
        continue
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    # Find x.id === y patterns (should use String())
    matches = re.findall(r'\.id === (\w+)', content)
    for m in matches:
        if m not in ['true', 'false', 'null', 'undefined', 'String']:
            strict_issues += 1
            print(f'  ISSUE {f}: .id === {m}')

print(f'\nTotal STRICT issues: {strict_issues}')

print('\n=== CHECKING FOR .find/.filter WITH === ===')
find_issues = 0
for f in files:
    if not os.path.exists(f):
        continue
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    matches = re.findall(r'\.(find|filter)\([^)]*\.id === [^S][^)]*\)', content)
    for m in matches:
        find_issues += 1
        print(f'  ISSUE {f}: .{m[0]}() with bare ===')

print(f'\nTotal find/filter issues: {find_issues}')
print('\n=== SUMMARY ===')
total = broken + strict_issues + find_issues
if total == 0:
    print('ALL CLEAR - No MongoDB ID issues found!')
else:
    print(f'FOUND {total} issue(s) to fix')
