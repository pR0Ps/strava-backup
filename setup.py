#!/usr/bin/env python

from setuptools import setup
import os.path


try:
    DIR = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(DIR, "README.md"), encoding='utf-8') as f:
        long_description = f.read()
except Exception:
    long_description=None


setup(
    name="strava-backup",
    version="0.4.0",
    description="Get your data back from Strava",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pR0Ps/strava-backup",
    license="MPLv2",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
    ],
    python_requires=">=3.8",
    packages=["stravabackup"],
    package_data={"stravabackup": ["strava-backup.conf"]},
    install_requires=[
        "stravaweblib>=0.0.9,<1.0.0",
        "stravalib>=0.10.4,<1.0.0",
        "commented-configparser>=2,<3",
    ],
    entry_points={'console_scripts': ["strava-backup=stravabackup.__main__:main"]}
)
