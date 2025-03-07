# Run this command in this directory to install CLI global command:
# pip3 install --editable .
from setuptools import setup, find_packages

setup(
    name="migrationtool",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests",
    ],
    entry_points={
        "console_scripts": [
            "migrationtool=src.cli:main",
        ],
    },
)
