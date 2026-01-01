"""
Fault Injection Engine
Intentionally breaks system components to test detection and remediation
"""

import psutil
import time
import random
import json
import os
from datetime import datetime
import boto3
from threading import Thread

class FaultInjector:
    def __init__(self):
        self.localstack_endpoint = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')
        self.logs_client = self._create_logs_client()
        self.dynamodb = self._create_dynamodb_client()
        self.active_faults = []
    
    def _create_logs_client(self):
        return boto3.client(
            'logs',
            endpoint_url=self.localstack_endpoint,
            aws_access_key_id='test',
            aws_secret_access_key='test',
            region_name='us-east-1'
        )
    
    def _create_dynamodb_client(self):
        return boto3.client(
            'dynamodb',
            endpoint_url=self.localstack_endpoint,
            aws_access_key_id='test',
            aws_secret_access_key='test',
            region_name='us-east-1'
        )
    
    def _log_fault(self, fault_type, details):
        """Log fault injection to CloudWatch"""
        log_stream = f"fault-{int(time.time())}"
        
        try:
            # Create log stream
            self.logs_client.create_log_stream(
                logGroupName='/autonomous/faults',
                logStreamName=log_stream
            )
        except:
            pass  # Stream might already exist
        
        try:
            # Put log event
            self.logs_client.put_log_events(
                logGroupName='/autonomous/faults',
                logStreamName=log_stream,
                logEvents=[{
                    'timestamp': int(time.time() * 1000),
                    'message': json.dumps({
                        'fault_type': fault_type,
                        'details': details,
                        'timestamp': datetime.now().isoformat()
                    })
                }]
            )
            print(f"✓ Logged fault: {fault_type}")
        except Exception as e:
            print(f"✗ Failed to log fault: {e}")
    
    def inject_cpu_saturation(self, duration_seconds=60):
        """Simulate high CPU usage"""
        print(f"\n{'='*60}")
        print("INJECTING FAULT: CPU SATURATION")
        print(f"{'='*60}")
        print(f"Duration: {duration_seconds}s")
        
        fault_details = {
            'duration': duration_seconds,
            'target_cpu': 95,
            'start_time': time.time()
        }
        
        self._log_fault('CPU_SATURATION', fault_details)
        
        def cpu_stress():
            end_time = time.time() + duration_seconds
            print("CPU stress started...")
            while time.time() < end_time:
                # Busy loop to consume CPU
                [x**2 for x in range(10000)]
        
        # Run in multiple threads to maximize CPU usage
        threads = []
        for i in range(psutil.cpu_count() or 4):
            t = Thread(target=cpu_stress)
            t.start()
            threads.append(t)
        
        self.active_faults.append({
            'type': 'CPU_SATURATION',
            'threads': threads,
            'end_time': time.time() + duration_seconds
        })
        
        print(f"✓ CPU saturation injected ({len(threads)} threads)")
        print(f"{'='*60}\n")
    
    def inject_memory_leak(self, size_mb=500, duration_seconds=120):
        """Simulate memory leak"""
        print(f"\n{'='*60}")
        print("INJECTING FAULT: MEMORY LEAK")
        print(f"{'='*60}")
        print(f"Size: {size_mb}MB, Duration: {duration_seconds}s")
        
        fault_details = {
            'size_mb': size_mb,
            'duration': duration_seconds,
            'start_time': time.time()
        }
        
        self._log_fault('MEMORY_LEAK', fault_details)
        
        # Allocate memory
        leak = []
        chunk_size = 1024 * 1024  # 1MB chunks
        for i in range(size_mb):
            leak.append(' ' * chunk_size)
            if i % 100 == 0:
                print(f"  Allocated {i}MB...")
        
        self.active_faults.append({
            'type': 'MEMORY_LEAK',
            'data': leak,
            'end_time': time.time() + duration_seconds
        })
        
        print(f"✓ Memory leak injected ({size_mb}MB)")
        print(f"{'='*60}\n")
        
        # Keep reference alive
        time.sleep(duration_seconds)
    
    def inject_error_storm(self, error_rate=100, duration_seconds=60):
        """Generate high error rate in logs"""
        print(f"\n{'='*60}")
        print("INJECTING FAULT: ERROR STORM")
        print(f"{'='*60}")
        print(f"Rate: {error_rate} errors/sec, Duration: {duration_seconds}s")
        
        fault_details = {
            'error_rate': error_rate,
            'duration': duration_seconds,
            'start_time': time.time()
        }
        
        self._log_fault('ERROR_STORM', fault_details)
        
        error_types = [
            'DatabaseConnectionTimeout',
            'NullPointerException',
            'OutOfMemoryError',
            'FileNotFoundException',
            'NetworkTimeoutException',
            'AuthenticationFailure',
            'RateLimitExceeded',
            'ServiceUnavailable'
        ]
        
        log_stream = f"errors-{int(time.time())}"
        
        try:
            self.logs_client.create_log_stream(
                logGroupName='/autonomous/faults',
                logStreamName=log_stream
            )
        except:
            pass
        
        end_time = time.time() + duration_seconds
        error_count = 0
        
        while time.time() < end_time:
            # Generate batch of errors
            events = []
            for _ in range(min(error_rate, 50)):  # Batch limit
                error_type = random.choice(error_types)
                events.append({
                    'timestamp': int(time.time() * 1000),
                    'message': json.dumps({
                        'level': 'ERROR',
                        'error': error_type,
                        'message': f'{error_type} occurred in service',
                        'stack_trace': f'at module.function (line {random.randint(1, 1000)})'
                    })
                })
                error_count += 1
            
            try:
                self.logs_client.put_log_events(
                    logGroupName='/autonomous/faults',
                    logStreamName=log_stream,
                    logEvents=events
                )
            except Exception as e:
                print(f"  Error logging batch: {e}")
            
            time.sleep(1)
            if error_count % 100 == 0:
                print(f"  Generated {error_count} errors...")
        
        print(f"✓ Error storm completed ({error_count} total errors)")
        print(f"{'='*60}\n")
    
    def inject_service_crash(self, service_name='web-api'):
        """Simulate service crash"""
        print(f"\n{'='*60}")
        print(f"INJECTING FAULT: SERVICE CRASH - {service_name}")
        print(f"{'='*60}")
        
        fault_details = {
            'service': service_name,
            'crash_time': time.time()
        }
        
        self._log_fault('SERVICE_CRASH', fault_details)
        
        # Log crash event
        log_stream = f"crash-{int(time.time())}"
        
        try:
            self.logs_client.create_log_stream(
                logGroupName='/autonomous/faults',
                logStreamName=log_stream
            )
            
            self.logs_client.put_log_events(
                logGroupName='/autonomous/faults',
                logStreamName=log_stream,
                logEvents=[{
                    'timestamp': int(time.time() * 1000),
                    'message': json.dumps({
                        'level': 'CRITICAL',
                        'event': 'SERVICE_CRASH',
                        'service': service_name,
                        'message': f'{service_name} has crashed unexpectedly',
                        'exit_code': random.choice([1, 137, 139, 255])
                    })
                }]
            )
            
            print(f"✓ Service crash simulated: {service_name}")
        except Exception as e:
            print(f"✗ Failed to simulate crash: {e}")
        
        print(f"{'='*60}\n")
    
    def inject_disk_exhaustion(self, path='./logs', size_mb=1000):
        """Simulate disk space exhaustion"""
        print(f"\n{'='*60}")
        print("INJECTING FAULT: DISK EXHAUSTION")
        print(f"{'='*60}")
        print(f"Path: {path}, Size: {size_mb}MB")
        
        fault_details = {
            'path': path,
            'size_mb': size_mb,
            'start_time': time.time()
        }
        
        self._log_fault('DISK_EXHAUSTION', fault_details)
        
        os.makedirs(path, exist_ok=True)
        
        # Create large file
        filename = os.path.join(path, f'disk_filler_{int(time.time())}.tmp')
        
        try:
            with open(filename, 'wb') as f:
                chunk = b'0' * (1024 * 1024)  # 1MB chunk
                for i in range(size_mb):
                    f.write(chunk)
                    if i % 100 == 0:
                        print(f"  Written {i}MB...")
            
            self.active_faults.append({
                'type': 'DISK_EXHAUSTION',
                'filename': filename
            })
            
            print(f"✓ Disk exhaustion injected: {filename}")
        except Exception as e:
            print(f"✗ Failed to create disk file: {e}")
        
        print(f"{'='*60}\n")
    
    def inject_random_fault(self):
        """Inject a random fault"""
        faults = [
            lambda: self.inject_cpu_saturation(duration_seconds=random.randint(30, 90)),
            lambda: self.inject_error_storm(error_rate=random.randint(50, 200), duration_seconds=random.randint(30, 90)),
            lambda: self.inject_service_crash(service_name=random.choice(['web-api', 'auth-service', 'database', 'cache']))
        ]
        
        selected_fault = random.choice(faults)
        selected_fault()
    
    def cleanup_faults(self):
        """Clean up active faults"""
        print("\nCleaning up active faults...")
        
        for fault in self.active_faults:
            if fault['type'] == 'DISK_EXHAUSTION':
                try:
                    os.remove(fault['filename'])
                    print(f"  ✓ Removed {fault['filename']}")
                except Exception as e:
                    print(f"  ✗ Failed to remove file: {e}")
            elif fault['type'] == 'MEMORY_LEAK':
                fault['data'].clear()
                print(f"  ✓ Cleared memory leak")
        
        self.active_faults.clear()
        print("✓ Cleanup complete")


if __name__ == '__main__':
    print("="*60)
    print("FAULT INJECTION ENGINE - TEST MODE")
    print("="*60)
    
    injector = FaultInjector()
    
    # Test each fault type
    print("\n1. Testing Error Storm...")
    injector.inject_error_storm(error_rate=50, duration_seconds=10)
    
    print("\n2. Testing Service Crash...")
    injector.inject_service_crash('test-service')
    
    print("\n3. Cleaning up...")
    injector.cleanup_faults()
    
    print("\n✓ All fault injection tests completed")
