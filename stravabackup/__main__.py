#!/usr/bin/env python

import argparse
import configparser
import logging
import os
import sys

from stravabackup import StravaBackup


__log__ = logging.getLogger(__name__)


CONFIG_FILE = os.path.join(os.environ.get('XDG_CONFIG_HOME', os.path.join(os.environ['HOME'], '.config')), 'strava-backup.conf')
OUTPUT_DIR = os.path.join(os.environ.get('XDG_DATA_HOME', os.path.join(os.environ['HOME'], ".local", "share")), "strava-backup")


def main():
    parser = argparse.ArgumentParser(
            description='Get your data back from Strava'
    )
    parser.add_argument("--config", nargs="?", type=argparse.FileType('r'),
                        default=CONFIG_FILE,
                        help="The config file to use (default: %(default)s)")
    parser.add_argument("--limit", nargs="?", type=int, default=None,
                        help="The maximum number of activities to back up in "
                        "a single run (default: %(default)s)")
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read_file(args.config)

    api_token = config['global']['api_token']
    output_dir = config['global'].get('output_dir', OUTPUT_DIR)
    email = config['user']['email']
    password = config['user']['password']

    __log__.debug("Backing up '%s' to '%s'", email, output_dir)
    sb = StravaBackup(api_token, email, password, output_dir)
    return sb.run_backup(args.limit)


if __name__ == "__main__":
    sys.exit(main())
