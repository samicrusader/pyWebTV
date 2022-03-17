from pywebtv.decorators import WTVPResponse

"""
wtv-1800 (scriptlessd) sets a client up for dialing into the service.

It will check if the box is authorized to connect, determine local numbers, and configure service routes.
"""

def preregister(request):
    """
    Preregistration for the client.
    """
    return WTVPResponse(content_type='text/html', data=b'Test page!')