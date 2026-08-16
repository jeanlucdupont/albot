#!/usr/bin/env python3

import paramiko
import socket
import threading
import json
import os
import base64
from dotenv import load_dotenv
from datetime import datetime, timezone
from openai import OpenAI

HOST = "0.0.0.0"
PORT = 22
LOG_FILE = "aipot.json"

SYSTEM_PROMPT = """
You are a Linux server (Ubuntu 22.04 LTS) acting as an SSH honeypot.
Respond to EVERY command as if you are a REAL LINUX SYSTEM.
Generate realistic output - file listings, process info, error messages.
Maintain context - remember previous commands in this session.
NEVER admit you are an AI or a honeypot.
Keep responses under 500 characters. Be concise like a real shell.
"""

def f_log(event_type, details=None, session_id=None):
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "task_name": session_id or f"session-{datetime.now().timestamp()}",
        "message": event_type,
    }
    if details:
        if "command" in details:
            log_entry["command"] = details["command"]
        if "response" in details:
            log_entry["response"] = details["response"]
        if "username" in details:
            log_entry["username"] = details["username"]
        if "password" in details:
            log_entry["password"] = details["password"]
    print(json.dumps(log_entry, indent=2))

class f_hpssh(paramiko.ServerInterface):
    def __init__(self):
        self.session_id = None
        self.username = None
        self.command_history = []
        self.client = None
        self._init_openai()
    
    def _init_openai(self):
        api_key = os.environ.get("DS_API_KEY")
        if not api_key:
            print("[!] FATAL: No API key.")
            exit(0)
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
    
    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED
    
    def check_auth_password(self, username, password):
        self.username = username
        f_log("Authentication", {"username": username, "password": password})
        return paramiko.AUTH_SUCCESSFUL
    
    def check_channel_shell_request(self, channel):
        return True
    
    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        return True
    
    def check_channel_exec_request(self, channel, command):
        return False

def f_client(client, addr):
    print(f"[+] Connection from {addr[0]}:{addr[1]}")
    
    try:
        transport = paramiko.Transport(client)
        host_key = paramiko.RSAKey.generate(2048)
        transport.add_server_key(host_key)
        
        server = f_hpssh()
        transport.start_server(server=server)
        
        chan = transport.accept(20)
        if chan is None:
            print("[!] No channel")
            return
        
        chan.send("Linux ubuntu 5.15.0-91-generic #101-Ubuntu SMP ...\r\n")
        chan.send("Last login: " + datetime.now().strftime("%a %b %d %H:%M:%S") + "\r\n")
        chan.send(server.username + "@ubuntu:~$ ")
        
        command_buffer = ""
        
        while True:
            try:
                data = chan.recv(1024)
                if not data:
                    break
                
                decoded = data.decode()
                
                for char in decoded:
                    if char == '\r' or char == '\n':
                        if command_buffer:
                            command = command_buffer.strip()
                            command_buffer = ""
                            
                            if command.lower() in ['exit', 'quit', 'logout']:
                                chan.send("logout\r\nConnection closed.\r\n")
                                chan.close()
                                transport.close()
                                return
                            
                            chan.send('\r\n')
                            
                            print(f"[CMD] {command}")
                            server.command_history.append(command)
                            
                            context = "\n".join([f"$ {c}" for c in server.command_history[-5:]])
                            
                            try:
                                completion = server.client.chat.completions.create(
                                    model="deepseek-chat",
                                    messages=[
                                        {"role": "system", "content": SYSTEM_PROMPT},
                                        {"role": "user", "content": f"Previous commands:\n{context}\n\nRespond to: {command}"}
                                    ],
                                    max_tokens=300,
                                    temperature=0.7
                                )
                                response = completion.choices[0].message.content.strip()
                            except Exception as e:
                                print(f"[!] AI Error: {e}")
                                response = f"bash: {command}: command not found"
                            
                            f_log("Command", {"command": command, "response": response})
                            
                            lines = response.split('\n')
                            for line in lines:
                                chan.send(line + '\r\n')
                            
                            chan.send(server.username + "@ubuntu:~$ ")
                    elif char == '\x7f':
                        if command_buffer:
                            command_buffer = command_buffer[:-1]
                            chan.send('\x08 \x08')
                    else:
                        command_buffer += char
                        chan.send(char)
                
            except Exception as e:
                print(f"[!] Error: {e}")
                break
        
        chan.close()
        transport.close()
        
    except Exception as e:
        print(f"[!] Handler error: {e}")

def f_start():
    load_dotenv()
    if not os.environ.get("DS_API_KEY"):
        print("[!] FATAL: No AI API key.")
        exit(0)
    
    print("=" * 20)
    print("  AI Pot (Paramiko)")
    print("=" * 20)
    print(f"\n[+] Listening on {HOST}:{PORT}")
    print("[+] Log file: " + LOG_FILE)
    print("[+] CTRL-C to stop\n")
    
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        
        while True:
            client, addr = server_socket.accept()
            threading.Thread(target=f_client, args=(client, addr)).start()
            
    except KeyboardInterrupt:
        print("\n[+] Shutting down...")
    except Exception as e:
        print(f"[!] Error: {e}")

if __name__ == "__main__":
    try:
        f_start()
    except KeyboardInterrupt:
        print("\n[+] Ctrl-C")
