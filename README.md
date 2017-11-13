Strava-Backup
=============
Get your data back from Strava.

Strava has an export options, but it will only give you the GPX files that Strava produces after
analyzing your uploads.

Thankfully, there is a hidden option to download the original file for individual activities. However,
this is only available on the website and not via the API.

This tool uses the API to get a list of all your events, then web scraping to log into the site
using your username and password and download the original files for all your activities.

The "original file" will usually be either a `*.fit` file (most Garmin devices), `*.tcx`, `*.gpx`,
or `*.json` (Strava mobile application).

The tool will also output a `*.meta.json` file for every activity that includes more information on
the activity (name, description, type, distance, equipment, etc).

Additionally, the tool will dump all your 'Gear' information, as well as any photos that have been
added to activities.

Setup
-----
Before the application can access the Strava API, it will need a Strava API token. An API token can
be generated using a separate program such as
[strava-tokengen](https://github.com/pR0Ps/strava-tokengen).

After obtaining an API token, use `pip` to install this package:
```bash
pip install strava-backup
```

`strava-backup` expects to find a config file at `~/.config/strava-backup.conf` by default.

A sample has been included in this package. Copy the sample to the correct spot and set the API
token and other options.

Running
-------
`strava-backup` is an incremental backup. It tracks what has already been downloaded by looking at
the output directory and doesn't download it again.

To download all new information, simply run `strava-backup`. See `strava-backup --help` for other
options. To automatically download new information on an ongoing basis, add the `strava-backup` call
to a cronjob.
