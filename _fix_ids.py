"""
Fix MongoDB string ID issues across all frontend HTML/JS files.
After MongoDB migration, IDs are strings (ObjectIds like "679a3b...") 
not numbers. This script:
1. Quotes IDs in onclick handlers: addToCart(${id}) -> addToCart('${id}')
2. Fixes strict equality comparisons: === id -> === String(id)
"""
import os
import re

BASE = 'static'
fixed_files = []
issues_found = []

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        original = f.read()
    
    content = original
    file_issues = []
    
    # Pattern 1: Unquoted ${xxx.id} in onclick handlers
    # Match: onclick="someFunc(${expr.id})" and similar
    # But NOT already quoted: onclick="someFunc('${expr.id}')"
    
    # Fix onclick="...Func(${var.id})" -> onclick="...Func('${var.id}')"
    # This handles patterns like: addToCart(${book.id}), editBook(${book.id}), deleteBook(${book.id}), etc.
    
    def quote_id_in_onclick(match):
        full = match.group(0)
        # Don't fix if already quoted
        if "'" in full and "${" in full:
            before_dollar = full[:full.index("${")]
            if before_dollar.endswith("'"):
                return full
        return full
    
    # More targeted approach: find specific patterns and fix them
    
    # Pattern: onclick="funcName(${expr.id})" -> onclick="funcName('${expr.id}')"
    # Handles both simple and complex cases
    patterns = [
        # Simple: func(${x.id}) -> func('${x.id}')
        (r'''onclick="([^"]*?)\(\$\{(\w+)\.id\}\)''',
         lambda m: f'''onclick="{m.group(1)}('${{{m.group(2)}.id}}')"''' if "'" not in m.group(0).split("${")[0][-1:] else m.group(0)),
        
        # With additional params: func(${x.id}, other) -> func('${x.id}', other)
        (r'''onclick="([^"]*?)\(\$\{(\w+)\.id\},\s*''',
         lambda m: f'''onclick="{m.group(1)}('${{{m.group(2)}.id}}', '''),
    ]
    
    # Let's do more surgical replacements
    # These are the exact patterns found in the grep
    
    replacements = [
        # Store index.html & catalog.html - addToCart
        (r"onclick=\"addToCart\(\$\{book\.id\}\)\"", 
         "onclick=\"addToCart('${book.id}')\""),
        
        # Store product.html - submitReview
        (r"onclick=\"submitReview\(\$\{book\.id\}\)\"",
         "onclick=\"submitReview('${book.id}')\""),
        
        # Cart updateQty (unquoted)
        (r"onclick=\"updateQty\(\$\{item\.id\}, (-?\d+)\)\"",
         lambda m: f"onclick=\"updateQty('${{item.id}}', {m.group(1)})\""),
        
        # Admin inventory - editBook/deleteBook
        (r"onclick=\"editBook\(\$\{book\.id\}\)\"",
         "onclick=\"editBook('${book.id}')\""),
        (r"onclick=\"deleteBook\(\$\{book\.id\}\)\"",
         "onclick=\"deleteBook('${book.id}')\""),
        
        # Admin orders - viewOrder
        (r"onclick=\"viewOrder\(\$\{order\.id\}(, event)?\)\"",
         lambda m: f"onclick=\"viewOrder('${{order.id}}'{', event' if m.group(1) else ''})\""),
        
        # Admin sales - viewDetails
        (r"onclick=\"viewDetails\(\$\{s\.id\}\)\"",
         "onclick=\"viewDetails('${s.id}')\""),
        
        # Admin settings - deleteCoupon
        (r"onclick=\"deleteCoupon\(\$\{c\.id\}\)\"",
         "onclick=\"deleteCoupon('${c.id}')\""),
        
        # Admin settings - togglePromo (two unquoted IDs)
        (r"onclick=\"togglePromo\(\$\{p\.id\}, \$\{p\.is_active\}\)\"",
         "onclick=\"togglePromo('${p.id}', ${p.is_active})\""),
        
        # Admin staff - deleteUser
        (r"onclick=\"deleteUser\(\$\{u\.id\}\)\"",
         "onclick=\"deleteUser('${u.id}')\""),
        
        # Shipping - openStatusModal
        (r"onclick=\"openStatusModal\(\$\{order\.id\},",
         "onclick=\"openStatusModal('${order.id}',"),
        
        # Shipping - viewOrder
        (r"onclick=\"viewOrder\(\$\{order\.id\}\)\"",
         "onclick=\"viewOrder('${order.id}')\""),
        
        # Inventory manage - editBook/deleteBook  
        # (same pattern as admin, already covered above)
        
        # Fix .find(x => x.id === someId) comparisons
        # These need String() wrapping for safe comparison
        (r"\.find\((\w+) => \1\.id === (\w+)\.id\)",
         lambda m: f".find({m.group(1)} => String({m.group(1)}.id) === String({m.group(2)}.id))"),
        
        (r"\.find\((\w+) => \1\.id === (\w+)\)",
         lambda m: f".find({m.group(1)} => String({m.group(1)}.id) === String({m.group(2)}))"),
        
        (r"\.filter\((\w+) => \1\.id !== (\w+)\)",
         lambda m: f".filter({m.group(1)} => String({m.group(1)}.id) !== String({m.group(2)}))"),
        
        (r"\.filter\((\w+) => \1\.id === (\w+)\)",
         lambda m: f".filter({m.group(1)} => String({m.group(1)}.id) === String({m.group(2)}))"),
    ]
    
    for pattern, replacement in replacements:
        if callable(replacement):
            new_content = re.sub(pattern, replacement, content)
        else:
            new_content = re.sub(pattern, replacement, content)
        
        if new_content != content:
            count = len(re.findall(pattern, content))
            file_issues.append(f"  Fixed {count}x: {pattern[:60]}")
            content = new_content
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        fixed_files.append(filepath)
        issues_found.extend([f"\n{filepath}:"] + file_issues)
        return True
    return False

# Walk all HTML files
for root, dirs, files in os.walk(BASE):
    for fname in files:
        if fname.endswith('.html'):
            filepath = os.path.join(root, fname)
            fix_file(filepath)

print("=" * 60)
print(f"FILES FIXED: {len(fixed_files)}")
print("=" * 60)
for issue in issues_found:
    print(issue)

if not fixed_files:
    print("No issues found!")
