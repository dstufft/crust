#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name="crust",
    version="0.1",

    description="Framework for Tastypie API Clients",
    long_description=open("README.rst").read(),
    url="https://github.com/dstufft/crust/",
    license=open("LICENSE").read(),

    author="Donald Stufft",
    author_email="donald.stufft@gmail.com",

    install_requires=[
        "requests",
    ],

    extras_require={
        "test": ["pytest"]
    },

    packages=find_packages(exclude=["tests"]),
    package_data={"": ["LICENSE"]},
    include_package_data=True,

    zip_safe=False,
)
