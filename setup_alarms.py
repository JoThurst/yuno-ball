import boto3
import os
from botocore.config import Config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_alarms():
    """Create CloudWatch alarms for critical metrics"""
    try:
        # Configure AWS client
        config = Config(
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            retries={'max_attempts': 3}
        )
        
        # Create CloudWatch client with credentials from .env
        cloudwatch = boto3.client('cloudwatch',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            config=config
        )
        
        # API Response Time Alarm
        cloudwatch.put_metric_alarm(
            AlarmName='NBA-HighResponseTime',
            MetricName='ResponseTime',
            Namespace='NBA/API',
            Statistic='Average',
            Period=300,  # 5 minutes
            EvaluationPeriods=2,
            Threshold=5.0,  # 5 seconds
            ComparisonOperator='GreaterThanThreshold',
            AlarmDescription='Alert when API response time exceeds 5 seconds'
        )

        # Database Connection Pool Utilization
        cloudwatch.put_metric_alarm(
            AlarmName='NBA-HighPoolUtilization',
            MetricName='PoolUtilization',
            Namespace='NBA/Database',
            Statistic='Average',
            Period=300,
            EvaluationPeriods=2,
            Threshold=80.0,  # 80% utilization
            ComparisonOperator='GreaterThanThreshold',
            AlarmDescription='Alert when connection pool utilization exceeds 80%'
        )

        # Error Rate Alarm
        cloudwatch.put_metric_alarm(
            AlarmName='NBA-HighErrorRate',
            MetricName='ErrorCount',
            Namespace='NBA/Errors',
            Statistic='Sum',
            Period=300,
            EvaluationPeriods=2,
            Threshold=50.0,  # 50 errors in 5 minutes
            ComparisonOperator='GreaterThanThreshold',
            AlarmDescription='Alert when error count exceeds 50 in 5 minutes'
        )

        # Active Sessions Drop Alarm
        cloudwatch.put_metric_alarm(
            AlarmName='NBA-LowActiveSessions',
            MetricName='ActiveSessions',
            Namespace='NBA/Sessions',
            Statistic='Average',
            Period=300,
            EvaluationPeriods=2,
            Threshold=5.0,  # Less than 5 active sessions
            ComparisonOperator='LessThanThreshold',
            AlarmDescription='Alert when active sessions drop below 5'
        )

        print("✅ Alarms created successfully!")

    except Exception as e:
        print(f"❌ Error creating alarms: {e}")
        print("Make sure your .env file contains AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION")
        raise

if __name__ == "__main__":
    # Verify required environment variables
    required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("Please check your .env file")
        exit(1)
    
    # Ensure AWS region is set
    if not os.getenv('AWS_REGION'):
        os.environ['AWS_REGION'] = 'us-east-1'
        print(f"Using default region: {os.getenv('AWS_REGION')}")
    
    create_alarms() 