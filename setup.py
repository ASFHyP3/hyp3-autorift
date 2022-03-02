from pathlib import Path

from setuptools import find_packages, setup

readme = Path(__file__).parent / 'README.md'

setup(
    name='hyp3_autorift',
    use_scm_version=True,
    description='A HyP3 plugin for feature tracking processing with AutoRIFT-ISCE',
    long_description=readme.read_text(),
    long_description_content_type='text/markdown',

    url='https://github.com/ASFHyP3/hyp3-autorift',
    project_urls={
        'Documentation': 'https://hyp3-docs.asf.alaska.edu',
    },

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
        'Programming Language :: Python :: 3.9',
    ],

    python_requires='~=3.8',

    install_requires=[
        'boto3',
        'botocore',
        'gdal',
        'hyp3lib==1.7.0',
        'matplotlib',
        'netCDF4',
        'numpy',
        'requests',
        'scipy',
    ],

    extras_require={
        'develop': [
            'flake8',
            'flake8-import-order',
            'flake8-blind-except',
            'flake8-builtins',
            'pillow',
            'pytest',
            'pytest-cov',
            'pytest-console-scripts',
            'responses',
        ]
    },

    packages=find_packages(),

    entry_points={'console_scripts': [
        'hyp3_autorift = hyp3_autorift.__main__:main',
        'autorift_proc_pair = hyp3_autorift.process:main',
        ]
    },

    zip_safe=False,
)
