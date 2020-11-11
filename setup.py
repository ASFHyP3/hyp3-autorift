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

    url='https://github.com/ASFHyP3/hyp3-autorift',

    author='ASF APD/Tools Team',
    author_email='uaf-asf-apd@alaska.edu',

    license='BSD',
    include_package_data=True,

    classifiers=[
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        ],

    python_requires='~=3.8',

    install_requires=[
        'boto3',
        'botocore',
        'gdal',
        'hyp3lib==1.6.1',
        'hyp3proclib',
        'importlib_metadata',
        'netCDF4',
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
        'autorift = hyp3_autorift.__main__:entry',
        'hyp3_autorift = hyp3_autorift.__main__:main',
        'hyp3_autorift_v2 = hyp3_autorift.__main__:main_v2',
        'autorift_proc_pair = hyp3_autorift.process:main',
        'testautoRIFT_ISCE.py = hyp3_autorift.vend.testautoRIFT_ISCE:main',
        'testGeogrid_ISCE.py = hyp3_autorift.vend.testGeogrid_ISCE:main',
        'testautoRIFT.py = hyp3_autorift.vend.testautoRIFT:main',
        'testGeogridOptical.py = hyp3_autorift.vend.testGeogridOptical:main',
        'optical = hyp3_autorift.vend.single_scene_proc_optical_fetchDEM_full:main',
        # FIXME: Only needed for testautoRIFT_ISCE.py
        'topsinsar_filename.py = hyp3_autorift.io:topsinsar_mat',
        ]
    },

    zip_safe=False,
)
