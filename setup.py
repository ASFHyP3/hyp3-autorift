import os

from setuptools import find_packages, setup

_HERE = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(_HERE, 'README.md'), 'r') as f:
    long_desc = f.read()

setup(
    name='hyp3_autorift',
    use_scm_version=True,
    description='A HyP3 plugin for feature tracking processing with AutoRIFT-ISCE',
    long_description=long_desc,
    long_description_content_type='text/markdown',

    url='https://scm.asf.alaska.edu/hyp3/hyp3-autorift',

    author='ASF APD/Tools Team',
    author_email='uaf-asf-apd@alaska.edu',

    license='BSD',
    include_package_data=True,

    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3.7',
        ],

    python_requires='~=3.5',

    install_requires=[
        # FIXME: use boto3 instead of requests for download in hyp3_autorift.io.fetch_jpl_tifs
        'requests',
        # 'boto3',
        # 'botocore',
        'hyp3lib',
        'hyp3proclib',
        'importlib_metadata',
        'numpy',
    ],

    extras_require={
        'develop': [
            'pytest',
            'pytest-cov',
            'pytest-console-scripts',
            'tox',
            'tox-conda',
        ]
    },

    packages=find_packages(),

    # TODO: add netcdf_output.py and topsinsar_filename.py entrypoints
    entry_points={'console_scripts': [
        'hyp3_autorift = hyp3_autorift.__main__:main',
        ]
    },

    zip_safe=False,
)
