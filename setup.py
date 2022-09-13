import sys

# Make sure we are running python3.5+
if 10 * sys.version_info[0]  + sys.version_info[1] < 35:
    sys.exit("Sorry, only Python 3.5+ is supported.")

from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()

setup(
      name             =   'pfdo',
      version          =   '3.2.6',
      description      =   'Base machinery for performing operations on pftrees',
      long_description =   readme(),
      author           =   'FNNDSC',
      author_email     =   'dev@babymri.org',
      url              =   'https://github.com/FNNDSC/pfdo',
      packages         =   ['pfdo'],
      install_requires =   ['pfmisc', 'pftree'],
      #test_suite       =   'nose.collector',
      #tests_require    =   ['nose'],
      entry_points={
          'console_scripts': [
              'pfdo = pfdo.__main__:main'
          ]
      },
      #   scripts          =   ['bin/pfdo'],
      license          =   'MIT',
      zip_safe         =   False
)
