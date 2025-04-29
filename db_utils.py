from dbutils.pooled_db import PooledDB
import pymysql
from config import DB_CONFIG

def create_db_pool():
    """Create and return a database connection pool for Aiven MySQL"""
    return PooledDB(
        creator=pymysql,
        maxconnections=10,
        mincached=2,
        host=DB_CONFIG['host'],
        port=DB_CONFIG.get('port', 3306),  # Default to Aiven's MySQL port
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database'],
        cursorclass=pymysql.cursors.DictCursor,
        ping=1,
        ssl={
            'ca': None,  
            'check_hostname': True 
        }
    )

def get_db_connection(pool):
    """Get a connection from the pool"""
    return pool.connection()