"""
Lambda Function: Metrics Generator
Generates detailed system metrics
"""

import json
import random
import time
from datetime import datetime

def generate_service_metrics(service_name):
    """Generate metrics for a specific service"""
    return {
        'service': service_name,
        'cpu': random.uniform(15, 95),
        'memory': random.uniform(25, 90),
        'requests_per_sec': random.randint(10, 1000),
        'error_count': random.randint(0, 50),
        'avg_latency_ms': random.uniform(50, 1500),
        'p95_latency_ms': random.uniform(100, 3000),
        'p99_latency_ms': random.uniform(200, 5000),
        'active_threads': random.randint(5, 200),
        'database_connections': random.randint(5, 100),
        'cache_operations': random.randint(100, 5000)
    }

def lambda_handler(event, context):
    """Generate comprehensive metrics"""
    
    timestamp = int(time.time())
    
    services = ['web-api', 'auth-service', 'database', 'cache', 'worker-queue']
    
    metrics = {
        'timestamp': timestamp,
        'services': {}
    }
    
    for service in services:
        metrics['services'][service] = generate_service_metrics(service)
    
    # Global metrics
    metrics['global'] = {
        'total_requests': sum(m['requests_per_sec'] for m in metrics['services'].values()),
        'total_errors': sum(m['error_count'] for m in metrics['services'].values()),
        'avg_cpu': sum(m['cpu'] for m in metrics['services'].values()) / len(services),
        'avg_memory': sum(m['memory'] for m in metrics['services'].values()) / len(services)
    }
    
    # Calculate system health
    critical_issues = []
    for service, service_metrics in metrics['services'].items():
        if service_metrics['cpu'] > 85:
            critical_issues.append(f"{service}_HIGH_CPU")
        if service_metrics['memory'] > 85:
            critical_issues.append(f"{service}_HIGH_MEMORY")
        if service_metrics['error_count'] > 30:
            critical_issues.append(f"{service}_HIGH_ERRORS")
        if service_metrics['p99_latency_ms'] > 4000:
            critical_issues.append(f"{service}_HIGH_LATENCY")
    
    metrics['critical_issues'] = critical_issues
    metrics['health_score'] = max(0, 100 - (len(critical_issues) * 15))
    
    print(json.dumps(metrics))
    
    return {
        'statusCode': 200,
        'body': json.dumps(metrics)
    }
