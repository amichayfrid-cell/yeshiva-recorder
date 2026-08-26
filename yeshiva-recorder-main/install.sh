#!/bin/bash
set -e

echo "==================================================="
echo "  התקנת מערכת מיון שיעורי תורה (Ubuntu / Linux)  "
echo "==================================================="

# Determine real user running the script
REAL_USER=${SUDO_USER:-$(whoami)}
CURRENT_DIR=$(pwd)

# 1. Update system & install dependencies
echo ""
echo "[1/4] התקנת חבילות מערכת (ffmpeg, python3, pip, venv, git, curl)..."
sudo apt update
sudo apt install -y ffmpeg python3-pip python3-venv git curl

# 2. Setup Virtual Environment & install python dependencies
echo ""
echo "[2/4] הגדרת סביבת Python והתקנת ספריות..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Fix permissions if run with sudo
chown -R ${REAL_USER}:${REAL_USER} venv || true

# 3. Install Ollama & Pull Model
echo ""
echo "[3/4] התקנת Ollama והורדת מודל Gemma 4..."
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
fi

# Ensure ollama service is running
sudo systemctl start ollama || true
sleep 2

ollama pull gemma4:e2b

# 4. Setup Systemd Service
echo ""
echo "[4/4] הגדרת שירות רקע אוטומטי (systemd)..."

cat << EOF > recorder.service
[Unit]
Description=Torah Recording Auto Classifier Service
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=${REAL_USER}
WorkingDirectory=${CURRENT_DIR}
ExecStart=${CURRENT_DIR}/venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo cp recorder.service /etc/systemd/system/recorder.service
sudo systemctl daemon-reload
sudo systemctl enable recorder.service
sudo systemctl start recorder.service

echo ""
echo "==================================================="
echo "  ✓ ההתקנה הושלמה בהצלחה!"
echo "  - לבדיקת סטטוס השירות: sudo systemctl status recorder.service"
echo "  - לצפייה בלוגים חיים: journalctl -u recorder.service -f"
echo "==================================================="
