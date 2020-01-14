
import os
import re

from setuptools import setup


_HERE = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(_HERE, 'README.md'), 'r') as f:
    long_desc = f.read()
with open(os.path.join(_HERE, 'hyp3_autorift', '__init__.py')) as f:
    init_file = f.read()

setup(
    name='hyp3-autorift',
    version=re.search(r'{}\s*=\s*[(]([^)]*)[)]'.format('__version_info__'),
                      init_file
                      ).group(1).replace(', ', '.'),

    description='HyP3 processing for autoRIFT ISCE',
    long_description=long_desc,
    long_description_content_type='text/markdown',

    url='https://scm.asf.alaska.edu/jhkennedy/hyp3-autorift',

    author='Joseph H. Kennedy',
    author_email='jhkennedy@alaska.edu',

    license='BSD',
    include_package_data=True,

    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3.7',
        ],

    install_requires=[],

    packages=[
        'hyp3_autorift'
        ],

    entry_points={'console_scripts': ['hyp3_autorift = hyp3_autorift.__main__:main']},

    zip_safe=False,
)
