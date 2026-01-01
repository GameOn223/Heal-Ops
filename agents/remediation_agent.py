"""
Remediation Agent
Plans and executes fixes for detected incidents
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import uuid
import subprocess
from datetime import datetime
import boto3
from llm.nvidia_nim_wrapper import NvidiaNIMWrapper

class RemediationAgent:
    def __init__(self):
        self.llm = NvidiaNIMWrapper()
        self.localstack_endpoint = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')
        self.dynamodb = self._create_dynamodb_client()
        self.logs_client = self._create_logs_client()
        
        print("✓ Remediation Agent initialized")
    
    def _create_dynamodb_client(self):
        return boto3.client(
            'dynamodb',
            endpoint_url=self.localstack_endpoint,
            aws_access_key_id='test',
            aws_secret_access_key='test',
            region_name='us-east-1'
        )
    
    def _create_logs_client(self):
        return boto3.client(
            'logs',
            endpoint_url=self.localstack_endpoint,
            aws_access_key_id='test',
            aws_secret_access_key='test',
            region_name='us-east-1'
        )
    
    def _log_command_execution(self, execution_id, remediation_id, command, exit_code, output, error):
        """Log command execution to DynamoDB"""
        try:
            item = {
                'execution_id': {'S': execution_id},
                'timestamp': {'N': str(time.time())},
                'remediation_id': {'S': remediation_id},
                'command': {'S': command[:1000]},
                'exit_code': {'N': str(exit_code)},
                'output': {'S': output[:5000]},
                'error': {'S': error[:5000]},
                'status': {'S': 'SUCCESS' if exit_code == 0 else 'FAILED'}
            }
            
            self.dynamodb.put_item(
                TableName='command_executions',
                Item=item
            )
        except Exception as e:
            print(f"  Warning: Could not log command execution: {e}")
    
    def _log_remediation(self, log_stream, message):
        """Log remediation action to CloudWatch"""
        try:
            # Create log stream if needed
            try:
                self.logs_client.create_log_stream(
                    logGroupName='/autonomous/remediation-agent',
                    logStreamName=log_stream
                )
            except:
                pass
            
            # Put log event
            self.logs_client.put_log_events(
                logGroupName='/autonomous/remediation-agent',
                logStreamName=log_stream,
                logEvents=[{
                    'timestamp': int(time.time() * 1000),
                    'message': json.dumps(message) if isinstance(message, dict) else message
                }]
            )
        except Exception as e:
            print(f"  Warning: Could not log to CloudWatch: {e}")
    
    def get_system_state(self):
        """Get current system state for remediation planning"""
        # Get recent metrics
        try:
            response = self.dynamodb.scan(
                TableName='system_metrics',
                Limit=10
            )
            
            metrics = []
            for item in response.get('Items', []):
                metrics.append({
                    'metric_id': item.get('metric_id', {}).get('S', ''),
                    'timestamp': float(item.get('timestamp', {}).get('N', 0))
                })
        except:
            metrics = []
        
        # Get recent agent decisions
        try:
            response = self.dynamodb.scan(
                TableName='agent_decisions',
                Limit=10
            )
            
            decisions = []
            for item in response.get('Items', []):
                decisions.append({
                    'decision_id': item.get('decision_id', {}).get('S', ''),
                    'timestamp': float(item.get('timestamp', {}).get('N', 0)),
                    'agent_type': item.get('agent_type', {}).get('S', '')
                })
        except:
            decisions = []
        
        return {
            'metrics': metrics,
            'recent_decisions': decisions,
            'timestamp': time.time()
        }
    
    def plan_remediation(self, incident):
        """Create remediation plan for incident"""
        print(f"\n{'='*60}")
        print("REMEDIATION AGENT - PLANNING")
        print(f"{'='*60}")
        print(f"Incident: {incident.get('type', 'UNKNOWN')}")
        print(f"Severity: {incident.get('severity', 'UNKNOWN')}")
        
        # Get system state
        print("\n1. Collecting system state...")
        system_state = self.get_system_state()
        
        # Use LLM to create plan
        print("\n2. Generating remediation plan with Gemini...")
        plan = self.llm.plan_remediation(
            incident=incident,
            system_state=system_state
        )
        
        print("\n3. Remediation Plan:")
        if 'remediation_plan' in plan:
            for step in plan['remediation_plan']:
                print(f"   Step {step.get('step', '?')}: {step.get('action', 'Unknown')}")
        else:
            print("   Warning: No structured plan returned")
        
        print(f"{'='*60}\n")
        
        return plan
    
    def execute_remediation(self, plan, incident):
        """Execute remediation plan"""
        print(f"\n{'='*60}")
        print("REMEDIATION AGENT - EXECUTION")
        print(f"{'='*60}")
        
        remediation_id = str(uuid.uuid4())
        log_stream = f"remediation-{remediation_id}"
        
        self._log_remediation(log_stream, {
            'event': 'REMEDIATION_START',
            'remediation_id': remediation_id,
            'incident': incident,
            'timestamp': datetime.now().isoformat()
        })
        
        execution_results = []
        
        if 'remediation_plan' not in plan:
            print("Error: No remediation plan found")
            return {'success': False, 'error': 'No plan available'}
        
        # Capture pre-remediation metrics
        pre_metrics = self.get_system_state()
        
        # Execute each step
        for step in plan['remediation_plan']:
            step_num = step.get('step', '?')
            action = step.get('action', 'Unknown')
            command = step.get('command')
            
            print(f"\nExecuting Step {step_num}: {action}")
            
            step_result = {
                'step': step_num,
                'action': action,
                'command': command,
                'success': False,
                'output': '',
                'error': ''
            }
            
            if command and command.lower() != 'null':
                # Execute command
                try:
                    print(f"  Running: {command}")
                    
                    # For safety, we'll simulate command execution
                    # In production, use subprocess carefully
                    if 'restart' in command.lower():
                        step_result['output'] = f"Simulated restart command: {command}"
                        step_result['success'] = True
                        print(f"  ✓ Simulated: {command}")
                    elif 'kill' in command.lower():
                        step_result['output'] = f"Simulated kill command: {command}"
                        step_result['success'] = True
                        print(f"  ✓ Simulated: {command}")
                    elif 'clean' in command.lower() or 'rm' in command.lower():
                        step_result['output'] = f"Simulated cleanup: {command}"
                        step_result['success'] = True
                        print(f"  ✓ Simulated: {command}")
                    else:
                        step_result['output'] = f"Simulated execution: {command}"
                        step_result['success'] = True
                        print(f"  ✓ Simulated: {command}")
                    
                    # Log command execution to DynamoDB
                    self._log_command_execution(
                        execution_id=str(uuid.uuid4()),
                        remediation_id=remediation_id,
                        command=command,
                        exit_code=0,
                        output=step_result['output'],
                        error=step_result['error']
                    )
                    
                except Exception as e:
                    step_result['error'] = str(e)
                    step_result['success'] = False
                    print(f"  ✗ Failed: {e}")
                    
                    # Log failed command
                    self._log_command_execution(
                        execution_id=str(uuid.uuid4()),
                        remediation_id=remediation_id,
                        command=command,
                        exit_code=1,
                        output='',
                        error=str(e)
                    )
            else:
                # Manual action required
                step_result['output'] = f"Manual action: {action}"
                step_result['success'] = True
                print(f"  ℹ Manual action logged: {action}")
            
            execution_results.append(step_result)
            
            self._log_remediation(log_stream, {
                'event': 'STEP_COMPLETED',
                'step': step_num,
                'result': step_result
            })
        
        # Capture post-remediation metrics (quick MVP mode)
        post_metrics = self.get_system_state()
        
        # Auto-verify success for MVP (skip LLM verification)
        print(f"\n{'='*60}")
        print("VERIFICATION")
        print(f"{'='*60}")
        
        # MVP: Assume success based on execution results
        all_steps_passed = all(r.get('success', False) for r in execution_results)
        verification = {
            'success': all_steps_passed,
            'recommendation': 'RESOLVED' if all_steps_passed else 'NEEDS_ATTENTION',
            'message': 'Remediation executed successfully' if all_steps_passed else 'Some steps failed'
        }
        
        print(f"\nSuccess: {verification['success']}")
        print(f"Recommendation: {verification['recommendation']}")
        print("  ✓ MVP Mode: Quick verification enabled")
        
        # Store remediation in DynamoDB
        remediation_data = {
            'remediation_id': {'S': remediation_id},
            'timestamp': {'N': str(time.time())},
            'incident': {'S': json.dumps(incident)[:5000]},
            'plan': {'S': json.dumps(plan)[:5000]},
            'execution_results': {'S': json.dumps(execution_results)[:5000]},
            'verification': {'S': json.dumps(verification)[:5000]},
            'success': {'BOOL': verification.get('success', False)}
        }
        
        try:
            self.dynamodb.put_item(
                TableName='remediations',
                Item=remediation_data
            )
            print(f"\n✓ Stored remediation: {remediation_id}")
        except Exception as e:
            print(f"\n✗ Failed to store remediation: {e}")
        
        self._log_remediation(log_stream, {
            'event': 'REMEDIATION_COMPLETE',
            'remediation_id': remediation_id,
            'verification': verification,
            'timestamp': datetime.now().isoformat()
        })
        
        print(f"{'='*60}\n")
        
        return {
            'remediation_id': remediation_id,
            'execution_results': execution_results,
            'verification': verification
        }
    
    def remediate_incident(self, incident):
        """Full remediation flow: plan → execute → verify"""
        print(f"\n{'#'*60}")
        print("REMEDIATION AGENT - FULL CYCLE")
        print(f"{'#'*60}")
        
        # Plan
        plan = self.plan_remediation(incident)
        
        # Execute
        result = self.execute_remediation(plan, incident)
        
        print(f"\n{'#'*60}")
        print("REMEDIATION COMPLETE")
        print(f"{'#'*60}")
        print(f"Remediation ID: {result['remediation_id']}")
        print(f"Success: {result['verification'].get('success', False)}")
        print(f"{'#'*60}\n")
        
        return result


if __name__ == '__main__':
    agent = RemediationAgent()
    
    # Test with sample incident
    test_incident = {
        'type': 'HIGH_CPU_USAGE',
        'severity': 'HIGH',
        'affected_components': ['web-api'],
        'evidence': ['CPU at 95%', 'Response time degraded']
    }
    
    print("Testing remediation with sample incident...")
    result = agent.remediate_incident(test_incident)
    
    print("\n" + "="*60)
    print("REMEDIATION SUMMARY")
    print("="*60)
    print(json.dumps(result, indent=2, default=str))
