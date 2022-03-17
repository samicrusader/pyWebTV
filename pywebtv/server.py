# -*- coding: UTF-8 -*-

import logging
import socketserver

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

    def __init__(self, *args, service_ip, service_dir, service_config, **kwargs):
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
        elif self.method in ['GET', 'POST', 'HEAD']:
            self.wfile.write(b'400 Bad Request\nConnection: close\n\n')
            self.close_connection = True
            return
        else:
            pass

class WTVPRequestHandler:
    """
    WebTV request handler class.

    This class will handle requests coming from the request router.
    """
    router = None

    def __init__(self, router):
        """
        This will initialize service settings.
        """
        self.router = router