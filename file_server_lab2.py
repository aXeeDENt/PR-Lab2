

import socket
import sys
import os
import threading
import time
from queue import Queue
from pathlib import Path
from collections import defaultdict
from datetime import datetime

class ThreadPool:
    
    def __init__(self, num_threads=4):
        self.num_threads = num_threads
        self.task_queue = Queue()
        self.threads = []
        self.is_running = True
        
        self.tasks_completed = 0
        self.tasks_lock = threading.Lock()
        
        print(f"[ThreadPool] Creating pool with {num_threads} workers")
        
        for i in range(num_threads):
            thread = threading.Thread(target=self._worker, args=(i,), daemon=True)
            thread.start()
            self.threads.append(thread)
    
    def _worker(self, worker_id):
        while self.is_running:
            try:
                task = self.task_queue.get(timeout=1)
                
                if task is None: 
                    break
                
                func, args = task
                
                try:
                    func(*args)
                    with self.tasks_lock:
                        self.tasks_completed += 1
                except Exception as e:
                    print(f"[Worker-{worker_id}] Error: {e}")
                finally:
                    self.task_queue.task_done()
                    
            except:
                continue
    
    def submit(self, func, *args):
        self.task_queue.put((func, args))
    
    def get_queue_size(self):
        return self.task_queue.qsize()
    
    def shutdown(self):
        print("\n[ThreadPool] Shutting down...")
        self.is_running = False
        
        for _ in range(self.num_threads):
            self.task_queue.put(None)
        
        for thread in self.threads:
            thread.join(timeout=2)
        
        print(f"[ThreadPool] Shutdown complete. Total tasks: {self.tasks_completed}")

class HTTPFileServer:
    
    def __init__(self, serve_directory, host='0.0.0.0', port=8080, 
                 num_threads=4, simulate_work_delay=0, use_locks=True,
                 enable_rate_limiting=False, rate_limit=5):
        self.serve_directory = os.path.abspath(serve_directory)
        self.host = host
        self.port = port
        self.simulate_work_delay = simulate_work_delay
        self.use_locks = use_locks
        self.enable_rate_limiting = enable_rate_limiting
        self.rate_limit = rate_limit
        
        self.request_counter = defaultdict(int)
        self.counter_lock = threading.Lock() 
        
        self.ip_requests = defaultdict(list)  
        self.rate_limit_lock = threading.Lock()  
        
        self.total_requests = 0
        self.blocked_requests = 0
        self.stats_lock = threading.Lock()
        
        self.thread_pool = ThreadPool(num_threads=num_threads)
        
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.settimeout(1.0)
        
        print(f"\n[Server] Configuration:")
        print(f"  - Serving from: {self.serve_directory}")
        print(f"  - Address: {self.host}:{self.port}")
        print(f"  - Thread pool size: {num_threads}")
        print(f"  - Work delay: {simulate_work_delay}s")
        print(f"  - Thread-safe locks: {'ENABLED' if use_locks else 'DISABLED (RACE CONDITION!)'}")
        print(f"  - Rate limiting: {'ENABLED' if enable_rate_limiting else 'DISABLED'}")
        if enable_rate_limiting:
            print(f"  - Rate limit: {rate_limit} req/sec per IP")
    
    def start(self):
        self.server_socket.listen(5)
        print(f"\n[Server] Listening on {self.host}:{self.port}")
        print("[Server] Press Ctrl+C to stop\n")
        
        try:
            while True:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    
                    self.thread_pool.submit(
                        self.handle_request, 
                        client_socket, 
                        client_address
                    )
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[Server] Error accepting connection: {e}")
                    
        except KeyboardInterrupt:
            print("\n[Server] Keyboard interrupt received")
        finally:
            self.shutdown()
    
    def handle_request(self, client_socket, client_address):
        start_time = time.time()
        client_ip = client_address[0]
        
        try:
            if self.enable_rate_limiting:
                if not self._check_rate_limit(client_ip):
                    with self.stats_lock:
                        self.blocked_requests += 1
                    self.send_error_response(client_socket, 429, "Too Many Requests")
                    print(f"[{client_ip}] RATE LIMITED")
                    return
            
            with self.stats_lock:
                self.total_requests += 1
            
            if self.simulate_work_delay > 0:
                time.sleep(self.simulate_work_delay)
            
            request_data = client_socket.recv(1024).decode('utf-8')
            
            if not request_data:
                return
            
            request_lines = request_data.split('\n')
            request_line = request_lines[0].strip()
            
            parts = request_line.split(' ')
            if len(parts) < 2:
                self.send_error_response(client_socket, 400, "Bad Request")
                return
            
            method = parts[0]
            path = parts[1]
            
            if method != 'GET':
                self.send_error_response(client_socket, 405, "Method Not Allowed")
                return
            
            self.serve_file(client_socket, path, client_ip)
            
            elapsed = time.time() - start_time
            print(f"[{client_ip}] {method} {path} - {elapsed:.3f}s")
            
        except Exception as e:
            print(f"[{client_ip}] Error: {e}")
            try:
                self.send_error_response(client_socket, 500, "Internal Server Error")
            except:
                pass
        finally:
            client_socket.close()
    
    def _check_rate_limit(self, client_ip):
        """
        Check if client IP is within rate limit.
        Thread-safe implementation.
        
        Returns:
            True if request allowed, False if rate limited
        """
        current_time = time.time()
        
        with self.rate_limit_lock:
            timestamps = self.ip_requests[client_ip]
            
            timestamps = [ts for ts in timestamps if current_time - ts < 1.0]
            
            if len(timestamps) >= self.rate_limit:
                return False
            
            timestamps.append(current_time)
            self.ip_requests[client_ip] = timestamps
            
            return True
    
    def _increment_counter(self, path):

        if self.use_locks:
            with self.counter_lock:
                current_value = self.request_counter[path]
                time.sleep(0.002) 
                self.request_counter[path] = current_value + 1
        else:
            current_value = self.request_counter[path]
            time.sleep(0.002)
            self.request_counter[path] = current_value + 1
    
    def serve_file(self, client_socket, requested_path, client_ip):
        """Serve a file or directory listing."""
        if requested_path.startswith('/'):
            requested_path = requested_path[1:]
        
        if not requested_path:
            requested_path = '.'
        
        self._increment_counter(requested_path)
        
        file_path = os.path.join(self.serve_directory, requested_path)
        
        try:
            real_file_path = os.path.realpath(file_path)
            real_serve_dir = os.path.realpath(self.serve_directory)
            
            if not real_file_path.startswith(real_serve_dir):
                self.send_error_response(client_socket, 403, "Forbidden")
                return
        except:
            self.send_error_response(client_socket, 400, "Bad Request")
            return
        
        if not os.path.exists(file_path):
            self.send_error_response(client_socket, 404, "Not Found")
            return
        
        if os.path.isdir(file_path):
            self.serve_directory_listing(client_socket, file_path, requested_path)
        else:
            self.serve_single_file(client_socket, file_path)
    
    def serve_single_file(self, client_socket, file_path):
        content_type = self.get_content_type(file_path)
        
        if content_type is None:
            self.send_error_response(client_socket, 404, "Not Found")
            return
        
        try:
            if content_type.startswith('text/'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                self.send_response(client_socket, 200, content_type, file_content)
            else:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                self.send_binary_response(client_socket, 200, content_type, file_content)
        except Exception as e:
            print(f"[Server] Error reading file {file_path}: {e}")
            self.send_error_response(client_socket, 500, "Internal Server Error")
    
    def serve_directory_listing(self, client_socket, dir_path, requested_path):
        try:
            entries = os.listdir(dir_path)
            entries.sort()
            
            lock_status = "THREAD-SAFE" if self.use_locks else "RACE CONDITION"
            
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Directory listing for /{requested_path}</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        .stats {{ background: #e7f3ff; padding: 10px; border-radius: 5px; margin: 10px 0; }}
        .stats-item {{ display: inline-block; margin-right: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th {{ background: #007bff; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f8f9fa; }}
        a {{ text-decoration: none; color: #007bff; }}
        a:hover {{ text-decoration: underline; }}
        .directory {{ font-weight: bold; }}
        .count {{ background: #28a745; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; }}
        .lock-status {{ float: right; padding: 5px 10px; border-radius: 5px; font-size: 14px; }}
        .safe {{ background: #28a745; color: white; }}
        .unsafe {{ background: #dc3545; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Directory: /{requested_path}
            <span class="lock-status {'safe' if self.use_locks else 'unsafe'}">{lock_status}</span>
        </h1>
        
        <div class="stats">
            <div class="stats-item"><strong>Total Requests:</strong> {self.total_requests - 1}</div>
            <div class="stats-item"><strong>Blocked:</strong> {self.blocked_requests}</div>
            <div class="stats-item"><strong>Queue:</strong> {self.thread_pool.get_queue_size()}</div>
        </div>
        
        <table>
            <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Requests</th>
            </tr>
"""
            
            # Parent directory
            if requested_path != '.':
                parent_path = os.path.dirname(requested_path) if requested_path != '.' else ''
                parent_count = self.request_counter.get(parent_path, 0)
                html_content += f"""
            <tr>
                <td><a href="/{parent_path}" class="directory"> ../</a></td>
                <td>Directory</td>
                <td><span class="count">{parent_count}</span></td>
            </tr>
"""
            
            # Entries
            for entry in entries:
                entry_path = os.path.join(dir_path, entry)
                if requested_path == '.':
                    url_path = entry
                else:
                    url_path = f"{requested_path}/{entry}"
                
                count = self.request_counter.get(url_path, 0)
                
                if os.path.isdir(entry_path):
                    html_content += f"""
            <tr>
                <td><a href="/{url_path}/" class="directory"> {entry}</a></td>
                <td>Directory</td>
                <td><span class="count">{count}</span></td>
            </tr>
"""
                else:
                    html_content += f"""
            <tr>
                <td><a href="/{url_path}"> {entry}</a></td>
                <td>File</td>
                <td><span class="count">{count}</span></td>
            </tr>
"""
            
            html_content += """
        </table>
        <p style="color: #666; margin-top: 20px; font-size: 12px;">
            Lab 2: Multithreaded HTTP Server with Thread Pool
        </p>
    </div>
</body>
</html>"""
            
            self.send_response(client_socket, 200, "text/html", html_content)
        except Exception as e:
            print(f"[Server] Error creating directory listing: {e}")
            self.send_error_response(client_socket, 500, "Internal Server Error")
    
    def get_content_type(self, file_path):
        extension = os.path.splitext(file_path)[1].lower()
        
        mime_types = {
            '.html': 'text/html',
            '.htm': 'text/html',
            '.png': 'image/png',
            '.pdf': 'application/pdf',
            '.txt': 'text/plain'
        }
        
        return mime_types.get(extension)
    
    def send_response(self, client_socket, status_code, content_type, body):
        status_text = self.get_status_text(status_code)
        response_headers = f"HTTP/1.1 {status_code} {status_text}\r\n"
        response_headers += f"Content-Type: {content_type}\r\n"
        response_headers += f"Content-Length: {len(body.encode('utf-8'))}\r\n"
        response_headers += "Connection: close\r\n\r\n"
        
        response = response_headers + body
        client_socket.send(response.encode('utf-8'))
    
    def send_binary_response(self, client_socket, status_code, content_type, body_bytes):
        status_text = self.get_status_text(status_code)
        response_headers = f"HTTP/1.1 {status_code} {status_text}\r\n"
        response_headers += f"Content-Type: {content_type}\r\n"
        response_headers += f"Content-Length: {len(body_bytes)}\r\n"
        response_headers += "Connection: close\r\n\r\n"
        
        client_socket.send(response_headers.encode('utf-8'))
        client_socket.send(body_bytes)
    
    def send_error_response(self, client_socket, status_code, status_text):
        body = f"<html><body><h1>{status_code} {status_text}</h1></body></html>"
        self.send_response(client_socket, status_code, "text/html", body)
    
    def get_status_text(self, status_code):
        status_texts = {
            200: "OK",
            400: "Bad Request",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            429: "Too Many Requests",
            500: "Internal Server Error"
        }
        return status_texts.get(status_code, "Unknown")
    
    def get_statistics(self):
        with self.stats_lock:
            return {
                'total_requests': self.total_requests,
                'blocked_requests': self.blocked_requests,
                'successful_requests': self.total_requests - self.blocked_requests,
                'request_counter': dict(self.request_counter)
            }
    
    def shutdown(self):
        print("\n[Server] Shutting down...")
        
        stats = self.get_statistics()
        print(f"\n[Server] Final Statistics:")
        print(f"  - Total requests: {stats['total_requests']}")
        print(f"  - Successful: {stats['successful_requests']}")
        print(f"  - Blocked: {stats['blocked_requests']}")
        
        self.thread_pool.shutdown()
        self.server_socket.close()
        print("[Server] Shutdown complete\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python file_server_lab2.py <directory> [options]")
        print("\nOptions:")
        print("  --threads N          Number of worker threads (default: 4)")
        print("  --delay N            Simulate work delay in seconds (default: 0)")
        print("  --no-locks           Disable locks (demonstrate race condition)")
        print("  --rate-limit N       Enable rate limiting (N requests/second)")
        print("\nExamples:")
        print("  python file_server_lab2.py content/")
        print("  python file_server_lab2.py content/ --threads 4 --delay 1")
        print("  python file_server_lab2.py content/ --no-locks")
        print("  python file_server_lab2.py content/ --rate-limit 5")
        sys.exit(1)
    
    serve_directory = sys.argv[1]
    
    if not os.path.isdir(serve_directory):
        print(f"Error: {serve_directory} is not a valid directory")
        sys.exit(1)
    
    num_threads = 4
    delay = 0
    use_locks = True
    enable_rate_limiting = False
    rate_limit = 5
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--threads' and i + 1 < len(sys.argv):
            num_threads = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--delay' and i + 1 < len(sys.argv):
            delay = float(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--no-locks':
            use_locks = False
            i += 1
        elif sys.argv[i] == '--rate-limit' and i + 1 < len(sys.argv):
            enable_rate_limiting = True
            rate_limit = int(sys.argv[i + 1])
            i += 2
        else:
            i += 1
    
    server = HTTPFileServer(
        serve_directory=serve_directory,
        host='0.0.0.0',
        port=8080,
        num_threads=num_threads,
        simulate_work_delay=delay,
        use_locks=use_locks,
        enable_rate_limiting=enable_rate_limiting,
        rate_limit=rate_limit
    )
    
    server.start()

if __name__ == "__main__":
    main()
