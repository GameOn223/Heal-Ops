"""
Gemini Flash 2.0 LLM Wrapper with Full Logging
Logs all prompts, responses, and reasoning to DynamoDB and S3
"""

import google.generativeai as genai
import json
import time
import uuid
import os
from datetime import datetime
import boto3
from botocore.config import Config

class GeminiWrapper:
    def __init__(self, api_key=None):
        """Initialize Gemini API and logging infrastructure"""
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set in environment or provided")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # LocalStack clients
        self.localstack_endpoint = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')
        self.dynamodb = self._create_dynamodb_client()
        self.s3 = self._create_s3_client()
        
        print(f"✓ Gemini LLM Wrapper initialized")
    
    def _create_dynamodb_client(self):
        """Create DynamoDB client for LocalStack"""
        return boto3.client(
            'dynamodb',
            endpoint_url=self.localstack_endpoint,
            aws_access_key_id='test',
            aws_secret_access_key='test',
            region_name='us-east-1'
        )
    
    def _create_s3_client(self):
        """Create S3 client for LocalStack"""
        return boto3.client(
            's3',
            endpoint_url=self.localstack_endpoint,
            aws_access_key_id='test',
            aws_secret_access_key='test',
            config=Config(region_name='us-east-1', signature_version='s3v4')
        )
    
    def _log_to_dynamodb(self, action_data):
        """Log LLM action to DynamoDB"""
        try:
            # Truncate prompt to first 500 chars for dashboard display
            prompt_preview = action_data['prompt'][:500] + '...' if len(action_data['prompt']) > 500 else action_data['prompt']
            response_preview = action_data['response'][:500] + '...' if len(action_data['response']) > 500 else action_data['response']
            
            item = {
                'action_id': {'S': action_data['action_id']},
                'timestamp': {'N': str(action_data['timestamp'])},
                'agent_type': {'S': action_data['agent_type']},
                'prompt': {'S': prompt_preview},  # Truncated for display
                'response': {'S': response_preview},  # Truncated for display
                'latency_ms': {'N': str(action_data['latency_ms'])},
                'success': {'BOOL': action_data['success']},
                'error': {'S': action_data.get('error', '')}
            }
            
            self.dynamodb.put_item(
                TableName='llm_actions',
                Item=item
            )
            print(f"  ✓ Logged to DynamoDB: {action_data['action_id']}")
        except Exception as e:
            print(f"  ✗ DynamoDB logging failed: {e}")
    
    def _log_to_s3(self, action_data):
        """Archive full LLM trace to S3"""
        try:
            timestamp = datetime.fromtimestamp(action_data['timestamp'])
            key = f"llm-traces/{timestamp.strftime('%Y/%m/%d')}/{action_data['action_id']}.json"
            
            self.s3.put_object(
                Bucket='autonomous-llm-traces',
                Key=key,
                Body=json.dumps(action_data, indent=2),
                ContentType='application/json'
            )
            print(f"  ✓ Archived to S3: {key}")
        except Exception as e:
            print(f"  ✗ S3 archiving failed: {e}")
    
    def reason(self, prompt, agent_type='generic', context=None):
        """
        Send prompt to Gemini Flash 2.0 and log everything
        
        Args:
            prompt: The reasoning prompt
            agent_type: 'detection', 'remediation', or 'generic'
            context: Optional context dict to include in logs
        
        Returns:
            dict with 'response' and 'action_id'
        """
        action_id = str(uuid.uuid4())
        timestamp = time.time()
        start_time = time.time()
        
        print(f"\n{'='*60}")
        print(f"LLM REASONING REQUEST")
        print(f"{'='*60}")
        print(f"Action ID: {action_id}")
        print(f"Agent Type: {agent_type}")
        print(f"Timestamp: {datetime.fromtimestamp(timestamp).isoformat()}")
        print(f"\nPrompt:\n{prompt[:500]}...")
        
        try:
            # Call Gemini
            response = self.model.generate_content(prompt)
            response_text = response.text
            latency_ms = int((time.time() - start_time) * 1000)
            success = True
            error_msg = ''
            
            print(f"\n{'='*60}")
            print(f"LLM RESPONSE")
            print(f"{'='*60}")
            print(f"Latency: {latency_ms}ms")
            print(f"Response:\n{response_text[:500]}...")
            
        except Exception as e:
            response_text = ''
            latency_ms = int((time.time() - start_time) * 1000)
            success = False
            error_msg = str(e)
            
            print(f"\n{'='*60}")
            print(f"LLM ERROR")
            print(f"{'='*60}")
            print(f"Error: {error_msg}")
        
        # Build action data
        action_data = {
            'action_id': action_id,
            'timestamp': timestamp,
            'agent_type': agent_type,
            'prompt': prompt,
            'response': response_text,
            'latency_ms': latency_ms,
            'success': success,
            'error': error_msg,
            'context': context or {}
        }
        
        # Log to both storage systems
        print(f"\nLogging LLM action...")
        self._log_to_dynamodb(action_data)
        self._log_to_s3(action_data)
        
        print(f"{'='*60}\n")
        
        return {
            'response': response_text,
            'action_id': action_id,
            'success': success,
            'latency_ms': latency_ms
        }
    
    def detect_and_predict(self, metrics, logs, current_incidents):
        """
        Detection Agent: Analyze current state and predict failures
        
        Args:
            metrics: Current system metrics
            logs: Recent log entries
            current_incidents: Active incidents
        
        Returns:
            dict with detected issues and predictions
        """
        prompt = f"""
You are an Incident Detection and Future Risk Prediction Agent.

Your task is to analyze the current system state and:
1. Detect any active failures or anomalies
2. Predict what will break next based on current trends
3. Assess urgency and priority
4. Determine what additional information is needed

CURRENT METRICS:
{json.dumps(metrics, indent=2)}

RECENT LOGS:
{json.dumps(logs[-50:], indent=2)}

ACTIVE INCIDENTS:
{json.dumps(current_incidents, indent=2)}

ANALYSIS REQUIRED:
1. What is currently broken? (Severity: CRITICAL, HIGH, MEDIUM, LOW)
2. What will break soon? (Timeframe: <5min, <30min, <1hr, <24hr)
3. What is the root cause?
4. What additional data do you need?
5. Should remediation be triggered? (YES/NO with reasoning)

Respond in JSON format:
{{
  "current_failures": [
    {{
      "type": "string describing failure",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "affected_components": ["component1", "component2"],
      "evidence": ["metric or log entry"]
    }}
  ],
  "future_risks": [
    {{
      "prediction": "string describing what will break",
      "timeframe": "<5min|<30min|<1hr|<24hr",
      "confidence": "HIGH|MEDIUM|LOW",
      "leading_indicators": ["metric trend", "log pattern"]
    }}
  ],
  "root_cause_analysis": "detailed explanation",
  "missing_information": ["what data is needed"],
  "trigger_remediation": true|false,
  "reasoning": "explain your decision"
}}
"""
        
        result = self.reason(prompt, agent_type='detection', context={
            'metrics_count': len(metrics),
            'logs_count': len(logs),
            'incidents_count': len(current_incidents)
        })
        
        # Parse JSON response
        try:
            response_text = result['response']
            # Remove markdown code blocks if present
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            analysis = json.loads(response_text)
            return analysis
        except (json.JSONDecodeError, IndexError) as e:
            print(f"Warning: LLM response parsing failed: {e}")
            print(f"Response preview: {result['response'][:200]}...")
            return {'raw_response': result['response'], 'parse_error': True, 'current_failures': [], 'future_risks': [], 'trigger_remediation': False}
    
    def plan_remediation(self, incident, system_state):
        """
        Remediation Agent: Plan and decide fixes
        
        Args:
            incident: The detected incident
            system_state: Current system state
        
        Returns:
            dict with remediation steps
        """
        prompt = f"""
You are a Remediation Planning and Execution Agent.

Your task is to plan step-by-step fixes for the detected incident.

INCIDENT:
{json.dumps(incident, indent=2)}

SYSTEM STATE:
{json.dumps(system_state, indent=2)}

REMEDIATION PLANNING:
1. What are the exact steps to fix this issue?
2. What commands should be executed?
3. What changes need to be made?
4. How will you verify success?
5. What are the risks and rollback procedures?

Respond in JSON format:
{{
  "remediation_plan": [
    {{
      "step": 1,
      "action": "describe action",
      "command": "exact command to execute or null",
      "expected_outcome": "what should happen",
      "verification": "how to check success"
    }}
  ],
  "estimated_duration_minutes": 5,
  "risks": ["potential issue 1", "potential issue 2"],
  "rollback_procedure": "how to undo if it fails",
  "confidence": "HIGH|MEDIUM|LOW"
}}
"""
        
        result = self.reason(prompt, agent_type='remediation', context={
            'incident_type': incident.get('type', 'unknown')
        })
        
        # Parse JSON response
        try:
            response_text = result['response']
            # Remove markdown code blocks if present
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            plan = json.loads(response_text)
            return plan
        except (json.JSONDecodeError, IndexError) as e:
            print(f"Warning: Remediation plan parsing failed: {e}")
            return {'raw_response': result['response'], 'parse_error': True, 'remediation_plan': []}
    
    def verify_remediation(self, remediation_plan, pre_metrics, post_metrics):
        """
        Verification: Check if remediation succeeded
        
        Args:
            remediation_plan: The executed plan
            pre_metrics: Metrics before remediation
            post_metrics: Metrics after remediation
        
        Returns:
            dict with verification results
        """
        prompt = f"""
You are a Remediation Verification Agent.

Your task is to determine if the remediation was successful.

REMEDIATION PLAN EXECUTED:
{json.dumps(remediation_plan, indent=2)}

METRICS BEFORE:
{json.dumps(pre_metrics, indent=2)}

METRICS AFTER:
{json.dumps(post_metrics, indent=2)}

VERIFICATION QUESTIONS:
1. Did the remediation resolve the issue?
2. Are metrics improved?
3. Are there any new problems introduced?
4. Should we retry or escalate?

Respond in JSON format:
{{
  "success": true|false,
  "improvement_percentage": 0-100,
  "resolved_issues": ["issue1", "issue2"],
  "remaining_issues": ["issue1", "issue2"],
  "new_issues": ["issue1", "issue2"],
  "recommendation": "COMPLETE|RETRY|ESCALATE|ROLLBACK",
  "reasoning": "detailed explanation"
}}
"""
        
        result = self.reason(prompt, agent_type='verification', context={
            'plan_steps': len(remediation_plan.get('remediation_plan', []))
        })
        
        # Parse JSON response
        try:
            response_text = result['response']
            # Remove markdown code blocks if present
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            verification = json.loads(response_text)
            return verification
        except (json.JSONDecodeError, IndexError) as e:
            print(f"Warning: Verification parsing failed: {e}")
            return {'raw_response': result['response'], 'parse_error': True, 'success': False}


if __name__ == '__main__':
    # Test the wrapper
    print("Testing Gemini LLM Wrapper...")
    
    wrapper = GeminiWrapper()
    
    # Test basic reasoning
    test_result = wrapper.reason(
        "Analyze this: CPU usage is at 95% and memory is at 80%. What should we do?",
        agent_type='test'
    )
    
    print(f"\nTest completed. Action ID: {test_result['action_id']}")
