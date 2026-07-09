import json, os, subprocess

REPO = 'soli0x4ea/digital-life-card'
BASE_SHA = '851e0d687df06028136ec5c668408980ab47db32'
ROOT = r'C:\ProgramData\WorkBuddy\chromium-env\6oiz7e\WorkBuddy\Claw\dlc-skill'

# Get base tree SHA
r = subprocess.run(['gh', 'api', f'repos/{REPO}/git/commits/{BASE_SHA}', '--jq', '.tree.sha'],
    capture_output=True, text=True, timeout=30)
base_tree = r.stdout.strip()
print(f'Base tree: {base_tree}')

# Collect all files
files = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in ('.git', '__pycache__', '.pytest_cache')]
    for fn in filenames:
        if fn.endswith('.pyc'):
            continue
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, ROOT).replace('\\', '/')
        with open(full, 'rb') as f:
            content = f.read()
        files.append((rel, content))

print(f'Files: {len(files)}')

# Build tree items (inline content)
tree_items = []
for path, content in files:
    tree_items.append({
        'path': path,
        'mode': '100644',
        'type': 'blob',
        'content': content.decode('utf-8', errors='replace'),
        'encoding': 'utf-8',
    })

# Create tree
payload = json.dumps({'base_tree': base_tree, 'tree': tree_items})
r = subprocess.run(['gh', 'api', f'repos/{REPO}/git/trees', '--input', '-', '-X', 'POST'],
    input=payload, capture_output=True, text=True, timeout=120)
result = json.loads(r.stdout)
tree_sha = result['sha']
truncated = result.get('truncated', False)
print(f'New tree: {tree_sha} (truncated={truncated})')

# Create commit
commit_msg = (
    'v0.4.0: 双核线性记忆 + 命令叙事管线\n\n'
    '核心变化:\n'
    '- 记忆系统重制: 三层结构化 -> 双核线性 (ChatlogStore + TimelineStore)\n'
    '- Narrator 升级: 四原子操作 + 命令叙事管线\n'
    '- 格式兼容: 命令/物品系统兼容 Soli 实战格式\n'
    '- Breaking: MemoryEngine -> ChatlogStore + TimelineStore\n\n'
    '测试: 315/315 零回归'
)
commit_payload = json.dumps({
    'message': commit_msg,
    'tree': tree_sha,
    'parents': [BASE_SHA],
})
r = subprocess.run(['gh', 'api', f'repos/{REPO}/git/commits', '--input', '-', '-X', 'POST'],
    input=commit_payload, capture_output=True, text=True, timeout=30)
result = json.loads(r.stdout)
commit_sha = result['sha']
print(f'Commit: {commit_sha}')

# Update ref
ref_payload = json.dumps({'sha': commit_sha, 'force': False})
r = subprocess.run(['gh', 'api', f'repos/{REPO}/git/refs/heads/main', '--input', '-', '-X', 'PATCH'],
    input=ref_payload, capture_output=True, text=True, timeout=30)
result = json.loads(r.stdout)
print(f'Ref: {result.get("ref")} -> {result["object"]["sha"]}')

# Create tag
tag_payload = json.dumps({
    'ref': 'refs/tags/v0.4.0',
    'sha': commit_sha,
})
r = subprocess.run(['gh', 'api', f'repos/{REPO}/git/refs', '--input', '-', '-X', 'POST'],
    input=tag_payload, capture_output=True, text=True, timeout=30)
print(f'Tag: {json.loads(r.stdout).get("ref")}')

print('DONE')
