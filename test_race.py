
import socket
import threading
import time
import re

def make_request(path):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect(('localhost', 8080))
        s.send(f'GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n'.encode())
        
        resp = b''
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
        s.close()
        return resp.decode('utf-8', errors='ignore')
    except:
        return None

def get_file_counter(filename):
    html = make_request('/')
    if not html:
        return None
    
    pattern = rf'<td><a href="/{re.escape(filename)}"[^>]*>\s*{re.escape(filename)}</a></td>.*?<span class="count">(\d+)</span>'
    match = re.search(pattern, html, re.DOTALL)
    
    if match:
        return int(match.group(1))
    return 0

print("""SIMPLE RACE CONDITION TEST""")

print(" Checking server on localhost:8080...")
try:
    s = socket.socket()
    s.settimeout(2)
    s.connect(('localhost', 8080))
    s.close()
    print(" Server is running!\n")
except:
    print(" Server is not running!\n")
    print("Start the server:")
    print("  WITHOUT locks: python3 file_server_lab2.py content/ --no-locks --threads 20")
    print("  WITH locks:    python3 file_server_lab2.py content/\n")
    exit(1)

TEST_FILE = 'index.html'
NUM_REQUESTS = 100

print(f" TEST: {NUM_REQUESTS} requests to /{TEST_FILE}")

print(f"\n Reading initial counter for {TEST_FILE}...")
time.sleep(0.3)
initial = get_file_counter(TEST_FILE)
print(f"   Initial value: {initial}")

print(f"\nLaunching {NUM_REQUESTS} concurrent requests...")
start = time.time()

threads = []
for i in range(NUM_REQUESTS):
    t = threading.Thread(target=make_request, args=(f'/{TEST_FILE}',), daemon=True)
    threads.append(t)
    t.start()

for t in threads:
    t.join()

elapsed = time.time() - start
print(f" All requests completed in {elapsed:.2f} seconds")

time.sleep(1)

print(f"\n Reading final counter for {TEST_FILE}...")
final = get_file_counter(TEST_FILE)
print(f"   Final value: {final}")

increase = final - initial
lost = NUM_REQUESTS - increase

print("\n")
print(" RESULTS")
print(f"""
  Initial counter:      {initial}
  Final counter:        {final}
  
  Expected requests:    {NUM_REQUESTS}
  Actually added:       {increase}
  Lost:                 {lost}
""")

if lost > 0:
    percent = (lost / NUM_REQUESTS) * 100
    print(f" RACE CONDITION DETECTED!")
    print(f"   Lost {lost} out of {NUM_REQUESTS} requests ({percent:.1f}%)")
    print(f"""
   Solution: Run server WITH locks (without --no-locks flag)
""")
elif lost < 0:
    print(f"  Strange: counter increased more than expected")
    print(f"   Server might not have been restarted between tests")
else:
    print(f" PERFECT!")
    print(f"   All {NUM_REQUESTS} requests counted correctly")
    print(f"   Locks are working properly!")
