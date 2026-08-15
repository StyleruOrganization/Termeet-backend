#!/bin/sh
set -e

if [ -f /etc/alertmanager/alertmanager.yml.template ]; then
  # Если message_thread_id пустой или 0, заменяем на отсутствие поля или корректный вывод
  if [ -z "$TELEGRAM_ALERTS_THREAD_ID" ] || [ "$TELEGRAM_ALERTS_THREAD_ID" = "0" ]; then
    sed -e "s/\${TELEGRAM_BOT_TOKEN}/$TELEGRAM_BOT_TOKEN/g" \
        -e "s/\${TELEGRAM_ALERTS_CHAT_ID}/$TELEGRAM_ALERTS_CHAT_ID/g" \
        -e "/message_thread_id/d" \
        /etc/alertmanager/alertmanager.yml.template > /etc/alertmanager/alertmanager.yml
  else
    sed -e "s/\${TELEGRAM_BOT_TOKEN}/$TELEGRAM_BOT_TOKEN/g" \
        -e "s/\${TELEGRAM_ALERTS_CHAT_ID}/$TELEGRAM_ALERTS_CHAT_ID/g" \
        -e "s/\${TELEGRAM_ALERTS_THREAD_ID}/$TELEGRAM_ALERTS_THREAD_ID/g" \
        /etc/alertmanager/alertmanager.yml.template > /etc/alertmanager/alertmanager.yml
  fi
fi

exec /bin/alertmanager --config.file=/etc/alertmanager/alertmanager.yml --storage.path=/alertmanager "$@"
