#!/usr/bin/env python3

import socket
import sys
import os
import urllib.parse
import time
from pathlib import Path
from datetime import datetime

def main():
    if len(sys.argv) != 2:
        print("Usage: python file_server.py <directory_to_serve>")
        sys.exit(1)
    
    serve_directory = sys.argv[1]
    if not os.path.isdir(serve_directory):
        print(f"Error: {serve_directory} is not a valid directory")
        sys.exit(1)
    
    print(f"Serving files from: {os.path.abspath(serve_directory)}")
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    host = '0.0.0.0'
    port = 8080
    server_socket.bind((host, port))
    
    print(f"Server starting on {host}:{port}")
    server_socket.listen(5)
    print("Server is listening for connections... (Press Ctrl+C to exit)")
    
    server_socket.settimeout(1.0)
    
    try:
        while True:
            try:
                client_socket, client_address = server_socket.accept()
                print(f"Connection from {client_address}")
                handle_request(client_socket, serve_directory)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error: {e}")
    except KeyboardInterrupt:
        print("\nServer shutting down...")
    finally:
        server_socket.close()

def handle_request(client_socket, serve_directory):
    try:
        request_data = client_socket.recv(1024).decode('utf-8')
        
        if not request_data:
            return
        
        request_lines = request_data.split('\n')
        request_line = request_lines[0].strip()
        print(f"Request: {request_line}")
        
        parts = request_line.split(' ')
        if len(parts) < 2:
            send_error_response(client_socket, 400, "Bad Request")
            return
        
        method = parts[0]
        path = parts[1]
        
        if method != 'GET':
            send_error_response(client_socket, 405, "Method Not Allowed")
            return
        
        time.sleep(1)
        
        serve_file(client_socket, path, serve_directory)
        
    except Exception as e:
        print(f"Error handling request: {e}")
        send_error_response(client_socket, 500, "Internal Server Error")
    finally:
        client_socket.close()

def serve_file(client_socket, requested_path, serve_directory):
    if requested_path.startswith('/'):
        requested_path = requested_path[1:]
    
    if not requested_path:
        requested_path = '.'
    
    file_path = os.path.join(serve_directory, requested_path)
    
    try:
        real_file_path = os.path.realpath(file_path)
        real_serve_dir = os.path.realpath(serve_directory)
        
        if not real_file_path.startswith(real_serve_dir):
            send_error_response(client_socket, 403, "Forbidden")
            return
    except:
        send_error_response(client_socket, 400, "Bad Request")
        return
    
    if not os.path.exists(file_path):
        send_error_response(client_socket, 404, "Not Found")
        return
    
    if os.path.isdir(file_path):
        serve_directory_listing(client_socket, file_path, requested_path)
    else:
        serve_single_file(client_socket, file_path)

def serve_single_file(client_socket, file_path):
    content_type = get_content_type(file_path)
    
    if content_type is None:
        print(f"Not Found: {file_path}")
        send_error_response(client_socket, 404, "Not Found")
        return
    
    try:
        if content_type.startswith('text/'):
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            send_response(client_socket, 200, content_type, file_content)
        else:
            with open(file_path, 'rb') as f:
                file_content = f.read()
            send_binary_response(client_socket, 200, content_type, file_content)
            
        print(f"Served file: {file_path} ({content_type})")
        
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        send_error_response(client_socket, 500, "Internal Server Error")

def serve_directory_listing(client_socket, dir_path, requested_path):
    try:
        entries = os.listdir(dir_path)
        entries.sort()
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Directory listing for /{requested_path}</title>
    <style>
        body {{ font-family: monospace; }}
        a {{ text-decoration: none; color: blue; }}
        a:hover {{ text-decoration: underline; }}
        .directory {{ font-weight: bold; }}
        .file {{ }}
    </style>
</head>
<body>
    <h1>Directory listing for /{requested_path}</h1>
    <hr>
    <ul>
"""
        
        if requested_path != '.':
            parent_path = os.path.dirname(requested_path) if requested_path != '.' else ''
            html_content += f'        <li><a href="/{parent_path}" class="directory">../</a></li>\n'
        
        for entry in entries:
            entry_path = os.path.join(dir_path, entry)
            if requested_path == '.':
                url_path = entry
            else:
                url_path = f"{requested_path}/{entry}"
            
            if os.path.isdir(entry_path):
                html_content += f'        <li><a href="/{url_path}/" class="directory">{entry}/</a></li>\n'
            else:
                html_content += f'        <li><a href="/{url_path}" class="file">{entry}</a></li>\n'
        
        html_content += """    </ul>
    <hr>
</body>
</html>"""
        
        send_response(client_socket, 200, "text/html", html_content)
        print(f"Served directory listing: {dir_path}")
        
    except Exception as e:
        print(f"Error creating directory listing for {dir_path}: {e}")
        send_error_response(client_socket, 500, "Internal Server Error")

def get_content_type(file_path):
    extension = os.path.splitext(file_path)[1].lower()
    
    mime_types = {
        '.html': 'text/html',
        '.htm': 'text/html',
        '.png': 'image/png',
        '.pdf': 'application/pdf'
    }
    
    return mime_types.get(extension)

def send_response(client_socket, status_code, content_type, body):
    status_text = get_status_text(status_code)
    response_headers = f"HTTP/1.1 {status_code} {status_text}\r\n"
    response_headers += f"Content-Type: {content_type}\r\n"
    response_headers += f"Content-Length: {len(body.encode('utf-8'))}\r\n"
    response_headers += "Connection: close\r\n\r\n"
    
    response = response_headers + body
    client_socket.send(response.encode('utf-8'))

def send_binary_response(client_socket, status_code, content_type, body_bytes):
    status_text = get_status_text(status_code)
    response_headers = f"HTTP/1.1 {status_code} {status_text}\r\n"
    response_headers += f"Content-Type: {content_type}\r\n"
    response_headers += f"Content-Length: {len(body_bytes)}\r\n"
    response_headers += "Connection: close\r\n\r\n"
    
    client_socket.send(response_headers.encode('utf-8'))
    client_socket.send(body_bytes)

def send_error_response(client_socket, status_code, status_text):
    body = f"<html><body><h1>{status_code} {status_text}</h1></body></html>"
    send_response(client_socket, status_code, "text/html", body)

def get_status_text(status_code):
    status_texts = {
        200: "OK",
        400: "Bad Request",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        500: "Internal Server Error"
    }
    return status_texts.get(status_code, "Unknown")

if __name__ == "__main__":
    main()