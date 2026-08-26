#!/bin/bash
set -e

# ==============================================================================
# Yeshiva Windows Server SMB/CIFS Auto-Mount Configuration Script
# Sets up /mnt/shiurei_shema -> \\mdserver\שיעורי שמע
# ==============================================================================

if [ "$EUID" -ne 0 ]; then
  echo "[!] Please run as root (sudo ./setup_smb_mount.sh)"
  exit 1
fi

SERVER_HOST="${1:-mdserver}"
SHARE_NAME="${2:-שיעורי שמע}"
MOUNT_POINT="/mnt/shiurei_shema"
CRED_DIR="/etc/yeshiva-recorder"
CRED_FILE="$CRED_DIR/.smbcredentials"

echo "============================================================"
echo " 🌐 הגדרת חיבור שרת הקבצים של הישיבה (Windows Server SMB)"
echo "============================================================"
echo "• כתובת שרת: $SERVER_HOST"
echo "• שם שיתוף:  $SHARE_NAME"
echo "• נקודת עגינה בלינוקס: $MOUNT_POINT"
echo "============================================================"

# 1. Install cifs-utils
echo "[1/5] מתקין חבילת cifs-utils..."
apt-get update -qq
apt-get install -y cifs-utils

# 2. Setup Credentials
mkdir -p "$CRED_DIR"
if [ ! -f "$CRED_FILE" ]; then
    echo ""
    echo "[2/5] הזנת פרטי משתמש שרת ה-Windows שנוצר עבור שרת ההקלטות:"
    read -p "הזן שם משתמש (Windows Username): " SMB_USER
    read -s -p "הזן סיסמה (Windows Password): " SMB_PASS
    echo ""
    read -p "הזן Domain/Workgroup (הקש Enter לברירת מחדל WORKGROUP): " SMB_DOMAIN
    SMB_DOMAIN="${SMB_DOMAIN:-WORKGROUP}"

    cat <<EOF > "$CRED_FILE"
username=$SMB_USER
password=$SMB_PASS
domain=$SMB_DOMAIN
EOF
    chmod 600 "$CRED_FILE"
    echo "✓ קובץ האימות נשמר בהצלחה בהרשאות מאובטחות ב-$CRED_FILE"
else
    echo "[2/5] ✓ קובץ אימות קיים כבר ב-$CRED_FILE"
fi

# 3. Create mount point
echo "[3/5] יוצר תיקיית עגינה $MOUNT_POINT..."
mkdir -p "$MOUNT_POINT"

# 4. Configure /etc/fstab for auto-mount on boot
FSTAB_SHARE="//${SERVER_HOST}/שיעורי\\040שמע"
FSTAB_LINE="${FSTAB_SHARE} ${MOUNT_POINT} cifs credentials=${CRED_FILE},iocharset=utf8,vers=3.0,file_mode=0777,dir_mode=0777,nofail,_netdev 0 0"

if grep -q "$MOUNT_POINT" /etc/fstab; then
    echo "[4/5] ✓ שורת עגינה כבר קיימת ב-/etc/fstab"
else
    echo "[4/5] מוסיף עגינה קבועה ב-/etc/fstab..."
    echo "$FSTAB_LINE" >> /etc/fstab
fi

# 5. Mount the share now
echo "[5/5] מבצע עגינה כעת..."
mount -a || true

# 6. Verify and create 'שיעורים למיון' directory
TARGET_SUBDIR="$MOUNT_POINT/שיעורים למיון"
if [ -d "$MOUNT_POINT" ] && mountpoint -q "$MOUNT_POINT"; then
    mkdir -p "$TARGET_SUBDIR"
    chmod -R 777 "$TARGET_SUBDIR" || true
    echo ""
    echo "============================================================"
    echo "✓ ההתחברות לשרת הישיבה הושלמה בהצלחה!"
    echo "• תיקיית היעד מוכנה: $TARGET_SUBDIR"
    echo "============================================================"
else
    echo ""
    echo "============================================================"
    echo "⚠️ אזהרה: העגינה לא הושלמה מיד (ייתכן שרת ה-Windows כבוי או כתובת לא זמינה ברגע זה)."
    echo "המערכת תעבוד בינתיים במצב Staging מקומי ותסנכרן אוטומטית ברגע שהשרת יחובר."
    echo "============================================================"
fi
