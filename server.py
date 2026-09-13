#!/usr/bin/env python3
import os
import json
import http.server
import socketserver
from datetime import datetime, timedelta
import caldav
from icalendar import Calendar, Event
import pytz

ICLOUD_USERNAME = os.environ.get('ICLOUD_USERNAME', '')
ICLOUD_PASSWORD = os.environ.get('ICLOUD_APP_PASSWORD', '')
MCP_PORT = int(os.environ.get('MCP_PORT', '3457'))
CALDAV_URL = 'https://caldav.icloud.com'

def get_calendar_client():
    if not ICLOUD_USERNAME or not ICLOUD_PASSWORD:
        raise Exception("Missing iCloud credentials")
    client = caldav.DAVClient(url=CALDAV_URL, username=ICLOUD_USERNAME, password=ICLOUD_PASSWORD)
    return client

def get_primary_calendar():
    client = get_calendar_client()
    principal = client.principal()
    calendars = principal.calendars()
    if not calendars:
        raise Exception("No calendars found")
    return calendars[0]

def search_events(start_date=None, end_date=None, keyword=None):
    calendar = get_primary_calendar()
    if not start_date:
        start_date = datetime.now(pytz.UTC)
    if not end_date:
        end_date = start_date + timedelta(days=30)
    events = calendar.date_search(start=start_date, end=end_date, expand=True)
    results = []
    for event in events:
        ical = Calendar.from_ical(event.data)
        for component in ical.walk():
            if component.name == "VEVENT":
                summary = str(component.get('summary', ''))
                if keyword and keyword.lower() not in summary.lower():
                    continue
                start = component.get('dtstart').dt
                end = component.get('dtend').dt if component.get('dtend') else start
                location = str(component.get('location', ''))
                description = str(component.get('description', ''))
                uid = str(component.get('uid', ''))
                results.append({
                    'uid': uid,
                    'summary': summary,
                    'start': start.isoformat() if isinstance(start, datetime) else str(start),
                    'end': end.isoformat() if isinstance(end, datetime) else str(end),
                    'location': location,
                    'description': description
                })
    return results

def get_events_by_range(days_from_now=0, days_count=1):
    start = datetime.now(pytz.UTC) + timedelta(days=days_from_now)
    end = start + timedelta(days=days_count)
    return search_events(start_date=start, end_date=end)

def create_event(summary, start_time, end_time=None, location='', description=''):
    calendar = get_primary_calendar()
    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    if end_time:
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    else:
        end_time = start_time + timedelta(hours=1)
    cal = Calendar()
    event = Event()
    event.add('summary', summary)
    event.add('dtstart', start_time)
    event.add('dtend', end_time)
    if location:
        event.add('location', location)
    if description:
        event.add('description', description)
    event.add('uid', f"{datetime.now().timestamp()}@mcp-calendar")
    event.add('dtstamp', datetime.now(pytz.UTC))
    cal.add_component(event)
    calendar.save_event(cal.to_ical())
    return {'success': True, 'summary': summary, 'start': start_time.isoformat(), 'end': end_time.isoformat()}

def delete_event(uid):
    calendar = get_primary_calendar()
    events = calendar.events()
    for event in events:
        ical = Calendar.from_ical(event.data)
        for component in ical.walk():
            if component.name == "VEVENT":
                event_uid = str(component.get('uid', ''))
                if event_uid == uid:
                    event.delete()
                    return {'success': True, 'uid': uid}
    return {'success': False, 'error': 'Event not found'}

def get_reminders():
    client = get_calendar_client()
    principal = client.principal()
    calendars = principal.calendars()
    reminders = []
    for cal in calendars:
        try:
            todos = cal.todos(include_completed=False)
            for todo in todos:
                ical = Calendar.from_ical(todo.data)
                for component in ical.walk():
                    if component.name == "VTODO":
                        summary = str(component.get('summary', ''))
                        due = component.get('due')
                        priority = component.get('priority', 0)
                        status = str(component.get('status', 'NEEDS-ACTION'))
                        uid = str(component.get('uid', ''))
                        reminders.append({'uid': uid, 'summary': summary, 'due': due.dt.isoformat() if due else None, 'priority': int(priority), 'status': status, 'calendar': cal.name})
        except:
            continue
    return reminders

MCP_TOOLS = [
    {"name": "get_events", "description": "Get calendar events for a specific date range", "inputSchema": {"type": "object", "properties": {"days_from_now": {"type": "integer", "description": "Days offset from today"}, "days_count": {"type": "integer", "description": "Number of days to fetch"}}}},
    {"name": "search_events", "description": "Search calendar events by keyword", "inputSchema": {"type": "object", "properties": {"keyword": {"type": "string", "description": "Keyword to search"}, "days_from_now": {"type": "integer"}, "days_count": {"type": "integer"}}, "required": ["keyword"]}},
    {"name": "create_event", "description": "Create a new calendar event", "inputSchema": {"type": "object", "properties": {"summary": {"type": "string"}, "start_time": {"type": "string"}, "end_time": {"type": "string"}, "location": {"type": "string"}, "description": {"type": "string"}}, "required": ["summary", "start_time"]}},
    {"name": "delete_event", "description": "Delete a calendar event by UID", "inputSchema": {"type": "object", "properties": {"uid": {"type": "string"}}, "required": ["uid"]}},
    {"name": "get_reminders", "description": "Get all active reminders", "inputSchema": {"type": "object", "properties": {}}}
]

def handle_tool_call(tool_name, arguments):
    try:
        if tool_name == "get_events":
            events = get_events_by_range(arguments.get('days_from_now', 0), arguments.get('days_count', 1))
            return {"content": [{"type": "text", "text": json.dumps(events, indent=2, ensure_ascii=False)}]}
        elif tool_name == "search_events":
            keyword = arguments.get('keyword')
            days_from = arguments.get('days_from_now', 0)
            days_count = arguments.get('days_count', 30)
            start = datetime.now(pytz.UTC) + timedelta(days=days_from)
            end = start + timedelta(days=days_count)
            events = search_events(start_date=start, end_date=end, keyword=keyword)
            return {"content": [{"type": "text", "text": json.dumps(events, indent=2, ensure_ascii=False)}]}
        elif tool_name == "create_event":
            result = create_event(arguments['summary'], arguments['start_time'], arguments.get('end_time'), arguments.get('location', ''), arguments.get('description', ''))
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
        elif tool_name == "delete_event":
            result = delete_event(arguments['uid'])
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
        elif tool_name == "get_reminders":
            reminders = get_reminders()
            return {"content": [{"type": "text", "text": json.dumps(reminders, indent=2, ensure_ascii=False)}]}
        else:
            return {"content": [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {tool_name}"})}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}], "isError": True}

class MCPHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/mcp':
            self.send_error(404)
            return
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            request = json.loads(body)
            method = request.get('method')
            if method == 'initialize':
                response = {"jsonrpc": "2.0", "id": request.get('id'), "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "apple-calendar-mcp", "version": "1.0.0"}}}
            elif method == 'tools/list':
                response = {"jsonrpc": "2.0", "id": request.get('id'), "result": {"tools": MCP_TOOLS}}
            elif method == 'tools/call':
                params = request.get('params', {})
                result = handle_tool_call(params.get('name'), params.get('arguments', {}))
                response = {"jsonrpc": "2.0", "id": request.get('id'), "result": result}
            else:
                response = {"jsonrpc": "2.0", "id": request.get('id'), "error": {"code": -32601, "message": f"Method not found: {method}"}}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
        except Exception as e:
            error_response = {"jsonrpc": "2.0", "id": request.get('id') if 'request' in locals() else None, "error": {"code": -32603, "message": str(e)}}
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    def log_message(self, format, *args):
        pass

def main():
    print(f"Apple Calendar MCP Server v1.0")
    print(f"Listening on port {MCP_PORT}")
    with socketserver.TCPServer(("", MCP_PORT), MCPHandler) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    main()
