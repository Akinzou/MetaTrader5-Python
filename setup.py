from setuptools import setup, find_packages
import codecs
import os

here = os.path.abspath(os.path.dirname(__file__))

with codecs.open(os.path.join(here, "README.md"), encoding="utf-8") as fh:
    long_description = "\n" + fh.read()

VERSION = '1'
DESCRIPTION = 'Connect MT5 with python'
LONG_DESCRIPTION = 'Connect MT5 with python'

# Setting up
setup(
    name="MetaTrader5Python",
    version=VERSION,
    author="Wiktor Jelen",
    author_email="wiktorjn@gmail.com",
    description=DESCRIPTION,
    long_description_content_type="text/markdown",
    long_description=long_description,
    packages=find_packages(),
    install_requires=[],
    keywords=['python', 'trading', 'mt5', 'metatrader5', 'meta trader5', 'meta trader 5'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Unix",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
    ]
)
