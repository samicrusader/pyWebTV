import os
from pywebtv.decorators import WTVPResponse
from pywebtv.functions import return_service, returnLocalTime
from pywebtv.security import WTVNetworkSecurity

"""
wtv-1800 (scriptlessd) sets a client up for dialing into the service.

It will check if the box is authorized to connect, determine local numbers, and configure service routes.
"""


def preregister(request):
    """
    Client preregistration.
    """
    openisp_disabled = True
    if 'wtv-open-access' in request.headers.keys():  # hax
        openisp_disabled = False
        # visit = 'wtv-1800:/openisp_suggest' # This doesnt matter, they're using systems that aren't live, and therefore won't be billed.
    headers = {'wtv-open-isp-disabled': str(openisp_disabled).lower(
    ), 'wtv-visit': f'wtv-1800:/finish_scriptless?oisp=true'}
    return WTVPResponse(content_type='text/html', headers=headers)


def finish_scriptless(request):
    """
    Sends dialing information to the client.
    """
    netsec = WTVNetworkSecurity()
    netsec.issue_challenge()
    initial_key = netsec.current_shared_key_b64
    dump = netsec.dump()
    request.router.close_connection = True
    headers = {
        'Connection': 'close',
        'wtv-initial-key': initial_key,
        'wtv-service^n-0': 'reset',
        'wtv-service^n-1': return_service('wtv-*', '1603', request.service_ip, DontEncryptRequests=True),
        'wtv-service^n-2': return_service('wtv-head-waiter', '1601', request.service_ip, connections=1),
        'wtv-service^n-3': return_service('wtv-flashrom', '1618', request.service_ip),
        'wtv-boot-url': 'wtv-head-waiter:/login',
        'wtv-visit': f'wtv-head-waiter:/login',
        'wtv-ticket': dump
    }
    headers.update(returnLocalTime(request.router.client_address[0]))
    if request.router.box.systeminfo['romtype'] == 'bf0app':
        if request.params['oisp'] == 'true':
            data = open(os.path.join(request.service_dir,
                                     'static', 'classic_openisp.tok'), 'rb')
        else:
            data = open(os.path.join(request.service_dir,
                                     'static', 'classic.tok'), 'rb')
    elif request.router.box.client == 3:
        data = open(os.path.join(request.service_dir,
                                 'static', 'fiji.tok'), 'rb')
        # TODO: OpenISP for Dreamcast clients
    elif request.router.box.client == 2:
        data = open(os.path.join(request.service_dir,
                                 'static', 'mstv.tok'), 'rb')
    else:
        if request.params['oisp'] == 'true':
            data = open(os.path.join(request.service_dir,
                                     'static', 'plus_openisp.tok'), 'rb')
        else:
            data = open(os.path.join(request.service_dir,
                                     'static', 'plus.tok'), 'rb')
    return WTVPResponse(content_type='text/tellyscript', data=data.read(), headers=headers)
