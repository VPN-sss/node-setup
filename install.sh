#!/usr/bin/env bash
set -euo pipefail
umask 077
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/lib/ui.sh"
if [[ ${1:-} == --help ]]; then
    printf 'HAM node installer · interactive RU/EN\nsudo bash install.sh — new node or Xray-only maintenance\npython3 corectl.py --help — guarded core preparation/rollback\n';exit 0
fi
printf '\n  HAM · NODE SETUP\n\n  1. Русский\n  2. English\n\n'
builtin read -r -p 'Language / Язык [1]: ' language
case "$language" in ''|1) export HAM_LANG=ru;;2) export HAM_LANG=en;;*) exit 1;;esac
title "$(text 'Установка и обслуживание ноды' 'Node installation and maintenance')"
[[ $EUID == 0 ]] || { printf '%s\n' "$(text 'Запусти через sudo.' 'Run with sudo.')";exit 1; }
printf '  1. %s\n' "$(text 'Установить новую ноду' 'Install a new node')"
printf '  2. %s\n\n' "$(text 'Сменить только Xray — сохранить остальные настройки' 'Change Xray only — preserve other settings')"
builtin read -r -p "$(text 'Действие [2]: ' 'Action [2]: ')" action
action=${action:-2}
[[ $action == 1 || $action == 2 ]] || exit 1
if [[ $action == 1 && -e /opt/remnanode/docker-compose.yml ]]; then
    printf '%s\n' "$(text 'Нода уже установлена. Используй режим смены Xray.' 'Node already exists. Use Xray-only maintenance.')";exit 1
fi
if [[ $action == 2 && ! -f /opt/remnanode/docker-compose.yml ]]; then
    printf '%s\n' "$(text 'Действующая нода в /opt/remnanode не найдена.' 'No existing node in /opt/remnanode.')";exit 1
fi
printf '\n  1. %s\n' "$(text 'Последний Xray — официальный актуальный релиз' 'Latest Xray — current official release')"
printf '  2. %s\n\n' "$(text 'Проверенный Xray 26.7.28 — Firefox/mihomo' 'Tested Xray 26.7.28 — Firefox/mihomo')"
builtin read -r -p "$(text 'Версия [1/2, Enter — отмена]: ' 'Version [1/2, Enter — cancel]: ')" version
case "$version" in 1) channel=latest;;2) channel=verified;;'') exit 0;;*) exit 1;;esac
if [[ $channel == latest ]]; then
    printf '%s\n' "$(text 'Последний релиз может не работать со старыми Koala/mihomo и Firefox. Для проверенного варианта выбери 26.7.28.' 'The latest release may not work with older Koala/mihomo and Firefox. Choose 26.7.28 for the tested compatibility option.')"
    builtin read -r -p "$(text 'Продолжить с последним релизом? [y/N]: ' 'Continue with the latest release? [y/N]: ')" confirm
    [[ $confirm =~ ^[Yy]$ ]] || exit 0
fi
if [[ $channel == verified ]]; then
    printf '%s\n' "$(text 'Это старый релиз, а не гарантия безопасности или обхода. MPTCP будет отключён для процесса.' 'Older release, not a security or bypass guarantee. Process MPTCP will be disabled.')"
    builtin read -r -p "$(text 'Продолжить с 26.7.28? [y/N]: ' 'Continue with 26.7.28? [y/N]: ')" confirm
    [[ $confirm =~ ^[Yy]$ ]] || exit 0
fi
if [[ $action == 1 ]]; then
    builtin read -r -p "$(text 'Ставим self-steal — свой домен, HTTPS-сайт и сертификат? Да / Нет: ' 'Enable self-steal — own domain, HTTPS site and certificate? Yes / No: ')" selfsteal
    case "$selfsteal" in
        Да|да|д|yes|Yes|y|Y) cd "$SCRIPT_DIR";bash "$SCRIPT_DIR/legacy-install.sh";;
        Нет|нет|н|no|No|n|N)
            command -v docker >/dev/null || { apt-get update;apt-get install -y docker.io; }
            docker compose version >/dev/null 2>&1 || {
                apt-get update
                if apt-cache show docker-compose-v2 >/dev/null 2>&1; then apt-get install -y docker-compose-v2;else apt-get install -y docker-compose-plugin;fi
            }
            command -v python3 >/dev/null || { apt-get update;apt-get install -y python3 ca-certificates; }
            ask_value SECRET_KEY "$(text 'SECRET_KEY из панели (ввод скрыт)' 'Panel SECRET_KEY (hidden input)')"
            [[ -n $SECRET_KEY ]] || exit 1
            export SECRET_KEY;mkdir -p /opt/remnanode
            python3 - <<'PY'
import json,os
from pathlib import Path
cfg={'services':{'remnanode':{'container_name':'remnanode','hostname':'remnanode','image':'remnawave/node:latest','network_mode':'host','restart':'unless-stopped','environment':{'NODE_PORT':'2222','SECRET_KEY':os.environ['SECRET_KEY']},'ulimits':{'nofile':{'soft':1048576,'hard':1048576}},'logging':{'driver':'json-file','options':{'max-size':'10m','max-file':'3'}}}}}
Path('/opt/remnanode/docker-compose.yml').write_text(json.dumps(cfg,indent=2))
PY
            unset SECRET_KEY;docker compose -f /opt/remnanode/docker-compose.yml up -d;;
        *) printf '%s\n' "$(text 'Выбор не распознан; установка отменена.' 'Unknown choice; installation cancelled.')";exit 1;;
    esac
fi
command -v python3 >/dev/null || { printf 'python3 is required\n';exit 1; }
title "$(text 'Проверка и установка Xray' 'Verify and install Xray')"
if [[ $action == 1 ]]; then
    python3 - <<'PY'
from pathlib import Path
with Path('/opt/remnanode/.ham-fresh-install').open('x') as file:file.write('new installation\n')
PY
    python3 "$SCRIPT_DIR/corectl.py" install --channel "$channel" --fresh
    rm -- /opt/remnanode/.ham-fresh-install
    case "$selfsteal" in
        Да|да|д|yes|Yes|y|Y)
            load_saved_settings "$SCRIPT_DIR/.env"
            python3 "$SCRIPT_DIR/profile_template.py" --domain "$DOMAIN" --selfsteal;;
        *)
            builtin read -r -p "$(text 'SNI целевого HTTPS-сайта для REALITY (например, www.microsoft.com): ' 'Target HTTPS website SNI for REALITY (e.g. www.microsoft.com): ')" reality_sni
            python3 "$SCRIPT_DIR/profile_template.py" --domain "$reality_sni";;
    esac
    printf '%s\n' "$(text 'Бинарник установлен. Назначь профиль панели и проверь клиентом — клиентская работа ещё не подтверждена.' 'Binary installed. Assign the panel profile and test a client — end-to-end connectivity is not yet verified.')"
else
    python3 "$SCRIPT_DIR/corectl.py" install --channel "$channel"
    printf '\n%s\n' "$(text 'Автооткат через 20 минут. Проверь URL-test, несколько сайтов и выходной IP.' 'Automatic return in 20 minutes. Test URL delay, several sites and exit IP.')"
    printf '%s\n' "$(text 'Для фиксации: python3 corectl.py accept --state <PREPARED_STATE из вывода>' 'To keep it: python3 corectl.py accept --state <PREPARED_STATE from output>')"
fi
printf '\n%s\n' "$(text 'Для клиентского REALITY-входа в профиле панели: minClientVer = "1.8.2"; отпечаток хоста — firefox. Не добавляй это в обычный TLS.' 'For the client-facing REALITY panel profile: minClientVer = "1.8.2"; host fingerprint — firefox. Do not add this to ordinary TLS.')"
