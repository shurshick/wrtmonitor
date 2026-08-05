import os

changelog_entry = '''## v0.33.2

- Исправлено ложное срабатывание Google Safe Browsing / антифишингового сканера Chrome, возникавшее при переходе неавторизованного пользователя напрямую по ссылке роутера (\/devices/{uuid}\). Теперь используется стандартный механизм редиректа \?next=\, который распознаётся браузерами как безопасный поток аутентификации.
- Перенаправление после успешного входа всегда ведёт на список устройств, кроме случаев, когда используется \?next=\.

'''

rn_entry = '''# v0.33.2

Патч-релиз, устраняющий предупреждение «Опасный сайт» (Google Safe Browsing / Phishing Protection) в браузере Chrome при переходе по прямой ссылке устройства.

## Изменения
- При переходе на \/devices/{uuid}\ без активной сессии сервер корректно перенаправляет на \/login?next=...\, что предотвращает срабатывание локальных антифишинговых эвристик браузера.
- Восстановлено поведение редиректа после логина по умолчанию: пользователь перенаправляется на список роутеров.

'''

def prepend(path, text):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if path == 'CHANGELOG.md':
        lines = content.split('\n')
        # Insert after # Changelog
        for i, line in enumerate(lines):
            if line.startswith('## '):
                lines.insert(i, text.strip() + '\n')
                break
        else:
            lines = [text] + lines
        content = '\n'.join(lines)
    elif path == 'RELEASE_NOTES.md':
        content = text + content
        
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Updated {path}')

prepend('CHANGELOG.md', changelog_entry)
prepend('RELEASE_NOTES.md', rn_entry)
