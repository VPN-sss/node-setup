#!/usr/bin/env bash
text() {
    if [[ ${HAM_LANG:-ru} == ru ]]; then printf '%s' "$1"; else printf '%s' "$2"; fi
}
load_saved_settings() {
    local file=$1 key value
    [[ -f $file ]] || return 0
    while IFS='=' read -r key value || [[ -n $key ]]; do
        case "$key" in
            EMAIL|DOMAIN|SECRET_KEY|SERVICE_NAME|XHTTP_PATH|GRPC_PATH|CF_Token)
                printf -v "$key" '%s' "$value";export "$key";;
        esac
    done < "$file"
}
ask_value() {
    local key=$1 prompt value
    prompt=$(translate "$2")
    if [[ $key == SECRET_KEY || $key == CF_Token ]]; then
        builtin read -r -s -p "$prompt: " value;printf '\n'
    else builtin read -r -p "$prompt: " value;fi
    [[ $value != *$'\r'* && $value != *$'\n'* ]] || return 1
    printf -v "$key" '%s' "$value"
}
title() {
    printf '\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n  HAM · %s\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n' "$1"
}
translate() {
    [[ ${HAM_LANG:-ru} == ru ]] || { printf '%s' "$1"; return; }
    case "$1" in
        'Email (for SSL)') printf 'Email для сертификата';;
        'Domain (e.g., node.example.com)') printf 'Домен ноды (например, node.example.com)';;
        'SECRET_KEY (from panel)') printf 'SECRET_KEY из панели (ввод скрыт)';;
        'XHTTP Location Path (e.g., /xhttppath/)') printf 'Путь XHTTP (например, /xhttppath/)';;
        'gRPC Service Name/Path (e.g., /grpcpath)') printf 'Путь gRPC (например, /grpcpath)';;
        'Cloudflare API Token '*) printf 'Cloudflare API Token с правом DNS:Edit (ввод скрыт)';;
        '--- Configuration ---') printf 'Шаг 1 · Домен и доступ к панели';;
        'Select the service you want to install:') printf 'Выбери сервис для HTTPS-сайта:';;
        'Service number (Press Enter for a random one): ') printf 'Номер сервиса (Enter — случайный): ';;
        'Enable BBR (TCP Congestion Control)? (y/N): ') printf 'Включить BBR? [y/N]: ';;
        'Select default Certificate Authority (CA):') printf 'Выбери центр сертификации:';;
        'Enter choice [1-2]: ') printf 'Выбор [1–2]: ';;
        '--- 1. Checking and Installing Dependencies ---') printf 'Шаг 2 · Установка зависимостей';;
        '--- 2. Installing acme.sh ---') printf 'Шаг 3 · Подготовка сертификата';;
        '--- 3. Issuing SSL Certificate ---') printf 'Выпуск или подключение сертификата';;
        '--- 5. Configuring Nginx Proxy ---') printf 'Шаг 5 · HTTPS-прокси';;
        '--- 6. Installing Remnanode ---') printf 'Шаг 6 · Агент Remnanode';;
        '--- 7. Configuring Firewall ---') printf 'Шаг 7 · Правила межсетевого экрана';;
        'No existing certificates found.') printf 'Сохранённых сертификатов нет.';;
        'Select SSL validation method:') printf 'Способ проверки домена:';;
        '2) DNS-01 via Cloudflare (certbot + API Token only, no inbound port needed)') printf '2) DNS-01 через Cloudflare: certbot и API-токен, входящий порт не нужен';;
        '1) Standalone (HTTP/TLS-ALPN-01 on port 8443 - requires this port reachable from the internet)') printf '1) TLS-ALPN-01: потребуется перенаправление внешнего 443 на локальный 8443';;
        'Configuring automatic renewal via crontab...') printf 'Настройка автоматического продления сертификата…';;
        'INSTALLATION COMPLETE!') printf 'Базовая установка завершена. Далее — проверка Xray.';;
        'Invalid service number') printf 'Номер сервиса вне допустимого диапазона';;
        'Cron task successfully configured/verified.') printf 'Расписание продления настроено.';;
        'Certbot deploy-hook and renewal cron task configured.') printf 'Настроены обработчик продления и расписание certbot.';;
        'Docker not found. Installing...') printf 'Docker не найден — устанавливаю…';;
        'Docker Compose plugin is available. Skipping installation.') printf 'Docker Compose уже установлен.';;
        'Docker Compose not found or outdated. Updating docker packages...') printf 'Устанавливаю плагин Docker Compose…';;
        'Ensuring system utilities are installed...') printf 'Устанавливаю системные утилиты…';;
        "Setting default CA to Let's Encrypt...") printf "Выбран Let's Encrypt.";;
        'Setting default CA to ZeroSSL...') printf 'Выбран ZeroSSL.';;
        "Invalid choice. Defaulting to Let's Encrypt to be safe.") printf "Выбор не распознан. Использую Let's Encrypt.";;
        'Issuing a new certificate via standalone ALPN...') printf 'Выпускаю сертификат через TLS-ALPN-01…';;
        '--- Cloudflare DNS-01 challenge (certbot) ---') printf 'Проверка DNS-01 через Cloudflare';;
        'Installing certbot + Cloudflare DNS plugin...') printf 'Устанавливаю certbot и плагин Cloudflare…';;
        'Issuing certificate via Cloudflare DNS-01...') printf 'Выпускаю сертификат через Cloudflare DNS-01…';;
        'Error: Failed to issue SSL certificate via Cloudflare DNS-01.') printf 'Ошибка выпуска сертификата через Cloudflare DNS-01.';;
        'Error: Failed to issue SSL certificate.') printf 'Ошибка выпуска сертификата.';;
        'Check that the API Token has Zone:DNS:Edit permission for '*) printf 'Проверь право Zone:DNS:Edit у API-токена для домена.';;
        'Issue reported an error, but certificate files were found. Copying...') printf 'Команда сообщила об ошибке, но сертификат найден. Подключаю…';;
        'Setting up a certbot deploy-hook to sync renewed certs and restart services...') printf 'Настраиваю подхват обновлённых сертификатов…';;
        'Remnanode Port: 2222') printf 'Порт управления нодой: 2222';;
        'Checking WARP SOCKS5 proxy...') printf 'Проверка WARP SOCKS5 (если установлен)…';;
        'Docker is already installed '*) printf 'Docker уже установлен — повторная установка не нужна.';;
        '--- Installing service: '*) printf 'Установка выбранного HTTPS-сервиса';;
        '--- 4. Setting up '*) printf 'Шаг 4 · Запуск выбранного сайта';;
        'Saved service is '*) printf 'Использовать сохранённый сервис? [Y/n]: ';;
        'Selected Service: '*) printf 'Сервис: %s' "${1#Selected Service: }";;
        'Domain: '*) printf 'Домен: %s' "${1#Domain: }";;
        'Certificate source: '*) printf 'Источник сертификата: %s' "${1#Certificate source: }";;
        *) printf '%s' "$1";;
    esac
}
echo() {
    local flag=''
    if [[ ${1:-} == -e || ${1:-} == -n ]]; then flag=$1; shift; fi
    if [[ -n $flag ]]; then builtin echo "$flag" "$(translate "$*")"; else builtin echo "$(translate "$*")"; fi
}
read() {
    local -a args=()
    while (($#)); do
        if [[ $1 == -p && $# -ge 2 ]]; then args+=(-p "$(translate "$2")");shift 2;else args+=("$1");shift;fi
    done
    builtin read "${args[@]}"
}
