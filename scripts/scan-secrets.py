"""Scan tracked or staged text files without printing matched secret values."""
import re
import subprocess
from pathlib import Path

patterns = [
    re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'),
    re.compile(r'github_pat_[A-Za-z0-9_]{30,}'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'\b\d{8,12}:[A-Za-z0-9_-]{35}\b'),
    re.compile(r'AKIA[A-Z0-9]{16}'),
]
files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z']).decode().split('\0')
errors = []
for name in filter(None, files):
    path = Path(name)
    if path.name == '.env' or (path.name.startswith('.env.') and path.name != '.env.example'):
        errors.append(f'Environment file is tracked: {name}')
    if path.is_file():
        source = path.read_bytes().decode('utf-8', errors='ignore')
        if any(pattern.search(source) for pattern in patterns):
            errors.append(f'Potential secret: {name}')
if errors:
    raise SystemExit('\n'.join(errors))
print(f'Secret scan passed: {len(files)-1} files checked')
