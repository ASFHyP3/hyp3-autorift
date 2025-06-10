import glob
from pathlib import Path

import boto3
import numpy as np
from botocore.exceptions import ClientError
from osgeo import gdal

from hyp3_autorift.utils import upload_file_to_s3_with_publish_access_keys


gdal.UseExceptions()

S3_CLIENT = boto3.client('s3')

# Default bucket for retrieval to support hyp3
S3_BUCKET = 'its-live-data'
S3_BUCKET_PREFIX = 'static-topo-corrections'

STATIC_DIR = Path('./static_topo_corrections/')

RADAR_GRID_PARAMS = [
    'NC_GLOBAL#sensing_start',
    'NC_GLOBAL#wavelength',
    'NC_GLOBAL#prf',
    'NC_GLOBAL#starting_range',
    'NC_GLOBAL#range_pixel_spacing',
    'NC_GLOBAL#length',
    'NC_GLOBAL#width',
    'NC_GLOBAL#ref_epoch',
]

TOPO_CORRECTION_FILES = ['x.tif', 'y.tif', 'z.tif', 'layover_shadow_mask.tif']


def retrieve_static_nc_from_s3(burst_id: str, bucket: str, filename: str) -> str | None:
    """Attempt to download a radar static topographic correction file from S3.

    Args:
        burst_id: The format ISCE burst ID
        bucket: The bucket to download from
        filename: The filename to save the static file as

    Returns:
        The filename of the downloaded static file if one was found, else None
    """

    bucket_prefix = f'{S3_BUCKET_PREFIX}/{burst_id[:-4]}'
    s3_filename = f'{burst_id}_static_rdr.nc'
    key = f'{bucket_prefix}/{s3_filename}'

    print(f'Retrieving Static File: {key}')

    try:
        S3_CLIENT.download_file(bucket, key, filename)
    except ClientError as e:
        code = e.response['Error']['Code']
        if code == '404':
            message = f'Unable to find static correction file for {burst_id}.'
        elif code == '403':
            message = f'Got access denied when attempting to retrieve static correction file for {burst_id}.'
        else:
            message = e
        print(message + ' `rdr2geo` will be run for this burst.')
        return None

    return filename


def upload_static_nc_to_s3(filename: Path, burst_id: str, bucket: str) -> None:
    """Attempt to upload a radar static topographic correction file to S3.

    Args:
        filename: The path to the static file to upload
        burst_id: The ISCE format burst ID
        bucket: The AWS S3 bucket to upload to

    Returns:
        None
    """

    assert filename.exists()

    bucket_prefix = f'{S3_BUCKET_PREFIX}/{burst_id[:-4]}'

    try:
        upload_file_to_s3_with_publish_access_keys(filename, bucket, bucket_prefix)
    except Exception as e:
        print(f'Unable to upload {filename} to S3 due to {e}.')


def get_static_layers(burst_ids: list[str], bucket: str) -> dict[str, bool]:
    """Download radar-geometry topographic corrections and stage them for ISCE3 processing

    Args:
        burst_ids: List of ISCE format burst IDs
        bucket: The bucket to download from

    Returns:
        Dict of burst ids to boolean values that correspond to whether a static correction file was found
    """

    has_static_layer = {}
    for burst_id in burst_ids:
        has_static_layer[burst_id] = get_static_layer(burst_id, bucket)
    return has_static_layer


def get_static_layer(burst_id: str, bucket: str) -> bool:
    """Download a radar-geometry topographic correction and stage it for ISCE3 processing
    in the following manner:

        static_topo_corrections/
          - | {burst_id}/
            - | {burst_id}_static.nc     (Retrived from S3)
            - | x.tif                    (Created from NetCDF)
            - | y.tif                    (Created from NetCDF)
            - | z.tif                    (Created from NetCDF)
            - | layover_shadow_mask.tif  (Created from NetCDF)
            - | radar_grid.txt           (Created from NetCDF)

    Args:
        burst_id: ISCE format burst ID
        bucket: The bucket to download from

    Returns:
        True if a static file was retreived else False
    """

    STATIC_DIR.mkdir(exist_ok=True)
    burst_static_dir = STATIC_DIR / burst_id
    burst_static_dir.mkdir(exist_ok=True)

    static_file = retrieve_static_nc_from_s3(
        burst_id=burst_id, bucket=bucket, filename=str(burst_static_dir / f'{burst_id}_static_rdr.nc')
    )

    if not static_file:
        return False

    static_file = 'NETCDF:' + static_file

    files = [str(burst_static_dir / file) for file in TOPO_CORRECTION_FILES]

    for band, filename in enumerate(files, start=1):
        band_str = f':Band{band}'
        band_gdal_type = gdal.GDT_Float64 if band != 4 else gdal.GDT_Byte
        band_numpy_type = np.float64 if band != 4 else np.uint8

        in_ds = gdal.Open(static_file + band_str)
        in_band = in_ds.GetRasterBand(1)
        in_arr = in_band.ReadAsArray().astype(band_numpy_type)

        rows, cols = in_arr.shape

        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(filename, cols, rows, 1, band_gdal_type)
        out_ds.GetRasterBand(1).WriteArray(in_arr)
        out_ds.FlushCache()

    gdal.BuildVRT(str(burst_static_dir / 'topo.vrt'), files, separate=True, outputSRS='EPSG:4326')

    with gdal.Open(static_file) as ds:
        metadata = ds.GetMetadata()

    with open(burst_static_dir / 'radar_grid.txt', 'w') as rdr_grid_file:
        for param in RADAR_GRID_PARAMS:
            rdr_grid_file.write(metadata[param] + '\n')

    return True


def create_static_layer(burst_id: str, isce_product_path: str = './product/*') -> Path | None:
    """Create a radar-geometry static topographic correction netCDF from a processed reference burst.

    Args:
        burst_id: ISCE format burst ID
        isce_product_path: The directory containing the reference burst ISCE product

    Returns:
        The Path to the static file if one was able to be created, else None
    """

    burst_paths = sorted(glob.glob(isce_product_path))
    burst_path = [p for p in burst_paths if p.split('/')[-1] == burst_id][0]
    burst_dir = glob.glob(burst_path + '/*')[0]
    burst_rdr_grid_txt = glob.glob(glob.glob(burst_path + '/*')[0] + '/*.txt')[0]
    burst_topo_nc = f'{burst_id}_static_rdr.nc'
    topo_files = [burst_dir + '/' + file for file in TOPO_CORRECTION_FILES]

    with open(burst_rdr_grid_txt, 'r') as rdr_grid_file:
        rdr_grid = dict(zip(RADAR_GRID_PARAMS, [line.strip('\n') for line in rdr_grid_file.readlines()]))

    with gdal.Open(burst_dir + '/' + 'topo.vrt') as ds:
        cols = ds.RasterXSize
        rows = ds.RasterYSize

    driver = gdal.GetDriverByName('netCDF')
    options = ['FORMAT=NC4', 'COMPRESS=DEFLATE']
    out_ds = driver.Create(burst_topo_nc, cols, rows, len(topo_files), gdal.GDT_Float64, options)

    if out_ds is None:
        print('Failed to create radar static correction NetCDF file. Check that your GDAL has NetCDF-4 support.')
        return None

    out_ds.SetMetadata(rdr_grid)

    for i, file in enumerate(topo_files):
        with gdal.Open(file) as in_ds:
            band_data = in_ds.GetRasterBand(1).ReadAsArray()

            if file.endswith('layover_shadow_mask.tif'):
                band_data = band_data.astype(np.float64)

            out_ds.GetRasterBand(i + 1).WriteArray(band_data)

    out_ds.FlushCache()

    return Path(burst_topo_nc)
