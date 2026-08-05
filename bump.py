import os

files = [
    'README.md',
    'RELEASE_TAG',
    'VERSION',
    'deploy/truenas/wrtmonitor-truenas.yaml',
    'openwrt-agent/agent-version.txt',
    'openwrt-agent/wrtmonitor-agent'
]

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    content = content.replace('0.33.0', '0.33.1')
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

print('Bumped 0.33.1')
