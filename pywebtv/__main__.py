# -*- coding: UTF-8 -*-

from .server import WTVPRequestRouter, WTVPServer
from .functions import load_json
import argparse
import logging
import os
import sys
from functools import partial

__version__ = "1.0"
print(f"""pyWebTV
Version {__version__} - https://github.com/samicrusader/pyWebTV
--""")

logging.basicConfig(level=logging.DEBUG)


def run(
        port: int,
        bind: str,
        service_ip: str,
        service_dir: str,
        config: dict
):
    """
    Runs a WTVP server.
    """
    service_dir = os.path.abspath(service_dir)
    service_config = load_json(os.path.join(
        service_dir, 'config/service.json'))
    if port == 0:
        port = service_config['port']
    sys.path.insert(1, service_dir)  # FIXME: This is a hack.
    handlerargs = partial(
        WTVPRequestRouter,
        service_ip=service_ip,
        service_dir=service_dir,
        service_config=service_config,
        global_config=config
    )
    with WTVPServer((bind, port), handlerargs) as s:
        try:
            s.serve_forever()
        except KeyboardInterrupt:
            print('\nstopping...')
            sys.exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='python3 -m pywebtv')

    parser.add_argument('--config', '-c', default='config.json',
                        help='Specify global configuration file.')
    parser.add_argument('--service', '-s', help='Specify service directory.')
    parser.add_argument('--bind', '-b', help='Specify IP address to bind to.')
    parser.add_argument('--port', '-p', default=0,
                        help='Override port to listen on.')
    parser.add_argument('--service-ip', '-x',
                        help='Specify IP address for network use.')

    args = parser.parse_args()

    try:
        config = load_json(args.config)
    except:
        print('Specify a config.')
        parser.print_help()
        exit(1)

    run(
        service_dir=args.service,
        bind=args.bind,
        port=args.port,
        service_ip=args.service_ip,
        config=config
    )
