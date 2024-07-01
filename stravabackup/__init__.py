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
ACTIVITY_REGEX = re.compile(r"[\dTZ-]*_(\d*)\..*")
PHOTO_REGEX = re.compile(r"(\d*)_([\w-]*)\..*")

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
    elif isinstance(unit, list):
        # units can be a list of units (ex: m/s)
        return all(valid_unit(x) for x in unit)
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
                                             "gear_id", "total_elevation_gain",
                                             "average_speed", "max_speed")}
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


def json_dump(*args, **kwargs):
    """Custom JSON dump that knows how to handle all the required formats"""
    json.dump(*args, sort_keys=True, ensure_ascii=False, default=obj_to_json, **kwargs)


class StravaBackup:
    """Download your data from Strava"""

    def __init__(self, access_token, email, password, out_dir):
        self.out_dir = out_dir

        # Will attempt to log in using the username/password
        self.client = WebClient(access_token=access_token, email=email,
                                password=password)
        self._have = self._find_existing_data()

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

    def _ensure_output_dirs(self, gear=True, photos=True):
        os.makedirs(self.activity_dir, exist_ok=True)
        if photos:
            os.makedirs(self.photo_dir, exist_ok=True)
        if gear:
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

    def _save_metadata(self, obj):
        """Write the objects's metadata into the correct file"""
        path = self._data_path(obj)
        with open(path, "wt", encoding="utf8") as fp:
            json_dump(obj, fp)

    def have_activity(self, activity, photos=True, metadata=True):
        """Check if we have an activity (and all it's photos)"""
        h = self._have[activity.id]

        if metadata and not h[0]:
            return False

        if not h[1] and not activity.manual:
            return False

        if not photos:
            return True

        complete_photos = [k for k, v in h[2].items() if all(v)]
        return len(complete_photos) >= activity.total_photo_count

    def _activities(self):
        i = self.client.get_activities()
        try:
            yield from i
        except stravalib.exc.AccessUnauthorized:
            __log__.error("Failed to list activities (missing activity:read scope?). Skipping.")

    def backup_gear(self, dry_run=False):
        athlete = self.client.get_athlete()
        if athlete.bikes is None and athlete.shoes is None:
            __log__.error("Failed to get gear data (missing profile:read_all scope?). Skipping.")
            return

        bikes = athlete.bikes or []
        shoes = athlete.shoes or []

        if dry_run:
            __log__.info(
                "Would download current gear data from %d bike(s) and %d shoe(s)",
                len(bikes), len(shoes)
            )
            return

        __log__.info(
            "Downloading current gear data (%d bike(s) and %d shoe(s))",
            len(bikes), len(shoes)
        )

        for gear in bikes + shoes:
            obj = self.client.get_gear(gear)
            if isinstance(obj, stravalib.model.Bike):
                obj.components = self.client.get_bike_components(gear.id)
            self._save_metadata(obj)

    def backup_photos(self, activity_id, photo_data):
        for p in self.client.get_activity_photos(activity_id,
                                                 only_instagram=False,
                                                 size=5000):
            # unique_id for Strava, id for Instagram
            photo_id = p.unique_id or p.id

            if not photo_data[photo_id][0]:
                self._save_metadata(p)

            if not photo_data[photo_id][1]:
                url = photo_url(p)
                if not url:
                    continue

                __log__.info("Downloading photo %s", photo_id)
                resp = requests.get(url, stream=True)
                # TODO: Check for filetype instead of assuming jpg
                with open(self._data_path(p, ext="jpg"), "wb") as f:
                    f.writelines(resp.iter_content(chunk_size=16384))

    def backup_activities(self, *, limit=None, metadata=True, photos=True, dry_run=False):
        count = 0
        for a in self._activities():

            if limit is not None and count >= limit:
                return

            if self.have_activity(a, photos=photos, metadata=metadata):
                continue

            count += 1

            have_meta, have_data, photo_data = self._have[a.id]

            if dry_run:
                if not a.manual and not have_data:
                    __log__.info("Would download activity %s", a)
                elif metadata and not have_meta:
                    __log__.info("Would download metadata for activity %s", a)

                if photos and a.total_photo_count:
                    __log__.info("Would download %d photo(s) from activity %s", a.total_photo_count, a)

                continue

            need_photos = photos and a.total_photo_count
            need_metadata =  metadata and not have_meta

            # Get the fully-detailed activity for photos and metadata
            if need_photos or need_metadata:
                a = self.client.get_activity(a.id)

            if need_photos:
                __log__.info("Downloading %d photo(s) from activity %s", a.total_photo_count, a)
                self.backup_photos(a.id, photo_data)

            if need_metadata:
                self._save_metadata(a)

            if not a.manual and not have_data:
                # Download the original activity from the website
                data = self.client.get_activity_data(a.id,
                                                     fmt=DataFormat.ORIGINAL,
                                                     json_fmt=DataFormat.GPX)
                ext = data.filename.rsplit(".", 1)[-1]

                __log__.info("Downloading activity %s (%s)", a, data.filename)
                with open(self._data_path(a, ext=ext), "wb") as f:
                    f.writelines(data.content)

    def run_backup(self, *, limit=None, metadata=True, gear=True, photos=True, dry_run=False):

        if not dry_run:
            self._ensure_output_dirs(gear=gear, photos=photos)

        if gear:
            self.backup_gear(dry_run=dry_run)

        self.backup_activities(limit=limit, metadata=metadata, photos=photos, dry_run=dry_run)
