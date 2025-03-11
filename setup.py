# Run this command in root directory to install CLI global command:
# pip3 install -e .
from setuptools import setup, find_packages

setup(
    name='rabbitmq_migration',
    version='0.1',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[

    ],
    entry_points={
        'console_scripts': [
            'rabbitmq-migration = cli:main',
        ],
    },
)