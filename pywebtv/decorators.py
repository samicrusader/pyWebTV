# -*- coding: UTF-8 -*-

lookuptable = {
    200: '200 OK',
    302: '302 Found',
    404: '404 MSN TV ran into a technical problem. Please try again.',
    500: '500 MSN TV ran into a technical problem. Please try again.'
}

class WTVPError():
    def __init__(self, status_code:int):
        self.status_code = status_code
    
    def generate_response(self):
        data = lookuptable[self.status_code]
        data += '\r\n'
        data += 'Connection: Keep-Alive\r\n'
        data += '\r\n'
        data = data.encode()
        return data

class WTVPResponse():
    """
    WebTV protocol response class.

    This essentially handles responses between each function within the service
    script in a clean and concise manner, so things like encryption can be
    handled with the handler itself.
    """

    def __init__(self, content_type:str, data:bytes=b'', status_code:int=200, headers:dict={}, forceEncrypt:bool=False, forceEncryptObj=None):
        """
        Initializes the class by setting shared variables.
        """
        self.status_code = status_code
        self.headers = headers
        self.content_length = len(data)
        self.content_type = content_type
        self.data = data
        self.forceEncrypt = forceEncrypt
        if self.forceEncrypt:
            self.forceEncryptObj = forceEncryptObj

    def generate_response(self):
        """
        This generates a response that can be returned directly (for
        non-encrypted sessions), or to be encrypted by the base
        request handler class.
        """
        if self.forceEncrypt:
            return self.generate_encrypted_response(self.forceEncryptObj)
        data = lookuptable[self.status_code]
        data += '\r\n'
        data += 'Connection: Keep-Alive\r\n'
        for key, value in self.headers.items():
            if key.find('^n') > -1:
                key = key.split('^n')[0] # hack for multiple headers wtv-service
            data += f'{key}: {value}\r\n'
        data += f'Content-Length: {self.content_length}\r\n'
        data += f'Content-Type: {self.content_type}\r\n'
        data += '\r\n'
        data = data.encode()
        data += self.data
        return data
    
    def generate_encrypted_response(self, sec):
        data = self.lookuptable[self.status_code]
        data += '\r\n'
        data += 'Connection: Keep-Alive\r\n'
        data += 'wtv-encrypted: true\r\n'
        for key, value in self.headers.items():
            if key.find('^n') > -1:
                key = key.split('^n')[0] # hack for multiple headers wtv-service
            data += f'{key}: {value}\r\n'
        encdata = sec.EncryptKey2(self.data)
        data += f'Content-Length: {len(encdata)}\r\n'
        data += f'Content-Type: {self.content_type}\r\n'
        data += '\r\n'
        data = data.encode()
        data += encdata
        return data