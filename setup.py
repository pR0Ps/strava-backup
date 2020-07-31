#!/usr/bin/env python

from setuptools import setup

setup(name="strava-backup",
      version="0.2.0",
      description="Get your data back from Strava",
      url="https://github.com/pR0Ps/strava-backup",
      license="MPLv2",
      classifiers=[
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.4",
          "Programming Language :: Python :: 3.5",
          "Programming Language :: Python :: 3.6",
      ],
      packages=["stravabackup"],
      package_data={"stravabackup": ["strava-backup.conf"]},
      install_requires=["stravaweblib>=0.0.4,<1.0.0", "stravalib>=0.10.2,<1.0.0"],
      entry_points={'console_scripts': ["strava-backup=stravabackup.__main__:main"]}
)
