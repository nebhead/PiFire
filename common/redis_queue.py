"""
Class to create a generic redis based queue
"""
import redis 
import json


class RedisQueue():
    def __init__(self, hashname):
        self.hashname = hashname
        self.redis_db = redis.StrictRedis(
            'localhost',
            6379,
            charset="utf-8",
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
            health_check_interval=30,
        )

    def push(self, data):
        try:
            self.redis_db.rpush(self.hashname, json.dumps(data))
        except redis.exceptions.RedisError:
            return
    
    def pop(self):
        popped = None 
        try:
            if self.length() > 0:
                raw_data = self.redis_db.lpop(self.hashname)
                if raw_data is not None:
                    popped = json.loads(raw_data)
        except (redis.exceptions.RedisError, TypeError, ValueError):
            popped = None
        return popped 
        
    def length(self):
        try:
            return self.redis_db.llen(self.hashname)
        except redis.exceptions.RedisError:
            return 0
    
    def list(self, start=0, end=-1):
        try:
            data = self.redis_db.lrange(self.hashname, start, end)
        except redis.exceptions.RedisError:
            return []

        output = []
        while len(data) > 0:
            try:
                output.append(json.loads(data.pop(0)))
            except (TypeError, ValueError):
                continue
        return output

    def flush(self):
        try:
            self.redis_db.delete(self.hashname)
        except redis.exceptions.RedisError:
            return