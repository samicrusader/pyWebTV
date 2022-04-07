# -*- coding: UTF-8 -*-

from . import functions
from .decorators import Box, WTVPError
from .security import WTVNetworkSecurity
import io
import logging
import os
import redis
import socketserver
import sqlalchemy
from redis.commands.json.path import Path
from urllib.parse import quote, unquote
from sqlalchemy.sql import text


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
        host, port = self.server_address
        logging.info(f'Service listening on {host}:{port}.')


class WTVPRequestRouter(socketserver.StreamRequestHandler):
    """
    WebTV request routing class.

    This class will handle requests made to the server.
    """
    box: Box = None
    close_connection: bool = True
    global_config: dict = None
    headers: dict = None
    security: WTVNetworkSecurity = None
    security_on: bool = False
    service_ip: str = None
    service_dir: str = None
    service_config: dict = None
    service_name: str = None
    ssid: str = None

    def __init__(self, *args, service_config, service_dir, service_ip, global_config, **kwargs):
        """
        This will initialize service settings.
        """
        self.service_ip = service_ip
        self.service_dir = service_dir
        self.service_config = service_config
        self.global_config = global_config

        sqlconfig = global_config['db']['psql']
        redisconfig = global_config['db']['redis']
        # sql used for service and user information storage
        self.sqlengine = sqlalchemy.create_engine(
            f"postgresql+pg8000://{sqlconfig['username']}:{quote(sqlconfig['password'])}@{sqlconfig['host']}:{sqlconfig['port']}/{sqlconfig['database']}")
        # redis used for temporary session storage
        self.redisengine = redis.Redis(
            host=redisconfig['host'], port=redisconfig['port'], db=redisconfig['db'])
        self.redisengine.json().set('connections', Path.rootPath(), dict())
        super().__init__(*args, **kwargs)

    def handle(self):
        """
        This allows Keep-Alive or secure requests to go through without dropping after the request is handled.

        It will pass requests through to the actual request handler.
        """
        logging.debug(
            f'Connection from {self.client_address[0]}:{self.client_address[1]}')
        if self.sqlengine.execute(text('select * from public.ipblacklist where ip = :ip;'), ip=self.client_address[0]).fetchall():
            self.wfile.write(
                b'500 MSN TV ran into a technical problem. Please try again.\nConnection: close\n\n')
            return
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
        def garbage_collection(self):
            if self.ssid: # if we have an ssid for this connection
                connectionlist = self.redisengine.json().get('connections')
                try:
                    # remove connection from "pool"
                    connectionlist[self.ssid].remove(f'{self.client_address[1]}:{self.service_config["port"]}')
                except:
                    pass
                self.redisengine.json().set('connections', Path.rootPath(), connectionlist)
                if connectionlist[self.ssid]:
                    if len(connectionlist[self.ssid]) == 0:
                        for key in x.scan_iter(f'session_{self.ssid}_*'):
                            print('garbage')
                            self.redisengine.delete(key) # session garbage collection
        if self.security_on:
            data = bytes()
            while True:
                rbyte = self.rfile.read(1)
                if not rbyte:
                    logging.debug(
                        f'Connection from {self.client_address[0]}:{self.client_address[1]} dropped.')
                    self.close_connection = True
                    garbage_collection(self)
                    return
                try:
                    decattempt = self.security.decrypt(1, rbyte)
                except RuntimeError as e:
                    self.wfile.write((f'500 {e}').encode())
                    return
                data += decattempt
                if data.endswith(b'\r\n\r\n') or data.endswith(b'\r\r') or data.endswith(b'\n\n') or data.endswith(b'\r\n\r\n') or data.endswith(b'\r\n\r') or data.endswith(b'\n\r\n'):
                    if data.startswith(b'POST'):
                        cl = int(data.split(b'ength:')[
                                 1].split(b'\n')[0].strip())
                        data += self.security.decrypt(1, self.rfile.read(cl))
                    break
            self.zfile = io.BytesIO(data)
            #self.requestline = self.zfile.readline(65536)
        else:
            self.zfile = self.rfile

        self.requestline = self.zfile.readline(65536).decode().strip()
        if not self.requestline:
            logging.debug(
                f'Connection from {self.client_address[0]}:{self.client_address[1]} dropped.')
            self.close_connection = True
            garbage_collection(self)
            return
        words = self.requestline.split(' ')
        if self.requestline.endswith('HTTP/1.0') or self.requestline.endswith('HTTP/1.1'):
            self.wfile.write(
                f'''{words[-1]} 301 Moved\nConnection: close\nContent-Length: 0\nContent-Type: text/html\nLocation: https://github.com/samicrusader/pyWebTV\n\n'''.encode())
            return
        elif words[0] not in ['GET', 'POST', 'HEAD', 'SECURE']:
            self.wfile.write(b'400 Bad Request\nConnection: close\n\n')
            self.close_connection = True
            return
        # parse box headers
        if not self.headers:
            parse_headers(self)
            print(self.headers)
        if not self.box:
            self.box = Box(self.headers)
        if not self.ssid:
            self.ssid = self.headers['wtv-client-serial-number']

        # note connection
        connectionlist = self.redisengine.json().get('connections')
        if self.ssid not in connectionlist.keys():
            connectionlist.update({self.ssid: list()})
        portdata = f'{self.client_address[1]}:{self.service_config["port"]}'
        if connectionlist[self.ssid] == None:
            connectionlist[self.ssid] = list()
        if not portdata in connectionlist[self.ssid]:
            connectionlist[self.ssid] = connectionlist[self.ssid].append(portdata) # client port:server port
            self.redisengine.json().set('connections', Path.rootPath(), connectionlist)
        if words[0] == 'SECURE':
            self.security = WTVNetworkSecurity()
            if 'wtv-ticket' in self.headers:
                self.security.import_dump(self.headers['wtv-ticket'])
                self.security.incarnation = int(self.headers['wtv-incarnation'])
                self.security.secure_on()
                self.security_on = True
            else:
                # FIXME: Something something missing ticket.
                raise Exception('')
            self.headers = None
            self.close_connection = False
            return 'break'
        else:
            self.close_connection = False
            request_handler = WTVPRequestHandler(
                rfile=self.zfile,
                wfile=self.wfile,
                router=self
            )
            request_handler.handle_request()


class WTVPRequestHandler:
    """
    WebTV request handler class.

    This class will handle requests coming from the request router.
    """
    router = None

    def __init__(self, rfile, wfile, router):
        """
        This will initialize service settings.
        """
        self.rfile = router.rfile
        self.wfile = router.wfile
        self.service_config = router.service_config
        self.service_dir = router.service_dir
        self.service_ip = router.service_ip
        self.router = router

    def handle_request(self):
        words = self.router.requestline.split(' ')
        self.method = words[0]
        self.url = words[1]
        parse_url(self)
        if not self.service == self.service_config['name']:
            self.wfile.write(
                b'500 MSN TV ran into a technical problem. Please try again.\r\nConnection: close\r\n\r\n')
            router.close_connection = False
            return
        if not self.router.headers:
            parse_headers(self)
        else:
            self.headers = self.router.headers
        if not self.router.box:
            self.router.box = Box(self.headers)
        if not self.router.ssid:
            self.router.ssid = self.headers['wtv-client-serial-number']
        if self.method == 'POST':
            self.data = self.rfile.read(self.headers['Content-Length'])
            if self.headers['Content-Type'] == 'application/x-www-form-urlencoded':
                decode_data_params(self)
        path = self.path[0].replace('-', '_')
        try:
            if not self.service_config['stub']:
                import service  # This is that hack mentioned in __main__.py
                page = getattr(service, path)
                request = self
            else:
                raise Exception('')
        except:
            try:
                page = functions.return_file
                request = self.return_filepath()
            except UnboundLocalError:
                page = WTVPError
                request = 404
        resp = page(request)
        self.wfile.write(resp.generate_response())
        return

    def return_filepath(request):
        """
        Return file path if found.
        """
        paths = [
            os.path.join(request.service_dir, 'static',
                         '/'.join(request.path)),
            os.path.join(request.service_dir, 'static',
                         '/'.join(request.path)+'.html'),
            os.path.join(request.service_dir, 'static',
                         '/'.join(request.path).replace('-', '_')),
            os.path.join(request.service_dir, 'static',
                         '/'.join(request.path).replace('-', '_')+'.html')
        ]
        for checkpath in paths:
            # https://stackoverflow.com/q/6803505
            normalized_path = os.path.normpath(checkpath)
            if not normalized_path.startswith(request.service_dir):
                raise IOError()
            if os.path.isfile(normalized_path):
                path = normalized_path
        return path


def parse_headers(request):
    """
    Parses HTTP headers to a dictionary.
    """
    request.headers = dict()
    while True:
        line = request.rfile.readline(65537)
        if len(line) > 65536:
            raise ValueError('Header is too long.')
        if line in [b'\r\n', b'\n', b'']:
            break
        else:
            line = line.split(b':')
            request.headers.update(
                {line[0].decode(): line[1].decode().strip()})
    return


def parse_url(request):
    """
    This will parse a URL for use with services.
    It will output the service, url, and parameters.
    """
    request.service = request.url.split(':')[0]
    request.params = dict()
    try:
        params = request.url.split('?')[1].split('&')
    except:
        pass
    else:
        for param in params:
            param = param.split('=')
            try:
                request.params.update(
                    {unquote(param[0].replace('+', ' ')): unquote(param[1].replace('+', ' '))})
            except:
                if param[0] == '':
                    pass
                else:
                    request.params.update(
                        {unquote(param[0].replace('+', ' ')): ''})
    request.path = list()
    path = request.url.split(':')[1].split('?')[0]
    for f in list(filter(str, path.split('/'))):
        request.path.append(f)
    return


def decode_data_params(request):
    """
    This will decode request.data to a key: value dictionary.
    Useful for POST requests.
    """
    data = request.data.decode()
    request.post_params = dict()
    for param in data.split('&'):
        param = param.split('=')
        request.post_params.update({param[0]: param[1]})
    return
