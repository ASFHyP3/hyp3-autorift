# MIT License
#
# Copyright (c) 2020 NASA Jet Propulsion Laboratory
# Modifications (c) Copyright 2023 Alaska Satellite Facility
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Crop HyP3 AutoRIFT products to their valid data range, inplace

This module is based on the ITS_LIVE production script for cropping V2 products
after they have been generated and has been heavily refactored for use in this HyP3 plugin:

The original script:
https://github.com/nasa-jpl/its_live_production/blob/957e9aba627be2abafcc9601712a7f9c4dd87849/src/tools/crop_v2_granules.py
"""

import argparse
from pathlib import Path

import numpy as np
import pyproj
import xarray as xr
from dateutil.parser import parse as parse_dt


ENCODING_ATTRS = ['_FillValue', 'dtype', 'zlib', 'complevel', 'shuffle', 'add_offset', 'scale_factor']
CHUNK_SIZE = 512
PIXEL_SIZE = 120


def get_aligned_min(val, grid_spacing):
    """Align a value with the nearest grid posting less than it"""
    nearest = np.floor(val / grid_spacing) * grid_spacing
    difference = val - nearest
    pixel_misalignment = difference % PIXEL_SIZE
    padding = difference - pixel_misalignment
    return val - padding, int(padding / 120)


def get_aligned_max(val, grid_spacing):
    """Align a value with the nearest grid posting greater than it"""
    nearest = np.ceil(val / grid_spacing) * grid_spacing
    difference = nearest - val
    pixel_misalignment = difference % PIXEL_SIZE
    padding = difference - pixel_misalignment
    return val + padding, int(padding / 120)


def get_alignment_info(
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
    grid_spacing: int = CHUNK_SIZE * PIXEL_SIZE,
):
    """Get the bounds and additional info necessary for chunk alignment

    Args:
        x_min: cropped minimum x coordinate
        y_min: cropped minimum y coordinate
        x_max: cropped maximum x coordinate
        y_max: cropped maximum y coordinate
        grid_spacing: width/height of the chunk in the units of the product's SRS

    Returns:
        1. aligned bounds
        2. padding in pixels required to align
        3. new range of x coordinates
        4. new range of y coordinates
    """
    x_min, left_pad = get_aligned_min(x_min, grid_spacing)
    y_min, bottom_pad = get_aligned_min(y_min, grid_spacing)
    x_max, right_pad = get_aligned_max(x_max, grid_spacing)
    y_max, top_pad = get_aligned_max(y_max, grid_spacing)

    aligned_bounds = [x_min, y_min, x_max, y_max]
    aligned_padding = [left_pad, bottom_pad, right_pad, top_pad]

    x_values = np.arange(x_min, x_max + PIXEL_SIZE, PIXEL_SIZE)
    y_values = np.arange(y_min, y_max + PIXEL_SIZE, PIXEL_SIZE)[::-1]
    return aligned_bounds, aligned_padding, x_values, y_values


def crop_netcdf_product(netcdf_file: Path) -> Path:
    """Crop the netCDF product to its valid extent and then pad it such that its
    chunks will be aligned spatially with other products in the same frame.

    Args:
        netcdf_file: Path to the netCDF file to crop and align

    Returns:
        The Path to the cropped netCDF file
    """
    with xr.open_dataset(netcdf_file, engine='h5netcdf') as ds:
        # this will drop X/Y coordinates, so drop non-None values just to get X/Y extends
        xy_ds = ds.where(ds.v.notnull()).dropna(dim='x', how='all').dropna(dim='y', how='all')

        x_values = xy_ds.x.values
        grid_x_min, grid_x_max = x_values.min(), x_values.max()

        y_values = xy_ds.y.values
        grid_y_min, grid_y_max = y_values.min(), y_values.max()

        # Based on X/Y extends, mask original dataset
        mask_lon = (ds.x >= grid_x_min) & (ds.x <= grid_x_max)
        mask_lat = (ds.y >= grid_y_min) & (ds.y <= grid_y_max)
        mask = mask_lon & mask_lat

        cropped_ds = ds.where(mask).dropna(dim='x', how='all').dropna(dim='y', how='all')
        cropped_ds = cropped_ds.load()

        projection = ds['mapping'].attrs['spatial_epsg']

        aligned_bounds, padding, x_values, y_values = get_alignment_info(grid_x_min, grid_y_min, grid_x_max, grid_y_max)

        grid_x_min, grid_y_min, grid_x_max, grid_y_max = aligned_bounds
        left_pad, bottom_pad, right_pad, top_pad = padding

        cropped_ds = cropped_ds.pad(x=(left_pad, right_pad), mode='constant', constant_values=-32767)
        cropped_ds = cropped_ds.pad(y=(top_pad, bottom_pad), mode='constant', constant_values=-32767)

        # Reset data for mapping and img_pair_info data variables as ds.where() extends data of all data variables
        # to the dimensions of the "mask"
        cropped_ds['img_pair_info'] = ds['img_pair_info']
        cropped_ds.drop_vars('mapping')

        if 'time' not in cropped_ds.coords:
            date_center = parse_dt(cropped_ds['img_pair_info'].date_center)
            cropped_ds = cropped_ds.assign_coords(time=date_center)
            cropped_ds = cropped_ds.expand_dims(dim='time', axis=0)
            cropped_ds['time'].attrs = {
                'standard_name': 'time_coordinate',
                'description': 'mid date of the image pair aquisition dates',
            }

        cropped_ds['mapping'] = ds['mapping']

        cropped_ds['x'] = x_values
        cropped_ds['y'] = y_values

        cropped_ds['x'].attrs = ds['x'].attrs
        cropped_ds['y'].attrs = ds['y'].attrs

        # Compute centroid longitude/latitude
        center_x = (grid_x_min + grid_x_max) / 2
        center_y = (grid_y_min + grid_y_max) / 2

        # Convert to lon/lat coordinates
        to_lon_lat_transformer = pyproj.Transformer.from_crs(f'EPSG:{projection}', 'EPSG:4326', always_xy=True)

        # Update centroid information for the granule
        center_lon_lat = to_lon_lat_transformer.transform(center_x, center_y)

        cropped_ds['img_pair_info'].attrs['latitude'] = round(center_lon_lat[1], 2)
        cropped_ds['img_pair_info'].attrs['longitude'] = round(center_lon_lat[0], 2)

        # Update mapping.GeoTransform
        x_cell = x_values[1] - x_values[0]
        y_cell = y_values[1] - y_values[0]

        # It was decided to keep all values in GeoTransform center-based
        cropped_ds['mapping'].attrs['GeoTransform'] = f'{x_values[0]} {x_cell} 0 {y_values[0]} 0 {y_cell}'

        dim_chunks_settings = (1, CHUNK_SIZE, CHUNK_SIZE)

        encoding = {}
        for variable in ds.data_vars.keys():
            if variable in ['img_pair_info', 'mapping']:
                continue
            attributes = {attr: ds[variable].encoding[attr] for attr in ENCODING_ATTRS if attr in ds[variable].encoding}
            encoding[variable] = attributes

        for _, attributes in encoding.items():
            if attributes['_FillValue'] is not None:
                attributes['chunksizes'] = dim_chunks_settings

        cropped_file = netcdf_file.with_stem(f'{netcdf_file.stem}_cropped')
        cropped_ds.to_netcdf(cropped_file, engine='h5netcdf', unlimited_dims=['time'], encoding=encoding)

    return cropped_file


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'netcdf_file',
        type=str,
        help='Path to the netCDF product to crop and align',
    )
    args = parser.parse_args()

    netcdf_file = Path(args.netcdf_file)

    if not netcdf_file.exists():
        print(f'{netcdf_file} does not exist.')

    cropped = crop_netcdf_product(netcdf_file)

    print(f'Saved the cropped and chunk-aligned product to {cropped}.')


if __name__ == '__main__':
    main()
