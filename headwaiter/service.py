from pywebtv.decorators import WTVPResponse
from pywebtv.functions import return_service, returnLocalTime
from pywebtv.security import WTVNetworkSecurity

"""
wtv-head-waiter is the authentication service for WebTV clients.

It will authenticate boxes to the service, or register them. It will also manage disabled boxes.
"""