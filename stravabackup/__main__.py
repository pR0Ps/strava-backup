#!/usr/bin/env python

import argparse
import configparser
import logging
import os
import re
import sys

from stravabackup import StravaBackup
from stravalib import Client


__log__ = logging.getLogger(__name__)


LOG_FORMAT = "%(asctime)s [%(levelname)8s] %(name)s: %(message)s"
HOME = os.path.expanduser("~")
CONFIG_FILE = os.path.join(
    os.environ.get('XDG_CONFIG_HOME', os.path.join(HOME, '.config')),
    'strava-backup.conf'
)
OUTPUT_DIR = os.path.join(
    os.environ.get('XDG_DATA_HOME', os.path.join(HOME, ".local", "share")),
    "strava-backup"
)


def main():
    parser = argparse.ArgumentParser(
            description='Get your data back from Strava'
    )
    parser.add_argument("--config", nargs="?", type=argparse.FileType('rt'),
                        default=CONFIG_FILE,
                        help="The config file to use (default: %(default)s)")
    parser.add_argument("--limit", nargs="?", type=int, default=None,
                        help="The maximum number of activities to back up in "
                             "a single run (default: %(default)s)")
    parser.add_argument("--no-meta", action="store_true", default=False,
                        help="Don't download activity metadata")
    parser.add_argument("--no-gear", action="store_true", default=False,
                        help="Don't download gear information")
    parser.add_argument("--no-photos", action="store_true", default=False,
                        help="Don't download the photos attached to activities")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Only list what would be downloaded")
    parser.add_argument("--quiet", action="store_true", default=False,
                        help="Don't output informational messages "
                             "(default: %(default)s)")
    parser.add_argument("--debug", action="store_true", default=False,
                        help="Output debug information (default: %(default)s)")
    args = parser.parse_args()

    config_data = args.config.read()
    config = configparser.ConfigParser()
    config.read_string(config_data)

    client_id = config['api']['client_id']
    client_secret = config['api']['client_secret']
    refresh_token = config['api']['refresh_token']
    output_dir = os.path.expanduser(config['global'].get('output_dir', OUTPUT_DIR))
    email = config['user']['email']
    password = config['user']['password']

    # Reduce logspam
    logging.getLogger("stravalib.model").setLevel(logging.INFO)
    logging.getLogger("stravalib.attributes").setLevel(logging.ERROR)
    logging.getLogger("stravaweblib.model").setLevel(logging.INFO)
    logging.basicConfig(format=LOG_FORMAT,
                        level=logging.DEBUG if args.debug else
                              logging.ERROR if args.quiet else logging.INFO)

    __log__.info("Using the refresh token to get an access token")
    tokens = Client().refresh_access_token(client_id, client_secret, refresh_token)
    if tokens['refresh_token'] != refresh_token:
        refresh_token = tokens['refresh_token']
        config_path = args.config.name
        __log__.info("Refresh token has changed, updating the config file")
        try:
            if config_path == "<stdin>":
                raise FileNotFoundError("Cannot write to config file passed via stdin")
            with open(config_path, 'w') as f:
                new_config = re.sub(
                    r'^(\s*refresh_token\s*=\s*)\w+(.*)$',
                    r'\1{}\2'.format(refresh_token),
                    config_data
                )
                f.write(new_config)
        except OSError:
            __log__.warning(
                "Failed to automatically update refresh token in the config file - "
                "please update it manually", exc_info=True
            )
            __log__.warning("New refresh token is '%s'", refresh_token)

    access_token = tokens['access_token']

    if args.dry_run:
        __log__.info("Would backup '%s' to '%s'", email, output_dir)
    else:
        __log__.info("Backing up '%s' to '%s'", email, output_dir)

    sb = StravaBackup(access_token, email, password, output_dir)
    return sb.run_backup(
        limit=args.limit,
        metadata=not args.no_meta,
        gear=not args.no_gear,
        photos=not args.no_photos,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    sys.exit(main())
