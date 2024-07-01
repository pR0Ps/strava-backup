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
    version="0.3.2",
    description="Get your data back from Strava",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pR0Ps/strava-backup",
    license="MPLv2",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ],
    python_requires=">=3.4",
    packages=["stravabackup"],
    package_data={"stravabackup": ["strava-backup.conf"]},
    install_requires=["stravaweblib>=0.0.8,<1.0.0", "stravalib>=0.10.4,<1.0.0"],
    entry_points={'console_scripts': ["strava-backup=stravabackup.__main__:main"]}
)
