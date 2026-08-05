import os
import hashlib

old_ver = '0.33.1'
new_ver = '0.33.2'

path = 'openwrt-agent/wrtmonitor-agent'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace(f'AGENT_VERSION="{old_ver}"', f'AGENT_VERSION="{new_ver}"')
with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

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
