"""
Detection Agent
Continuously monitors system, detects failures, predicts future risks
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import uuid
from datetime import datetime
import boto3
from llm.nvidia_nim_wrapper import NvidiaNIMWrapper

class DetectionAgent:
    def __init__(self):
        self.llm = NvidiaNIMWrapper()
        self.localstack_endpoint = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')
        self.logs_client = self._create_logs_client()
        self.dynamodb = self._create_dynamodb_client()
        self.cloudwatch = self._create_cloudwatch_client()
        
        print("✓ Detection Agent initialized")
    
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
    
    def _create_cloudwatch_client(self):
        return boto3.client(
            'cloudwatch',
            endpoint_url=self.localstack_endpoint,
            aws_access_key_id='test',
            aws_secret_access_key='test',
            region_name='us-east-1'
        )
    
    def collect_metrics(self):
        """Collect current system metrics"""
        metrics = {
            'timestamp': time.time(),
            'cloudwatch_logs': self._get_recent_logs(),
            'system_health': self._get_system_health(),
            'service_status': self._get_service_status()
        }
        
        return metrics
    
    def _get_recent_logs(self, limit=100):
        """Fetch recent logs from CloudWatch"""
        all_logs = []
        
        log_groups = [
            '/autonomous/faults',
            '/autonomous/metrics',
            '/autonomous/detection-agent',
            '/autonomous/remediation-agent'
        ]
        
        for log_group in log_groups:
            try:
                # Get log streams
                streams_response = self.logs_client.describe_log_streams(
                    logGroupName=log_group,
                    orderBy='LastEventTime',
                    descending=True,
                    limit=5
                )
                
                for stream in streams_response.get('logStreams', []):
                    # Get log events
                    events_response = self.logs_client.get_log_events(
                        logGroupName=log_group,
                        logStreamName=stream['logStreamName'],
                        limit=20
                    )
                    
                    for event in events_response.get('events', []):
                        all_logs.append({
                            'log_group': log_group,
                            'timestamp': event['timestamp'],
                            'message': event['message']
                        })
            except Exception as e:
                print(f"  Warning: Could not fetch logs from {log_group}: {e}")
        
        # Sort by timestamp and limit
        all_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        return all_logs[:limit]
    
    def _get_system_health(self):
        """Get current system health indicators"""
        # In real implementation, this would query actual system metrics
        # For now, we'll simulate based on log content
        
        health = {
            'status': 'UNKNOWN',
            'cpu_usage': 0,
            'memory_usage': 0,
            'error_count': 0,
            'warning_count': 0
        }
        
        # Analyze recent logs for health indicators
        recent_logs = self._get_recent_logs(limit=50)
        
        for log in recent_logs:
            message = log.get('message', '')
            if 'ERROR' in message or 'CRITICAL' in message:
                health['error_count'] += 1
            if 'WARNING' in message or 'WARN' in message:
                health['warning_count'] += 1
            
            # Extract metrics from log messages
            try:
                log_data = json.loads(message)
                if 'cpu' in log_data:
                    health['cpu_usage'] = max(health['cpu_usage'], log_data['cpu'])
                if 'memory' in log_data:
                    health['memory_usage'] = max(health['memory_usage'], log_data['memory'])
            except:
                pass
        
        # Determine status
        if health['error_count'] > 10:
            health['status'] = 'CRITICAL'
        elif health['error_count'] > 5 or health['warning_count'] > 20:
            health['status'] = 'DEGRADED'
        elif health['cpu_usage'] > 85 or health['memory_usage'] > 85:
            health['status'] = 'WARNING'
        else:
            health['status'] = 'HEALTHY'
        
        return health
    
    def _get_service_status(self):
        """Get status of all services"""
        services = ['web-api', 'auth-service', 'database', 'cache', 'worker-queue']
        
        status = {}
        for service in services:
            # Check for recent crashes or errors related to this service
            service_logs = [log for log in self._get_recent_logs(limit=50) 
                          if service in log.get('message', '')]
            
            error_count = sum(1 for log in service_logs 
                            if 'ERROR' in log.get('message', '') or 'CRITICAL' in log.get('message', ''))
            
            crash_detected = any('CRASH' in log.get('message', '') or 'crash' in log.get('message', '') 
                               for log in service_logs)
            
            if crash_detected:
                status[service] = 'DOWN'
            elif error_count > 5:
                status[service] = 'DEGRADED'
            else:
                status[service] = 'UP'
        
        return status
    
    def get_active_incidents(self):
        """Fetch active incidents from DynamoDB"""
        try:
            response = self.dynamodb.scan(
                TableName='incidents',
                Limit=50
            )
            
            incidents = []
            for item in response.get('Items', []):
                # Parse DynamoDB item
                incident = {
                    'incident_id': item.get('incident_id', {}).get('S', ''),
                    'timestamp': float(item.get('timestamp', {}).get('N', 0)),
                    'status': item.get('status', {}).get('S', 'ACTIVE')
                }
                
                # Only return active incidents from last hour
                if incident['status'] == 'ACTIVE' and (time.time() - incident['timestamp']) < 3600:
                    incidents.append(incident)
            
            return incidents
        except Exception as e:
            print(f"  Warning: Could not fetch incidents: {e}")
            return []
    
    def detect_and_predict(self):
        """Main detection loop - analyze current state and predict failures"""
        print(f"\n{'='*60}")
        print("DETECTION AGENT - ANALYSIS CYCLE")
        print(f"{'='*60}")
        print(f"Time: {datetime.now().isoformat()}")
        
        # Collect current state
        print("\n1. Collecting metrics and logs...")
        metrics = self.collect_metrics()
        active_incidents = self.get_active_incidents()
        
        print(f"   - Logs collected: {len(metrics['cloudwatch_logs'])}")
        print(f"   - System health: {metrics['system_health']['status']}")
        print(f"   - Active incidents: {len(active_incidents)}")
        
        # Use LLM to detect and predict
        print("\n2. Analyzing with Gemini Flash 2.0...")
        analysis = self.llm.detect_and_predict(
            metrics=metrics,
            logs=metrics['cloudwatch_logs'],
            current_incidents=active_incidents
        )
        
        print("\n3. Analysis Results:")
        print(f"   - Current failures: {len(analysis.get('current_failures', []))}")
        print(f"   - Future risks: {len(analysis.get('future_risks', []))}")
        print(f"   - Trigger remediation: {analysis.get('trigger_remediation', False)}")
        
        # Log decision to DynamoDB
        decision_id = str(uuid.uuid4())
        decision_data = {
            'decision_id': {'S': decision_id},
            'timestamp': {'N': str(time.time())},
            'agent_type': {'S': 'detection'},
            'analysis': {'S': json.dumps(analysis)[:10000]},
            'metrics_snapshot': {'S': json.dumps(metrics)[:10000]},
            'trigger_remediation': {'BOOL': analysis.get('trigger_remediation', False)}
        }
        
        try:
            self.dynamodb.put_item(
                TableName='agent_decisions',
                Item=decision_data
            )
            print(f"\n4. Logged decision: {decision_id}")
        except Exception as e:
            print(f"\n4. Failed to log decision: {e}")
        
        # Store incidents in DynamoDB
        for failure in analysis.get('current_failures', []):
            incident_id = str(uuid.uuid4())
            incident_data = {
                'incident_id': {'S': incident_id},
                'timestamp': {'N': str(time.time())},
                'type': {'S': failure.get('type', 'UNKNOWN')},
                'severity': {'S': failure.get('severity', 'MEDIUM')},
                'affected_components': {'S': json.dumps(failure.get('affected_components', []))},
                'evidence': {'S': json.dumps(failure.get('evidence', []))},
                'status': {'S': 'ACTIVE'}
            }
            
            try:
                self.dynamodb.put_item(
                    TableName='incidents',
                    Item=incident_data
                )
                print(f"   ✓ Created incident: {incident_id} ({failure.get('type', 'UNKNOWN')})")
            except Exception as e:
                print(f"   ✗ Failed to create incident: {e}")
        
        print(f"{'='*60}\n")
        
        return analysis
    
    def run_continuous(self, interval_seconds=60):
        """Run detection continuously"""
        print(f"\n{'='*60}")
        print("DETECTION AGENT - CONTINUOUS MODE")
        print(f"{'='*60}")
        print(f"Interval: {interval_seconds}s")
        print("Press Ctrl+C to stop\n")
        
        cycle_count = 0
        
        try:
            while True:
                cycle_count += 1
                print(f"\n>>> Detection Cycle #{cycle_count}")
                
                analysis = self.detect_and_predict()
                
                print(f"\n>>> Sleeping for {interval_seconds}s...")
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n\nDetection Agent stopped by user")
        except Exception as e:
            print(f"\n\nDetection Agent error: {e}")
            raise


if __name__ == '__main__':
    agent = DetectionAgent()
    
    # Run one detection cycle
    print("Running single detection cycle...")
    analysis = agent.detect_and_predict()
    
    print("\n" + "="*60)
    print("ANALYSIS SUMMARY")
    print("="*60)
    print(json.dumps(analysis, indent=2))
