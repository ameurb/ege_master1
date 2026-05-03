#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

SERVER="root@173.212.241.70"
REMOTE_DIR="/root/ege_master1"

echo "==> Deploying EGE Documents to $SERVER..."

# Sync project files (exclude uploads, venv, pycache)
echo "==> Syncing files..."
rsync -avz --delete \
    --exclude 'uploads/' \
    --exclude 'data/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.venv/' \
    --exclude 'venv/' \
    --exclude 'node_modules/' \
    --exclude '.git/' \
    ./ "$SERVER:$REMOTE_DIR/"

# Sync TP config and course files (preserve other data like students, grades)
echo "==> Syncing TP data and course files..."
rsync -avz data/tps.json "$SERVER:$REMOTE_DIR/data/tps.json"
rsync -avz --delete data/tp_files/ "$SERVER:$REMOTE_DIR/data/tp_files/"

# Sync .env file
echo "==> Syncing .env..."
rsync -avz .env "$SERVER:$REMOTE_DIR/.env"

# Install dependencies and restart
echo "==> Installing dependencies and restarting..."
ssh "$SERVER" << 'EOF'
cd /root/ege_master1
mkdir -p uploads data data/tp_files data/submissions

# Create venv if it doesn't exist, then install deps
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install -r requirements.txt

# Run database migration (safe to re-run, uses ON CONFLICT DO NOTHING)
echo "==> Running database migration..."
.venv/bin/python migrate_to_db.py

# Delete and re-add to ensure PM2 picks up config changes
pm2 delete ege-docs 2>/dev/null || true
pm2 start ecosystem.config.js
pm2 save
EOF

echo "==> Deploy complete! App should be running on port 9050."
echo "==> Check: ssh $SERVER 'pm2 logs ege-docs --lines 20'"
