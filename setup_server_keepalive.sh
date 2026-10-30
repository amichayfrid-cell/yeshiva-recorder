#!/bin/bash
# ==============================================================================
# Prevent Ubuntu server from sleeping/suspending and keep network/services active
# ==============================================================================

echo "==> [KeepAlive] Masking sleep & suspend targets..."
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target 2>/dev/null || true

echo "==> [KeepAlive] Configuring logind to ignore lid close and idle..."
sudo sed -i 's/#\?HandleLidSwitch=.*/HandleLidSwitch=ignore/' /etc/systemd/logind.conf 2>/dev/null || true
sudo sed -i 's/#\?HandleLidSwitchExternalPower=.*/HandleLidSwitchExternalPower=ignore/' /etc/systemd/logind.conf 2>/dev/null || true
sudo sed -i 's/#\?HandleLidSwitchDocked=.*/HandleLidSwitchDocked=ignore/' /etc/systemd/logind.conf 2>/dev/null || true
sudo sed -i 's/#\?IdleAction=.*/IdleAction=ignore/' /etc/systemd/logind.conf 2>/dev/null || true
sudo systemctl restart systemd-logind 2>/dev/null || true

echo "==> [KeepAlive] Disabling GNOME desktop sleep..."
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing' 2>/dev/null || true
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type 'nothing' 2>/dev/null || true
gsettings set org.gnome.desktop.session idle-delay 0 2>/dev/null || true

echo "==> [KeepAlive] Disabling WiFi power savings..."
sudo sed -i 's/wifi.powersave = 3/wifi.powersave = 2/' /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf 2>/dev/null || true

echo "==> [KeepAlive] Enabling services on startup..."
sudo systemctl enable web.service 2>/dev/null || true
sudo systemctl enable recorder.service 2>/dev/null || true

echo "==> [KeepAlive] Ensuring mammoth is installed for in-browser Word rendering..."
if [ -d "venv" ]; then
    venv/bin/pip install mammoth 2>/dev/null || true
elif command -v pip &>/dev/null; then
    pip install mammoth 2>/dev/null || true
fi

echo "==> [KeepAlive] Ensuring ffmpeg is installed for audio transcoding..."
if ! command -v ffmpeg &>/dev/null; then
    sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg 2>/dev/null || true
fi

echo "==> [KeepAlive] Ensuring //mdserver/העלאת שיעורים is mounted..."
if [ -f "/etc/yeshiva_smb.cred" ]; then
    sudo mkdir -p /mnt/yeshiva_upload 2>/dev/null || true
    
    # 1. Detect SMB Server host from existing yeshiva_share or fstab
    SMB_SERVER=$(grep -i "yeshiva_share" /etc/fstab /proc/mounts 2>/dev/null | grep -o '//[^/]*' | head -n 1 | tr -d '/')
    if [ -z "$SMB_SERVER" ]; then
        SMB_SERVER="mdserver"
    fi
    echo "==> [KeepAlive] Detected SMB Server host: $SMB_SERVER"
    
    # 2. Update /etc/fstab with correct \\040 space escape
    sudo sed -i '/yeshiva_upload/d' /etc/fstab 2>/dev/null || true
    echo "//$SMB_SERVER/העלאת\040שיעורים /mnt/yeshiva_upload cifs credentials=/etc/yeshiva_smb.cred,iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0,nofail,x-systemd.automount 0 0" | sudo tee -a /etc/fstab >/dev/null 2>&1 || true
    sudo systemctl daemon-reload 2>/dev/null || true
    
    # 3. Mount if not currently mounted
    if ! mountpoint -q /mnt/yeshiva_upload; then
        echo "==> [KeepAlive] Mounting //$SMB_SERVER/העלאת שיעורים to /mnt/yeshiva_upload..."
        sudo mount /mnt/yeshiva_upload 2>/dev/null || \
        sudo mount -t cifs "//$SMB_SERVER/העלאת שיעורים" /mnt/yeshiva_upload \
          -o credentials="/etc/yeshiva_smb.cred",iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0,noperm 2>/dev/null || \
        sudo mount -t cifs "//$SMB_SERVER/העלאת שיעורים" /mnt/yeshiva_upload \
          -o credentials="/etc/yeshiva_smb.cred",iocharset=utf8,file_mode=0777,dir_mode=0777,noperm 2>/dev/null || \
        sudo mount -t cifs "//mdserver/העלאת שיעורים" /mnt/yeshiva_upload \
          -o credentials="/etc/yeshiva_smb.cred",iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0,noperm 2>/dev/null || true
    fi
    
    if mountpoint -q /mnt/yeshiva_upload; then
        FILE_COUNT=$(ls -1 "/mnt/yeshiva_upload" 2>/dev/null | wc -l)
        echo "==> [KeepAlive] SUCCESS: /mnt/yeshiva_upload is mounted! Found $FILE_COUNT items."
    else
        echo "==> [KeepAlive] Note: /mnt/yeshiva_upload direct mount not active yet, checking subfolder fallback..."
    fi
fi

echo "==> [KeepAlive] Keep-alive setup complete!"
