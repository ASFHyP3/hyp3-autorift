import glob
from pathlib import Path

import boto3
import numpy as np
from osgeo import gdal

from hyp3_autorift.utils import upload_file_to_s3_with_publish_access_keys


gdal.UseExceptions()

S3_CLIENT = boto3.client('s3')

# FIXME: This is a temporary bucket for testing
S3_BUCKET = 's1-static-file-testing'

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


def retrieve_static_nc_from_s3(burst_id, bucket):
    """
    Planned Bucket Structure:

    static_topo_layers:
      - | {burst_id_w/o_swath}
        - | {burst_id}_static.nc  # Should be 3 files total for IW1, IW2, IW3. (What about EW?)
    """

    bucket_prefix = burst_id[:-4]
    filename = f'{burst_id}_static_rdr.nc'
    key = f'{bucket_prefix}/{filename}'

    print(f'Retrieving Static File: {key}')

    try:
        S3_CLIENT.download_file(bucket, key, filename)
    except Exception:
        print(f'Unable to retrieve static topographic corrections for {burst_id} from S3.')
        return None

    return filename


# TODO: Replace with upload_to_s3 publish version
def upload_static_nc_to_s3(filename: Path, burst_id: str, bucket: str):
    """
    Planned Bucket Structure:

    static_topo_layers:
      - | {burst_id_w/o_swath}
        - | {burst_id}_static.nc  # Should be 3 files total for IW1, IW2, IW3. (What about EW?)
    """

    assert filename.exists()

    bucket_prefix = burst_id[:-4]  # Exclude swath

    try:
        upload_file_to_s3_with_publish_access_keys(filename, bucket, bucket_prefix)
    except Exception as e:
        print(f'Unable to upload {filename} to S3 due to {e}.')


def get_static_layers(burst_ids, bucket):
    has_static_layer = {}
    for burst_id in burst_ids:
        has_static_layer[burst_id] = get_static_layer(burst_id, bucket)
    return has_static_layer


def get_static_layer(burst_id, bucket):
    """
    Planned Directory Structure:

        static_topo_corrections/
          - | {burst_id}/
            - | {burst_id}_static.nc     (Retrived from S3)
            - | x.tif                    (Created from NetCDF)
            - | y.tif                    (Created from NetCDF)
            - | z.tif                    (Created from NetCDF)
            - | layover_shadow_mask.tif  (Created from NetCDF)
            - | radar_grid.txt           (Created from NetCDF)
    """

    static_file = retrieve_static_nc_from_s3(burst_id, bucket)

    if not static_file:  # Does not have static layer
        return False

    static_file = 'NETCDF:' + static_file

    STATIC_DIR.mkdir(exist_ok=True)
    burst_static_dir = STATIC_DIR / burst_id
    burst_static_dir.mkdir(exist_ok=True)

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


def create_static_layer(burst_id, isce_product_path='./product/*'):
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

    # Create with Float64 to allow storing all types safely
    driver = gdal.GetDriverByName('netCDF')
    options = ['FORMAT=NC4', 'COMPRESS=DEFLATE']
    out_ds = driver.Create(burst_topo_nc, cols, rows, len(topo_files), gdal.GDT_Float64, options)

    if out_ds is None:
        raise RuntimeError('Failed to create NetCDF file. Check that your GDAL has NetCDF-4 support.')

    out_ds.SetMetadata(rdr_grid)

    expected_types = [gdal.GDT_Float64, gdal.GDT_Float64, gdal.GDT_Float64, gdal.GDT_Byte]

    for i, (file, gdal_type) in enumerate(zip(topo_files, expected_types)):
        with gdal.Open(file) as in_ds:
            band_data = in_ds.GetRasterBand(1).ReadAsArray()

            if gdal_type == gdal.GDT_Byte:
                band_data = band_data.astype(np.float64)

            out_ds.GetRasterBand(i + 1).WriteArray(band_data)

    out_ds.FlushCache()
    return Path(burst_topo_nc)
