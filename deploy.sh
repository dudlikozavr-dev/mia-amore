#!/bin/bash
# Деплой mini-app на Timeweb VPS
# Использование:
#   bash deploy.sh          — деплой фронта
#   bash deploy.sh --back   — деплой фронта + перезапуск бэкенда

VPS_USER="root"
VPS_HOST="72.56.38.179"
VPS_KEY="C:/Users/Денис/.ssh/id_ed25519_vps"
KNOWN_HOSTS="C:/Users/Денис/.ssh/known_hosts"
REMOTE_FRONT="/var/www/app.sikretsweet.ru"
LOCAL_FRONT="./tg-app"

echo "==> Деплой фронта на $VPS_HOST..."
scp -r \
  -i "$VPS_KEY" \
  -o UserKnownHostsFile="$KNOWN_HOSTS" \
  "$LOCAL_FRONT"/* "$VPS_USER@$VPS_HOST:$REMOTE_FRONT/"

if [ "$1" == "--back" ]; then
  echo "==> Перезапуск бэкенда..."
  ssh -i "$VPS_KEY" \
    -o UserKnownHostsFile="$KNOWN_HOSTS" \
    "$VPS_USER@$VPS_HOST" \
    "cd /home/deploy/mia-amore && git pull && systemctl restart miamore"
fi

echo "==> Готово! https://app.sikretsweet.ru"
