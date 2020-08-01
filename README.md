Strava-Backup
=============
Get your data back from Strava.

Strava has an export options, but it will only give you the GPX files that Strava produces after
analyzing your uploads.

Thankfully, there is a hidden option to download the original file for individual activities.
However, this is only available on the website and not via the API.

This tool uses the API to get a list of all your events, then web scraping to log into the site
using your username and password and download the original files for all your activities.

The "original file" will usually be either a `*.fit` file (most Garmin devices), `*.tcx`, `*.gpx`,
or `*.json` (Strava mobile application).

The tool will also output a `*.meta.json` file for every activity that includes more information on
the activity (name, description, type, distance, equipment, etc).

Additionally, the tool will backup your shoes and bikes information, as well as any photos that have
been added to activities.


Authentication
--------------
Accessing the Strava API requires a short-term access token. In order access your account on an
ongoing basis, `strava-backup` requires a long-term "refresh token" and some other information with
which it can generate access tokens. For more information see the [Strava API authentication
documentation](https://developers.strava.com/docs/authentication/).

A "refresh token" can be generated using a separate program such as
[strava-tokengen](https://github.com/pR0Ps/strava-tokengen).

In order to back up your data, `strava-backup` can use the following scopes (all optional):
- `profile:read_all` ("View your complete Strava profile"): Will read and backup gear data
- `activity:read` ("View data about your activities"): Will read and backup activity data
- `activity:read_all` ("View data about your private activities"): Will read and backup private activity data


Setup
-----
Use `pip` to install this package:
```bash
pip install strava-backup
```

By default, `strava-backup` will look for a config file called `strava-backup.conf` in
`$XDG_CONFIG_HOME/`, falling back to `~/.config/` if it's unset. An alternate file can be specified
using the `--config` option.

A sample config file has been included in this package. Copy it to the correct spot and fill in the
required information.


Running
-------
`strava-backup` is an incremental backup. It tracks what has already been downloaded by looking at
the output directory and doesn't download it again.

To download all new data, simply run `strava-backup`. See `strava-backup --help` for other options.
To backup data on an ongoing basis, configure your system to call `strava-backup` periodically (see
the [/contrib](contrib/) folder for examples).
