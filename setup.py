#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name="crust",
    version="0.2.1",

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

    classifiers=(
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.0",
        "Programming Language :: Python :: 3.1",
        "Programming Language :: Python :: 3.2",
    ),

    zip_safe=False,
)
