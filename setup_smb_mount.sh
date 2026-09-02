#!/bin/bash
# ==============================================================================
# Yeshiva Network Share Auto-Mount Script (SMB/CIFS)
# עגינה מאובטחת של שיתוף שיעורי השמע משרת הישיבה (Windows Share)
# ==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
  echo "[-] יש להריץ סקריפט זה כ-root או באמצעות sudo!"
  echo "    דוגמה: sudo ./setup_smb_mount.sh"
  exit 1
fi

echo "============================================================"
echo "    הגדרת חיבור שרת הקבצים של הישיבה (SMB Mount)"
echo "============================================================"

# 1. התקנת חבילות נדרשות
echo "[*] בודק ומתקין cifs-utils..."
apt-get update -qq
apt-get install -y -qq cifs-utils

MOUNT_POINT="/mnt/yeshiva_share"
CRED_FILE="/etc/yeshiva_smb.cred"

# 2. קבלת פרטי התחברות מהמשתמש
echo ""
read -p "הזן את נתיב שרת הקבצים [ברירת מחדל: //mdserver/שיעורי שמע]: " SHARE_PATH
SHARE_PATH=${SHARE_PATH:-"//mdserver/שיעורי שמע"}

read -p "הזן שם משתמש לשרת ה-Windows: " SMB_USER
read -s -p "הזן סיסמה: " SMB_PASS
echo ""
read -p "הזן Domain/Workgroup [ברירת מחדל: WORKGROUP]: " SMB_DOMAIN
SMB_DOMAIN=${SMB_DOMAIN:-"WORKGROUP"}

# 3. שמירת קובץ ההרשאות בצורה מאובטחת
echo "[*] שומר קובץ הרשאות מאובטח ב-$CRED_FILE..."
cat <<EOF > "$CRED_FILE"
username=$SMB_USER
password=$SMB_PASS
domain=$SMB_DOMAIN
EOF
chmod 600 "$CRED_FILE"

# 4. יצירת תיקיית העגינה
echo "[*] יוצר נקודת עגינה ב-$MOUNT_POINT..."
mkdir -p "$MOUNT_POINT"

# 5. בדיקת עגינה מיידית
echo "[*] בודק עגינה לשיתוף..."
umount "$MOUNT_POINT" 2>/dev/null || true
mount -t cifs "$SHARE_PATH" "$MOUNT_POINT" \
  -o credentials="$CRED_FILE",iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0,noperm

# 6. יצירת תיקיית 'שיעורים למיון' בשיתוף
TARGET_DIR="$MOUNT_POINT/שיעורים למיון"
if [ ! -d "$TARGET_DIR" ]; then
    echo "[*] יוצר תיקיית יעד: $TARGET_DIR..."
    mkdir -p "$TARGET_DIR"
fi

# 7. הגדרה לעגינה קבועה ב-fstab
echo "[*] מגדיר עגינה אוטומטית בעליית השרת ב-/etc/fstab..."
# הסרת הגדרות ישנות אם קיימות
sed -i "\|$MOUNT_POINT|d" /etc/fstab

FSTAB_ENTRY="$SHARE_PATH $MOUNT_POINT cifs credentials=$CRED_FILE,iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0,noperm,_netdev 0 0"
echo "$FSTAB_ENTRY" >> /etc/fstab

echo ""
echo "============================================================"
echo "✓ חיבור שרת הקבצים של הישיבה הושלם בהצלחה!"
echo "  נתיב מקומי בשרת: $MOUNT_POINT"
echo "  תיקיית היעד להקלטות: $TARGET_DIR"
echo "============================================================"
