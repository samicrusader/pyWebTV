import json as jsonlib

class Response:
    def __init__(self, status, message, headers, content):
        self.status = status
        self.message = message
        self.headers = headers
        self.content = content

    def __repr__(self):
        return "<Response [%d]>" % (self.status)
    
    def json(self):
        return jsonlib.loads(self.content)
    
    @property
    def text(self):
        return self.content.decode("UTF-8", errors="ignore")
