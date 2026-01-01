"""
Nvidia NIM LLM Wrapper with Full Logging
Uses OpenAI SDK to connect to Nvidia NIM API
Logs all prompts, responses, and reasoning to DynamoDB and S3
"""

from openai import OpenAI
import json
import time
import uuid
import os
from datetime import datetime
import boto3
from botocore.config import Config

class NvidiaNIMWrapper:
    def __init__(self, api_key=None, base_url=None):
        """Initialize Nvidia NIM API and logging infrastructure"""
        self.api_key = api_key or os.getenv('NVIDIA_API_KEY')
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY must be set in environment or provided")
        
        # Nvidia NIM endpoint (use local or cloud)
        self.base_url = base_url or os.getenv('NVIDIA_NIM_URL', 'https://integrate.api.nvidia.com/v1')
        
        # Initialize OpenAI client pointing to Nvidia NIM
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # Model to use
        self.model = "openai/gpt-oss-20b"
        
        # LocalStack clients
        self.localstack_endpoint = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')
        self.dynamodb = self._create_dynamodb_client()
        self.s3 = self._create_s3_client()
        
        print(f"✓ Nvidia NIM LLM Wrapper initialized (model: {self.model})")
    
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
    
    def reason(self, prompt, agent_type="general", max_tokens=8000, temperature=0.7):
        """
        Call Nvidia NIM API with full logging
        
        Args:
            prompt: The prompt to send to the LLM
            agent_type: Type of agent making the request (detection, remediation, etc.)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            
        Returns:
            dict: Response with prompt, response text, and metadata
        """
        action_id = str(uuid.uuid4())
        timestamp = time.time()
        
        print(f"\n{'='*60}")
        print("LLM REASONING REQUEST")
        print(f"{'='*60}")
        print(f"Action ID: {action_id}")
        print(f"Agent Type: {agent_type}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"\nPrompt:\n{prompt[:500]}...")
        
        start_time = time.time()
        success = False
        response_text = ""
        error_msg = ""
        
        try:
            # Call Nvidia NIM API
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert system reliability engineer and incident response specialist."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            response_text = completion.choices[0].message.content
            success = True
            
            print(f"\n{'='*60}")
            print("LLM RESPONSE")
            print(f"{'='*60}")
            print(f"{response_text[:500]}...")
            
        except Exception as e:
            error_msg = str(e)
            success = False
            print(f"\n{'='*60}")
            print("LLM ERROR")
            print(f"{'='*60}")
            print(f"Error: {error_msg}")
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log action
        action_data = {
            'action_id': action_id,
            'timestamp': timestamp,
            'agent_type': agent_type,
            'prompt': prompt,
            'response': response_text,
            'latency_ms': latency_ms,
            'success': success,
            'error': error_msg,
            'model': self.model
        }
        
        print(f"\nLogging LLM action...")
        self._log_to_dynamodb(action_data)
        self._archive_to_s3(action_data)
        print(f"{'='*60}\n")
        
        return {
            'action_id': action_id,
            'prompt': prompt,
            'response': response_text,
            'latency_ms': latency_ms,
            'success': success,
            'error': error_msg,
            'model': self.model
        }
    
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
            print(f"  ✗ Failed to log to DynamoDB: {e}")
    
    def _archive_to_s3(self, action_data):
        """Archive full LLM interaction to S3"""
        try:
            # Full trace with all details
            trace = {
                'action_id': action_data['action_id'],
                'timestamp': action_data['timestamp'],
                'timestamp_iso': datetime.fromtimestamp(action_data['timestamp']).isoformat(),
                'agent_type': action_data['agent_type'],
                'model': action_data['model'],
                'prompt': action_data['prompt'],  # Full prompt
                'response': action_data['response'],  # Full response
                'latency_ms': action_data['latency_ms'],
                'success': action_data['success'],
                'error': action_data.get('error', '')
            }
            
            # Organize by date
            now = datetime.fromtimestamp(action_data['timestamp'])
            key = f"llm-traces/{now.year}/{now.month:02d}/{now.day:02d}/{action_data['action_id']}.json"
            
            self.s3.put_object(
                Bucket='autonomous-llm-traces',
                Key=key,
                Body=json.dumps(trace, indent=2),
                ContentType='application/json'
            )
            print(f"  ✓ Archived to S3: {key}")
        except Exception as e:
            print(f"  ✗ Failed to archive to S3: {e}")
    
    def detect_and_predict(self, metrics=None, logs=None, current_incidents=None):
        """
        Analyze metrics and detect failures/predict risks
        
        Args:
            metrics: Dict containing system metrics, logs, etc.
            logs: CloudWatch logs (can be passed separately or included in metrics)
            current_incidents: List of current active incidents
            
        Returns:
            dict: Analysis with current_failures, future_risks, and trigger_remediation
        """
        # Combine all inputs
        if metrics is None:
            metrics = {}
        if logs is not None:
            metrics['cloudwatch_logs'] = logs
        if current_incidents is not None:
            metrics['current_incidents'] = current_incidents
            
        prompt = f"""You are an Incident Detection and Future Risk Prediction Agent.

Your task is to analyze the current system state and:
1. Detect any active failures or anomalies
2. Predict what will break next based on current trends
3. Assess urgency and priority
4. Determine what additional information is needed

CURRENT METRICS:
{json.dumps(metrics, indent=2)}

Respond with JSON ONLY (no markdown, no code blocks):
{{
    "current_failures": [
        {{
            "type": "Service Crash | CPU Saturation | Memory Leak | Disk Full | Network Issue",
            "severity": "CRITICAL | HIGH | MEDIUM | LOW",
            "affected_components": ["component1", "component2"],
            "evidence": ["observation1", "observation2"],
            "confidence": 0.0-1.0
        }}
    ],
    "future_risks": [
        {{
            "risk_type": "Resource Exhaustion | Cascading Failure | Data Loss",
            "probability": 0.0-1.0,
            "time_to_failure": "immediate | minutes | hours | days",
            "preventive_actions": ["action1", "action2"]
        }}
    ],
    "root_cause_analysis": "Brief analysis of root causes",
    "trigger_remediation": true/false,
    "confidence_score": 0.0-1.0
}}"""

        result = self.reason(prompt, agent_type="DETECTION", temperature=0.3)
        
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
        Create remediation plan for incident
        
        Args:
            incident: Dict describing the incident
            system_state: Current system state
            
        Returns:
            dict: Remediation plan with steps
        """
        prompt = f"""You are a Remediation Planning Agent.

Your task is to create a detailed remediation plan for the following incident:

INCIDENT:
{json.dumps(incident, indent=2)}

CURRENT SYSTEM STATE:
{json.dumps(system_state, indent=2)}

Respond with JSON ONLY (no markdown, no code blocks):
{{
    "remediation_plan": [
        {{
            "step": 1,
            "action": "Detailed action description",
            "command": "exact command to execute (or null for manual action)",
            "expected_outcome": "what should happen",
            "rollback_command": "command to undo this step if needed",
            "risk_level": "LOW | MEDIUM | HIGH"
        }}
    ],
    "estimated_duration_minutes": 5,
    "prerequisites": ["prerequisite1", "prerequisite2"],
    "potential_side_effects": ["effect1", "effect2"],
    "success_criteria": ["criterion1", "criterion2"]
}}"""

        result = self.reason(prompt, agent_type="REMEDIATION", temperature=0.3)
        
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
        Verify if remediation was successful
        
        Args:
            remediation_plan: The plan that was executed
            pre_metrics: Metrics before remediation
            post_metrics: Metrics after remediation
            
        Returns:
            dict: Verification result with success flag and analysis
        """
        prompt = f"""You are a Remediation Verification Agent.

Your task is to verify if the remediation was successful by comparing before/after metrics.

REMEDIATION PLAN EXECUTED:
{json.dumps(remediation_plan, indent=2)}

PRE-REMEDIATION METRICS:
{json.dumps(pre_metrics, indent=2)}

POST-REMEDIATION METRICS:
{json.dumps(post_metrics, indent=2)}

Respond with JSON ONLY (no markdown, no code blocks):
{{
    "success": true/false,
    "confidence": 0.0-1.0,
    "improvements": ["improvement1", "improvement2"],
    "remaining_issues": ["issue1", "issue2"],
    "recommendation": "COMPLETE | PARTIAL_SUCCESS | FAILED | NEEDS_RETRY",
    "analysis": "Detailed analysis of the remediation outcome"
}}"""

        result = self.reason(prompt, agent_type="VERIFICATION", temperature=0.2)
        
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
