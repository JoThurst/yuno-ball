import unittest
import subprocess
import os
import signal
import atexit

class BaseTestCase(unittest.TestCase):
    redis_process = None
    
    @classmethod
    def setUpClass(cls):
        """Start Redis server before running tests."""
        try:
            redis_path = os.path.join(os.getcwd(), 'redis', 'redis-server.exe')
            config_path = os.path.join(os.getcwd(), 'redis', 'redis.conf')
            cls.redis_process = subprocess.Popen([redis_path, config_path])
            print("[OK] Redis server started for tests")
            
            # Register cleanup on program exit
            atexit.register(cls.tearDownClass)
            
        except Exception as e:
            print(f"[ERROR] Failed to start Redis: {e}")
            raise

    @classmethod
    def tearDownClass(cls):
        """Stop Redis server after tests complete."""
        if hasattr(cls, 'redis_process'):
            cls.redis_process.terminate()
            cls.redis_process.wait()
            print("[OK] Redis server stopped") 