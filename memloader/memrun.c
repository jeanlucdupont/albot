#include <windows.h>

// Option 1: Simple exports
__declspec(dllexport) void ShowMessage() {
    MessageBoxA(NULL, "Hello from exported function!", "Memory Loader", MB_OK);
}

__declspec(dllexport) int AddNumbers(int a, int b) {
    return a + b;
}

__declspec(dllexport) void ExecutePayload() {
    // Example payload function
    MessageBoxA(NULL, "Payload executed from memory!", "Memory Loader", MB_OK);
    
    // You can add more sophisticated code here
    // CreateThread, file operations, network connections, etc.
}

// DllMain - entry point
BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID lpReserved) {
    switch (reason) {
        case DLL_PROCESS_ATTACH:
            // Disable thread notifications for performance
            DisableThreadLibraryCalls(hModule);
            
            // This runs immediately when DLL is loaded
            MessageBoxA(NULL, "DLL successfully loaded in memory!\n\n", "Memory Loader PoC", MB_OK);
            break;
            
        case DLL_PROCESS_DETACH:
            // Cleanup if needed
            break;
    }
    return TRUE;
}
