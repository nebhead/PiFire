"""
Class to create a generic redis handler for logging
"""
import logging
import redis

class RedisHandler(logging.Handler):
    def __init__(self, redis_client, redis_key_prefix):
        super().__init__()
        self.redis_client = redis_client
        self.redis_key_prefix = redis_key_prefix

    def emit(self, record):
        message = self.format(record)
        key = f"{self.redis_key_prefix}"
        try:
            self.redis_client.lpush(key, message)
        except redis.exceptions.RedisError:
            pass

    def flush(self):
        try:
            self.redis_client.delete(self.redis_key_prefix)
        except redis.exceptions.RedisError:
            pass