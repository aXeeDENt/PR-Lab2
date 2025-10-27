import socket
import threading
import time
import sys
from datetime import datetime

def make_request(client_id, host, port, path, results, delay=0):
    if delay > 0:
        time.sleep(delay)
    
    start_time = time.time()
    
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(10)
        client_socket.connect((host, port))
        
        request = f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        client_socket.send(request.encode('utf-8'))
        
        response_data = b""
        while True:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            response_data += chunk
        
        client_socket.close()
        
        elapsed = time.time() - start_time
        
        response_str = response_data.decode('utf-8', errors='ignore')
        status_line = response_str.split('\r\n')[0]
        status_code = int(status_line.split(' ')[1])
        
        results.append({
            'client_id': client_id,
            'elapsed': elapsed,
            'status_code': status_code,
            'success': status_code == 200
        })
        
        return True
        
    except Exception as e:
        elapsed = time.time() - start_time
        results.append({
            'client_id': client_id,
            'elapsed': elapsed,
            'status_code': 0,
            'success': False,
            'error': str(e)
        })
        return False

def test_concurrent_requests(host, port, num_clients, path='/'):

    results = []
    threads = []
    
    print(f"   Starting {num_clients} concurrent requests to {host}:{port}")
    print(f"   Path: {path}")
    print(f"   Time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}\n")
    
    start_time = time.time()
    
    for i in range(num_clients):
        thread = threading.Thread(
            target=make_request,
            args=(i + 1, host, port, path, results),
            daemon=True
        )
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    total_time = time.time() - start_time
    
    return {
        'total_time': total_time,
        'results': results,
        'num_clients': num_clients
    }

def test_sequential_requests(host, port, num_requests, path='/'):

    results = []
    
    print(f"   Starting {num_requests} sequential requests to {host}:{port}")
    print(f"   Path: {path}")
    print(f"   Time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}\n")
    
    start_time = time.time()
    
    for i in range(num_requests):
        make_request(i + 1, host, port, path, results)
    
    total_time = time.time() - start_time
    
    return {
        'total_time': total_time,
        'results': results,
        'num_clients': num_requests
    }

def print_results(test_name, results):
    print("\n")
    print(f" {test_name}")
    
    total_time = results['total_time']
    num_clients = results['num_clients']
    individual_results = results['results']
    
    successful = sum(1 for r in individual_results if r['success'])
    failed = num_clients - successful
    
    if individual_results:
        avg_time = sum(r['elapsed'] for r in individual_results) / len(individual_results)
        min_time = min(r['elapsed'] for r in individual_results)
        max_time = max(r['elapsed'] for r in individual_results)
    else:
        avg_time = min_time = max_time = 0
    
    print(f"\n  Total Time: {total_time:.3f} seconds")
    print(f" Throughput: {successful / total_time:.2f} requests/second")
    print(f"\n Successful: {successful}")
    print(f" Failed: {failed}")
    print(f"\n Individual Request Times:")
    print(f"   Average: {avg_time:.3f}s")
    print(f"   Minimum: {min_time:.3f}s")
    print(f"   Maximum: {max_time:.3f}s")
    
    print(f"\n Detailed Results:")
    for r in individual_results:
        status = "Y" if r['success'] else "N"
        print(f"   Client {r['client_id']:2d}: {status} {r['elapsed']:.3f}s (HTTP {r['status_code']})")
    
    print()

def compare_results(single_results, multi_results):
    """Compare single-threaded vs multithreaded results."""
    print("\n")
    print(" COMPARISON: Single-threaded vs Multithreaded")
    
    single_time = single_results['total_time']
    multi_time = multi_results['total_time']
    speedup = single_time / multi_time
    improvement = ((single_time - multi_time) / single_time) * 100
    
    single_throughput = len(single_results['results']) / single_time
    multi_throughput = len(multi_results['results']) / multi_time
    
    print(f"\n  Time Comparison:")
    print(f"   Single-threaded: {single_time:.3f}s")
    print(f"   Multithreaded:   {multi_time:.3f}s")
    print(f"   Speedup:         {speedup:.2f}x faster")
    print(f"   Improvement:     {improvement:.1f}% faster")
    
    print(f"\n Throughput Comparison:")
    print(f"   Single-threaded: {single_throughput:.2f} req/s")
    print(f"   Multithreaded:   {multi_throughput:.2f} req/s")
    print(f"   Increase:        {multi_throughput/single_throughput:.2f}x")
    
    print(f"\n Analysis:")
    if speedup > 3:
        print(f"    Excellent! Multithreading provides significant speedup.")
    elif speedup > 1.5:
        print(f"    Good! Multithreading improves performance.")
    else:
        print(f"     Limited speedup. May be bottlenecked by CPU or I/O.")
    
    print()

def test_rate_limiting(host, port, requests_per_second, duration=5):

    print(f"\n Rate Limiting Test")
    print(f"   Target: {requests_per_second} requests/second")
    print(f"   Duration: {duration} seconds")
    print(f"   Expected total: {requests_per_second * duration} requests\n")
    
    results = []
    start_time = time.time()
    request_count = 0
    
    while time.time() - start_time < duration:
        delay = 1.0 / requests_per_second
        
        make_request(request_count + 1, host, port, '/', results)
        request_count += 1
        
        time.sleep(delay)
    
    total_time = time.time() - start_time
    successful = sum(1 for r in results if r['success'])
    blocked = len(results) - successful
    
    print(f"\n Rate Limiting Results:")
    print(f"   Total requests: {len(results)}")
    print(f"   Successful (200): {successful}")
    print(f"   Blocked (429): {blocked}")
    print(f"   Actual rate: {len(results) / total_time:.2f} req/s")
    print(f"   Success rate: {successful / total_time:.2f} req/s")
    
    return {
        'total_requests': len(results),
        'successful': successful,
        'blocked': blocked,
        'total_time': total_time,
        'results': results
    }

def check_server(host, port):
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(2)
        test_socket.connect((host, port))
        test_socket.close()
        return True
    except:
        return False

def main():
    print("""Lab 2: Performance Testing & Comparison Tool""")
    
    host = 'localhost'
    port = 8080
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help':
            print("Usage: python3 benchmark_lab2.py [test_type]")
            print("\nTest Types:")
            print("  comparison     - Compare single vs multithreaded (default)")
            print("  concurrent     - Test concurrent requests only")
            print("  rate-limit     - Test rate limiting")
            print("\nExamples:")
            print("  python3 benchmark_lab2.py")
            print("  python3 benchmark_lab2.py concurrent")
            print("  python3 benchmark_lab2.py rate-limit")
            sys.exit(0)
    
    # Check if server is running
    print(f" Checking server at {host}:{port}...")
    if not check_server(host, port):
        print(f"\n ERROR: Server is not running on {host}:{port}")
        print(f"\nPlease start the server first:")
        print(f"  Single-threaded (lab1): python3 file_server.py content/")
        print(f"  Multithreaded (lab2):   python3 file_server_lab2.py content/ --delay 1")
        sys.exit(1)
    
    print(f" Server is running!\n")
    
    test_type = sys.argv[1] if len(sys.argv) > 1 else 'comparison'
    
    if test_type == 'comparison':
        # Full comparison test
        print("TEST 1: Single-threaded Server (Sequential Requests)")
        print("\n  Make sure you're running the SINGLE-THREADED server:")
        print("   python3 file_server.py content/\n")
        
        input("Press Enter when ready to test single-threaded server...")
        
        single_results = test_sequential_requests(host, port, 10, '/')
        print_results("Single-threaded Server (10 Sequential Requests)", single_results)
        
        print("\n")
        print("TEST 2: Multithreaded Server (Concurrent Requests)")
        print("\n  Now switch to the MULTITHREADED server with delay:")
        print("   python3 file_server_lab2.py content/ --delay 1\n")
        
        input("Press Enter when ready to test multithreaded server...")
        
        multi_results = test_concurrent_requests(host, port, 10, '/')
        print_results("Multithreaded Server (10 Concurrent Requests)", multi_results)
        
        compare_results(single_results, multi_results)
        
    elif test_type == 'concurrent':
        num_clients = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        results = test_concurrent_requests(host, port, num_clients, '/')
        print_results(f"Concurrent Test ({num_clients} clients)", results)
        
    elif test_type == 'rate-limit':
        print("  Make sure server is running with rate limiting:")
        print("   python3 file_server_lab2.py content/ --rate-limit 5\n")
        input("Press Enter to start rate limiting test...")
        
        test_rate_limiting(host, port, requests_per_second=10, duration=5)
    
    print("\n Testing complete!\n")

if __name__ == "__main__":
    main()
