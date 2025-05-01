import redis
from redis.connection import ConnectionPool
from config import REDIS_CONFIG

def create_redis_pool():
    """Create and return a Redis connection pool for Redis Cloud"""
    pool_config = {
        'host': REDIS_CONFIG['host'],
        'username': REDIS_CONFIG['username'],
        'port': REDIS_CONFIG['port'],
        'password': REDIS_CONFIG['password'],
        'decode_responses': True,  # Automatically decode responses to strings
        'max_connections': 10,    # Maximum number of connections in the pool
        'retry_on_timeout': True  # Retry on connection timeout
    }
    return ConnectionPool(**pool_config)

def get_redis_connection(pool):
    """Get a Redis connection from the pool"""
    return redis.Redis(connection_pool=pool)