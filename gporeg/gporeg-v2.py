#!/usr/bin/env python3
"""
GPO Security Audit & Attack Chain Simulator
Windows Group Policy Object Security Assessment Tool

Features:
- Audit writable registry keys (GPO bypass vectors)
- Check CSE extension integrity
- Detect privileged tokens (SeTakeOwnershipPrivilege, etc.)
- Simulate full attack chain
- Calculate risk score
- Generate JSON + HTML reports
- MITRE ATT&CK mapping
"""

import winreg
import win32api
import win32con
import win32security
import sys
import json
import csv
import os
import ctypes
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# ============= CONSTANTS =============

KEY_WRITE_MASK = (
    win32con.KEY_WRITE
    | win32con.KEY_SET_VALUE
    | win32con.KEY_CREATE_SUB_KEY
    | win32con.DELETE
    | win32con.WRITE_DAC
    | win32con.WRITE_OWNER
)

TARGET_SIDS = [
    "S-1-5-32-545",  # BUILTIN\Users
    "S-1-1-0",       # Everyone
    "S-1-5-11",      # Authenticated Users
    "S-1-5-32-544",  # BUILTIN\Administrators
]

POLICY_HIVES = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Policies"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies"),
]

MITRE_ATTACK_CHAIN = {
    "Phase 1 - Discovery": {
        "Technique": "T1018 - Remote System Discovery",
        "Description": "Find writable registry keys and GPO policies"
    },
    "Phase 2 - Defense Evasion": {
        "Technique": "T1562.001 - Disable Security Tools",
        "Description": "Modify policy keys to disable Defender, UAC, LAPS"
    },
    "Phase 3 - Persistence": {
        "Technique": "T1547 - Boot/Logon Autostart Execution",
        "Description": "Add malicious entries to Run keys"
    },
    "Phase 4 - Privilege Escalation": {
        "Technique": "T1068 - Exploitation for Privilege Escalation",
        "Description": "Enable SeTakeOwnershipPrivilege to take ownership of GPOs"
    },
    "Phase 5 - Credential Access": {
        "Technique": "T1003 - Credential Dumping",
        "Description": "Dump LSA secrets after disabling security controls"
    }
}

# ============= HELPER FUNCTIONS =============

def is_admin() -> bool:
    """Check if running as administrator"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def print_header(title: str) -> None:
    """Print formatted section header"""
    print(f"\n[+] {title}")
    print("=" * 60)

def is_key_writable_by_users(root_key, subkey_path: str) -> bool:
    """Check if the key can be opened with write access"""
    try:
        test_handle = winreg.OpenKey(root_key, subkey_path, 0, win32con.KEY_SET_VALUE)
        winreg.CloseKey(test_handle)
        return True
    except:
        return False

def audit_policy_hives() -> List[Dict]:
    """Audit Group Policy registry hives for write access"""
    findings = []
    print_header("Registry Access Controls on Group Policy Hives")
    hive_names = {
        winreg.HKEY_LOCAL_MACHINE: "HKLM",
        winreg.HKEY_CURRENT_USER: "HKCU",
    }

    for root_key, path in POLICY_HIVES:
        full_path = f"{hive_names[root_key]}\\{path}"
        writable = is_key_writable_by_users(root_key, path)
        
        severity = "INFO"
        if writable:
            severity = "HIGH" if "HKLM" in full_path else "MEDIUM"
        
        findings.append({
            "path": full_path,
            "writable": writable,
            "severity": severity
        })
        
        if writable:
            print(f"[!] VULNERABLE: Write access granted on {full_path}")
            if "HKLM" in full_path:
                print(f"    WARNING: Local machine policy can be modified")
        else:
            print(f"[OK] Secure permissions confirmed on {full_path}")

    return findings

def audit_cse_extensions() -> List[Dict]:
    """Audit Group Policy Client-Side Extension registry keys"""
    findings = []
    print_header("Group Policy Client-Side Extension (CSE) Integrity")
    cse_base_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\GPExtensions"

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cse_base_path)
        i = 0
        vulnerable_count = 0

        while True:
            try:
                guid_key_name = winreg.EnumKey(key, i)
                sub_path = f"{cse_base_path}\\{guid_key_name}"
                writable = is_key_writable_by_users(winreg.HKEY_LOCAL_MACHINE, sub_path)
                
                findings.append({
                    "path": f"HKLM\\{sub_path}",
                    "writable": writable,
                    "severity": "CRITICAL" if writable else "INFO"
                })
                
                if writable:
                    print(f"[!] VULNERABLE: Writable CSE Extension key: {guid_key_name}")
                    print(f"    WARNING: Attackers can tamper with Group Policy application")
                    vulnerable_count += 1
                i += 1
            except OSError:
                break

        winreg.CloseKey(key)

        if vulnerable_count == 0:
            print("[OK] All Client-Side Extension registry keys are secured.")
    except OSError:
        print("[-] Unable to access GP Extensions registry path.")

    return findings

def audit_token_privileges() -> List[Dict]:
    """Audit current process token for dangerous privileges"""
    findings = []
    print_header("Privilege Delegation & Local Policy Overrides")

    dangerous_privs = [
        "SeTakeOwnershipPrivilege",
        "SeDebugPrivilege",
        "SeImpersonatePrivilege",
        "SeLoadDriverPrivilege",
        "SeBackupPrivilege",
        "SeRestorePrivilege",
    ]

    try:
        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), win32con.TOKEN_QUERY
        )
        privs = win32security.GetTokenInformation(token, win32security.TokenPrivileges)

        for priv_id, priv_flags in privs:
            name = win32security.LookupPrivilegeName(None, priv_id)
            if name in dangerous_privs and (priv_flags & win32con.SE_PRIVILEGE_ENABLED):
                findings.append({
                    "privilege": name,
                    "enabled": True,
                    "severity": "CRITICAL" if name == "SeTakeOwnershipPrivilege" else "HIGH",
                    "description": f"{name} is enabled - potential privilege escalation"
                })
                print(f"[!] RISK: {name} enabled")
                if name == "SeTakeOwnershipPrivilege":
                    print(f"    WARNING: Local admin can strip GPO ACLs and take ownership")
                elif name == "SeDebugPrivilege":
                    print(f"    WARNING: Can debug privileged processes (LSASS dump possible)")

        win32api.CloseHandle(token)

        if not findings:
            print("[OK] No dangerous privileges detected")

    except Exception as e:
        print(f"[-] Token evaluation error: {e}")

    return findings

# ============= RISK SCORING =============

def calculate_risk_score(findings: Dict) -> Dict:
    """Calculate overall risk score (0-100)"""
    score = 0
    details = []

    for f in findings.get("policy_hives", []):
        if f["writable"]:
            if "HKLM" in f["path"]:
                score += 25
                details.append(f"CRITICAL: {f['path']} is writable")
            else:
                score += 10
                details.append(f"MEDIUM: {f['path']} is writable")

    for f in findings.get("cse_extensions", []):
        if f["writable"]:
            score += 20
            details.append(f"CRITICAL: Writable CSE extension: {f['path']}")

    for f in findings.get("privileges", []):
        if f["enabled"]:
            if f["severity"] == "CRITICAL":
                score += 25
                details.append(f"CRITICAL: {f['privilege']} enabled")
            else:
                score += 15
                details.append(f"HIGH: {f['privilege']} enabled")

    score = min(score, 100)
    severity = "CRITICAL" if score > 70 else "HIGH" if score > 40 else "MEDIUM" if score > 20 else "LOW"
    
    return {"score": score, "details": details, "severity": severity}

# ============= REMEDIATION =============

def suggest_remediation(findings: Dict) -> List[str]:
    """Generate remediation suggestions"""
    suggestions = []

    for f in findings.get("policy_hives", []):
        if f["writable"]:
            suggestions.append(f"icacls {f['path']} /remove Everyone /inheritance:e")

    for f in findings.get("cse_extensions", []):
        if f["writable"]:
            suggestions.append(f"icacls {f['path']} /remove Users /inheritance:e")

    for f in findings.get("privileges", []):
        if f["enabled"] and f["privilege"] == "SeTakeOwnershipPrivilege":
            suggestions.append("Remove SeTakeOwnershipPrivilege from admin accounts via Group Policy")

    return list(set(suggestions))

# ============= REPORTING =============

def generate_json_report(findings: Dict, risk_score: Dict, suggestions: List[str], filename: str = "gpo_audit_report.json"):
    """Export findings to JSON"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "hostname": win32api.GetComputerName(),
        "username": win32api.GetUserName(),
        "is_admin": is_admin(),
        "findings": findings,
        "risk_score": risk_score,
        "remediation_suggestions": suggestions,
        "mitre_attack_chain": MITRE_ATTACK_CHAIN
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"[+] JSON report saved to {filename}")

def generate_html_report(findings: Dict, risk_score: Dict, suggestions: List[str], filename: str = "gpo_audit_report.html"):
    """Generate HTML dashboard report"""
    
    # Build findings tables
    policy_rows = ""
    for f in findings.get("policy_hives", []):
        status = "VULNERABLE" if f["writable"] else "SECURE"
        status_class = "vulnerable" if f["writable"] else "secure"
        badge = f["severity"] if f["writable"] else "LOW"
        policy_rows += f"<tr><td>{f['path']}</td><td class=\"{status_class}\">{status}</td><td><span class=\"badge badge-{badge}\">{badge}</span></td></tr>"

    cse_rows = ""
    for f in findings.get("cse_extensions", []):
        status = "VULNERABLE" if f["writable"] else "SECURE"
        status_class = "vulnerable" if f["writable"] else "secure"
        badge = f["severity"] if f["writable"] else "LOW"
        cse_rows += f"<tr><td>{f['path']}</td><td class=\"{status_class}\">{status}</td><td><span class=\"badge badge-{badge}\">{badge}</span></td></tr>"

    priv_rows = ""
    for f in findings.get("privileges", []):
        status = "ENABLED" if f["enabled"] else "DISABLED"
        status_class = "vulnerable" if f["enabled"] else "secure"
        badge = f["severity"] if f["enabled"] else "LOW"
        priv_rows += f"<tr><td>{f['privilege']}</td><td class=\"{status_class}\">{status}</td><td><span class=\"badge badge-{badge}\">{badge}</span></td></tr>"

    # Risk details
    risk_details = "".join([f"<li>{d}</li>" for d in risk_score["details"]])
    
    # Remediation suggestions
    remediation_items = "".join([f"<li><code>{s}</code></li>" for s in suggestions])
    
    # MITRE chain
    mitre_items = "".join([
        f"<li><strong>{phase}</strong>: {data['Technique']}<br><em>{data['Description']}</em></li>"
        for phase, data in MITRE_ATTACK_CHAIN.items()
    ])

    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>GPO Security Audit Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }}
        h1 {{ color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }}
        .risk-box {{ padding: 15px; border-radius: 5px; margin: 10px 0; }}
        .risk-CRITICAL {{ background: #ff4444; color: white; }}
        .risk-HIGH {{ background: #ff8800; color: white; }}
        .risk-MEDIUM {{ background: #ffcc00; color: black; }}
        .risk-LOW {{ background: #44bb44; color: white; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #333; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        .vulnerable {{ color: red; font-weight: bold; }}
        .secure {{ color: green; }}
        .badge {{ display: inline-block; padding: 2px 10px; border-radius: 3px; font-size: 12px; }}
        .badge-CRITICAL {{ background: #ff4444; color: white; }}
        .badge-HIGH {{ background: #ff8800; color: white; }}
        .badge-MEDIUM {{ background: #ffcc00; color: black; }}
        .badge-LOW {{ background: #44bb44; color: white; }}
        .badge-INFO {{ background: #888; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>GPO Security Audit Report</h1>
        <p><strong>Host:</strong> {win32api.GetComputerName()}</p>
        <p><strong>User:</strong> {win32api.GetUserName()}</p>
        <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Admin Privileges:</strong> {'Yes' if is_admin() else 'No'}</p>

        <div class="risk-box risk-{risk_score['severity']}">
            <h2>Risk Score: {risk_score['score']}/100 ({risk_score['severity']})</h2>
            <ul>{risk_details}</ul>
        </div>

        <h2>Findings</h2>
        <h3>Policy Hives</h3>
        <table>
            <tr><th>Key</th><th>Status</th><th>Severity</th></tr>
            {policy_rows}
        </table>

        <h3>CSE Extensions</h3>
        <table>
            <tr><th>Key</th><th>Status</th><th>Severity</th></tr>
            {cse_rows}
        </table>

        <h3>Privileges</h3>
        <table>
            <tr><th>Privilege</th><th>Status</th><th>Severity</th></tr>
            {priv_rows}
        </table>

        <h2>Remediation Suggestions</h2>
        <ul>{remediation_items}</ul>

        <h2>MITRE ATT&CK Attack Chain</h2>
        <ul>{mitre_items}</ul>

        <p style="text-align: center; color: #666; margin-top: 20px;">
            Generated by GPO Security Audit Tool
        </p>
    </div>
</body>
</html>'''

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[+] HTML report saved to {filename}")

def generate_csv_report(findings: Dict, filename: str = "gpo_audit_report.csv"):
    """Export findings to CSV"""
    all_findings = []
    for f in findings.get("policy_hives", []):
        all_findings.append({"type": "Policy Hive", "path": f["path"], "writable": f["writable"], "severity": f["severity"]})
    for f in findings.get("cse_extensions", []):
        all_findings.append({"type": "CSE Extension", "path": f["path"], "writable": f["writable"], "severity": f["severity"]})
    for f in findings.get("privileges", []):
        all_findings.append({"type": "Privilege", "path": f["privilege"], "writable": f["enabled"], "severity": f["severity"]})

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "path", "writable", "severity"])
        writer.writeheader()
        writer.writerows(all_findings)
    print(f"[+] CSV report saved to {filename}")

# ============= ATTACK SIMULATION =============

def simulate_attack_chain(findings: Dict):
    """Simulate the full attack chain based on findings"""
    print("\n" + "=" * 60)
    print("  SIMULATING ATTACK CHAIN")
    print("  Based on MITRE ATT&CK Framework")
    print("=" * 60)

    has_vulnerability = False

    print("\n[Phase 1] Discovery (T1018)")
    writable_keys = [f["path"] for f in findings.get("policy_hives", []) if f["writable"]]
    if writable_keys:
        has_vulnerability = True
        print("  FOUND: Writable registry keys:")
        for key in writable_keys:
            print(f"      - {key}")
        print("  -> Attackers can query these keys for exploitable policies")
    else:
        print("  No writable registry keys found - attack blocked")

    print("\n[Phase 2] Defense Evasion (T1562.001)")
    if any(f["writable"] for f in findings.get("policy_hives", []) if "HKLM" in f["path"]):
        has_vulnerability = True
        print("  FOUND: Writable local machine policy")
        print("  -> Attackers can disable:")
        print("      - Windows Defender (DisableAntiSpyware)")
        print("      - UAC (EnableLUA)")
        print("      - LAPS (AdminPasswordProtection)")
    else:
        print("  No writable local machine policy - attack blocked")

    print("\n[Phase 3] Persistence (T1547)")
    if any(f["writable"] for f in findings.get("cse_extensions", [])):
        has_vulnerability = True
        print("  FOUND: Writable CSE extension")
        print("  -> Attackers can add malicious run keys")
        print("      - HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run")
        print("      - HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run")
    else:
        print("  No writable CSE extensions - attack blocked")

    print("\n[Phase 4] Privilege Escalation (T1068)")
    privs = [f["privilege"] for f in findings.get("privileges", []) if f["enabled"]]
    if privs:
        has_vulnerability = True
        print("  FOUND: Enabled dangerous privileges:")
        for priv in privs:
            print(f"      - {priv}")
        if "SeTakeOwnershipPrivilege" in privs:
            print("  -> Attackers can take ownership of GPO objects")
        if "SeDebugPrivilege" in privs:
            print("  -> Attackers can debug LSASS.exe and dump credentials")
    else:
        print("  No dangerous privileges found - attack blocked")

    print("\n[Phase 5] Credential Access (T1003)")
    if "SeDebugPrivilege" in privs:
        has_vulnerability = True
        print("  FOUND: SeDebugPrivilege enables LSASS dump")
        print("  -> Attackers can use Mimikatz to extract passwords")
    else:
        print("  No credential dumping vectors found")

    print("\n" + "=" * 60)
    if has_vulnerability:
        print("  ATTACK CHAIN POSSIBLE")
        print("  The system is vulnerable to GPO bypass attack")
        print("  Impact: Complete system compromise")
    else:
        print("  ATTACK CHAIN BLOCKED")
        print("  The system is secure against GPO bypass")
    print("=" * 60)

# ============= MAIN =============

def parse_arguments():
    parser = argparse.ArgumentParser(description="GPO Security Audit & Attack Chain Simulator")
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    parser.add_argument("--json", action="store_true", help="Generate JSON report")
    parser.add_argument("--csv", action="store_true", help="Generate CSV report")
    parser.add_argument("--simulate", action="store_true", help="Simulate attack chain")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no changes)")
    parser.add_argument("--output-dir", default=".", help="Output directory for reports")
    return parser.parse_args()

def main():
    args = parse_arguments()

    print("=" * 60)
    print("  GPO Security Audit & Attack Chain Simulator")
    print("  Windows Group Policy Object Security Assessment")
    print("=" * 60)
    print(f"\n[i] Host: {win32api.GetComputerName()}")
    print(f"[i] User: {win32api.GetUserName()}")
    print(f"[i] Admin: {is_admin()}")
    print(f"[i] Dry-run: {args.dry_run}")
    print("\n")

    # Run audits
    policy_findings = audit_policy_hives()
    cse_findings = audit_cse_extensions()
    priv_findings = audit_token_privileges()

    # Compile findings
    findings = {
        "policy_hives": policy_findings,
        "cse_extensions": cse_findings,
        "privileges": priv_findings
    }

    # Calculate risk
    risk_score = calculate_risk_score(findings)
    suggestions = suggest_remediation(findings)

    # Display summary
    print("\n" + "=" * 60)
    print("  AUDIT SUMMARY")
    print("=" * 60)
    print(f"[!] Risk Score: {risk_score['score']}/100 ({risk_score['severity']})")
    print(f"[!] Vulnerable Policy Hives: {sum(1 for f in policy_findings if f['writable'])}")
    print(f"[!] Vulnerable CSE Extensions: {sum(1 for f in cse_findings if f['writable'])}")
    print(f"[!] Dangerous Privileges: {sum(1 for f in priv_findings if f['enabled'])}")
    print("\n" + "=" * 60)

    # Simulate attack
    if args.simulate:
        simulate_attack_chain(findings)

    # Generate reports
    if args.html:
        generate_html_report(findings, risk_score, suggestions, f"{args.output_dir}/gpo_audit_report.html")
    if args.json:
        generate_json_report(findings, risk_score, suggestions, f"{args.output_dir}/gpo_audit_report.json")
    if args.csv:
        generate_csv_report(findings, f"{args.output_dir}/gpo_audit_report.csv")

    print("\n[+] Audit Complete.\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[+] Ctrl-C detected. Exiting...")
    except Exception as e:
        print(f"[-] Error: {e}")
        import traceback
        traceback.print_exc()
