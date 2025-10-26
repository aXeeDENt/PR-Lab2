import socket
import sys
import os
import urllib.parse

def main():
    if len(sys.argv) != 5:
        print("Usage: python client.py server_host server_port url_path save_directory")
        sys.exit(1)
    
    server_host = sys.argv[1]
    server_port = int(sys.argv[2])
    url_path = sys.argv[3]
    save_directory = sys.argv[4]
    
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)
    
    make_request(server_host, server_port, url_path, save_directory)

def make_request(server_host, server_port, url_path, save_directory):
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((server_host, server_port))
        
        request = f"GET {url_path} HTTP/1.1\r\nHost: {server_host}:{server_port}\r\nConnection: close\r\n\r\n"
        client_socket.send(request.encode('utf-8'))
        
        response_data = b""
        while True:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            response_data += chunk
        
        client_socket.close()
        
        parse_response(response_data, url_path, save_directory)
        
    except Exception as e:
        print(f"Error making request: {e}")

def parse_response(response_data, url_path, save_directory):
    try:
        response_str = response_data.decode('utf-8', errors='ignore')
        
        header_end = response_str.find('\r\n\r\n')
        if header_end == -1:
            print("Invalid HTTP response")
            return
        
        headers = response_str[:header_end]
        body_start = header_end + 4
        
        header_lines = headers.split('\r\n')
        status_line = header_lines[0]
        print(f"Status: {status_line}")
        
        status_parts = status_line.split(' ', 2)
        if len(status_parts) < 2:
            print("Invalid status line")
            return
            
        status_code = int(status_parts[1])
        if status_code != 200:
            print(f"Error: HTTP {status_code}")
            body = response_str[body_start:]
            print(body)
            return
        
        content_type = "text/html"
        for line in header_lines[1:]:
            if line.lower().startswith('content-type:'):
                content_type = line.split(':', 1)[1].strip()
                break
        
        print(f"Content-Type: {content_type}")
        
        if content_type.startswith('text/html'):
            body = response_str[body_start:]
            print("HTML Content:")
            print(body)
            
        elif content_type == 'image/png' or content_type == 'application/pdf':
            body_bytes = response_data[body_start:]
            filename = os.path.basename(url_path) or "downloaded_file"
            if not filename:
                filename = "index.html" if content_type == "text/html" else "file"
                
            filepath = os.path.join(save_directory, filename)
            
            with open(filepath, 'wb') as f:
                f.write(body_bytes)
            
            print(f"File saved to: {filepath}")
            print(f"File type: {content_type}")
            print(f"File size: {len(body_bytes)} bytes")
            
        else:
            print(f"Unsupported file type: {content_type}")
            print("Server only supports HTML, PNG, and PDF files.")
        
    except Exception as e:
        print(f"Error parsing response: {e}")

if __name__ == "__main__":
    main()
