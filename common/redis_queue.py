"""
Class to create a generic redis based queue
"""
import redis 
import json


class RedisQueue():
    def __init__(self, hashname):
        self.hashname = hashname
        self.redis_db = redis.StrictRedis('localhost', 6379, charset="utf-8", decode_responses=True)

    def push(self, data):
        self.redis_db.rpush(self.hashname, json.dumps(data))
    
    def pop(self):
        popped = None 
        if self.length() > 0:
            popped = json.loads(self.redis_db.lpop(self.hashname))
        return popped 
        
    def length(self):
        return self.redis_db.llen(self.hashname)
    
    def list(self, start=0, end=-1):
        data = self.redis_db.lrange(self.hashname, start, end)
        output = []
        while len(data) > 0:
            output.append(json.loads(data.pop(0)))
        return output

    def flush(self):
        self.redis_db.delete(self.hashname)