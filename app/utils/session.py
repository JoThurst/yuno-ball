from flask import current_app
from datetime import datetime
import json
from app.utils.cache_utils import get_cache, set_cache, delete_cache

def get_user_sessions(user_id):
    """Get all active sessions for a user."""
    sessions = []
    session_keys = get_cache(f"user_sessions:{user_id}") or []
    
    for session_id in session_keys:
        session_data = get_cache(f"session:{session_id}")
        if session_data:
            try:
                session = json.loads(session_data)
                sessions.append({
                    'id': session_id,
                    'device': session.get('user_agent', 'Unknown Device'),
                    'ip': session.get('ip', 'Unknown'),
                    'last_active': datetime.fromtimestamp(session.get('last_active', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                    'is_current': session.get('is_current', False)
                })
            except Exception as e:
                current_app.logger.error(f"Error parsing session data: {str(e)}")
                continue
    
    return sorted(sessions, key=lambda x: x['last_active'], reverse=True)

def create_session(user_id, session_id, user_agent, ip):
    """Create a new session for a user."""
    try:
        # Get existing session list
        session_keys = get_cache(f"user_sessions:{user_id}") or []
        
        # Add new session if not exists
        if session_id not in session_keys:
            session_keys.append(session_id)
            set_cache(f"user_sessions:{user_id}", session_keys)
        
        # Store session data
        session_data = {
            'user_agent': user_agent,
            'ip': ip,
            'last_active': datetime.now().timestamp(),
            'is_current': True
        }
        set_cache(f"session:{session_id}", json.dumps(session_data))
        
        # Update other sessions to not be current
        for other_session_id in session_keys:
            if other_session_id != session_id:
                other_session_data = get_cache(f"session:{other_session_id}")
                if other_session_data:
                    try:
                        data = json.loads(other_session_data)
                        data['is_current'] = False
                        set_cache(f"session:{other_session_id}", json.dumps(data))
                    except:
                        continue
        
        return True
    except Exception as e:
        current_app.logger.error(f"Error creating session: {str(e)}")
        return False

def update_session(session_id):
    """Update the last active timestamp of a session."""
    try:
        session_data = get_cache(f"session:{session_id}")
        if session_data:
            data = json.loads(session_data)
            data['last_active'] = datetime.now().timestamp()
            set_cache(f"session:{session_id}", json.dumps(data))
            return True
    except Exception as e:
        current_app.logger.error(f"Error updating session: {str(e)}")
    return False

def delete_session(user_id, session_id=None, all_sessions=False):
    """Delete a user's session(s)."""
    try:
        session_keys = get_cache(f"user_sessions:{user_id}") or []
        
        if all_sessions:
            # Delete all sessions
            for sid in session_keys:
                delete_cache(f"session:{sid}")
            delete_cache(f"user_sessions:{user_id}")
        else:
            # Delete specific session
            if session_id in session_keys:
                delete_cache(f"session:{session_id}")
                session_keys.remove(session_id)
                set_cache(f"user_sessions:{user_id}", session_keys)
        
        return True
    except Exception as e:
        current_app.logger.error(f"Error deleting session: {str(e)}")
        return False

def cleanup_expired_sessions():
    """Clean up expired sessions (older than 30 days)."""
    try:
        # This would be run as a periodic task
        # Implementation depends on your task scheduler
        pass
    except Exception as e:
        current_app.logger.error(f"Error cleaning up sessions: {str(e)}")
        return False 