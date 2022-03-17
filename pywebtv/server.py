# -*- coding: UTF-8 -*-

import logging
import socketserver
from urllib.parse import quote, unquote

class WTVPServer(socketserver.ThreadingTCPServer):
    """
    WebTV protocol server class.

    This class essentially serves to leech onto ThreadingTCPServer and modify some options that it uses.
    """
    daemon_threads = True
    allow_reuse_address = 1

    def server_bind(self):
        """
        Binds the server to the TCP socket.
        """
        socketserver.ThreadingTCPServer.server_bind(self)
        host, port = self.server_address[:2]
        logging.info(f'Service listening on {host}:{port}.')

class WTVPRequestRouter(socketserver.StreamRequestHandler):
    """
    WebTV request routing class.

    This class will handle requests made to the server.
    """
    close_connection:bool = True
    service_ip:str = None
    service_dir:str = None
    service_config:dict = None
    service_name:str = None

    def __init__(self, *args, service_config, service_dir, service_ip, **kwargs):
        """
        This will initialize service settings.
        """
        self.service_ip = service_ip
        self.service_dir = service_dir
        self.service_config = service_config
        super().__init__(*args, **kwargs)

    def handle(self):
        """
        This allows Keep-Alive or secure requests to go through without dropping after the request is handled.
        
        It will pass requests through to the actual request handler.
        """
        logging.debug(f'Connection from {self.client_address[0]}:{self.client_address[1]}')
        self.close_connection = True
        self.handle_request()
        while not self.close_connection:
            self.handle_request()
        return

    def handle_request(self):
        """
        This function is the main request handler function.
        It will determine if the connection is plaintext, secure, or normal HTTP,
        then call functions to parse, perform, and log the request.
        """
        self.requestline = self.rfile.readline(65536).decode().strip()
        if not self.requestline:
            logging.debug(f'Connection from {self.client_address[0]}:{self.client_address[1]} dropped.')
            self.close_connection = True
            return

        words = self.requestline.split(' ')
        if self.requestline.endswith('HTTP/1.0') or self.requestline.endswith('HTTP/1.1'):
            self.wfile.write(f'''{words[-1]} 301 Moved\nConnection: close\nContent-Length: 0\nContent-Type: text/html\nLocation: https://github.com/samicrusader/pyWebTV\n\n'''.encode())
        elif words[0] not in ['GET', 'POST', 'HEAD']:
            self.wfile.write(b'400 Bad Request\nConnection: close\n\n')
            self.close_connection = True
            return
        else:
            self.zrfile = self.rfile
            self.zwfile = self.wfile
            request_handler = WTVPRequestHandler(
                rfile=self.zrfile, 
                wfile=self.zwfile,
                close_connection=self.close_connection, 
                service_config=self.service_config, 
                service_dir=self.service_dir, 
                service_ip=self.service_ip,
                requestline=self.requestline
            )
            self.close_connection = request_handler.handle_request()

class WTVPRequestHandler:
    """
    WebTV request handler class.

    This class will handle requests coming from the request router.
    """
    router = None

    def __init__(self, rfile, wfile, close_connection, service_config, service_dir, service_ip, requestline):
        """
        This will initialize service settings.
        """
        self.rfile = rfile
        self.wfile = wfile
        self.service_config = service_config
        self.service_dir = service_dir
        self.service_ip = service_ip
        self.close_connection = close_connection
        self.requestline = requestline

    def handle_request(self):
        words = self.requestline.split(' ')
        self.method = words[0]
        self.url = words[1]
        self.parse_url()
        self.parse_headers()
        if self.method == 'POST':
            self.data = self.rfile.read(self.headers['Content-Length'])
            if self.headers['Content-Type'] == 'application/x-www-form-urlencoded':
                self.decode_data_params()
        if not self.service_config['stub']: # TODO: add file handling
            import service # This is that hack mentioned in __main__.py
            path = self.path[0].replace('-', '_')
            page = getattr(service, path)
            request = self
        resp = page(request)
        self.wfile.write(resp.generate_response())
        return self.close_connection

    def parse_headers(self):
        """
        Parses HTTP headers to a dictionary.
        """
        self.headers = dict()
        while True:
            line = self.rfile.readline(65537)
            if len(line) > 65536:
                raise ValueError('Header is too long.')
            if line in [b'\r\n', b'\n', b'']:
                break
            else:
                line = line.split(b':')
                self.headers.update({line[0].decode(): line[1].decode().strip()})
        return

    def parse_url(self):
        """
        This will parse a URL for use with services.
        It will output the service, url, and parameters.
        """
        self.service = self.url.split(':')[0]
        self.params = dict()
        try: params = self.url.split('?')[1].split('&')
        except: pass
        else:
            for param in params:
                param = param.split('=')
                try: 
                    self.params.update({unquote(param[0].replace('+', ' ')): unquote(param[1].replace('+', ' '))})
                except: 
                    if param[0] == '':
                        pass
                    else:
                        self.params.update({unquote(param[0].replace('+', ' ')): ''})
        self.path = list()
        path = self.url.split(':')[1].split('?')[0]
        for f in list(filter(str, path.split('/'))):
            self.path.append(f)
        return

    def decode_data_params(self):
        """
        This will decode self.data to a key: value dictionary.
        Useful for POST requests.
        """
        data = self.data.decode()
        self.post_params = dict()
        for param in data.split('&'):
            param = param.split('=')
            self.post_params.update({param[0]: param[1]})
        return