import time
from functools import wraps
from flask import request, current_app, session, g
import boto3
import logging
from datetime import datetime
from psycopg2.extensions import cursor
from db_config import connection_pool, POOL_MAX_CONN
from flask_login import current_user
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

def track_user_sessions():
    """Track user session metrics"""
    if os.getenv('FORCE_LOCAL', 'false').lower() == 'true':
        return

    try:
        cloudwatch = get_cloudwatch_client()
        if not cloudwatch:
            return

        active_sessions = len(current_app.redis.keys('session:*'))
        authenticated_users = len([key for key in current_app.redis.keys('session:*') 
                                if current_app.redis.get(f"user_authenticated:{key}")])
        
        # Log metrics locally
        logger.debug(f"Session Metrics - Active Sessions: {active_sessions}, " +
                    f"Authenticated Users: {authenticated_users}")
        
        cloudwatch.put_metric_data(
            Namespace='NBA/Sessions',
            MetricData=[
                {
                    'MetricName': 'ActiveSessions',
                    'Value': active_sessions,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'AuthenticatedUsers',
                    'Value': authenticated_users,
                    'Unit': 'Count'
                }
            ]
        )
    except Exception as e:
        logger.error(f"Error sending session metrics to CloudWatch: {e}")

def track_user_activity(func):
    """Decorator to track user activity metrics"""
    def wrapped(*args, **kwargs):
        start_time = datetime.now()
        response = func(*args, **kwargs)
        
        if os.getenv('FORCE_LOCAL', 'false').lower() == 'true':
            return response

        try:
            cloudwatch = get_cloudwatch_client()
            if not cloudwatch:
                return response

            # Track user type (authenticated vs anonymous)
            user_type = 'authenticated' if not current_user.is_anonymous else 'anonymous'
            
            cloudwatch.put_metric_data(
                Namespace='NBA/UserActivity',
                MetricData=[
                    {
                        'MetricName': 'PageView',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'UserType', 'Value': user_type},
                            {'Name': 'Endpoint', 'Value': request.endpoint or 'unknown'}
                        ]
                    }
                ]
            )
            
        except Exception as e:
            logger.error(f"Error tracking user activity: {e}")
        
        return response
    return wrapped

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
        for endpoint, view_func in app.view_functions.items():
            if endpoint.startswith('api.'):  # Only track API routes
                app.view_functions[endpoint] = track_endpoint_metrics()(view_func)
            
            # Track user activity on all routes
            app.view_functions[endpoint] = track_user_activity(view_func)(view_func)
        
        # Schedule periodic session monitoring
        @app.before_request
        def monitor_sessions():
            # Only check every 5 minutes (using Redis to track last check)
            last_check = current_app.redis.get('last_session_check')
            current_time = time.time()
            
            if not last_check or (current_time - float(last_check)) > 300:  # 5 minutes
                track_user_sessions()
                current_app.redis.set('last_session_check', current_time)
            
        # Register error monitoring
        @app.errorhandler(Exception)
        def handle_error(error):
            if not app.config.get('LOCAL_MONITORING'):
                try:
                    cloudwatch = get_cloudwatch_client()
                    if not cloudwatch:
                        return "Internal Server Error", 500
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

    except Exception as e:
        logger.error(f"Failed to initialize CloudWatch monitoring: {e}")
        app.config['LOCAL_MONITORING'] = True 