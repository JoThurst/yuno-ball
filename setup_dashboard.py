import boto3
import json
import os
from botocore.config import Config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Dashboard configuration
dashboard_config = {
    "widgets": [
        {
            "type": "metric",
            "x": 0,
            "y": 0,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "NBA/API", "ResponseTime", "Endpoint", "ALL" ],
                    [ ".", "RequestCount", ".", "." ],
                    [ ".", "ErrorCount", ".", "." ]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": "us-east-1",
                "title": "API Performance",
                "period": 300
            }
        },
        {
            "type": "metric",
            "x": 12,
            "y": 0,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "NBA/Database", "QueryExecutionTime", "Operation", "ALL" ],
                    [ ".", "ConnectionCount", ".", "." ],
                    [ ".", "PoolUtilization", ".", "." ]
                ],
                "view": "timeSeries",
                "stacked": False,
                "region": "us-east-1",
                "title": "Database Performance",
                "period": 300
            }
        },
        {
            "type": "metric",
            "x": 0,
            "y": 6,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "NBA/Sessions", "ActiveSessions" ],
                    [ ".", "AuthenticatedUsers" ],
                    [ ".", "AnonymousUsers" ]
                ],
                "view": "timeSeries",
                "stacked": True,
                "region": "us-east-1",
                "title": "User Sessions",
                "period": 300
            }
        },
        {
            "type": "metric",
            "x": 12,
            "y": 6,
            "width": 12,
            "height": 6,
            "properties": {
                "metrics": [
                    [ "NBA/Errors", "ErrorCount", "Type", "ALL" ]
                ],
                "view": "timeSeries",
                "stacked": True,
                "region": "us-east-1",
                "title": "Error Distribution",
                "period": 300
            }
        }
    ]
}

def setup_dashboard():
    """Create or update the CloudWatch dashboard"""
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
        
        response = cloudwatch.put_dashboard(
            DashboardName='NBA-Analytics-Dashboard',
            DashboardBody=json.dumps(dashboard_config)
        )
        print("✅ Dashboard created successfully!")
        return response
    except Exception as e:
        print(f"❌ Error creating dashboard: {e}")
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
    
    setup_dashboard() 