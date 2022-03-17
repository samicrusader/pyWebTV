from .exceptions import *
from .structures import CaseInsensitiveDict
from .models import Response
from urllib.parse import urlsplit
import socks
import socket
import ssl
import brotli
import gzip
import zlib

protocol_to_proxy_type = {
    "http": socks.HTTP,
    "https": socks.HTTP,
    "socks": socks.SOCKS4,
    "socks5": socks.SOCKS5,
    "socks5h": socks.SOCKS5
}

scheme_to_port = {
    "http": 80,
    "https": 443
}

class Session:
    def __init__(self, proxy_url=None, timeout=None, chunk_size=None,
                 decode_content=None, encode_content=None, ssl_verify=None):
        timeout = timeout if timeout is not None else 60
        chunk_size = chunk_size if chunk_size is not None else (1024 ** 2)
        decode_content = decode_content if decode_content is not None else True
        encode_content = encode_content if encode_content is not None else True
        ssl_verify = ssl_verify if ssl_verify is not None else True

        self.proxy_url = proxy_url
        self.timeout = timeout
        self.max_chunk_size = chunk_size
        self.decode_content = decode_content
        self.encode_content = encode_content
        self.ssl_verify = ssl_verify
        self._proxy = urlsplit(proxy_url) if proxy_url is not None else None
        self._addr_to_conn = {}
        self._verified_context = ssl.create_default_context()
        self._unverified_context = ssl._create_unverified_context()

    
    def __enter__(self):
        return self


    def __exit__(self, *_):
        addrs = list(self._addr_to_conn)
        while addrs:
            self.close(addrs.pop())


    def request(self, method, url, headers=None, content=None, timeout=None,
                version=None, ssl_verify=None):
        parsed_url = urlsplit(url)
        scheme = parsed_url.scheme.lower()

        if not scheme in scheme_to_port:
            raise UnsupportedScheme("'%s' is not a supported scheme" % (
                scheme))

        host_addr = (
            parsed_url.hostname.lower(),
            parsed_url.port or scheme_to_port[scheme]
        )
        
        if ssl_verify is None:
            ssl_verify = self.ssl_verify

        if version is None:
            version = "1.1"

        if not isinstance(headers, CaseInsensitiveDict):
            headers = CaseInsensitiveDict(headers)

        if not "Host" in headers:
            headers["Host"] = parsed_url.hostname

        if content is not None:
            if not isinstance(content, bytes):
                content = content.encode("utf-8")
            if not "Content-Length" in headers:
                headers["Content-Length"] = "%d" % len(content)
        
        request = self._prepare_request(
            method=method,
            path=parsed_url.path \
                + ("?" + parsed_url.query if parsed_url.query else ""),
            version=version,
            headers=headers,
            content=content
        )
        
        conn_reused = host_addr in self._addr_to_conn
        while True:
            try:
                conn = self._addr_to_conn.get(host_addr)
                if conn is None:
                    conn = self._create_socket(
                        host_addr,
                        timeout=timeout or self.timeout,
                        ssl_wrap=("https" == scheme),
                        ssl_verify=ssl_verify)
                    self._addr_to_conn[host_addr] = conn
                
                self._send(conn, request)
                return Response(*self._get_response(conn))

            except Exception as err:
                if host_addr in self._addr_to_conn:
                    self._addr_to_conn.pop(host_addr)

                if not conn_reused:
                    if not isinstance(err, RequestException):
                        err = RequestException(err)
                    raise err

                conn_reused = False


    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)


    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


    def options(self, url, **kwargs):
        return self.request("OPTIONS", url, **kwargs)


    def head(self, url, **kwargs):
        return self.request("HEAD", url, **kwargs)


    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)


    def patch(self, url, **kwargs):
        return self.request("PATCH", url, **kwargs)


    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)


    def close(self, addr):
        if not addr in self._addr_to_conn:
            return

        sock = self._addr_to_conn[addr]
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()
        self._addr_to_conn.pop(addr, None)


    def _create_socket(self, dest_addr, timeout=None, ssl_wrap=True,
                       ssl_verify=True):
        sock = socks.socksocket()

        if timeout:
            sock.settimeout(timeout)
        
        if self._proxy is not None:
            proxy_type = protocol_to_proxy_type.get(self._proxy.scheme.lower())

            if proxy_type is None:
                raise UnsupportedScheme("'%s' is not a supported proxy scheme" % (
                    self._proxy.scheme))

            sock.set_proxy(
                proxy_type,
                addr=self._proxy.hostname,
                port=self._proxy.port,
                username=self._proxy.username,
                password=self._proxy.password,
                rdns=False
            )

        sock.connect(dest_addr)

        if ssl_wrap:
            context = self._verified_context \
                      if ssl_verify else self._unverified_context

            sock = context.wrap_socket(
                sock,
                server_hostname=dest_addr[0])

        return sock


    def _prepare_request(self, method, path, version, headers, content):
        request = "%s %s HTTP/%s\r\n" % (
            method, path, version)

        for header, value in headers.items():
            if value is None:
                continue
            request += "%s: %s\r\n" % (header, value)

        request += "\r\n"
        request = request.encode("UTF-8")

        if content is not None:
            if "content-encoding" in headers and self.encode_content:
                content = self._encode_content(content, headers["content-encoding"])
            request += content

        return request


    def _send(self, conn, data):
        conn.send(data)


    def _get_response(self, conn):
        resp = conn.recv(self.max_chunk_size)

        if len(resp) == 0:
            raise EmptyResponse("Empty response from server")

        resp, data = resp.split(b"\r\n\r\n", 1)
        resp = resp.decode()
        status, raw_headers = resp.split("\r\n", 1)
        version, status, message = status.split(" ", 2)

        headers = CaseInsensitiveDict()
        for header in raw_headers.splitlines():
            header, value = header.split(":", 1)
            if value.startswith(" "):
                value = value[1:]
            headers[header] = value
        
        if "content-length" in headers:
            goal = int(headers["content-length"])
            while goal > len(data):
                chunk = conn.recv(min(goal-len(data), self.max_chunk_size))
                if len(chunk) == 0:
                    raise RequestException("Empty chunk")
                data += chunk
    
        elif headers.get("transfer-encoding") == "chunked":
            while True:
                chunk = conn.recv(self.max_chunk_size)
                if len(chunk) == 0 or chunk == b"0\r\n\r\n":
                    break
                data += chunk

            raw = data
            data = b""
            while raw:
                length, raw = raw.split(b"\r\n", 1)
                length = int(length, 16)
                chunk, raw = raw[:length], raw[length+2:]
                data += chunk

        else:
            while True:
                chunk = conn.recv(self.max_chunk_size)
                if len(chunk) == 0:
                    break
                data += chunk

        if "content-encoding" in headers and self.decode_content:
            data = self._decode_content(data, headers["content-encoding"])

        return int(status), message, headers, data


    def _encode_content(self, content, encoding):
        if encoding == "br":
            content = brotli.compress(content)
        elif encoding == "gzip":
            content = gzip.compress(content)
        elif encoding == "deflate":
            content = zlib.compress(content)
        else:
            raise UnsupportedEncoding(
                "Unknown encoding type '%s' while encoding content" % (encoding))
        
        return content

    def _decode_content(self, content, encoding):
        if encoding == "br":
            content = brotli.decompress(content)
        elif encoding == "gzip":
            content = gzip.decompress(content)
        elif encoding == "deflate":
            content = zlib.decompress(content)
        else:
            raise UnsupportedEncoding(
                "Unknown encoding type '%s' while decoding content" % (encoding))
        
        return content
