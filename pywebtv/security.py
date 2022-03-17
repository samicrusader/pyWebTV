# -*- coding: UTF-8 -*-

import base64
from Crypto.Cipher import ARC4, DES
from Crypto.Hash import MD5
from Crypto.Random import get_random_bytes
from json import dumps as jdump
from json import loads as jload

class WTVNetworkSecurity():
    """
    Originally reversed and released by Eric MacDonald (eMac), additional help in
    figuring this out was also provided by Zefie (who's working on a similar
    project)

    Sources are:
    https://github.com/zefie/zefie_wtvp_minisrv/blob/master/zefie_wtvp_minisrv/WTVSec.js
    https://discord.com/channels/669359927893950483/808168241306140703/848731674962821181 (WebTV Server, join from https://webtvwiki.net)

    This is used to handle request encryption for WebTV clients.
    Many features will not work if encryption is not used, as this is a step in
    unlocking the box. (the other being headwaiter sign-in)

    Eric's original code is modified for use with this server backend.
    """
    initial_shared_key = bytes()
    initial_shared_key_b64 = str()
    current_shared_key = bytes()
    current_shared_key_b64 = str()
    past_shared_key = bytes()
    past_shared_key_b64 = str()
    incarnation = 1
    session_key1 = bytes()
    session_key2 = bytes()
    hRC4_Key1 = None
    hRC4_rawkey1 = bytes()
    hRC4_Key2 = None
    hRC4_rawkey2 = bytes()
    session_token = str()

    def __init__(self, wtv_initial_key:bytes=base64.b64encode(get_random_bytes(8)).decode(), wtv_incarnation:int=1):
        """
        We initialize the incarnation (request count) and initial shared key
        used for encryption in this function.
        """
        self.initial_shared_key_b64 = wtv_initial_key
        initial_key = base64.b64decode(wtv_initial_key)
        self.initial_shared_key = initial_key
        self.incarnation = wtv_incarnation
        self.SetSharedKey(initial_key)

    def dump(self):
        """
        This dumps a security object, used for either the client ticket, or
        for scriptless -> headwaiter handoff.
        """
        x = dict()
        for i in ['initial_shared_key', 'current_shared_key', 'past_shared_key', 'session_key1', 'session_key2', 'hRC4_rawkey1', 'hRC4_rawkey2']:
            obj = getattr(self, i)
            if type(obj) is bytes:
                obj = 'b~!'+base64.b64encode(obj).decode()
            x.update({i: obj})

        for i in ['initial_shared_key_b64', 'current_shared_key_b64', 'past_shared_key_b64', 'session_token']:
            obj = getattr(self, i)
            obj = 'c~!'+obj
            x.update({i: obj})
        
        x.update({'incarnation': self.incarnation})
        d = jdump(x).replace(':', '\\./')
        return d

    def importdump(self, dump:str):
        """
        This will import a security object, from a dump provided by the dump()
        function.
        """
        x = jload(dump.replace('\\./', ':'))
        for key, value in x.items():
            if (type(value) is int) == False and value.startswith('b~!'):
                value = base64.b64decode(value[3:])
            elif (type(value) is int) == False and value.startswith('c~!'):
                value = value[3:]
            setattr(self, key, value)
        if not self.hRC4_rawkey1 == b'':
            self.hRC4_Key1 = ARC4.new(self.hRC4_rawkey1)
        if not self.hRC4_rawkey2 == b'':
            self.hRC4_Key2 = ARC4.new(self.hRC4_rawkey2)

    def SetSharedKey(self, shared_key:bytes):
        """
        This will set the shared key used for encryption.

        It sets the past shared key to the current shared key, which is used
        when processing a challenge, then sets the current shared key, to the
        key passed in "shared_key".
        """
        if len(shared_key) == 8:
            if self.past_shared_key == bytes():
                self.past_shared_key = shared_key
                self.past_shared_key_b64 = base64.b64encode(shared_key).decode()
            else:
                self.past_shared_key = self.current_shared_key
                self.past_shared_key_b64 = self.current_shared_key_b64
            self.current_shared_key = shared_key
            self.current_shared_key_b64 = base64.b64encode(shared_key).decode()
        else:
            raise ValueError("Invalid shared key length")

    def set_incarnation(self, wtv_incarnation:int):
        'Sets the incarnation. Is there anything else to it?'
        self.incarnation = wtv_incarnation

    def ProcessChallenge(self, wtv_challenge:str):
        """
        This will process a security challenge and return a challenge response.
        The response is used to compare with what is sent back from the client
        to verify that a correct data stream is sent.

        This function is only used when issuing a challenge due to a quirk in
        WebTV's client.
        """
        challenge = base64.b64decode(wtv_challenge)

        if not len(challenge) > 8:
            raise ValueError("Invalid challenge length")

        hDES1 = DES.new(self.past_shared_key, DES.MODE_ECB)

        challenge_decrypted = hDES1.decrypt(challenge[8:])

        hMD5 = MD5.new()
        hMD5.update(challenge_decrypted[0:80])
        test = challenge_decrypted[80:96]
        test2 = hMD5.digest()
        if test == test2:
            self.SetSharedKey(challenge_decrypted[72:80])

            challenge_echo = challenge_decrypted[0:40]
            hMD5 = MD5.new()
            hMD5.update(challenge_echo)
            challenge_echo_md5 = hMD5.digest()

            # RC4 encryption keys.  Stored in the wtv-ticket on the server side.
            self.session_key1 = challenge_decrypted[40:56]
            self.session_key2 = challenge_decrypted[56:72]

            hDES2 = DES.new(self.current_shared_key, DES.MODE_ECB)
            echo_encrypted = hDES2.encrypt(challenge_echo_md5 + challenge_echo)

            # Last bytes is just extra padding
            challenge_response = challenge[0:8] + echo_encrypted + (b'\x00' * 8)

            return str(base64.b64encode(challenge_response), "ascii")
        else:
            raise ValueError("Couldn't solve challenge")

    def IssueChallenge(self):
        """
        Issues a security challenge for WebTV clients to check encryption
        status.
        
        This will also process said challenge to get a response, which is
        returned along with the challenge string. This is due to a bug either
        within WebTV's handling, or within Eric's code.

        Original notes from Eric:
        bytes 0-8: Random id?  Just echoed in the response
        bytes 8-XX: DES encrypted block.  Encrypted with the initial key or subsequent keys from the challenge.
            bytes 8-48: hidden random data we echo back in the response
            bytes 48-64: session key 1 used in RC4 encryption triggered by SECURE ON
            bytes 64-80: session key 2 used in RC4 encryption triggered by SECURE ON
            bytes 80-88: new key for future challenges
            bytes 88-104: MD5 of 8-88
            bytes 104-112: padding. not important
        """

        random_id_question_mark = get_random_bytes(8)

        echo_me = get_random_bytes(40)
        self.session_key1 = get_random_bytes(16)
        self.session_key2 = get_random_bytes(16)
        new_shared_key = get_random_bytes(8)

        challenge_puzzle = echo_me + self.session_key1 + self.session_key2 + new_shared_key
        hMD5 = MD5.new()
        hMD5.update(challenge_puzzle)
        challenge_puzzle_md5 = hMD5.digest()

        challenge_secret = challenge_puzzle + challenge_puzzle_md5 + (b'\x00' * 8)

        # Shhhh!!
        hDES2 = DES.new(self.current_shared_key, DES.MODE_ECB)
        challenge_secreted = hDES2.encrypt(challenge_secret)
        self.SetSharedKey(new_shared_key)

        challenge = random_id_question_mark + challenge_secreted
        challenge = str(base64.b64encode(challenge), "ascii")
        response = self.ProcessChallenge(challenge)
        challenge_cut = challenge[:-4]
        return [challenge_cut, response]

    def SecureOn(self):
        """
        This will initialize an encryption session.
        These are per-socket, and last the entire lifetime of the socket.

        Specifically, these will update 2 RC4 encryption keys.
        """
        hMD5 = MD5.new()
        hMD5.update(self.session_key1 + self.incarnation.to_bytes(4, byteorder='big') + self.session_key1)
        self.hRC4_rawkey1 = hMD5.digest()
        self.hRC4_Key1 = ARC4.new(self.hRC4_rawkey1)

        hMD51 = MD5.new()
        hMD51.update(self.session_key2 + self.incarnation.to_bytes(4, byteorder='big') + self.session_key2)
        self.hRC4_rawkey2 = hMD51.digest()
        self.hRC4_Key2 = ARC4.new(self.hRC4_rawkey2)

    # These handle data encryption.
    def Encrypt(self, context:ARC4.ARC4Cipher, data:bytes):
        if context != None:
            return context.encrypt(data)
        else:
            raise RuntimeError("Invalid RC4 encryption context")

    def Decrypt(self, context:ARC4.ARC4Cipher, data:bytes):
        if context != None:
            return context.decrypt(data)
        else:
            raise RuntimeError("Invalid RC4 decryption context")

    # These deal with encryption using the 2 keys.
    def EncryptKey1(self, data:bytes):
        return self.Encrypt(self.hRC4_Key1, data)

    def EncryptKey2(self, data:bytes):
        return self.Encrypt(self.hRC4_Key2, data)

    def DecryptKey1(self, data):
        return self.Decrypt(self.hRC4_Key1, data)

    def DecryptKey2(self, data):
        return self.Decrypt(self.hRC4_Key2, data)