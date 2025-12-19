#!/bin/bash

set -euo pipefail

# === Настройки ===
# Можно переопределить каталог с userbot через USERBOT_PROJECT_DIR.
# Если переменная не задана, пробуем найти проект рядом с менеджером, иначе используем запасной путь.
MANAGER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR=""

SESSION_PATH="${1:-}"
API_ID="${2:-}"
API_HASH="${3:-}"
PHONE="${4:-}"
SESSION_DIR="$(dirname "$SESSION_PATH")"

LOG_DIR="$MANAGER_DIR/sessions"
LOG_FILE="$LOG_DIR/${PHONE}.log"
PID_FILE="$LOG_DIR/${PHONE}.pid"

# === Проверка аргументов ===
if [ -z "$PHONE" ]; then
    echo "Usage: $0 <session_path> <api_id> <api_hash> <phone>"
    exit 1
fi

# Готовим каталог/файл сессии, чтобы Telethon мог писать в SQLite
if [ -n "$SESSION_DIR" ] && [ "$SESSION_DIR" != "." ]; then
    mkdir -p "$SESSION_DIR" || {
        echo "Не удалось создать каталог для сессий: $SESSION_DIR"
        exit 1
    }
fi

if [ ! -w "$SESSION_DIR" ]; then
    echo "Каталог сессии недоступен для записи: $SESSION_DIR"
    exit 1
fi

if [ -n "$SESSION_PATH" ]; then
    if [ -e "$SESSION_PATH" ]; then
        if [ ! -w "$SESSION_PATH" ]; then
            echo "Снимаем read-only с файла сессии $SESSION_PATH"
            chmod u+rw "$SESSION_PATH" || {
                echo "Не удалось сделать файл сессии доступным для записи"
                exit 1
            }
        fi
    else
        touch "$SESSION_PATH" || {
            echo "Не удалось создать файл сессии $SESSION_PATH"
            exit 1
        }
        chmod 600 "$SESSION_PATH" || true
    fi
fi

# Создаём папку для логов и включаем логирование всего скрипта в файл
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
exec >>"$LOG_FILE" 2>&1
echo "[$(date --iso-8601=seconds)] === start_bot.sh for $PHONE ==="

# Определяем PROJECT_DIR
POSSIBLE_DIRS=()
[ -n "${USERBOT_PROJECT_DIR:-}" ] && POSSIBLE_DIRS+=("$USERBOT_PROJECT_DIR")
POSSIBLE_DIRS+=("$MANAGER_DIR/../userbot" "/home/max/Desktop/userbot")
for dir in "${POSSIBLE_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        PROJECT_DIR="$(cd "$dir" && pwd)"
        break
    fi
done

if [ -z "$PROJECT_DIR" ]; then
    echo "Userbot project dir not found. Checked: ${POSSIBLE_DIRS[*]}"
    exit 1
fi
echo "Using PROJECT_DIR=$PROJECT_DIR"

# === Проверка, запущен ли уже бот ===
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        echo "Bot for $PHONE is already running (PID: $PID)"
        exit 0
    else
        echo "Stale PID file found. Removing..."
        rm -f "$PID_FILE"
    fi
fi

# === Переходим в папку проекта и запускаем через uv ===
cd "$PROJECT_DIR" || {
    echo "Failed to cd to $PROJECT_DIR"
    exit 1
}
echo "pwd=$(pwd)"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found in PATH=$PATH"
    exit 1
fi

# Убираем VIRTUAL_ENV, чтобы uv не ругался
unset VIRTUAL_ENV

# Запускаем в фоне с помощью nohup
nohup uv run -m bot "$SESSION_PATH" "$API_ID" "$API_HASH" \
    >> "$LOG_FILE" 2>&1 &

# Сохраняем PID фонового процесса
echo $! > "$PID_FILE"

echo "Bot started for $PHONE with PID: $!"
