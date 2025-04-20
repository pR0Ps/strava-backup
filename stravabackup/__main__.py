#!/usr/bin/env python

import argparse
import contextlib
import io
import logging
import os
import sys

from commentedconfigparser import CommentedConfigParser
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


@contextlib.contextmanager
def _manage_config(fp):
    """Handle reading/writing the config file

    If the config is updated within this context manager, the config file will
    be rewritten when it exits.
    """
    config = CommentedConfigParser()
    config.read_file(fp)

    # ensure that we only try to write the config out if it was passed via an actual file
    path = getattr(fp, "name", None)
    can_write = path and path != "<stdin>" and os.path.isfile(path)

    # janky way to track updates - if set to true, the config will be rewritten
    config._updated = False

    try:
        yield config
    finally:
        if config._updated:
            __log__.info("Config changed, attempting to update the config file")
            s = io.StringIO()
            config.write(s)
            new_config = s.getvalue()
            try:
                if not can_write:
                    raise FileNotFoundError("Cannot rewrite config - input config was a non-file")
                with open(path, 'wt') as f:
                    f.write(new_config)
            except OSError:
                __log__.warning(
                    "Failed to automatically update the config file - "
                    "please update it manually with the following contents:\n```%s\n```",
                    new_config,
                    exc_info=True
                )
            else:
                __log__.info("Updated configuration file with new values!")


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

    # Reduce logspam
    logging.getLogger("stravalib.model").setLevel(logging.INFO)
    logging.getLogger("stravalib.attributes").setLevel(logging.ERROR)
    logging.getLogger("stravaweblib.model").setLevel(logging.INFO)
    logging.basicConfig(format=LOG_FORMAT,
                        level=logging.DEBUG if args.debug else
                              logging.ERROR if args.quiet else logging.INFO)

    with _manage_config(args.config) as config:
        client_id = config['api']['client_id']
        client_secret = config['api']['client_secret']
        refresh_token = config['api']['refresh_token']
        output_dir = os.path.expanduser(config['global'].get('output_dir', OUTPUT_DIR))
        email = config['user']['email']
        password = config['user']['password']
        jwt = config['user'].get('jwt')

        __log__.info("Using the refresh token to get an access token")
        tokens = Client().refresh_access_token(client_id, client_secret, refresh_token)
        if tokens['refresh_token'] != refresh_token:
            __log__.info("Refresh token has changed, will attempt to update the config file")
            config['api']['refresh_token'] = refresh_token
            config._updated = True

        access_token = tokens['access_token']

        sb = StravaBackup(
            access_token=access_token,
            email=email,
            password=password,
            jwt=jwt,
            out_dir=output_dir,
        )
        if sb.jwt != jwt:
            __log__.info("JWT token has changed, will attempt to update the config file")
            config['user']['jwt'] = sb.jwt
            config._updated = True

    if args.dry_run:
        __log__.info("Logged in, would backup '%s' to '%s'", email, output_dir)
    else:
        __log__.info("Logged in, backing up '%s' to '%s'", email, output_dir)

    return sb.run_backup(
        limit=args.limit,
        metadata=not args.no_meta,
        gear=not args.no_gear,
        photos=not args.no_photos,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    sys.exit(main())
