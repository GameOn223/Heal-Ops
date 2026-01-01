"""
Flask Dashboard
Live monitoring of autonomous system operations
"""

from flask import Flask, render_template, jsonify, request
import boto3
import json
import os
import sys
import uuid
from datetime import datetime
from botocore.config import Config
import threading

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Add paths for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fault-injection'))

from fault_injector import FaultInjector

app = Flask(__name__)

# Initialize fault injector
fault_injector = FaultInjector()

# Initialize agents lazily (only when needed)
detection_agent = None
remediation_agent = None

def get_detection_agent():
    global detection_agent
    if detection_agent is None:
        from agents.detection_agent import DetectionAgent
        detection_agent = DetectionAgent()
    return detection_agent

def get_remediation_agent():
    global remediation_agent
    if remediation_agent is None:
        from agents.remediation_agent import RemediationAgent
        remediation_agent = RemediationAgent()
    return remediation_agent

LOCALSTACK_ENDPOINT = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')

def create_dynamodb_client():
    return boto3.client(
        'dynamodb',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )

def create_logs_client():
    return boto3.client(
        'logs',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )

def create_s3_client():
    return boto3.client(
        's3',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        config=Config(region_name='us-east-1', signature_version='s3v4')
    )

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/stats')
def get_stats():
    """Get overall system statistics"""
    dynamodb = create_dynamodb_client()
    
    try:
        # Count incidents
        incidents_response = dynamodb.scan(
            TableName='incidents',
            Select='COUNT'
        )
        total_incidents = incidents_response.get('Count', 0)
        
        # Count remediations
        remediations_response = dynamodb.scan(
            TableName='remediations',
            Select='COUNT'
        )
        total_remediations = remediations_response.get('Count', 0)
        
        # Count LLM actions
        llm_response = dynamodb.scan(
            TableName='llm_actions',
            Select='COUNT'
        )
        total_llm_actions = llm_response.get('Count', 0)
        
        # Get successful remediations
        remediations_full = dynamodb.scan(
            TableName='remediations',
            Limit=100
        )
        
        successful = 0
        for item in remediations_full.get('Items', []):
            if item.get('success', {}).get('BOOL', False):
                successful += 1
        
        success_rate = (successful / total_remediations * 100) if total_remediations > 0 else 0
        
        return jsonify({
            'total_incidents': total_incidents,
            'total_remediations': total_remediations,
            'successful_remediations': successful,
            'success_rate': round(success_rate, 1),
            'total_llm_actions': total_llm_actions,
            'system_status': 'ACTIVE'
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'total_incidents': 0,
            'total_remediations': 0,
            'successful_remediations': 0,
            'success_rate': 0,
            'total_llm_actions': 0,
            'system_status': 'ERROR'
        })

@app.route('/api/incidents')
def get_incidents():
    """Get recent incidents"""
    dynamodb = create_dynamodb_client()
    
    try:
        response = dynamodb.scan(
            TableName='incidents',
            Limit=50
        )
        
        incidents = []
        for item in response.get('Items', []):
            incidents.append({
                'incident_id': item.get('incident_id', {}).get('S', ''),
                'timestamp': float(item.get('timestamp', {}).get('N', 0)),
                'type': item.get('type', {}).get('S', 'UNKNOWN'),
                'severity': item.get('severity', {}).get('S', 'MEDIUM'),
                'status': item.get('status', {}).get('S', 'ACTIVE'),
                'affected_components': item.get('affected_components', {}).get('S', '[]')
            })
        
        # Sort by timestamp (most recent first)
        incidents.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Format timestamps
        for incident in incidents:
            incident['timestamp_str'] = datetime.fromtimestamp(incident['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(incidents[:20])
    
    except Exception as e:
        print(f"Error fetching incidents: {e}")
        return jsonify([])

@app.route('/api/remediations')
def get_remediations():
    """Get recent remediations"""
    dynamodb = create_dynamodb_client()
    
    try:
        response = dynamodb.scan(
            TableName='remediations',
            Limit=50
        )
        
        remediations = []
        for item in response.get('Items', []):
            remediations.append({
                'remediation_id': item.get('remediation_id', {}).get('S', ''),
                'timestamp': float(item.get('timestamp', {}).get('N', 0)),
                'success': item.get('success', {}).get('BOOL', False),
                'incident': item.get('incident', {}).get('S', '{}')
            })
        
        # Sort by timestamp (most recent first)
        remediations.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Format timestamps and parse incident
        for remediation in remediations:
            remediation['timestamp_str'] = datetime.fromtimestamp(remediation['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            try:
                incident_data = json.loads(remediation['incident'])
                remediation['incident_type'] = incident_data.get('type', 'UNKNOWN')
            except:
                remediation['incident_type'] = 'UNKNOWN'
        
        return jsonify(remediations[:20])
    
    except Exception as e:
        print(f"Error fetching remediations: {e}")
        return jsonify([])

@app.route('/api/llm-actions')
def get_llm_actions():
    """Get recent LLM actions"""
    dynamodb = create_dynamodb_client()
    
    try:
        response = dynamodb.scan(
            TableName='llm_actions',
            Limit=50
        )
        
        actions = []
        for item in response.get('Items', []):
            actions.append({
                'action_id': item.get('action_id', {}).get('S', ''),
                'timestamp': float(item.get('timestamp', {}).get('N', 0)),
                'agent_type': item.get('agent_type', {}).get('S', 'unknown'),
                'success': item.get('success', {}).get('BOOL', False),
                'latency_ms': int(item.get('latency_ms', {}).get('N', 0)),
                'prompt': item.get('prompt', {}).get('S', '')[:200],
                'response': item.get('response', {}).get('S', '')[:200]
            })
        
        # Sort by timestamp (most recent first)
        actions.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Format timestamps
        for action in actions:
            action['timestamp_str'] = datetime.fromtimestamp(action['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(actions[:20])
    
    except Exception as e:
        print(f"Error fetching LLM actions: {e}")
        return jsonify([])

@app.route('/api/logs')
def get_logs():
    """Get recent CloudWatch logs"""
    logs_client = create_logs_client()
    
    try:
        all_logs = []
        
        log_groups = [
            '/autonomous/detection-agent',
            '/autonomous/remediation-agent',
            '/autonomous/faults',
            '/autonomous/orchestrator'
        ]
        
        for log_group in log_groups:
            try:
                # Get log streams
                streams = logs_client.describe_log_streams(
                    logGroupName=log_group,
                    orderBy='LastEventTime',
                    descending=True,
                    limit=3
                )
                
                for stream in streams.get('logStreams', []):
                    # Get log events
                    events = logs_client.get_log_events(
                        logGroupName=log_group,
                        logStreamName=stream['logStreamName'],
                        limit=10
                    )
                    
                    for event in events.get('events', []):
                        all_logs.append({
                            'timestamp': event['timestamp'],
                            'timestamp_str': datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                            'log_group': log_group,
                            'message': event['message'][:500]
                        })
            except:
                pass
        
        # Sort by timestamp (most recent first)
        all_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify(all_logs[:50])
    
    except Exception as e:
        print(f"Error fetching logs: {e}")
        return jsonify([])

@app.route('/api/agent-decisions')
def get_agent_decisions():
    """Get recent agent decisions"""
    dynamodb = create_dynamodb_client()
    
    try:
        response = dynamodb.scan(
            TableName='agent_decisions',
            Limit=30
        )
        
        decisions = []
        for item in response.get('Items', []):
            decisions.append({
                'decision_id': item.get('decision_id', {}).get('S', ''),
                'timestamp': float(item.get('timestamp', {}).get('N', 0)),
                'agent_type': item.get('agent_type', {}).get('S', 'unknown'),
                'trigger_remediation': item.get('trigger_remediation', {}).get('BOOL', False)
            })
        
        # Sort by timestamp (most recent first)
        decisions.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Format timestamps
        for decision in decisions:
            decision['timestamp_str'] = datetime.fromtimestamp(decision['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(decisions[:20])
    
    except Exception as e:
        print(f"Error fetching agent decisions: {e}")
        return jsonify([])

# ============================================================
# INTERACTIVE FAULT INJECTION ENDPOINTS
# ============================================================

def run_autonomous_cycle(fault_type=None):
    """Run a single autonomous cycle with optional specific fault"""
    try:
        print(f"\n{'='*60}")
        print(f"MANUAL TRIGGER: {fault_type or 'Random Fault'}")
        print(f"{'='*60}")
        
        # Phase 1: Inject Fault
        if fault_type == 'cpu':
            fault_injector.inject_cpu_saturation()
        elif fault_type == 'memory':
            fault_injector.inject_memory_leak()
        elif fault_type == 'error':
            fault_injector.inject_error_storm()
        elif fault_type == 'crash':
            fault_injector.inject_service_crash()
        elif fault_type == 'disk':
            fault_injector.inject_disk_exhaustion()
        else:
            fault_injector.inject_random_fault()
        
        # Wait for fault to manifest
        import time
        time.sleep(5)
        
        # Phase 2: Detect
        print("\n[DETECTION] Analyzing system...")
        set_agent_status('Detection Agent', 'Analyzing system metrics and logs')
        agent = get_detection_agent()
        analysis = agent.detect_and_predict()
        
        current_failures = analysis.get('current_failures', [])
        
        # Save incidents to DynamoDB
        dynamodb = create_dynamodb_client()
        for failure in current_failures:
            incident_id = str(uuid.uuid4())
            incident_data = {
                'incident_id': {'S': incident_id},
                'timestamp': {'N': str(time.time())},
                'type': {'S': failure.get('type', 'UNKNOWN')},
                'severity': {'S': failure.get('severity', 'MEDIUM')},
                'status': {'S': 'ACTIVE'},
                'affected_components': {'S': json.dumps(failure.get('affected_components', []))},
                'evidence': {'S': json.dumps(failure.get('evidence', []))}
            }
            try:
                dynamodb.put_item(TableName='incidents', Item=incident_data)
                print(f"  ✓ Saved incident: {incident_id}")
            except Exception as e:
                print(f"  ✗ Failed to save incident: {e}")
        
        # Phase 3: Remediate
        if current_failures:
            remediation = get_remediation_agent()
            for failure in current_failures:
                severity = failure.get('severity', 'MEDIUM')
                if severity in ['CRITICAL', 'HIGH']:
                    print(f"\n[REMEDIATION] Fixing: {failure.get('type', 'UNKNOWN')}")
                    set_agent_status('Remediation Agent', f'Planning fix for {failure.get("type", "UNKNOWN")}')
                    result = remediation.remediate_incident(failure)
                    
                    # Save remediation to DynamoDB
                    remediation_id = str(uuid.uuid4())
                    remediation_data = {
                        'remediation_id': {'S': remediation_id},
                        'timestamp': {'N': str(time.time())},
                        'incident': {'S': json.dumps(failure)},
                        'success': {'BOOL': result.get('verification', {}).get('success', False)},
                        'plan': {'S': json.dumps(result.get('plan', {}))[:10000]}
                    }
                    try:
                        dynamodb.put_item(TableName='remediations', Item=remediation_data)
                        print(f"  ✓ Saved remediation: {remediation_id}")
                    except Exception as e:
                        print(f"  ✗ Failed to save remediation: {e}")
        
        print(f"\n{'='*60}")
        print("CYCLE COMPLETE")
        print(f"{'='*60}\n")
        
        set_agent_status('idle', 'System ready')
        
    except Exception as e:
        print(f"Error in autonomous cycle: {e}")
        set_agent_status('error', f'Error: {str(e)}')

@app.route('/api/inject/cpu', methods=['POST'])
def inject_cpu():
    """Trigger CPU saturation"""
    try:
        # Run in background thread so API responds immediately
        thread = threading.Thread(target=run_autonomous_cycle, args=('cpu',))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'CPU saturation triggered - Watch dashboard for detection & remediation'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inject/memory', methods=['POST'])
def inject_memory():
    """Trigger memory leak"""
    try:
        thread = threading.Thread(target=run_autonomous_cycle, args=('memory',))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Memory leak triggered - Watch dashboard for detection & remediation'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inject/error', methods=['POST'])
def inject_error():
    """Trigger error storm"""
    try:
        thread = threading.Thread(target=run_autonomous_cycle, args=('error',))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Error storm triggered - Watch dashboard for detection & remediation'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inject/crash', methods=['POST'])
def inject_crash():
    """Trigger service crash"""
    try:
        thread = threading.Thread(target=run_autonomous_cycle, args=('crash',))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Service crash triggered - Watch dashboard for detection & remediation'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inject/disk', methods=['POST'])
def inject_disk():
    """Trigger disk exhaustion"""
    try:
        thread = threading.Thread(target=run_autonomous_cycle, args=('disk',))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Disk exhaustion triggered - Watch dashboard for detection & remediation'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inject/random', methods=['POST'])
def inject_random():
    """Trigger random fault"""
    try:
        thread = threading.Thread(target=run_autonomous_cycle, args=(None,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Random fault triggered - Watch dashboard for detection & remediation'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Global agent status tracking
agent_status = {
    'current_agent': 'idle',
    'operation': 'System ready',
    'started_at': None
}

@app.route('/api/agent-status')
def get_agent_status():
    """Get current agent operation status"""
    return jsonify(agent_status)

def set_agent_status(agent_name, operation):
    """Update agent status"""
    global agent_status
    agent_status = {
        'current_agent': agent_name,
        'operation': operation,
        'started_at': datetime.now().isoformat()
    }

@app.route('/api/command-history')
def get_command_history():
    """Get recent command executions"""
    dynamodb = create_dynamodb_client()
    
    try:
        response = dynamodb.scan(
            TableName='command_executions',
            Limit=50
        )
        
        commands = []
        for item in response.get('Items', []):
            commands.append({
                'execution_id': item.get('execution_id', {}).get('S', ''),
                'timestamp': float(item.get('timestamp', {}).get('N', 0)),
                'remediation_id': item.get('remediation_id', {}).get('S', ''),
                'command': item.get('command', {}).get('S', ''),
                'exit_code': int(item.get('exit_code', {}).get('N', 1)),
                'status': item.get('status', {}).get('S', 'UNKNOWN'),
                'output': item.get('output', {}).get('S', '')[:200],
                'error': item.get('error', {}).get('S', '')
            })
        
        # Sort by timestamp (most recent first)
        commands.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Format timestamps
        for cmd in commands:
            cmd['timestamp_str'] = datetime.fromtimestamp(cmd['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(commands[:20])
    
    except Exception as e:
        print(f"Error fetching command history: {e}")
        return jsonify([])

@app.route('/api/clear-data', methods=['POST'])
def clear_data():
    """Clear all data from DynamoDB tables, S3 buckets, and CloudWatch logs"""
    dynamodb = create_dynamodb_client()
    s3 = create_s3_client()
    logs_client = create_logs_client()
    
    # Table definitions with their composite keys (HASH + RANGE)
    tables = [
        {'name': 'incidents', 'hash_key': 'incident_id', 'range_key': 'timestamp'},
        {'name': 'remediations', 'hash_key': 'remediation_id', 'range_key': 'timestamp'},
        {'name': 'agent_decisions', 'hash_key': 'decision_id', 'range_key': 'timestamp'},
        {'name': 'system_metrics', 'hash_key': 'metric_id', 'range_key': 'timestamp'},
        {'name': 'command_executions', 'hash_key': 'execution_id', 'range_key': 'timestamp'},
        {'name': 'llm_actions', 'hash_key': 'action_id', 'range_key': 'timestamp'}
    ]
    
    s3_buckets = [
        'autonomous-logs',
        'autonomous-metrics',
        'autonomous-incidents',
        'autonomous-llm-traces'
    ]
    
    log_groups = [
        '/autonomous/detection-agent',
        '/autonomous/remediation-agent',
        '/autonomous/metrics',
        '/autonomous/faults',
        '/autonomous/orchestrator',
        '/autonomous/lambda/healthcheck',
        '/autonomous/lambda/metrics'
    ]
    
    try:
        cleared_tables = []
        cleared_buckets = []
        cleared_logs = []
        total_deleted = 0
        
        # Clear DynamoDB tables
        for table_def in tables:
            table_name = table_def['name']
            hash_key = table_def['hash_key']
            range_key = table_def['range_key']
            
            try:
                response = dynamodb.scan(TableName=table_name)
                items = response.get('Items', [])
                
                for item in items:
                    key = {
                        hash_key: item.get(hash_key),
                        range_key: item.get(range_key)
                    }
                    dynamodb.delete_item(TableName=table_name, Key=key)
                
                cleared_tables.append(table_name)
                total_deleted += len(items)
                print(f"✓ Cleared {len(items)} items from {table_name}")
            except Exception as e:
                print(f"✗ Error clearing {table_name}: {e}")
        
        # Clear S3 buckets
        for bucket in s3_buckets:
            try:
                # List and delete all objects
                response = s3.list_objects_v2(Bucket=bucket)
                if 'Contents' in response:
                    for obj in response['Contents']:
                        s3.delete_object(Bucket=bucket, Key=obj['Key'])
                    cleared_buckets.append(bucket)
                    print(f"✓ Cleared {len(response['Contents'])} objects from {bucket}")
                else:
                    cleared_buckets.append(bucket)
            except Exception as e:
                print(f"✗ Error clearing bucket {bucket}: {e}")
        
        # Clear CloudWatch log streams
        for log_group in log_groups:
            try:
                # List all log streams
                response = logs_client.describe_log_streams(logGroupName=log_group)
                for stream in response.get('logStreams', []):
                    try:
                        logs_client.delete_log_stream(
                            logGroupName=log_group,
                            logStreamName=stream['logStreamName']
                        )
                    except:
                        pass
                cleared_logs.append(log_group)
                print(f"✓ Cleared log streams from {log_group}")
            except Exception as e:
                print(f"✗ Error clearing logs {log_group}: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Cleared {total_deleted} DB items, {len(cleared_buckets)} S3 buckets, {len(cleared_logs)} log groups',
            'cleared_tables': cleared_tables,
            'cleared_buckets': cleared_buckets,
            'cleared_logs': cleared_logs
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print("="*60)
    print("AUTONOMOUS SYSTEM DASHBOARD")
    print("="*60)
    print(f"Starting dashboard on http://localhost:{port}")
    print("="*60)
    
    # Disable reloader to avoid watchdog compatibility issues with Python 3.13
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False)
