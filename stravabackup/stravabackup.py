#!/usr/bin/env python

from collections import defaultdict
import datetime
import json
import logging
import os
import re
import sys

import requests
import stravalib
from units import LeafUnit, ComposedUnit
from units.quantity import Quantity

from stravaweblib import WebClient, FrameType, DataFormat

__all__ = ["StravaBackup"]
__log__ = logging.getLogger(__name__)

TIME_FMT = "%Y-%m-%dT%H:%m:%SZ"
TIME_FMT_FILE = "%Y-%m-%dT%H-%m-%SZ"

META_EXTENSION = "meta.json"
ACTIVITY_FILENAME = "{start}_{id}.{ext}"
GEAR_FILENAME = "{id}.{ext}"
PHOTO_FILENAME = "{activity_id}_{photo_id}.{ext}"
ACTIVITY_REGEX = re.compile("[\dTZ-]*_(\d*)\..*")
PHOTO_REGEX = re.compile("(\d*)_([\w-]*)\..*")

PHOTO_SOURCES = {1: "Strava", 2: "Instagram"}


def valid_unit(unit):
    """A unit is valid if it uses meters, seconds, or a combination thereof"""
    if isinstance(unit, LeafUnit):
        return unit.specifier in ("m", "s")
    elif isinstance(unit, ComposedUnit):
        numer = unit.numer
        denom = unit.denom
        if len(numer) == len(denom) == 1:
            return valid_unit(numer) and valid_unit(denom)
    return False


def photo_url(photo):
    """Return the largest picture URL for the photo object"""
    if not photo.urls:
        return None
    return photo.urls[sorted(photo.urls, key=int, reverse=True)[0]]


def obj_to_json(obj):
    """How to dump everything to JSON"""
    if isinstance(obj, datetime.date):
        return obj.strftime(TIME_FMT)
    elif isinstance(obj, datetime.timedelta):
        return obj.total_seconds()
    elif isinstance(obj, Quantity) and valid_unit(obj.unit):
        return obj.num
    elif isinstance(obj, stravalib.model.Activity):
        return {p: getattr(obj, p) for p in ("id", "name", "description",
                                             "type", "commute", "trainer",
                                             "distance", "start_date",
                                             "moving_time", "elapsed_time",
                                             "calories", "device_name",
                                             "gear_id")}
    elif isinstance(obj, stravalib.model.Gear):
        d = {p: getattr(obj, p) for p in ('id', 'name', 'brand_name',
                                          'model_name', 'description')}
        if hasattr(obj, 'components'):
            d['components'] = obj.components
        if isinstance(obj, stravalib.model.Bike):
            d['frame_type'] = str(FrameType(obj.frame_type))
        return d
    elif isinstance(obj, stravalib.model.ActivityPhoto):
        d = {p: getattr(obj, p) for p in ('activity_id', 'caption', 'location',
                                          'created_at', 'uploaded_at')}
        d['id'] = obj.unique_id or obj.id
        d['source'] = PHOTO_SOURCES.get(obj.source)
        d['url'] = photo_url(obj)
        return d

    raise ValueError("Can't serialize object: {!r}".format(obj))


class StravaBackup:
    """Download your data from Strava"""

    def __init__(self, api_token, email, password, out_dir):
        self.api_token = api_token
        self.out_dir = out_dir
        self.client = WebClient(access_token=api_token, email=email, password=password)
        self._have = self._find_existing_data()
        self._ensure_output_dirs()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    @property
    def activity_dir(self):
        return os.path.join(self.out_dir, "activities")

    @property
    def photo_dir(self):
        return os.path.join(self.out_dir, "photos")

    @property
    def gear_dir(self):
        return os.path.join(self.out_dir, "gear")

    def _ensure_output_dirs(self):
        os.makedirs(self.activity_dir, exist_ok=True)
        os.makedirs(self.photo_dir, exist_ok=True)
        os.makedirs(self.gear_dir, exist_ok=True)

    def _find_existing_data(self):
        """Look through the output dir for existing files"""
        # layout is [meta, data, {photoid: [photo_meta, photo_data]}]

        # Find existing activities
        have = defaultdict(lambda: [False, False, defaultdict(lambda: [False, False])])
        for _, _, filenames in os.walk(self.activity_dir):
            for filename in filenames:
                m = ACTIVITY_REGEX.match(filename)
                if not m:
                    continue
                activity_id = int(m.group(1))
                if filename.endswith("." + META_EXTENSION):
                    have[activity_id][0] = True
                else:
                    have[activity_id][1] = True

        # Find existing photos for activities
        for _, _, filenames in os.walk(self.photo_dir):
            for filename in filenames:
                m = PHOTO_REGEX.match(filename)
                if not m:
                    continue
                activity_id = int(m.group(1))
                photo_id = m.group(2)
                if filename.endswith("." + META_EXTENSION):
                    have[activity_id][2][photo_id][0] = True
                else:
                    have[activity_id][2][photo_id][1] = True

        return have

    def _data_path(self, data, ext=META_EXTENSION):
        """Return a file to save any given object into"""
        if isinstance(data, stravalib.model.Activity):
            filename = ACTIVITY_FILENAME.format(
                start=data.start_date.strftime(TIME_FMT_FILE),
                id=data.id,
                ext=ext
            )
            path = os.path.join(self.activity_dir, str(data.start_date.year))
        elif isinstance(data, stravalib.model.Gear):
            filename = GEAR_FILENAME.format(
                id=data.id,
                ext=ext
            )
            path = self.gear_dir
        elif isinstance(data, stravalib.model.ActivityPhoto):
            filename = PHOTO_FILENAME.format(
                activity_id=data.activity_id,
                photo_id=data.unique_id or data.id,
                ext=ext
            )
            path = self.photo_dir
        else:
            raise AssertionError("Unknown datatype '{}'".format(type(data)))

        os.makedirs(path, exist_ok=True)
        return os.path.join(path, filename)

    def have_activity(self, activity):
        """Check if we have an activity (and all it's photos)"""
        h = self._have[activity.id]
        if not h[0] or not h[1]:
            return False

        complete_photos = [k for k, v in h[2].items() if all(v)]
        return len(complete_photos) >= activity.total_photo_count

    def run_backup(self, limit=None):

        # log in using the API and the web
        activities = self.client.get_activities()
        athlete = self.client.get_athlete()

        __log__.info("Downloading current gear data")
        for gear in athlete.bikes + athlete.shoes:
            obj = self.client.get_gear(gear)
            if isinstance(obj, stravalib.model.Bike):
                obj.components = self.client.get_bike_components(gear)
            with open(self._data_path(obj), 'w') as f:
                json.dump(obj, f, sort_keys=True, default=obj_to_json)

        count = 0
        for a in activities:

            if limit is not None and count >= limit:
                return 0

            if self.have_activity(a):
                continue

            count += 1
            a = self.client.get_activity(a.id)

            have_meta, have_data, photos = self._have[a.id]
            for p in self.client.get_activity_photos(a.id,
                                                     only_instagram=False,
                                                     size=5000):
                # unique_id for Strava, id for Instagram
                photo_id = p.unique_id or p.id

                if not photos[photo_id][0]:
                    with open(self._data_path(p), 'w') as f:
                        json.dump(p, f, sort_keys=True, default=obj_to_json)

                if not photos[photo_id][1]:
                    url = photo_url(p)
                    if not url:
                        continue

                    __log__.info("Downloading photo")
                    resp = requests.get(url, stream=True)
                    # TODO: Check for filetype instead of assuming jpg
                    with open(self._data_path(p, ext="jpg"), 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=16384):
                            if chunk:
                                f.write(chunk)

            if not have_meta:
                with open(self._data_path(a), 'w') as f:
                    json.dump(a, f, sort_keys=True, default=obj_to_json)

            if not a.manual and not have_data:
                # Download the original activity from the website
                data = self.client.get_activity_data(a,
                                                     fmt=DataFormat.ORIGINAL,
                                                     json_fmt=DataFormat.GPX)
                ext = data.filename.rsplit(".", 1)[-1]

                __log__.info("Downloading activity %s (%s)", a, data.filename)
                with open(self._data_path(a, ext=ext), 'wb') as f:
                    for chunk in data.content:
                        if chunk:
                            f.write(chunk)
        return 0
