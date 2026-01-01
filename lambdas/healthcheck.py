"""
Lambda Function: Health Check
Continuously generates health metrics and logs
"""

import json
import random
import time
from datetime import datetime

def lambda_handler(event, context):
    """Generate health check metrics"""
    
    timestamp = int(time.time())
    
    # Simulate varying system metrics
    metrics = {
        'timestamp': timestamp,
        'cpu_percent': random.uniform(20, 95),
        'memory_percent': random.uniform(30, 85),
        'disk_usage_percent': random.uniform(40, 90),
        'network_latency_ms': random.uniform(10, 500),
        'error_rate': random.uniform(0, 0.15),
        'request_count': random.randint(100, 10000),
        'response_time_ms': random.uniform(50, 2000),
        'active_connections': random.randint(10, 500),
        'queue_depth': random.randint(0, 100),
        'cache_hit_rate': random.uniform(0.6, 0.95)
    }
    
    # Detect anomalies
    anomalies = []
    if metrics['cpu_percent'] > 85:
        anomalies.append('HIGH_CPU')
    if metrics['memory_percent'] > 80:
        anomalies.append('HIGH_MEMORY')
    if metrics['disk_usage_percent'] > 85:
        anomalies.append('HIGH_DISK')
    if metrics['error_rate'] > 0.1:
        anomalies.append('HIGH_ERROR_RATE')
    if metrics['response_time_ms'] > 1500:
        anomalies.append('SLOW_RESPONSE')
    
    metrics['anomalies'] = anomalies
    metrics['health_status'] = 'UNHEALTHY' if anomalies else 'HEALTHY'
    
    # Log to CloudWatch (simulated via print in LocalStack)
    print(json.dumps(metrics))
    
    return {
        'statusCode': 200,
        'body': json.dumps(metrics)
    }
