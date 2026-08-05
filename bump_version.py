import os
import hashlib

old_ver = '0.33.1'
new_ver = '0.33.2'

def rep(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    content = content.replace(old_ver, new_ver)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Updated {path}')

rep('VERSION')
rep('RELEASE_TAG')
rep('openwrt-agent/agent-version.txt')
rep('README.md')
rep('deploy/truenas/wrtmonitor-truenas.yaml')

# Generate SHA256SUMS
os.chdir('openwrt-agent')
files_to_hash = [
    'install-openwrt.sh',
    'agent-version.txt',
    'wrtmonitor-agent',
    'lib/telemetry.sh',
    'lib/update.sh',
    'lib/utils.sh',
    'lib/wifi.sh',
    'openwrt-agent-files.txt',
    'update-rsa-public-key.pem'
]

hashes = []
for file in files_to_hash:
    if os.path.exists(file):
        with open(file, 'rb') as f:
            h = hashlib.sha256(f.read()).hexdigest()
        hashes.append(f"{h} *{file}")

with open('SHA256SUMS.txt', 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(hashes) + '\n')

print('Generated SHA256SUMS.txt')
