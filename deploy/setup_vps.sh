#!/bin/bash
# ============================================================
# SETUP SCRIPT - IHSG IDX Intelligence Bot v2
# Jalankan sekali di VPS Hostinger Ubuntu 22.04 sebagai root
# Usage: bash setup_vps.sh
# ============================================================
set -e

BOT_USER="botuser"
BOT_DIR="/home/$BOT_USER/ihsg-ohlcdev-bot"
SERVICE_NAME="ihsg-bot"
PYTHON="python3.11"

echo ""
echo "========================================"
echo "  IHSG Bot VPS Setup"
echo "========================================"

# 1. Update sistem
echo "[1/7] Update sistem..."
apt-get update -q && apt-get upgrade -y -q
apt-get install -y -q python3.11 python3.11-venv python3-pip git nano curl ufw

# 2. Buat user non-root
echo "[2/7] Setup user $BOT_USER..."
if id "$BOT_USER" &>/dev/null; then
    echo "  Skip - user sudah ada"
else
    adduser --disabled-password --gecos "" $BOT_USER
fi

# 3. Copy kode
echo "[3/7] Copy kode bot..."
if [ -d "$BOT_DIR" ]; then
    echo "  Skip - folder sudah ada"
elif [ -d "/root/ihsg-ohlcdev-bot" ]; then
    cp -r /root/ihsg-ohlcdev-bot $BOT_DIR
    chown -R $BOT_USER:$BOT_USER $BOT_DIR
else
    echo "  ERROR: Upload dulu dari PC dengan:"
    echo "  scp -r ihsg-ohlcdev-bot root@<IP_VPS>:/root/"
    exit 1
fi

# 4. Python virtual environment
echo "[4/7] Setup virtual environment..."
sudo -u $BOT_USER bash << VENVEOF
cd $BOT_DIR
$PYTHON -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  Packages installed OK"
VENVEOF

# 5. File .env
echo "[5/7] Setup .env..."
if [ -f "$BOT_DIR/.env" ]; then
    echo "  Skip - .env sudah ada"
else
    cat > $BOT_DIR/.env << ENVEOF
RAPIDAPI_KEY=GANTI_DENGAN_API_KEY_RAPIDAPI
TELEGRAM_BOT_TOKEN=GANTI_DENGAN_BOT_TOKEN
TELEGRAM_CHAT_ID=GANTI_DENGAN_CHAT_ID
ENVEOF
    chmod 600 $BOT_DIR/.env
    chown $BOT_USER:$BOT_USER $BOT_DIR/.env
    echo "  .env dibuat - wajib isi sebelum start bot!"
fi

# 6. systemd service
echo "[6/7] Setup systemd service..."
cat > /etc/systemd/system/$SERVICE_NAME.service << SVCEOF
[Unit]
Description=IHSG IDX Intelligence Bot v2
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$BOT_USER
WorkingDirectory=$BOT_DIR
EnvironmentFile=$BOT_DIR/.env
ExecStart=$BOT_DIR/venv/bin/python main.py
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target
SVCEOF
systemctl daemon-reload
systemctl enable $SERVICE_NAME
echo "  Service $SERVICE_NAME terdaftar."

# 7. Firewall
echo "[7/7] Setup UFW firewall..."
ufw --force reset -q
ufw default deny incoming -q
ufw default allow outgoing -q
ufw allow ssh -q
ufw --force enable -q
echo "  Firewall: hanya SSH terbuka."

echo ""
echo "========================================"
echo "  Setup selesai!"
echo "========================================"
echo ""
echo "LANGKAH SELANJUTNYA:"
echo "  1. Isi .env dengan API key dan Telegram token:"
echo "       nano $BOT_DIR/.env"
echo ""
echo "  2. Aktifkan jadwal otomatis di scheduler.py:"
echo "       nano $BOT_DIR/scheduler.py"
echo "       -> set AUTO_SCHEDULE = True"
echo ""
echo "  3. Jalankan bot:"
echo "       systemctl start $SERVICE_NAME"
echo ""
echo "  4. Cek status:"
echo "       systemctl status $SERVICE_NAME"
echo ""
echo "  5. Lihat log real-time:"
echo "       journalctl -u $SERVICE_NAME -f"
echo ""
