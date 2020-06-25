import os

from setuptools import find_packages, setup

_HERE = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(_HERE, 'README.md')) as f:
    long_desc = f.read()

setup(
    name='hyp3_autorift',
    use_scm_version=True,
    description='A HyP3 plugin for feature tracking processing with AutoRIFT-ISCE',
    long_description=long_desc,
    long_description_content_type='text/markdown',

    url='https://github.com/asfadmin/hyp3-autorift',

    author='ASF APD/Tools Team',
    author_email='uaf-asf-apd@alaska.edu',

    license='BSD',
    include_package_data=True,

    classifiers=[
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        ],

    python_requires='~=3.7',

    install_requires=[
        # FIXME: use boto3 instead of requests for download in hyp3_autorift.io.fetch_jpl_tifs
        'requests',
        # 'boto3',
        # 'botocore',
        'hyp3lib',
        'hyp3proclib',
        'importlib_metadata',
        'numpy',
        'scipy',
    ],

    extras_require={
        'develop': [
            'pytest',
            'pytest-cov',
            'pytest-console-scripts',
        ]
    },

    packages=find_packages(),

    entry_points={'console_scripts': [
        'hyp3_autorift = hyp3_autorift.__main__:main',
        'autorift_proc_pair = hyp3_autorift.process:main',
        'testautoRIFT_ISCE.py = hyp3_autorift.vend.testautoRIFT_ISCE:main',
        'testGeogrid_ISCE.py = hyp3_autorift.vend.testGeogrid_ISCE:main',
        # FIXME: Only needed for testautoRIFT_ISCE.py
        'topsinsar_filename.py = hyp3_autorift.io:topsinsar_mat',
        ]
    },

    zip_safe=False,
)
