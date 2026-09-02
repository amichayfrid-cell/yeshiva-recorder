import winreg
import sys

def install_context_menu():
    menu_name = "השאר הערה לאחראי השמע"
    command_str = r'powershell.exe -WindowStyle Hidden -Command "Start-Process (\'http://192.168.1.244:8000/student?file=\' + [uri]::EscapeDataString(\'%1\'))"'

    # 1. Clean old entries
    cleanup_paths = [
        r"Software\Classes\SystemFileAssociations\audio\shell\YeshivaFeedback",
        r"Software\Classes\SystemFileAssociations\.mp3\shell\YeshivaFeedback",
        r"Software\Classes\SystemFileAssociations\.wav\shell\YeshivaFeedback",
        r"Software\Classes\*\shell\YeshivaFeedback",
        r"Software\Classes\*\shell\YeshivaAudioFeedback",
        r"Software\Classes\mp3file\shell\YeshivaFeedback",
        r"Software\Classes\WMP11.AssocFile.MP3\shell\YeshivaFeedback"
    ]

    for p in cleanup_paths:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, p + r"\command")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, p)
        except OSError:
            pass

    # 2. Install to HKCU SystemFileAssociations and *
    targets = [
        r"Software\Classes\SystemFileAssociations\audio\shell\YeshivaFeedback",
        r"Software\Classes\SystemFileAssociations\.mp3\shell\YeshivaFeedback",
        r"Software\Classes\SystemFileAssociations\.wav\shell\YeshivaFeedback",
        r"Software\Classes\*\shell\YeshivaFeedback"
    ]

    for target in targets:
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, target)
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, menu_name)
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, "shell32.dll,269")
            winreg.CloseKey(key)

            cmd_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, target + r"\command")
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command_str)
            winreg.CloseKey(cmd_key)
        except Exception as e:
            print(f"Error on {target}: {e}")

    print("=" * 60)
    print("✓ תפריט 'השאר הערה לאחראי השמע' הותקן בהצלחה בעברית מלאה!")
    print("=" * 60)

if __name__ == "__main__":
    install_context_menu()
