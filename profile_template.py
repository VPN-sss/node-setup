#!/usr/bin/env python3
"""Generate a root-only Remnawave profile template; never print private keys."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--domain',required=True);parser.add_argument('--selfsteal',action='store_true');args=parser.parse_args()
    if not re.fullmatch(r'(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}',args.domain):raise ValueError('Invalid DNS name')
    output=subprocess.check_output(['docker','exec','remnanode','xray','x25519'],text=True)
    match=re.search(r'(?im)^Private(?:Key| key):\s*(\S+)',output)
    if not match:raise ValueError('Unsupported Xray key output; no private data printed')
    reality={'serverNames':[args.domain],'target':'/dev/shm/nginx.sock' if args.selfsteal else args.domain+':443','xver':1 if args.selfsteal else 0,'minClientVer':'1.8.2','privateKey':match[1],'shortIds':[secrets.token_hex(8)]}
    profile={'log':{'loglevel':'warning'},'inbounds':[{'tag':'VLESS_REALITY_443','listen':'0.0.0.0','port':443,'protocol':'vless','settings':{'clients':[],'decryption':'none','flow':'xtls-rprx-vision'},'streamSettings':{'network':'raw','security':'reality','realitySettings':reality}}],'outbounds':[{'tag':'DIRECT','protocol':'freedom'},{'tag':'BLOCK','protocol':'blackhole'}]}
    os.umask(0o077);path=Path('/opt/remnanode/profile-template.json')
    if path.exists():raise ValueError('Existing profile template preserved')
    path.write_text(json.dumps(profile,indent=2));path.chmod(0o600)
    print('PROFILE_TEMPLATE=/opt/remnanode/profile-template.json')


if __name__=='__main__':main()
