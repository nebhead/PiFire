"""
Class to create a generic redis handler for logging
"""
import logging

class RedisHandler(logging.Handler):
    def __init__(self, redis_client, redis_key_prefix):
        super().__init__()
        self.redis_client = redis_client
        self.redis_key_prefix = redis_key_prefix

    def emit(self, record):
        message = self.format(record)
        key = f"{self.redis_key_prefix}"
        self.redis_client.lpush(key, message)

    def flush(self):
        self.redis_client.delete(self.redis_key_prefix)