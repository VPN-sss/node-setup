"""Read-only inspection. No panel requests, configuration dumps or repairs."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import corectl as core


def inspect_pin():
    override=core.ROOT/'docker-compose.override.yml'
    if not override.exists():
        return {}, 'unmanaged'
    if override.is_symlink():
        return {}, 'unknown'
    raw=override.read_text()
    core.managed_override(raw)
    src=Path(json.loads(raw)['services']['remnanode']['volumes'][0]['source'])
    state=core.state_path(src.parent)
    if src != state/'xray' or src.is_symlink():
        return {}, 'unknown'
    m=json.loads((state/'manifest.json').read_text())
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+){2}',m['version']) or m['unit']!='ham-xray-return-'+state.name:
        return {}, 'unknown'
    fields={'version':m['version']}
    container=json.loads(core.run(['docker','inspect','remnanode']))[0]
    fields['compose']=core.sha(override)==m['override_sha'] and core.sha(core.ROOT/'docker-compose.yml')==m.get('pinned_base_sha',m['compose_sha'])
    if 'fragment_sha' in m:fields['compose'] &= core.sha(state/'core-pin.json')==m['fragment_sha']
    fields['mount']=any(v.get('Type')=='bind' and v.get('Destination')=='/usr/local/bin/xray' and
                        v.get('Source')==str(src) and v.get('RW') is False for v in container['Mounts'])
    # A base-only updater may legitimately change the agent image, independently of Xray.
    fields['image']=container['Image']==m['image']
    fields['file']=core.sha(src)==m['binary_sha']
    if not all(fields[k] for k in ('compose','mount','file')) or (not fields['image'] and 'fragment_sha' not in m):
        return fields,'drift'
    if not container['State']['Running']:
        return fields,'stopped'
    rows=core.run(['docker','top','remnanode','-eo','pid,comm']).decode().splitlines()[1:]
    matches=[r.split()[0] for r in rows if len(r.split())==2 and r.split()[1] in ('rw-core','xray')]
    if len(matches)!=1 or not matches[0].isdigit():
        return fields,'unverified'
    fields['process']=core.sha(Path('/proc')/matches[0]/'exe')==m['binary_sha']
    if not fields['process'] or not fields['image']:return fields,'drift'
    if m.get('pin_mode')=='immediate':
        return fields,'pinned' if 'pinned_base_sha' in m and 'fragment_sha' in m else 'unverified'
    timer=subprocess.run(['systemctl','show','-p','ActiveState','--value',m['unit']+'.timer'],
                         capture_output=True,text=True,timeout=8)
    if timer.returncode or timer.stdout.strip() not in ('active','inactive'):return fields,'unknown'
    return fields,'temporary' if timer.stdout.strip()=='active' else 'matched'


def main():
    ru=os.getenv('HAM_LANG','ru')=='ru'
    messages={
        'pinned':('Работающее ядро проверено и закреплено.','Running core verified and pinned.'),
        'matched':('Работающее ядро совпадает; таймер возврата не активен.','Running core matches; return timer inactive.'),
        'temporary':('Ядро совпадает, но таймер возврата ещё активен.','Core matches, but the return timer is still active.'),
        'drift':('Конфигурация или ядро отличается от сохранённого.','Configuration or core differs from the recorded state.'),
        'unmanaged':('Нет файла фиксации HAM. Версия не подтверждена.','No HAM override found. Version not verified.'),
        'stopped':('Контейнер остановлен.','Container stopped.'),
        'unverified':('Не удалось однозначно определить процесс Xray.','Cannot identify a single running Xray process.'),
        'unknown':('Недостаточно данных для проверки. Проверьте Docker, systemd и права.','Insufficient evidence. Check Docker, systemd and permissions.')}
    try: fields,status=inspect_pin()
    except (OSError,ValueError,KeyError,TypeError,IndexError,AttributeError,RuntimeError,subprocess.SubprocessError):
        fields,status={},'unknown'
    for key,value in fields.items():
        print(f'  {key:8}  {("OK" if value else "DIFF") if isinstance(value,bool) else value}')
    print(messages[status][0 if ru else 1])
    return 0 if status in ('matched','pinned') else 2


if __name__=='__main__':sys.exit(main())
