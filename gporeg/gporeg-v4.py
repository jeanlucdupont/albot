#!/usr/bin/env python3
"""
GPO Security Audit & Attack Chain Simulator
Windows Group Policy Object Security Assessment Tool

Features:
- Audit writable registry keys (GPO bypass vectors)
- Check CSE extension integrity
- Detect privileged tokens (SeTakeOwnershipPrivilege, etc.)
- Scan SYSVOL for writable GPO files and permissions
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
import ntpath
import glob
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

WRITE_RIGHT_NAMES = {
    win32con.KEY_SET_VALUE: "SET_VALUE",
    win32con.KEY_CREATE_SUB_KEY: "CREATE_SUB_KEY",
    win32con.DELETE: "DELETE",
    win32con.WRITE_DAC: "WRITE_DAC",
    win32con.WRITE_OWNER: "WRITE_OWNER",
}

# Representative registry-backed security controls. This is intentionally a
# focused catalog rather than an exhaustive Windows security baseline.
SENSITIVE_REGISTRY_VALUES = [
    {"name": "Microsoft Defender real-time protection", "root": winreg.HKEY_LOCAL_MACHINE,
     "path": r"SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection",
     "value": "DisableRealtimeMonitoring"},
    {"name": "User Account Control", "root": winreg.HKEY_LOCAL_MACHINE,
     "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "value": "EnableLUA"},
    {"name": "LSA protection", "root": winreg.HKEY_LOCAL_MACHINE,
     "path": r"SYSTEM\CurrentControlSet\Control\Lsa", "value": "RunAsPPL"},
    {"name": "PowerShell Script Block Logging", "root": winreg.HKEY_LOCAL_MACHINE,
     "path": r"SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging",
     "value": "EnableScriptBlockLogging"},
    {"name": "Remote Desktop connections", "root": winreg.HKEY_LOCAL_MACHINE,
     "path": r"SYSTEM\CurrentControlSet\Control\Terminal Server", "value": "fDenyTSConnections"},
    {"name": "SMB server signing", "root": winreg.HKEY_LOCAL_MACHINE,
     "path": r"SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters",
     "value": "RequireSecuritySignature"},
]

POLICY_HIVES = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Policies"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies"),
]

# SYSVOL GPO related constants
GPO_FILES = [
    "gpt.ini",
    "registry.pol",
    "scripts.ini",
    "Groups.xml",
    "ScheduledTasks.xml",
    "Services.xml",
    "DataSources.xml",
    "Drives.xml",
    "Files.xml",
    "Folders.xml",
    "IniFiles.xml",
    "Shortcuts.xml",
    "Printers.xml",
    "Registry.xml",
    "Secedit.inf",
]

# Sensitive GPP files that may contain credentials
GPP_CREDENTIAL_FILES = [
    "Groups.xml",
    "ScheduledTasks.xml",
    "Services.xml",
    "DataSources.xml",
]

# DANGEROUS GPO SETTINGS that could be abused
DANGEROUS_GPO_SETTINGS = {
    "DisableRealtimeMonitoring": "Disables Microsoft Defender real-time protection",
    "EnableLUA": "Disables User Account Control (UAC)",
    "RunAsPPL": "Disables LSA Protection",
    "DisableAntiSpyware": "Disables Windows Defender",
    "DisableBehaviorMonitoring": "Disables behavior monitoring in Defender",
    "DisableOnAccessProtection": "Disables on-access scanning in Defender",
    "DisableScanOnRealtimeEnable": "Prevents Defender from scanning when real-time protection is enabled",
    "fDenyTSConnections": "Allows Remote Desktop connections (0 = enabled)",
    "RequireSecuritySignature": "Disables SMB signing (0 = disabled)",
    "AdminPassword": "LAPS password storage",
    "Password": "Plaintext or encrypted passwords in GPP files",
    "cpassword": "Encrypted password in Group Policy Preferences (can be decrypted)",
    "DisableTaskMgr": "Disables Task Manager",
    "DisableRegistryTools": "Disables Registry Editor",
    "DisableCMD": "Disables Command Prompt",
    "DisablePowerShell": "Disables PowerShell",
}

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
    },
    "Phase 6 - GPO Tampering": {
        "Technique": "T1484.001 - Group Policy Modification",
        "Description": "Modify GPO files in SYSVOL to deploy malicious policies"
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

def resolve_sid(sid) -> str:
    """Resolve a SID to DOMAIN\\account, falling back to its string form."""
    sid_string = win32security.ConvertSidToStringSid(sid)
    try:
        account, domain, _ = win32security.LookupAccountSid(None, sid)
        return f"{domain}\\{account}" if domain else account
    except win32security.error:
        return sid_string

def describe_write_rights(access_mask: int) -> List[str]:
    """Return the write-capable registry rights represented by an ACE mask."""
    return [name for bit, name in WRITE_RIGHT_NAMES.items() if access_mask & bit]

def get_registry_writers(key_handle) -> List[Dict]:
    """Return principals granted write-capable rights by allow ACEs."""
    security_descriptor = win32security.GetSecurityInfo(
        key_handle, win32security.SE_REGISTRY_KEY,
        win32security.DACL_SECURITY_INFORMATION,
    )
    dacl = security_descriptor.GetSecurityDescriptorDacl()
    if dacl is None:
        return [{"principal": "Everyone", "sid": "S-1-1-0",
                 "rights": ["FULL_CONTROL (null DACL)"], "inherited": False}]

    writers = []
    allow_ace_types = {
        win32security.ACCESS_ALLOWED_ACE_TYPE,
        getattr(win32security, "ACCESS_ALLOWED_OBJECT_ACE_TYPE", -1),
    }
    inherited_ace = getattr(win32con, "INHERITED_ACE", 0x10)
    for index in range(dacl.GetAceCount()):
        ace = dacl.GetAce(index)
        ace_type, ace_flags = ace[0]
        if ace_type not in allow_ace_types:
            continue
        access_mask = ace[1]
        sid = ace[-1]
        rights = describe_write_rights(access_mask)
        if not rights:
            continue
        sid_string = win32security.ConvertSidToStringSid(sid)
        writers.append({
            "principal": resolve_sid(sid), "sid": sid_string, "rights": rights,
            "inherited": bool(ace_flags & inherited_ace),
        })
    return writers

# ============= SYSVOL GPO AUDIT FUNCTIONS =============

def get_domain_info() -> Dict:
    """Get domain information and SYSVOL path"""
    domain_info = {
        "is_domain_joined": False,
        "domain_name": None,
        "sysvol_path": None,
        "error": None
    }
    
    try:
        # Check if machine is domain joined
        import win32net
        import win32netcon
        domain_name, _, _ = win32net.NetGetJoinInformation()
        if domain_name:
            domain_info["is_domain_joined"] = True
            domain_info["domain_name"] = domain_name
            domain_info["sysvol_path"] = fr"\{domain_name}\SYSVOL\{domain_name}\Policies"
    except ImportError:
        domain_info["error"] = "pywin32 win32net module not available"
    except Exception as e:
        domain_info["error"] = f"Error getting domain info: {str(e)}"
    
    return domain_info

def get_local_sysvol_path() -> Optional[str]:
    """Get local SYSVOL path (for domain controllers)"""
    try:
        # For domain controllers, SYSVOL is typically at C:\Windows\SYSVOL\domain
        sysvol_paths = [
            os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "SYSVOL"),
            r"C:\Windows\SYSVOL\domain",
            r"C:\Windows\SYSVOL"
        ]
        
        for path in sysvol_paths:
            if os.path.exists(path):
                return path
    except Exception:
        pass
    return None

def get_sysvol_path(domain_info: Dict) -> Optional[str]:
    """Get SYSVOL path based on domain info"""
    # If domain joined, use network path
    if domain_info.get("is_domain_joined") and domain_info.get("sysvol_path"):
        return domain_info["sysvol_path"]
    
    # For domain controllers, use local path
    local_path = get_local_sysvol_path()
    if local_path:
        return local_path
    
    return None

def check_file_writable(filepath: str) -> Tuple[bool, Dict]:
    """Check if a file is writable and get its permissions"""
    result = {
        "writable": False,
        "permissions": [],
        "owner": None,
        "error": None
    }
    
    try:
        # Check if file exists
        if not os.path.exists(filepath):
            result["error"] = "File not found"
            return False, result
        
        # Try to open file in write mode (simulate write access)
        try:
            with open(filepath, 'a') as f:
                pass
            result["writable"] = True
        except PermissionError:
            result["writable"] = False
        except Exception as e:
            result["error"] = str(e)
            return False, result
        
        # Get file permissions using Windows API
        try:
            import win32security
            import win32con
            
            # Get security descriptor
            sec_desc = win32security.GetFileSecurity(
                filepath, 
                win32security.DACL_SECURITY_INFORMATION | win32security.OWNER_SECURITY_INFORMATION
            )
            
            # Get owner
            owner_sid = sec_desc.GetSecurityDescriptorOwner()
            if owner_sid:
                result["owner"] = resolve_sid(owner_sid)
            
            # Get DACL
            dacl = sec_desc.GetSecurityDescriptorDacl()
            if dacl:
                for i in range(dacl.GetAceCount()):
                    ace = dacl.GetAce(i)
                    ace_type, ace_flags = ace[0]
                    access_mask = ace[1]
                    sid = ace[-1]
                    
                    # Only check allow ACEs
                    if ace_type == win32security.ACCESS_ALLOWED_ACE_TYPE:
                        sid_str = win32security.ConvertSidToStringSid(sid)
                        principal = resolve_sid(sid)
                        
                        # Check for write permissions
                        write_perms = []
                        if access_mask & win32con.FILE_WRITE_DATA:
                            write_perms.append("WRITE_DATA")
                        if access_mask & win32con.FILE_WRITE_ATTRIBUTES:
                            write_perms.append("WRITE_ATTRIBUTES")
                        if access_mask & win32con.FILE_WRITE_EA:
                            write_perms.append("WRITE_EA")
                        if access_mask & win32con.FILE_APPEND_DATA:
                            write_perms.append("APPEND_DATA")
                        if access_mask & win32con.FILE_ALL_ACCESS:
                            write_perms.append("FULL_CONTROL")
                        if access_mask & win32con.GENERIC_WRITE:
                            write_perms.append("GENERIC_WRITE")
                        if access_mask & win32con.WRITE_DAC:
                            write_perms.append("WRITE_DAC")
                        if access_mask & win32con.WRITE_OWNER:
                            write_perms.append("WRITE_OWNER")
                        
                        if write_perms:
                            inherited = bool(ace_flags & getattr(win32con, "INHERITED_ACE", 0x10))
                            result["permissions"].append({
                                "principal": principal,
                                "sid": sid_str,
                                "rights": write_perms,
                                "inherited": inherited
                            })
        except Exception as e:
            result["error"] = f"Permission check error: {str(e)}"
        
    except Exception as e:
        result["error"] = str(e)
    
    return result["writable"], result

def check_directory_writable(dirpath: str) -> Tuple[bool, Dict]:
    """Check if a directory is writable and get its permissions"""
    result = {
        "writable": False,
        "permissions": [],
        "owner": None,
        "error": None
    }
    
    try:
        if not os.path.exists(dirpath):
            result["error"] = "Directory not found"
            return False, result
        
        # Try to create a test file
        test_file = os.path.join(dirpath, ".test_write_perm")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            result["writable"] = True
        except PermissionError:
            result["writable"] = False
        except Exception as e:
            result["error"] = str(e)
            return False, result
        
        # Get directory permissions
        try:
            import win32security
            import win32con
            
            sec_desc = win32security.GetFileSecurity(
                dirpath, 
                win32security.DACL_SECURITY_INFORMATION | win32security.OWNER_SECURITY_INFORMATION
            )
            
            owner_sid = sec_desc.GetSecurityDescriptorOwner()
            if owner_sid:
                result["owner"] = resolve_sid(owner_sid)
            
            dacl = sec_desc.GetSecurityDescriptorDacl()
            if dacl:
                for i in range(dacl.GetAceCount()):
                    ace = dacl.GetAce(i)
                    ace_type, ace_flags = ace[0]
                    access_mask = ace[1]
                    sid = ace[-1]
                    
                    if ace_type == win32security.ACCESS_ALLOWED_ACE_TYPE:
                        sid_str = win32security.ConvertSidToStringSid(sid)
                        principal = resolve_sid(sid)
                        
                        write_perms = []
                        if access_mask & win32con.FILE_ADD_FILE:
                            write_perms.append("ADD_FILE")
                        if access_mask & win32con.FILE_ADD_SUBDIRECTORY:
                            write_perms.append("ADD_SUBDIRECTORY")
                        if access_mask & win32con.FILE_ALL_ACCESS:
                            write_perms.append("FULL_CONTROL")
                        if access_mask & win32con.GENERIC_WRITE:
                            write_perms.append("GENERIC_WRITE")
                        if access_mask & win32con.WRITE_DAC:
                            write_perms.append("WRITE_DAC")
                        if access_mask & win32con.WRITE_OWNER:
                            write_perms.append("WRITE_OWNER")
                        
                        if write_perms:
                            inherited = bool(ace_flags & getattr(win32con, "INHERITED_ACE", 0x10))
                            result["permissions"].append({
                                "principal": principal,
                                "sid": sid_str,
                                "rights": write_perms,
                                "inherited": inherited
                            })
        except Exception as e:
            result["error"] = f"Permission check error: {str(e)}"
    
    except Exception as e:
        result["error"] = str(e)
    
    return result["writable"], result

def parse_gpt_ini(gpt_ini_path: str) -> Dict:
    """Parse gpt.ini file to get GPO version and flags"""
    gpt_info = {
        "version": None,
        "file_syspath": None,
        "gpc_file_syspath": None,
        "display_name": None,
        "flags": 0,
        "error": None
    }
    
    try:
        if not os.path.exists(gpt_ini_path):
            gpt_info["error"] = "gpt.ini not found"
            return gpt_info
        
        with open(gpt_ini_path, 'r', encoding='utf-16') as f:
            for line in f:
                line = line.strip()
                if line.startswith('[') or not line:
                    continue
                
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key == "Version":
                        gpt_info["version"] = int(value)
                    elif key == "FileSysPath":
                        gpt_info["file_syspath"] = value
                    elif key == "GPCFileSysPath":
                        gpt_info["gpc_file_syspath"] = value
                    elif key == "DisplayName":
                        gpt_info["display_name"] = value
                    elif key == "Flags":
                        gpt_info["flags"] = int(value)
    
    except Exception as e:
        gpt_info["error"] = f"Error parsing gpt.ini: {str(e)}"
    
    return gpt_info

def check_gpp_credentials(gpp_path: str) -> Dict:
    """Check for encrypted credentials in GPP XML files"""
    result = {
        "has_credentials": False,
        "encrypted_passwords": [],
        "plaintext_passwords": [],
        "error": None
    }
    
    try:
        if not os.path.exists(gpp_path):
            result["error"] = "GPP file not found"
            return result
        
        # Parse XML to look for credentials
        import xml.etree.ElementTree as ET
        
        tree = ET.parse(gpp_path)
        root = tree.getroot()
        
        # Look for cpassword attributes (encrypted passwords)
        for elem in root.iter():
            if 'cpassword' in elem.attrib:
                cpassword = elem.attrib['cpassword']
                result["has_credentials"] = True
                result["encrypted_passwords"].append({
                    "file": gpp_path,
                    "attribute": "cpassword",
                    "value": cpassword,
                    "note": "This can be decrypted with GPP password decryption"
                })
            
            # Look for plaintext passwords
            for attr_name, attr_value in elem.attrib.items():
                if 'password' in attr_name.lower() and attr_value:
                    result["has_credentials"] = True
                    result["plaintext_passwords"].append({
                        "file": gpp_path,
                        "attribute": attr_name,
                        "value": "[REDACTED]",
                        "note": "Plaintext password found (redacted)"
                    })
        
        # Also check for password in element text
        for elem in root.iter():
            if elem.text and 'password' in elem.tag.lower():
                result["has_credentials"] = True
                result["plaintext_passwords"].append({
                    "file": gpp_path,
                    "element": elem.tag,
                    "value": "[REDACTED]",
                    "note": "Plaintext password found in element text (redacted)"
                })
    
    except Exception as e:
        result["error"] = f"Error parsing GPP file: {str(e)}"
    
    return result

def audit_sysvol_gpo(gpo_path: str, gpo_id: str) -> Dict:
    """Audit a single GPO in SYSVOL"""
    gpo_findings = {
        "gpo_id": gpo_id,
        "path": gpo_path,
        "display_name": None,
        "version": None,
        "writable": False,
        "writable_files": [],
        "writable_dirs": [],
        "dangerous_settings": [],
        "gpp_credentials": None,
        "permissions": [],
        "severity": "INFO",
        "error": None
    }
    
    try:
        # Check if GPO directory is writable
        gpo_dir_writable, dir_perms = check_directory_writable(gpo_path)
        if gpo_dir_writable:
            gpo_findings["writable"] = True
            gpo_findings["severity"] = "CRITICAL"
            gpo_findings["permissions"].extend(dir_perms.get("permissions", []))
        
        # Parse gpt.ini
        gpt_ini_path = os.path.join(gpo_path, "gpt.ini")
        gpt_info = parse_gpt_ini(gpt_ini_path)
        gpo_findings["display_name"] = gpt_info.get("display_name", gpo_id)
        gpo_findings["version"] = gpt_info.get("version")
        
        # Check for writable files
        for gpo_file in GPO_FILES:
            file_path = os.path.join(gpo_path, gpo_file)
            if os.path.exists(file_path):
                file_writable, file_perms = check_file_writable(file_path)
                if file_writable:
                    gpo_findings["writable_files"].append({
                        "file": gpo_file,
                        "path": file_path,
                        "permissions": file_perms
                    })
                    gpo_findings["writable"] = True
                    gpo_findings["severity"] = "CRITICAL"
                
                # Check for GPP credentials in XML files
                if gpo_file in GPP_CREDENTIAL_FILES and gpo_file.endswith('.xml'):
                    gpp_result = check_gpp_credentials(file_path)
                    if gpp_result.get("has_credentials"):
                        gpo_findings["gpp_credentials"] = gpp_result
                        gpo_findings["severity"] = "CRITICAL"
        
        # Check User and Machine subdirectories
        for subdir in ["User", "Machine"]:
            subdir_path = os.path.join(gpo_path, subdir)
            if os.path.exists(subdir_path):
                subdir_writable, subdir_perms = check_directory_writable(subdir_path)
                if subdir_writable:
                    gpo_findings["writable_dirs"].append({
                        "dir": subdir,
                        "path": subdir_path,
                        "permissions": subdir_perms
                    })
                    gpo_findings["writable"] = True
                    gpo_findings["severity"] = "CRITICAL"
        
        # If no critical findings but has GPO files, set to MEDIUM
        if not gpo_findings["writable"] and (gpo_findings["writable_files"] or gpo_findings["writable_dirs"]):
            gpo_findings["severity"] = "HIGH"
        elif not gpo_findings["writable"]:
            gpo_findings["severity"] = "LOW"
    
    except Exception as e:
        gpo_findings["error"] = str(e)
        gpo_findings["severity"] = "ERROR"
    
    return gpo_findings

def audit_sysvol_gpos(sysvol_path: str) -> List[Dict]:
    """Audit all GPOs in SYSVOL"""
    findings = []
    print_header("SYSVOL GPO Security Audit")
    
    try:
        # Check if SYSVOL path exists
        if not os.path.exists(sysvol_path):
            print(f"[-] SYSVOL path not found: {sysvol_path}")
            print("    This machine may not be domain-joined or a domain controller.")
            return findings
        
        print(f"[i] Scanning SYSVOL at: {sysvol_path}")
        
        # Get list of GPO directories (they are GUID-named)
        gpo_dirs = []
        try:
            for entry in os.listdir(sysvol_path):
                entry_path = os.path.join(sysvol_path, entry)
                if os.path.isdir(entry_path):
                    # GPO directories have a specific format: {GUID}
                    if len(entry) == 38 and entry.count('-') == 4:  # UUID format
                        gpo_dirs.append(entry)
                    # Also check for {GUID} subdirectories
                    elif os.path.isdir(entry_path):
                        for sub_entry in os.listdir(entry_path):
                            if len(sub_entry) == 38 and sub_entry.count('-') == 4:
                                gpo_dirs.append(os.path.join(entry, sub_entry))
        except Exception as e:
            print(f"[-] Error listing SYSVOL directory: {str(e)}")
            return findings
        
        if not gpo_dirs:
            print("[-] No GPO directories found in SYSVOL")
            return findings
        
        print(f"[i] Found {len(gpo_dirs)} GPO(s) in SYSVOL")
        
        # Audit each GPO
        vulnerable_count = 0
        for gpo_id in gpo_dirs:
            gpo_path = os.path.join(sysvol_path, gpo_id)
            gpo_finding = audit_sysvol_gpo(gpo_path, gpo_id)
            
            # Print findings for this GPO
            display_name = gpo_finding.get("display_name", gpo_id)
            status = "VULNERABLE" if gpo_finding.get("writable") else "SECURE"
            severity = gpo_finding.get("severity", "INFO")
            
            print(f"[*] GPO: {display_name} ({gpo_id})")
            print(f"    Status: {status} ({severity})")
            
            if gpo_finding.get("writable"):
                vulnerable_count += 1
                print(f"    WARNING: GPO directory or files are writable!")
                
                if gpo_finding.get("writable_files"):
                    print(f"    Writable files: {', '.join([f['file'] for f in gpo_finding['writable_files']])}")
                
                if gpo_finding.get("writable_dirs"):
                    print(f"    Writable directories: {', '.join([d['dir'] for d in gpo_finding['writable_dirs']])}")
                
                if gpo_finding.get("gpp_credentials"):
                    gpp = gpo_finding["gpp_credentials"]
                    if gpp.get("encrypted_passwords"):
                        print(f"    CRITICAL: Found {len(gpp['encrypted_passwords'])} encrypted password(s) (cpassword)")
                    if gpp.get("plaintext_passwords"):
                        print(f"    CRITICAL: Found {len(gpp['plaintext_passwords'])} plaintext password(s)")
            else:
                print(f"    [OK] GPO is properly secured")
            
            if gpo_finding.get("error"):
                print(f"    Error: {gpo_finding['error']}")
            
            findings.append(gpo_finding)
        
        print(f"\n[!] Summary: {vulnerable_count}/{len(gpo_dirs)} GPO(s) have writable permissions")
        
    except Exception as e:
        print(f"[-] Error auditing SYSVOL: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return findings

# ============= REGISTRY AUDIT FUNCTIONS =============

def audit_sensitive_registry_values() -> List[Dict]:
    """Show selected security-sensitive values and principals with write rights."""
    findings = []
    print_header("Security-Sensitive Registry Values and Writers")
    for control in SENSITIVE_REGISTRY_VALUES:
        full_path = f"HKLM\\{control['path']}"
        finding = {
            "control": control["name"], "path": full_path,
            "value_name": control["value"], "status": "unknown",
            "current_value": None, "registry_type": None,
            "writers": [], "error": None,
        }
        try:
            access = win32con.KEY_QUERY_VALUE | win32con.READ_CONTROL
            with winreg.OpenKey(control["root"], control["path"], 0, access) as key:
                try:
                    value, value_type = winreg.QueryValueEx(key, control["value"])
                    finding.update(status="present", current_value=value,
                                   registry_type=value_type)
                except FileNotFoundError:
                    finding["status"] = "value_not_configured"
                finding["writers"] = get_registry_writers(key)

            print(f"[*] {control['name']}")
            print(f"    {full_path}\\{control['value']}")
            if finding["status"] == "present":
                print(f"    Current value: {finding['current_value']!r} "
                      f"(registry type {finding['registry_type']})")
            else:
                print("    Current value: NOT CONFIGURED")
            if finding["writers"]:
                print("    Principals granted write-capable rights:")
                for writer in finding["writers"]:
                    inherited = "inherited" if writer["inherited"] else "explicit"
                    rights = ", ".join(writer["rights"])
                    print(f"      - {writer['principal']} ({writer['sid']}): "
                          f"{rights} [{inherited}]")
            else:
                print("    Principals granted write-capable rights: none found")
        except FileNotFoundError:
            finding["status"] = "key_not_found"
            print(f"[*] {control['name']}: key not found ({full_path})")
        except PermissionError as exc:
            finding.update(status="access_denied", error=str(exc))
            print(f"[-] {control['name']}: access denied ({full_path})")
        except (OSError, win32security.error) as exc:
            finding.update(status="error", error=str(exc))
            print(f"[-] {control['name']}: evaluation error: {exc}")
        findings.append(finding)
    return findings

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

    # Policy hives
    for f in findings.get("policy_hives", []):
        if f["writable"]:
            if "HKLM" in f["path"]:
                score += 25
                details.append(f"CRITICAL: {f['path']} is writable")
            else:
                score += 10
                details.append(f"MEDIUM: {f['path']} is writable")

    # CSE extensions
    for f in findings.get("cse_extensions", []):
        if f["writable"]:
            score += 20
            details.append(f"CRITICAL: Writable CSE extension: {f['path']}")

    # Privileges
    for f in findings.get("privileges", []):
        if f["enabled"]:
            if f["severity"] == "CRITICAL":
                score += 25
                details.append(f"CRITICAL: {f['privilege']} enabled")
            else:
                score += 15
                details.append(f"HIGH: {f['privilege']} enabled")

    # SYSVOL GPOs
    for f in findings.get("sysvol_gpos", []):
        if f.get("writable"):
            score += 30
            display_name = f.get("display_name", f.get("gpo_id", "Unknown GPO"))
            details.append(f"CRITICAL: Writable GPO in SYSVOL: {display_name}")
        
        if f.get("gpp_credentials"):
            gpp = f["gpp_credentials"]
            if gpp.get("encrypted_passwords"):
                score += 25
                details.append(f"CRITICAL: GPP encrypted passwords found in {f.get('display_name', f.get('gpo_id', 'Unknown GPO'))}")
            if gpp.get("plaintext_passwords"):
                score += 35
                details.append(f"CRITICAL: GPP plaintext passwords found in {f.get('display_name', f.get('gpo_id', 'Unknown GPO'))}")

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

    # SYSVOL GPO remediation
    for f in findings.get("sysvol_gpos", []):
        if f.get("writable"):
            gpo_path = f.get("path", "")
            suggestions.append(f"Restrict permissions on SYSVOL GPO: {gpo_path}")
            suggestions.append(f"icacls '{gpo_path}' /remove Everyone /inheritance:r")
            suggestions.append(f"Audit GPO delegation for: {f.get('display_name', f.get('gpo_id', 'Unknown'))}")
        
        if f.get("gpp_credentials"):
            gpp = f["gpp_credentials"]
            if gpp.get("encrypted_passwords") or gpp.get("plaintext_passwords"):
                suggestions.append(f"Remove Group Policy Preferences passwords from GPO: {f.get('display_name', f.get('gpo_id', 'Unknown'))}")
                suggestions.append("Use Group Policy for password management instead of GPP")
                suggestions.append("Rotate all passwords stored in GPP files")

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

    sensitive_value_rows = ""
    for f in findings.get("sensitive_values", []):
        current_value = repr(f["current_value"]) if f["status"] == "present" else f["status"].upper()
        if f["writers"]:
            writers = "<br>".join(
                f"{w['principal']} ({w['sid']}): {', '.join(w['rights'])}"
                f" [{'inherited' if w['inherited'] else 'explicit'}]"
                for w in f["writers"]
            )
        else:
            writers = "None found"
        sensitive_value_rows += (
            f"<tr><td>{f['control']}</td><td>{f['path']}\\{f['value_name']}</td>"
            f"<td>{current_value}</td><td>{writers}</td></tr>"
        )

    # SYSVOL GPO rows
    sysvol_rows = ""
    for f in findings.get("sysvol_gpos", []):
        display_name = f.get("display_name", f.get("gpo_id", "Unknown"))
        status = "VULNERABLE" if f.get("writable") else "SECURE"
        status_class = "vulnerable" if f.get("writable") else "secure"
        badge = f.get("severity", "INFO")
        
        # Add details for writable GPOs
        details = ""
        if f.get("writable_files"):
            details += f"<br><strong>Writable files:</strong> {', '.join([wf['file'] for wf in f['writable_files']])}"
        if f.get("writable_dirs"):
            details += f"<br><strong>Writable dirs:</strong> {', '.join([wd['dir'] for wd in f['writable_dirs']])}"
        if f.get("gpp_credentials"):
            gpp = f["gpp_credentials"]
            if gpp.get("encrypted_passwords"):
                details += f"<br><strong>GPP encrypted passwords:</strong> {len(gpp['encrypted_passwords'])}"
            if gpp.get("plaintext_passwords"):
                details += f"<br><strong>GPP plaintext passwords:</strong> {len(gpp['plaintext_passwords'])}"
        
        sysvol_rows += f"<tr><td>{display_name}</td><td>{f.get('gpo_id', 'N/A')}</td><td class=\"{status_class}\">{status}</td><td><span class=\"badge badge-{badge}\">{badge}</span></td><td>{details or 'None'}</td></tr>"

    # Risk details
    risk_details = "".join([f"<li>{d}</li>" for d in risk_score["details"]])
    
    # Remediation suggestions
    remediation_items = "".join([f"<li><code>{s}</code></li>" for s in suggestions])
    
    # MITRE chain
    mitre_items = "".join([
        f"<li><strong>{phase}</strong>: {data['Technique']}<br><em>{data['Description']}</em></li>"
        for phase, data in MITRE_ATTACK_CHAIN.items()
    ])

    # Domain info for SYSVOL section
    domain_info = get_domain_info()
    sysvol_path = get_sysvol_path(domain_info)
    sysvol_section = ""
    if domain_info.get("is_domain_joined"):
        sysvol_section = f"""
        <h2>SYSVOL GPOs</h2>
        <p><strong>Domain:</strong> {domain_info.get('domain_name', 'N/A')}</p>
        <p><strong>SYSVOL Path:</strong> <code>{sysvol_path or 'N/A'}</code></p>
        <table>
            <tr><th>Display Name</th><th>GPO ID</th><th>Status</th><th>Severity</th><th>Details</th></tr>
            {sysvol_rows or '<tr><td colspan="5">No SYSVOL GPO findings</td></tr>'}
        </table>
        """
    else:
        sysvol_section = f"""
        <h2>SYSVOL GPOs</h2>
        <p><strong>Note:</strong> This machine is not domain-joined. SYSVOL scanning is for domain controllers or domain-joined machines.</p>
        """

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
        code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-family: monospace; }}
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
            <ul>{risk_details or '<li>No risk factors detected</li>'}</ul>
        </div>

        <h2>Findings</h2>
        <h3>Policy Hives</h3>
        <table>
            <tr><th>Key</th><th>Status</th><th>Severity</th></tr>
            {policy_rows or '<tr><td colspan="3">No findings</td></tr>'}
        </table>

        <h3>CSE Extensions</h3>
        <table>
            <tr><th>Key</th><th>Status</th><th>Severity</th></tr>
            {cse_rows or '<tr><td colspan="3">No findings</td></tr>'}
        </table>

        <h3>Privileges</h3>
        <table>
            <tr><th>Privilege</th><th>Status</th><th>Severity</th></tr>
            {priv_rows or '<tr><td colspan="3">No findings</td></tr>'}
        </table>

        <h3>Security-Sensitive Registry Values</h3>
        <table>
            <tr><th>Control</th><th>Registry Value</th><th>Current Value</th><th>Principals with Write Rights</th></tr>
            {sensitive_value_rows or '<tr><td colspan="4">No findings</td></tr>'}
        </table>

        {sysvol_section}

        <h2>Remediation Suggestions</h2>
        <ul>{remediation_items or '<li>No remediation suggestions</li>'}</ul>

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
    
    for f in findings.get("sensitive_values", []):
        value_path = f"{f['path']}\\{f['value_name']}"
        writers = f["writers"] or [{"principal": "None found", "rights": []}]
        for writer in writers:
            all_findings.append({
                "type": "Sensitive Registry Value", "path": value_path,
                "writable": f"{writer['principal']}: {', '.join(writer['rights'])}",
                "severity": f["status"],
            })
    
    # Add SYSVOL GPO findings
    for f in findings.get("sysvol_gpos", []):
        display_name = f.get("display_name", f.get("gpo_id", "Unknown"))
        all_findings.append({
            "type": "SYSVOL GPO",
            "path": display_name,
            "writable": f.get("writable", False),
            "severity": f.get("severity", "INFO")
        })
        
        # Add individual writable files
        for wf in f.get("writable_files", []):
            all_findings.append({
                "type": "GPO Writable File",
                "path": wf.get("path", ""),
                "writable": True,
                "severity": "CRITICAL"
            })
        
        # Add GPP credentials
        if f.get("gpp_credentials"):
            gpp = f["gpp_credentials"]
            if gpp.get("encrypted_passwords"):
                all_findings.append({
                    "type": "GPP Encrypted Password",
                    "path": display_name,
                    "writable": True,
                    "severity": "CRITICAL"
                })
            if gpp.get("plaintext_passwords"):
                all_findings.append({
                    "type": "GPP Plaintext Password",
                    "path": display_name,
                    "writable": True,
                    "severity": "CRITICAL"
                })

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

    # New phase for GPO tampering
    print("\n[Phase 6] GPO Tampering (T1484.001)")
    sysvol_findings = findings.get("sysvol_gpos", [])
    writable_gpos = [f for f in sysvol_findings if f.get("writable")]
    gpp_gpos = [f for f in sysvol_findings if f.get("gpp_credentials")]
    
    if writable_gpos or gpp_gpos:
        has_vulnerability = True
        if writable_gpos:
            print("  FOUND: Writable GPO(s) in SYSVOL")
            for gpo in writable_gpos:
                display_name = gpo.get("display_name", gpo.get("gpo_id", "Unknown"))
                print(f"      - {display_name} ({gpo.get('gpo_id', 'N/A')})")
            print("  -> Attackers can modify GPO files to deploy malicious policies")
        
        if gpp_gpos:
            print("  FOUND: GPP files with credentials")
            for gpo in gpp_gpos:
                display_name = gpo.get("display_name", gpo.get("gpo_id", "Unknown"))
                gpp = gpo["gpp_credentials"]
                if gpp.get("encrypted_passwords"):
                    print(f"      - {display_name}: {len(gpp['encrypted_passwords'])} encrypted password(s)")
                if gpp.get("plaintext_passwords"):
                    print(f"      - {display_name}: {len(gpp['plaintext_passwords'])} plaintext password(s)")
            print("  -> Attackers can decrypt GPP passwords to gain credentials")
    else:
        print("  No writable GPOs or GPP credentials found - attack blocked")

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
    parser.add_argument("--scan-sysvol", action="store_true", help="Scan SYSVOL for GPO files and permissions")
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
    print(f"[i] Scan SYSVOL: {args.scan_sysvol}")
    print("\n")

    # Run audits
    policy_findings = audit_policy_hives()
    cse_findings = audit_cse_extensions()
    priv_findings = audit_token_privileges()
    sensitive_value_findings = audit_sensitive_registry_values()
    
    # SYSVOL GPO audit
    sysvol_findings = []
    if args.scan_sysvol:
        domain_info = get_domain_info()
        sysvol_path = get_sysvol_path(domain_info)
        
        if domain_info.get("is_domain_joined") and sysvol_path:
            print(f"\n[i] Domain: {domain_info['domain_name']}")
            print(f"[i] SYSVOL Path: {sysvol_path}")
            sysvol_findings = audit_sysvol_gpos(sysvol_path)
        else:
            print("\n[!] Machine is not domain-joined. Skipping SYSVOL scan.")
            print("    Use --scan-sysvol on a domain controller or domain-joined machine.")

    # Compile findings
    findings = {
        "policy_hives": policy_findings,
        "cse_extensions": cse_findings,
        "privileges": priv_findings,
        "sensitive_values": sensitive_value_findings,
        "sysvol_gpos": sysvol_findings,
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
    print(f"[!] Vulnerable SYSVOL GPOs: {sum(1 for f in sysvol_findings if f.get('writable'))}")
    print(f"[!] GPOs with GPP Credentials: {sum(1 for f in sysvol_findings if f.get('gpp_credentials'))}")
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
