"""
LocalStack Infrastructure Setup
Creates all required AWS resources on LocalStack FREE tier
"""

import boto3
import json
import os
from botocore.config import Config

# LocalStack configuration
LOCALSTACK_ENDPOINT = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')

config = Config(
    region_name='us-east-1',
    signature_version='s3v4',
    retries={'max_attempts': 3}
)

def create_s3_client():
    return boto3.client(
        's3',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        config=config
    )

def create_dynamodb_client():
    return boto3.client(
        'dynamodb',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )

def create_cloudwatch_client():
    return boto3.client(
        'logs',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )

def create_lambda_client():
    return boto3.client(
        'lambda',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )

def setup_s3_buckets():
    """Create S3 buckets for logs, metrics, and incidents"""
    s3 = create_s3_client()
    
    buckets = [
        'autonomous-logs',
        'autonomous-metrics',
        'autonomous-incidents',
        'autonomous-llm-traces'
    ]
    
    for bucket in buckets:
        try:
            s3.create_bucket(Bucket=bucket)
            print(f"✓ Created S3 bucket: {bucket}")
        except Exception as e:
            print(f"✗ Failed to create bucket {bucket}: {e}")

def setup_dynamodb_tables():
    """Create DynamoDB tables for agent decisions and incident history"""
    dynamodb = create_dynamodb_client()
    
    tables = [
        {
            'TableName': 'llm_actions',
            'KeySchema': [
                {'AttributeName': 'action_id', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'action_id', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'N'}
            ],
            'BillingMode': 'PAY_PER_REQUEST'
        },
        {
            'TableName': 'incidents',
            'KeySchema': [
                {'AttributeName': 'incident_id', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'incident_id', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'N'}
            ],
            'BillingMode': 'PAY_PER_REQUEST'
        },
        {
            'TableName': 'remediations',
            'KeySchema': [
                {'AttributeName': 'remediation_id', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'remediation_id', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'N'}
            ],
            'BillingMode': 'PAY_PER_REQUEST'
        },
        {
            'TableName': 'agent_decisions',
            'KeySchema': [
                {'AttributeName': 'decision_id', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'decision_id', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'N'}
            ],
            'BillingMode': 'PAY_PER_REQUEST'
        },
        {
            'TableName': 'system_metrics',
            'KeySchema': [
                {'AttributeName': 'metric_id', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'metric_id', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'N'}
            ],
            'BillingMode': 'PAY_PER_REQUEST'
        },
        {
            'TableName': 'command_executions',
            'KeySchema': [
                {'AttributeName': 'execution_id', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'execution_id', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'N'}
            ],
            'BillingMode': 'PAY_PER_REQUEST'
        }
    ]
    
    for table_def in tables:
        try:
            dynamodb.create_table(**table_def)
            print(f"✓ Created DynamoDB table: {table_def['TableName']}")
        except Exception as e:
            print(f"✗ Failed to create table {table_def['TableName']}: {e}")

def setup_cloudwatch_logs():
    """Create CloudWatch log groups"""
    logs = create_cloudwatch_client()
    
    log_groups = [
        '/autonomous/detection-agent',
        '/autonomous/remediation-agent',
        '/autonomous/metrics',
        '/autonomous/faults',
        '/autonomous/orchestrator',
        '/autonomous/lambda/healthcheck',
        '/autonomous/lambda/metrics'
    ]
    
    for log_group in log_groups:
        try:
            logs.create_log_group(logGroupName=log_group)
            print(f"✓ Created CloudWatch log group: {log_group}")
        except Exception as e:
            print(f"✗ Failed to create log group {log_group}: {e}")

def verify_setup():
    """Verify all resources were created"""
    print("\n" + "="*60)
    print("VERIFYING INFRASTRUCTURE SETUP")
    print("="*60)
    
    # Verify S3
    s3 = create_s3_client()
    try:
        buckets = s3.list_buckets()
        print(f"\n✓ S3 Buckets: {len(buckets['Buckets'])} found")
        for bucket in buckets['Buckets']:
            print(f"  - {bucket['Name']}")
    except Exception as e:
        print(f"\n✗ S3 verification failed: {e}")
    
    # Verify DynamoDB
    dynamodb = create_dynamodb_client()
    try:
        tables = dynamodb.list_tables()
        print(f"\n✓ DynamoDB Tables: {len(tables['TableNames'])} found")
        for table in tables['TableNames']:
            print(f"  - {table}")
    except Exception as e:
        print(f"\n✗ DynamoDB verification failed: {e}")
    
    # Verify CloudWatch
    logs = create_cloudwatch_client()
    try:
        log_groups = logs.describe_log_groups()
        print(f"\n✓ CloudWatch Log Groups: {len(log_groups['logGroups'])} found")
        for lg in log_groups['logGroups']:
            print(f"  - {lg['logGroupName']}")
    except Exception as e:
        print(f"\n✗ CloudWatch verification failed: {e}")
    
    print("\n" + "="*60)
    print("SETUP COMPLETE")
    print("="*60)

if __name__ == '__main__':
    print("="*60)
    print("AUTONOMOUS SYSTEM - INFRASTRUCTURE SETUP")
    print("="*60)
    print(f"\nLocalStack Endpoint: {LOCALSTACK_ENDPOINT}")
    print("\nCreating infrastructure resources...\n")
    
    setup_s3_buckets()
    print()
    setup_dynamodb_tables()
    print()
    setup_cloudwatch_logs()
    
    verify_setup()
