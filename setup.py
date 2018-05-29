"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

from setuptools import setup, find_packages
from codecs import open
from os import path

VERSION = '1.2.1'

here = path.abspath(path.dirname(__file__))


setup(
    name='tc_mailmanager',
    version=VERSION,
    description="ToucanToco's cross-python-projects MailManager",
    long_description=open(path.join(here, 'README.md'), encoding='utf-8').read(),
    url='https://github.com/toucantoco/tc_mailmanager',
    author='Toucan Toco',
    author_email='dev@toucantoco.com',
    classifiers=[
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    install_requires=[
        'sendgrid>=3,<6',
        'tctc_envelopes==0.5',
    ],
    extras_require={'test': ['pytest', 'mock']},
)
