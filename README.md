
# HyP3 autoRIFT Plugin

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.4037015.svg)](https://doi.org/10.5281/zenodo.4037015)

The HyP3-autoRIFT plugin provides a set of workflows for feature tracking processing with the AutoRIFT [autonomous Repeat Image Feature Tracking](https://github.com/nasa-jpl/autoRIFT) (autoRIFT) software package. This plugin is part of the [Alaska Satellite Facility's](https://asf.alaska.edu) larger HyP3 (Hybrid Plugin Processing Pipeline) system, which is a batch processing pipeline designed for on-demand processing of remote sensing data. For more information on HyP3, see the [Background](#background) section.

## Installation

1. Ensure that conda is installed on your system (we recommend using [mambaforge](https://github.com/conda-forge/miniforge#mambaforge) to reduce setup times).
2. Clone the `hyp3-autorift` repository and navigate to the root directory of this project
   ```bash
   git clone https://github.com/mfangaritav/hyp3-autorift.git
   cd hyp3-autorift
   ```
3. Create  and activate your Python environment
   ```bash
   
   mamba env create -f environment.yml
   mamba activate hyp3-autorift
   ```
4. Install a development version of HyP3 autoRIFT
   ```bash
   python -m pip install -e .
   cd ..
   ```
5. Clone the `COMPASS` repository and navigate to the root directory of this project and install it.
   ```bash
   git clone https://github.com/mfangaritav/COMPASS.git
   cd COMPASS
   python -m pip install -e .
   cd ..
   ```
6. Clone the `autoRIFT` repository and navigate to the root directory of this project and install it.
   ```bash
   git clone https://github.com/mfangaritav/autoRIFT.git
   cd autoRIFT
   python setup.py install
   cd ..
   ```

## Usage

The HyP3-autoRIFT plugin provides workflows (accessible directly in Python or via a CLI) that can be used to process SAR  data or optical data using autoRIFT. HyP3-autoRIFT can process these satellite missions:
* SAR:
  * Sentinel-1
* Optical:
  * Sentinel-2
  * Landsat 4,5,7,8,9 
  
To see all available workflows, run:
```
python -m hyp3_autorift ++help
```

### `hyp3_autorift` workflow

The `hyp3_autorift` workflow is used to get dense feature tracking between two images using autoRIFT. You can run this workflow by selecting the `hyp3_autorift` process: 
```
python -m hyp3_autorift ++process hyp3_autorift [WORKFLOW_ARGS]
```
or by using the `hyp3_autorift` console script:
```
hyp3_autorift [WORKFLOW_ARGS]
```
For example:

```
hyp3_autorift \
  "S1_105606_IW1_20230612T025537_VV_3F09-BURST" \
  "S1_105606_IW1_20230624T025538_VV_8279-BURST"
```

This command will run autorift for a pair of Sentinel-1 bursts.

> [!IMPORTANT]
> Credentials are necessary to access Landsat and Sentinel-1 data. See the Credentials section for more information.

For all options available to this workflow, see the help documentation: 
```
hyp3_autorift --help
```

### Credentials

Depending on the mission being processed, some workflows will need you to provide credentials. Generally, credentials are provided via environment variables, but some may be provided by command-line arguments or via a `.netrc` file. 

#### AWS Credentials

To process Landsat images, you must provide AWS credentials because the data is hosted by USGS in a "requester pays" bucket. To provide AWS credentials, you can either use an AWS profile specified in your `~/.aws/credentials` by exporting:
```
export AWS_PROFILE=your-profile
```
or by exporting credential environment variables:
```
export AWS_ACCESS_KEY_ID=your-id
export AWS_SECRET_ACCESS_KEY=your-key
export AWS_SESSION_TOKEN=your-token  # optional; for when using temporary credentials
```

For more information, please see: <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html>

#### NASA Earthdata Login

To process Sentinel-1 images, you must provide Earthdata Login credentials in order to download input data.
* If you do not already have an Earthdata account, you can sign up [here](https://urs.earthdata.nasa.gov/home). 

For Earthdata login, you can provide credentials by exporting environment variables:
```
export EARTHDATA_USERNAME=your-edl-username
export EARTHDATA_PASSWORD=your-edl-password
```
or via your [`~/.netrc` file](https://everything.curl.dev/usingcurl/netrc) which should contain lines like these two:
```
machine urs.earthdata.nasa.gov login your-edl-username password your-edl-password
```

> [!TIP]
> Your `~/.netrc` file should only be readable by your user; otherwise, you'll receive a "net access too permissive" error. To fix, run:
> ```
> chmod 0600 ~/.netrc
> ```

### Docker Container

The ultimate goal of this project is to create a docker container that can run autoRIFT workflows within a HyP3 deployment. To run the current version of the project's container, use this command:
```
docker run -it --rm \
    -e AWS_ACCESS_KEY_ID=[YOUR_KEY] \
    -e AWS_SECRET_ACCESS_KEY=[YOUR_SECRET] \
    -e EARTHDATA_USERNAME=[YOUR_USERNAME_HERE] \
    -e EARTHDATA_PASSWORD=[YOUR_PASSWORD_HERE] \
    ghcr.io/asfhyp3/hyp3-autorift:latest \
    ++process hyp3_autorift \
    [WORKFLOW_ARGS]
```

> [!TIP]
> You can use [`docker run --env-file`](https://docs.docker.com/reference/cli/docker/container/run/#env) to capture all the necessary environment variables in a single file.

#### Docker Outputs

To retain hyp3_autorift output files running via Docker there are two recommended approaches:

1. Use a volume mount

   Add the `-w /tmp -v ${PWD}:/tmp` flags after `docker run`; `-w` changes the working directory inside the container to `/tmp` and `-v` will mount your current working directory to the `/tmp` location inside the container such that hyp3_autorift outputs are preserved locally. You can replace `${PWD}` with any valid path.

1. Copy outputs to a remote AWS S3 Bucket

   Append the `--bucket` and `--bucket-prefix` to [WORKFLOW_ARGS] so that the final output files are uploaded to AWS S3. This also requires that AWS credentials to write to the bucket are available to the running container. For example, to write outputs to a hypothetical bucket `s3://hypothetical-bucket/test-run/`:

   ```
   docker run -it --rm \
       -e AWS_ACCESS_KEY_ID=[YOUR_KEY] \
       -e AWS_SECRET_ACCESS_KEY=[YOUR_SECRET] \ 
       -e AWS_SESSION_TOKEN=[YOUR_TOKEN] \  # Optional
       -e EARTHDATA_USERNAME=[YOUR_USERNAME_HERE] \
       -e EARTHDATA_PASSWORD=[YOUR_PASSWORD_HERE] \
       ghcr.io/asfhyp3/hyp3-autorift:latest \
         ++process hyp3_autorift \
         [WORKFLOW_ARGS] \
         --bucket "hypothetical-bucket" \
         --bucket-prefix "test-run"
   ```

## Background
HyP3 is broken into two components: the cloud architecture/API that manages the processing of HyP3 workflows and Docker container plugins that contain scientific workflows that produce new science products from a variety of data sources (see figure below for the full HyP3 architecture).

![Cloud Architecture](images/arch_here.jpg)

The cloud infrastructure-as-code for HyP3 can be found in the main [HyP3 repository](https://github.com/asfhyp3/hyp3)., while this repository contains a plugin that can be used for feature tracking processing with AutoRIFT.

## License
The HyP3-autoRIFT plugin is licensed under the BSD 3-Clause license. See the LICENSE file for more details.

## Code of conduct
We strive to create a welcoming and inclusive community for all contributors to HyP3-autoRIFT. As such, all contributors to this project are expected to adhere to our code of conduct.

Please see `CODE_OF_CONDUCT.md` for the full code of conduct text.

## Contributing
Contributions to the HyP3-autoRIFT plugin are welcome! If you would like to contribute, please submit a pull request on the GitHub repository.

## Contact Us
Want to talk about HyP3-autoRIFT? We would love to hear from you!

Found a bug? Want to request a feature?
[open an issue](https://github.com/ASFHyP3/asf_tools/issues/new)

General questions? Suggestions? Or just want to talk to the team?
[chat with us on gitter](https://gitter.im/ASFHyP3/community)
