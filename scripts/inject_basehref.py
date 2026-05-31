import os, re, sys

BASE_TAG = '<base href="https://kylepounds.org/">'
HEAD_RE = re.compile(r'(<head[^>]*>)', re.IGNORECASE)
root = sys.argv[1]
patched = skipped = 0

for dirpath, dirs, files in os.walk(root):
    for fname in files:
        if not fname.lower().endswith(('.html', '.htm')):
            continue
        fpath = os.path.join(dirpath, fname)
        try:
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            skipped += 1; continue
        if 'base href' in content.lower():
            # Update existing base href to point to kylepounds.org
            content = re.sub(r'<base\s+href="[^"]*"[^>]*>', BASE_TAG, content, flags=re.IGNORECASE)
            with open(fpath, 'w', encoding='utf-8', errors='replace') as f:
                f.write(content)
            patched += 1
            continue
        new_content, n = HEAD_RE.subn(r'\1\n' + BASE_TAG, content, count=1)
        if n == 0:
            skipped += 1; continue
        with open(fpath, 'w', encoding='utf-8', errors='replace') as f:
            f.write(new_content)
        patched += 1

print(f'Base href injected: {patched}, skipped: {skipped}')
