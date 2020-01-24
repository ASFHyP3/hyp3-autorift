
import os

from setuptools import setup, find_packages


_HERE = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(_HERE, 'README.md'), 'r') as f:
    long_desc = f.read()

setup(
    name='hyp3-autorift',
    use_scm_version=True,
    description='HyP3 processing for autoRIFT ISCE',
    long_description=long_desc,
    long_description_content_type='text/markdown',

    url='https://scm.asf.alaska.edu/jhkennedy/hyp3-autorift',

    author='ASF APD/Tools Team',
    author_email='uaf-asf-apd@alaska.edu',

    license='BSD',
    include_package_data=True,

    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3.7',
        ],

    install_requires=[
        'importlib_metadata',
    ],

    packages=find_packages(),

    entry_points={'console_scripts': [
        'hyp3_autorift = hyp3_autorift.__main__:main',
        ]
    },

    zip_safe=False,
)
