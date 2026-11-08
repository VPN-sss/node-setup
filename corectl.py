#!/usr/bin/env python3
"""Versioned Xray bind mount with private backups and independent rollback."""
import argparse
from datetime import datetime,timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile

VERIFIED='26.7.28'
VERIFIED_SHA='8195d909f1109b8f3d99eefe401a3c451d7bf4af71f24d3815420f77e5dd2a40'
ROOT=Path('/opt/remnanode')
MARKER='x-ham-xray-managed'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args,root=ROOT,data=None,timeout=45):
    result=subprocess.run(args,cwd=root,input=data,capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError('Command failed: '+args[0]+' (private configuration not printed)')
    return result.stdout


def godebug(value):
    return ','.join([p for p in value.split(',') if p and not p.startswith('multipathtcp=')]+['multipathtcp=0'])


def artifact(channel,machine=None):
    machine=machine or platform.machine()
    names={'x86_64':'Xray-linux-64.zip','amd64':'Xray-linux-64.zip','aarch64':'Xray-linux-arm64-v8a.zip','arm64':'Xray-linux-arm64-v8a.zip'}
    if machine not in names:raise ValueError('Unsupported architecture')
    name=names[machine]
    if channel=='verified' and machine in {'x86_64','amd64'}:
        return VERIFIED,'https://github.com/XTLS/Xray-core/releases/download/v'+VERIFIED+'/'+name,VERIFIED_SHA
    path='latest' if channel=='latest' else 'tags/v'+VERIFIED
    req=urllib.request.Request('https://api.github.com/repos/XTLS/Xray-core/releases/'+path,headers={'User-Agent':'HAM-node-setup'})
    with urllib.request.urlopen(req,timeout=30) as response:release=json.load(response)
    version=release['tag_name'].removeprefix('v')
    if not version or any(ch not in '0123456789.' for ch in version):raise ValueError('Unexpected upstream tag')
    selected=next(a for a in release['assets'] if a['name']==name)
    expected=selected.get('digest','')
    url='https://github.com/XTLS/Xray-core/releases/download/v'+version+'/'+name
    if selected['browser_download_url']!=url or not expected.startswith('sha256:') or len(expected)!=71:raise ValueError('Verified upstream SHA256 unavailable')
    return version,url,expected[7:]


def runtime():
    rows=run(['docker','top','remnanode','-eo','pid,comm']).decode().splitlines()[1:]
    for row in rows:
        pid,comm=row.split(None,1)
        if comm.strip() not in {'rw-core','xray'}:continue
        process=Path('/proc')/pid
        args=(process/'cmdline').read_bytes().decode().split('\0')
        if '-config' not in args:continue
        uri=args[args.index('-config')+1]
        if uri.startswith('@rwint-') or uri.startswith('http+unix://'):
            if uri.startswith('@rwint-'):
                address,path=uri.split(':',1);address='\0'+address[1:]
            else:
                end=uri.index('.sock')+5
                address=str(process/'root')+uri[len('http+unix://'):end];path=uri[end:]
            if not path.startswith('/internal/get-config?token='):raise ValueError('Unexpected config endpoint')
            sock=socket.socket(socket.AF_UNIX);sock.settimeout(15);sock.connect(address)
            client=http.client.HTTPConnection('localhost');client.sock=sock;client.request('GET',path)
            response=client.getresponse()
            if response.status!=200:raise RuntimeError('Private runtime unavailable')
            cfg=json.loads(response.read());client.close();return cfg,process
        if uri.startswith('/'):
            return json.loads((process/'root'/uri.lstrip('/')).read_text()),process
    raise RuntimeError('Running Xray configuration unavailable; no live update performed')


def managed_override(raw):
    if raw is None:return
    try:cfg=json.loads(raw)
    except ValueError:raise ValueError('Existing non-managed override: merge manually, do not overwrite')
    if cfg.get(MARKER) is not True:raise ValueError('Existing override belongs to another deployment')
    if set(cfg)!={MARKER,'services'} or set(cfg.get('services',{}))!={'remnanode'}:raise ValueError('Managed override contains additional settings; preserve it for manual merge')
    service=cfg['services']['remnanode']
    if set(service)!={'image','environment','volumes'} or set(service['environment'])!={'GODEBUG'}:raise ValueError('Managed override was extended; manual merge required')
    if len(service['volumes'])!=1 or service['volumes'][0].get('target')!='/usr/local/bin/xray':raise ValueError('Additional volume configuration must be preserved manually')


def state_path(value):
    state=Path(value).resolve()
    if state.parent!=ROOT/'.ham-xray' or not state.is_dir():raise ValueError('State path outside managed directory')
    return state


def check_core(state,image,version,fresh=False):
    base=['docker','run','--rm','--network','none','-e','GODEBUG=multipathtcp=0','--mount',f'type=bind,src={state},dst=/work,readonly','--entrypoint','/work/xray']
    output=run(base+[image,'version']).decode()
    if not output.startswith('Xray '+version+' '):raise ValueError('Downloaded binary version mismatch')
    try:cfg,_=runtime()
    except RuntimeError:
        if not fresh:raise
        cfg={'inbounds':[],'outbounds':[{'protocol':'freedom'}]}
    (state/'runtime.before.json').write_text(json.dumps(cfg))
    validation=json.loads(json.dumps(cfg));validation['log']={'loglevel':'none','access':'none','error':'none'}
    run(base[:2]+['-i']+base[2:]+[image,'run','-test','-config','stdin:'],data=json.dumps(validation).encode())


def prepare(channel,fresh=False):
    os.umask(0o077)
    if fresh:
        marker=ROOT/'.ham-fresh-install'
        if not marker.is_file() or marker.is_symlink() or time.time()-marker.stat().st_mtime>600:raise ValueError('Fresh mode requires a recent installer marker')
    override=ROOT/'docker-compose.override.yml'
    if override.is_symlink():raise ValueError('Refuse symlinked override')
    before=override.read_text() if override.exists() else None;managed_override(before)
    container=json.loads(run(['docker','inspect','remnanode']))[0]
    if container['Config'].get('Labels',{}).get('com.docker.compose.project.working_dir')!=str(ROOT):raise ValueError('Unexpected Compose project')
    files=container['Config']['Labels'].get('com.docker.compose.project.config_files','').split(',')
    allowed={str(ROOT/'docker-compose.yml'),str(override)}
    if not files or set(files)-allowed:raise ValueError('Additional Compose files require manual review')
    base=ROOT/'.ham-xray';base.mkdir(mode=0o700,exist_ok=True)
    state=base/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3));state.mkdir(mode=0o700)
    shutil.copy2(ROOT/'docker-compose.yml',state/'compose.before.yml')
    if before is not None:(state/'override.before.json').write_text(before)
    version,url,expected=artifact(channel)
    archive=state/'xray.zip'
    with urllib.request.urlopen(url,timeout=60) as source,archive.open('wb') as dest:shutil.copyfileobj(source,dest)
    if sha(archive)!=expected:raise ValueError('Archive SHA256 mismatch')
    with zipfile.ZipFile(archive) as zipped,zipped.open('xray') as source,(state/'xray').open('wb') as dest:shutil.copyfileobj(source,dest)
    (state/'xray').chmod(0o755)
    check_core(state,container['Image'],version,fresh=fresh)
    manifest={'version':version,'channel':channel,'image':container['Image'],'image_ref':container['Config']['Image'],'compose_sha':sha(ROOT/'docker-compose.yml'),'override_before':before,'binary_sha':sha(state/'xray'),'godebug':next((v.split('=',1)[1] for v in container['Config'].get('Env',[]) if v.startswith('GODEBUG=')),''),'unit':'ham-xray-return-'+state.name,'prepared_at':time.time()}
    manifest['fresh']=fresh
    (state/'manifest.json').write_text(json.dumps(manifest));shutil.copy2(__file__,state/'operation.py')
    print('PREPARED_STATE='+str(state));return state


def rollback(state):
    m=json.loads((state/'manifest.json').read_text());override=ROOT/'docker-compose.override.yml'
    if sha(ROOT/'docker-compose.yml')!=m['compose_sha']:raise ValueError('Base Compose changed; manual rollback needed')
    if override.is_symlink():raise ValueError('Override became a symlink')
    if override.exists() and sha(override)!=m.get('override_sha'):raise ValueError('External override change; refuse overwrite')
    if json.loads(run(['docker','image','inspect',m['image_ref']]))[0]['Id']!=m['image']:raise ValueError('Original image tag drifted')
    if m['override_before'] is None:
        if override.exists():override.unlink()
    else:override.write_text(m['override_before'])
    run(['docker','compose','up','-d','--no-deps','--no-build','--pull','never','remnanode'],timeout=100)
    print('ORIGINAL_CORE_RESTORED')
    subprocess.run(['systemctl','stop',m['unit']+'.timer'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


def apply(state):
    m=json.loads((state/'manifest.json').read_text());override=ROOT/'docker-compose.override.yml'
    if time.time()-m['prepared_at']>3600:raise ValueError('Prepare again: state older than one hour')
    before=override.read_text() if override.exists() else None
    if before!=m['override_before'] or sha(ROOT/'docker-compose.yml')!=m['compose_sha']:raise ValueError('Configuration changed since preparation')
    cfg={MARKER:True,'services':{'remnanode':{'image':m['image'],'environment':{'GODEBUG':godebug(m['godebug'])},'volumes':[{'type':'bind','source':str(state/'xray'),'target':'/usr/local/bin/xray','read_only':True}]}}}
    pending=state/'override.next.json';pending.write_text(json.dumps(cfg,indent=2))
    run(['docker','compose','-f',str(ROOT/'docker-compose.yml'),'-f',str(pending),'config','--quiet'])
    run(['systemd-run','--unit='+m['unit'],'--on-active=20m','/usr/bin/python3',str(state/'operation.py'),'rollback','--state',str(state)])
    override.write_text(pending.read_text());override.chmod(0o600)
    m['override_sha']=sha(override);(state/'manifest.json').write_text(json.dumps(m))
    try:run(['docker','compose','up','-d','--no-deps','--no-build','--pull','never','remnanode'],timeout=100)
    except BaseException:
        rollback(state);raise
    print('APPLIED_WITH_20_MINUTE_AUTOMATIC_RETURN')


def accept(state):
    m=json.loads((state/'manifest.json').read_text())
    if sha(ROOT/'docker-compose.override.yml')!=m['override_sha']:raise ValueError('Override drift')
    try:_,process=runtime()
    except RuntimeError:
        if not m.get('fresh'):raise
        actual=run(['docker','exec','remnanode','sha256sum','/usr/local/bin/xray']).decode().split()[0]
        if actual!=m['binary_sha']:raise ValueError('Installed binary differs from tested artifact')
        container=json.loads(run(['docker','inspect','remnanode']))[0]
        if not container['State']['Running']:raise ValueError('Fresh node agent stopped')
        if 'GODEBUG='+godebug(m['godebug']) not in container['Config']['Env']:raise ValueError('MPTCP safeguard absent')
        run(['systemctl','stop',m['unit']+'.timer']);print('FRESH_NODE_BINARY_VERIFIED_CLIENT_TEST_PENDING');return
    if sha(process/'exe')!=m['binary_sha']:raise ValueError('Running core differs from tested artifact')
    env=(process/'environ').read_bytes().split(b'\0')
    if not any(v.startswith(b'GODEBUG=') and b'multipathtcp=0' in v.split(b'=',1)[1].split(b',') for v in env):raise ValueError('MPTCP safeguard missing')
    rows=run(['ss','-M','-lnp']).decode().splitlines()[1:]
    if any('pid='+process.name+',' in row for row in rows):raise ValueError('MPTCP listener on managed core')
    run(['systemctl','stop',m['unit']+'.timer'])
    print('CORE_VERIFIED_AND_AUTOMATIC_RETURN_CANCELLED')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply','accept','rollback','install'])
    parser.add_argument('--channel',choices=['latest','verified'],default='latest');parser.add_argument('--state');parser.add_argument('--fresh',action='store_true')
    args=parser.parse_args()
    if os.geteuid()!=0:raise ValueError('Run as root')
    os.umask(0o077)
    import fcntl
    lock=ROOT/'.ham-xray-operation.lock'
    if lock.is_symlink():raise ValueError('Refuse symlinked operation lock')
    handle=lock.open('a')
    try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise RuntimeError('Another Xray operation is active')
    if args.action in {'prepare','install'}:
        state=prepare(args.channel,args.fresh)
        if args.action=='install':
            apply(state)
            if args.fresh:accept(state)
    else:
        if not args.state:raise ValueError('--state is required')
        globals()[args.action](state_path(args.state))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('ERROR: '+str(exc),file=sys.stderr);sys.exit(1)
