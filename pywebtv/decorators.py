# -*- coding: UTF-8 -*-

lookuptable = {
    200: '200 OK',
    302: '302 Found',
    404: '404 MSN TV ran into a technical problem. Please try again.',
    500: '500 MSN TV ran into a technical problem. Please try again.'
}


class Box:
    """
    This class identifies a box and configures the class to have it's information.
    """
    client: int = None
    systeminfo: dict = None
    capabilities: dict = None
    language: str = None

    def __init__(self, headers: dict):
        """
        this uses headers to determinate box things
        the client variable's numbers will be one of these:
        0 = WebTV (Pre-MSN rebrand)
        1 = MSN TV (Post-MSN rebrand, not TV 2)
        2 = Microsoft TV[-based] (Microsoft TV[ Simulator], UltimateTV, etc...)
        3 = Japanese Dreamcast

        capabilities will be stored with internal name only
        you need to implement the proper strings yourself.
        """
        self.capabilities = self.getCapabilities(
            headers['wtv-capability-flags'])
        # FIXME: does this appear on a real box? ask whoever the fuck owns one
        if headers['wtv-client-rom-type'] == 'JP-Fiji':
            self.client = 3
        elif 'mstv-client-caps' in headers.keys():
            self.client = 2
            x = headers['mstv-client-caps']
            disk = x.split('STORAGESIZE="')[1].split('"')[0]
            version = headers['wtv-system-version'].replace(',', '.')
            self.systeminfo = {'version': version, 'disksize': disk}
        elif 'client-supports-MSN-service' not in self.capabilities.keys() or self.capabilities['client-supports-MSN-service'] == False:
            self.client = 0
        elif self.capabilities['client-supports-MSN-service'] == True:
            self.client = 1
        else:
            raise ValueError('invalid client')
        if self.client == 0 or self.client == 1:
            version = headers['wtv-system-version']
            bootrom = headers['wtv-client-bootrom-version']
            romtype = headers['wtv-client-rom-type']
            chipversion = headers['wtv-system-chipversion']
            self.systeminfo = {'version': version, 'bootrom-version': bootrom,
                               'romtype': romtype, 'chip-version': chipversion}
        elif self.client == 3:
            version = headers['wtv-system-version']
            romtype = headers['wtv-client-rom-type']
            self.systeminfo = {'version': version, 'romtype': romtype}
        self.language = headers['Accept-Language'].split('-')[0]
        return

    def getCapabilities(self, flags: str):
        ct = [
            'client-can-do-muzac',
            'client-can-do-chat',
            'client-can-do-openISP',
            'client-can-receive-compressed-data',
            'client-can-display-spotads1',
            'client-can-print',
            'client-can-do-macromedia-flash1',
            'client-can-do-javascript',
            'client-can-do-videoflash',
            'client-can-do-videoads',
            'client-has-disk',
            'client-supports-classical-service',
            'client-open-isp-settings-valid',
            'client-can-tell-valid-open-isp',
            'client-has-tuner',
            'client-can-data-download',
            'client-supports-approx-content-len',
            'client-has-built-in-printer-port',
            'client-has-tv-experience',
            'client-can-handle-proxy-bypass',
            'client-can-handle-download-v2',
            'client-has-relogin-function',
            'client-can-display-spotads2',
            'client-can-display-30-sec-video-ads',
            'client-supports-etude-service',
            'client-can-do-av-capture',
            'client-can-do-disconnected-email',
            'client-can-do-macromedia-flash2',
            'client-has-memory-size-bit1-set',
            'client-has-memory-size-bit2-set',
            'client-has-memory-size-bit3-set',
            'client-can-do-rmf',
            'client-can-do-png',
            'client-does-broadband-data-download',
            'client-has-softmodem',
            'client-can-do-preparsed-epg',
            'client-supports-funk-e-service',
            'client-wants-dial-script',
            'client-upgrade-visits-not-needed',
            'client-uses-flexible-videoad-paths',
            'client-non-production-build',
            'client-can-download-printer-drivers',
            'client-supports-hiphop-service',
            'client-can-use-messenger',
            'client-uses-third-party-billing',
            'client-can-do-offlineads',
            'client-has-no-dialin-support',
            'client-has-ssl-support-for-wtvp',
            'client-can-do-audio-capture',
            'client-can-do-metered-pricing',
            'client-negotiates-user-agent',
            'client-can-do-element-logging',
            'client-supports-jazz-security',
            'client-supports-MSN-service',
            'client-supports-notify-port-header',
            'client-supports-messenger-update-light',
            'client-supports-MSN-chat',
            'client-supports-MSN-chat-findu',
            'client-supports-MSN-messenger-CVR',
            'client-supports-MSN-messenger-MSNP8',
            'client-supports-MSN-chat-R9C'
        ]

        binary = bin(int(flags, 16))[2:].zfill(len(flags) * 4)

        rev = binary[::-1]

        split = list(rev)

        cflags = dict()

        for i, c in enumerate(split):
            x = False
            if c == '1':
                x = True
            try:
                z = ct[i]
            except:
                pass
            else:
                cflags.update({z: x})
        return cflags


class WTVPError():
    def __init__(self, status_code: int):
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

    def __init__(self, content_type: str, data: bytes = b'', status_code: int = 200, headers: dict = {}, forceEncrypt: bool = False, forceEncryptObj=None):
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
                # hack for multiple headers wtv-service
                key = key.split('^n')[0]
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
                # hack for multiple headers wtv-service
                key = key.split('^n')[0]
            data += f'{key}: {value}\r\n'
        encdata = sec.EncryptKey2(self.data)
        data += f'Content-Length: {len(encdata)}\r\n'
        data += f'Content-Type: {self.content_type}\r\n'
        data += '\r\n'
        data = data.encode()
        data += encdata
        return data
