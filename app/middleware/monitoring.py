import time
from functools import wraps
from flask import request, current_app
import boto3
import logging
from psycopg2.extensions import cursor
from db_config import connection_pool, POOL_MAX_CONN
import os
from botocore.config import Config

# Configure logging
logger = logging.getLogger(__name__)

def get_cloudwatch_client():
    """Get CloudWatch client with proper configuration based on environment"""
    if os.getenv('FORCE_LOCAL', 'false').lower() == 'true':
        logger.info("Running in local mode - CloudWatch disabled")
        return None

    try:
        session = boto3.Session()
        return session.client('cloudwatch',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            config=Config(
                retries={'max_attempts': 3},
                connect_timeout=5,
                read_timeout=5
            )
        )
    except Exception as e:
        logger.error(f"Failed to initialize CloudWatch client: {e}")
        return None

def should_send_metrics():
    """Determine if metrics should be sent based on environment."""
    is_local = current_app.config.get('IS_LOCAL', False)
    return not is_local

def track_database_metrics():
    """Decorator to track database query performance."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            start_time = time.time()
            result = None
            query_name = f.__name__
            
            try:
                result = f(*args, **kwargs)
                status = 'success'
            except Exception as e:
                status = 'error'
                raise e
            finally:
                # Calculate query time
                query_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                
                # Get pool statistics
                if connection_pool:
                    used_connections = len(connection_pool._used)
                    total_connections = connection_pool.maxconn
                    pool_utilization = (used_connections / total_connections) * 100
                else:
                    pool_utilization = 0
                
                # Log metrics locally
                logger.debug(f"DB Metrics - Query: {query_name}, Time: {query_time}ms, " +
                           f"Status: {status}, Pool Utilization: {pool_utilization}%")
                
                if should_send_metrics():
                    try:
                        cloudwatch = get_cloudwatch_client()
                        if not cloudwatch:
                            return result
                        cloudwatch.put_metric_data(
                            Namespace='NBA/Database',
                            MetricData=[
                                {
                                    'MetricName': 'QueryExecutionTime',
                                    'Value': query_time,
                                    'Unit': 'Milliseconds',
                                    'Dimensions': [
                                        {'Name': 'QueryName', 'Value': query_name},
                                        {'Name': 'Status', 'Value': status}
                                    ]
                                },
                                {
                                    'MetricName': 'PoolUtilization',
                                    'Value': pool_utilization,
                                    'Unit': 'Percent',
                                    'Dimensions': [
                                        {'Name': 'PoolSize', 'Value': str(POOL_MAX_CONN)}
                                    ]
                                },
                                {
                                    'MetricName': 'ActiveConnections',
                                    'Value': used_connections,
                                    'Unit': 'Count',
                                    'Dimensions': [
                                        {'Name': 'PoolSize', 'Value': str(POOL_MAX_CONN)}
                                    ]
                                }
                            ]
                        )
                    except Exception as e:
                        logger.error(f"Error sending database metrics to CloudWatch: {str(e)}")
            
            return result
        return wrapped
    return decorator

def track_endpoint_metrics():
    """Decorator to track API endpoint metrics in CloudWatch."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            start_time = time.time()
            
            try:
                response = f(*args, **kwargs)
                status_code = response[1] if isinstance(response, tuple) else 200
            except Exception as e:
                status_code = 500
                raise e
            finally:
                # Calculate response time
                response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                
                # Get endpoint path - normalize by replacing variable parts with {param}
                path = request.path
                for arg in request.view_args or {}:
                    path = path.replace(str(request.view_args[arg]), f"{{{arg}}}")
                
                # Log metrics locally
                logger.debug(f"API Metrics - Path: {path}, Method: {request.method}, " +
                           f"Status: {status_code}, Response Time: {response_time}ms")
                
                # Only send to CloudWatch if not in local mode
                if should_send_metrics():
                    try:
                        # Get CloudWatch client with current app context
                        cloudwatch = get_cloudwatch_client()
                        if not cloudwatch:
                            return response
                        
                        # Send metrics to CloudWatch
                        cloudwatch.put_metric_data(
                            Namespace='NBA/API',
                            MetricData=[
                                {
                                    'MetricName': 'ResponseTime',
                                    'Value': response_time,
                                    'Unit': 'Milliseconds',
                                    'Dimensions': [
                                        {'Name': 'Endpoint', 'Value': path},
                                        {'Name': 'Method', 'Value': request.method},
                                        {'Name': 'StatusCode', 'Value': str(status_code)}
                                    ]
                                },
                                {
                                    'MetricName': 'RequestCount',
                                    'Value': 1,
                                    'Unit': 'Count',
                                    'Dimensions': [
                                        {'Name': 'Endpoint', 'Value': path},
                                        {'Name': 'Method', 'Value': request.method},
                                        {'Name': 'StatusCode', 'Value': str(status_code)}
                                    ]
                                }
                            ]
                        )
                    except Exception as e:
                        logger.error(f"Error sending metrics to CloudWatch: {str(e)}")
            
            if isinstance(response, tuple):
                return response
            return response
            
        return wrapped
    return decorator

def init_monitoring(app):
    """Initialize monitoring based on environment"""
    if os.getenv('FORCE_LOCAL', 'false').lower() == 'true':
        logger.info("Local mode - CloudWatch monitoring disabled")
        app.config['LOCAL_MONITORING'] = True
        return

    try:
        # Initialize CloudWatch client
        cloudwatch = get_cloudwatch_client()
        if not cloudwatch:
            app.config['LOCAL_MONITORING'] = True
            return

        app.config['cloudwatch'] = cloudwatch
        app.config['LOCAL_MONITORING'] = False
        
        # Track all API endpoints
        for endpoint, view_func in list(app.view_functions.items()):  # Create a list to avoid runtime modification issues
            if endpoint.startswith('api.'):  # Only track API routes
                wrapped_func = track_endpoint_metrics()(view_func)
                app.view_functions[endpoint] = wrapped_func
        
        # Register error monitoring
        @app.errorhandler(Exception)
        def handle_error(error):
            if not app.config.get('LOCAL_MONITORING'):
                try:
                    cloudwatch = get_cloudwatch_client()
                    if cloudwatch:
                        error_type = error.__class__.__name__
                        
                        cloudwatch.put_metric_data(
                            Namespace='NBA/Errors',
                            MetricData=[
                                {
                                    'MetricName': 'ErrorCount',
                                    'Value': 1,
                                    'Unit': 'Count',
                                    'Dimensions': [
                                        {'Name': 'ErrorType', 'Value': error_type},
                                        {'Name': 'Endpoint', 'Value': request.endpoint or 'unknown'}
                                    ]
                                }
                            ]
                        )
                except Exception as e:
                    logger.error(f"Error tracking error in CloudWatch: {e}")
            return "Internal Server Error", 500

        logger.info("CloudWatch monitoring initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize CloudWatch monitoring: {e}")
        app.config['LOCAL_MONITORING'] = True
