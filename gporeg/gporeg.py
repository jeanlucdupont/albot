#!/usr/bin/env python3
import winreg
import win32api
import win32con
import win32security
import csv

C_HIVES = [
    (winreg.HKEY_LOCAL_MACHINE,     r"SOFTWARE\Policies"),
    (winreg.HKEY_LOCAL_MACHINE,     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies"),
    (winreg.HKEY_CURRENT_USER,      r"SOFTWARE\Policies"),
    (winreg.HKEY_CURRENT_USER,      r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies"),
]
C_CSE  = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\GPExtensions"


def f_checkwrite(root, subkey_path: str):
    try:
        test_handle             = winreg.OpenKey(root, subkey_path, 0, win32con.KEY_SET_VALUE)
        winreg.CloseKey(test_handle)
        return True
    except:
        return False

def f_hiveaudit():
    print("Policy hives audit")
    issues                      = []
    hives                       = { winreg.HKEY_LOCAL_MACHINE: "HKLM", winreg.HKEY_CURRENT_USER: "HKCU", }
    for root, path in C_HIVES:
        fullpath                = f"{hives[root]}\\{path}"
        writeaccess             = f_checkwrite(root, path)
        issues.append({"path": fullpath, "writeaccess": writeaccess})
    return issues

def f_cseaudit():
    print("CSE audit")
    issues                      = []
    try:
        key                     = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, C_CSE)
        i                       = 0
        while 42:
            try:
                keyname         = winreg.EnumKey(key, i)
                somepath        = f"{C_CSE}\\{keyname}"
                writeaccess     = f_checkwrite(winreg.HKEY_LOCAL_MACHINE, somepath)
                issues.append({"path": f"HKLM\\{somepath}", "writeaccess": writeaccess})               
                i               += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except OSError:
        print("CSE audit fAiled")
    return issues

def f_privilegeaudit():
    issues = []
    print("Policy audit")
    riskyprivs                  = [ "SeTakeOwnershipPrivilege", "SeDebugPrivilege", "SeImpersonatePrivilege",  "SeLoadDriverPrivilege", "SeBackupPrivilege", "SeRestorePrivilege", ]
    try:
        token                   = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
        privs                   = win32security.GetTokenInformation(token, win32security.TokenPrivileges)
        for privid, priv_flags in privs:
            name                = win32security.LookupPrivilegeName(None, privid)
            if name in riskyprivs and (priv_flags & win32con.SE_PRIVILEGE_ENABLED):
                issues.append({"privilege": name, "enabled": True})
        win32api.CloseHandle(token)
    except Exception as e:
        print(f"Policy audit fail {e}")
    return issues

polissues                       = f_hiveaudit()
cseissues                       = f_cseaudit()
priissues                       = f_privilegeaudit()
issues                          = { "policy_hives": polissues, "cse_extensions": cseissues, "privileges": priissues }
reportissues                    = []
for f in issues.get("policy_hives", []):
    reportissues.append({"type": "Policy Hive",     "path": f["path"],      "writeaccess": f["writeaccess"]})
for f in issues.get("cse_extensions", []):
    reportissues.append({"type": "CSE Extension",   "path": f["path"],      "writeaccess": f["writeaccess"]})
for f in issues.get("privileges", []):
    reportissues.append({"type": "Privilege",       "path": f["privilege"], "writeaccess": f["enabled"]})
with open('report.csv', "w", newline="", encoding="utf-8") as f:
    writer                      = csv.DictWriter(f, fieldnames=["type", "path", "writeaccess"])
    writer.writeheader()
    writer.writerows(reportissues)
print("\nDone")

