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

from pathlib import Path

import numpy as np
import pyproj
import xarray as xr


ENCODING_TEMPLATE = {
        'interp_mask':      {'_FillValue': 0.0, 'dtype': 'ubyte', "zlib": True, "complevel": 2, "shuffle": True},
        'chip_size_height': {'_FillValue': 0.0, 'dtype': 'ushort', "zlib": True, "complevel": 2, "shuffle": True},
        'chip_size_width':  {'_FillValue': 0.0, 'dtype': 'ushort', "zlib": True, "complevel": 2, "shuffle": True},
        'M11': {'_FillValue': -32767, 'dtype': 'short', "zlib": True, "complevel": 2, "shuffle": True},
        'M12': {'_FillValue': -32767, 'dtype': 'short', "zlib": True, "complevel": 2, "shuffle": True},
        'v':                {'_FillValue': -32767.0, 'dtype': 'short', "zlib": True, "complevel": 2, "shuffle": True},
        'vx':               {'_FillValue': -32767.0, 'dtype': 'short', "zlib": True, "complevel": 2, "shuffle": True},
        'vy':               {'_FillValue': -32767.0, 'dtype': 'short', "zlib": True, "complevel": 2, "shuffle": True},
        'v_error': {'_FillValue': -32767.0, 'dtype': 'short', "zlib": True, "complevel": 2, "shuffle": True},
        'va': {'_FillValue': -32767.0, 'dtype': 'short', "zlib": True, "complevel": 2, "shuffle": True},
        'vr': {'_FillValue': -32767.0, 'dtype': 'short', "zlib": True, "complevel": 2, "shuffle": True},
        'x':                {'_FillValue': None},
        'y':                {'_FillValue': None}
    }


def crop_netcdf_product(netcdf_file: Path):
    with xr.open_dataset(netcdf_file) as ds:
        # this will drop X/Y coordinates, so drop non-None values just to get X/Y extends
        xy_ds = ds.where(ds.v.notnull(), drop=True)

        x_values = xy_ds.x.values
        grid_x_min, grid_x_max = x_values.min(), x_values.max()

        y_values = xy_ds.y.values
        grid_y_min, grid_y_max = y_values.min(), y_values.max()

        # Based on X/Y extends, mask original dataset
        mask_lon = (ds.x >= grid_x_min) & (ds.x <= grid_x_max)
        mask_lat = (ds.y >= grid_y_min) & (ds.y <= grid_y_max)
        mask = (mask_lon & mask_lat)

        cropped_ds = ds.where(mask, drop=True)
        cropped_ds = cropped_ds.load()

        # Reset data for grid_mapping and img_pair_info data variables as ds.where() extends data of all data variables
        # to the dimensions of the "mask"
        cropped_ds['grid_mapping'] = ds['grid_mapping']
        cropped_ds['img_pair_info'] = ds['img_pair_info']

        # Compute centroid longitude/latitude
        center_x = (grid_x_min + grid_x_max) / 2
        center_y = (grid_y_min + grid_y_max) / 2

        # Convert to lon/lat coordinates
        projection = ds['mapping'].attrs['spatial_epsg']
        to_lon_lat_transformer = pyproj.Transformer.from_crs(
            f"EPSG:{projection}",
            'EPSG:4326',
            always_xy=True
        )

        # Update centroid information for the granule
        center_lon_lat = to_lon_lat_transformer.transform(center_x, center_y)

        cropped_ds['mapping'].attrs['latitude'] = round(center_lon_lat[1], 2)
        cropped_ds['img_pair_info'].attrs['longitude'] = round(center_lon_lat[0], 2)

        # Update mapping.GeoTransform
        x_cell = x_values[1] - x_values[0]
        y_cell = y_values[1] - y_values[0]

        # It was decided to keep all values in GeoTransform center-based
        cropped_ds['mapping'].attrs['GeoTransform'] = f"{x_values[0]} {x_cell} 0 {y_values[0]} 0 {y_cell}"

        # Compute chunking like AutoRIFT does:
        # https://github.com/ASFHyP3/hyp3-autorift/blob/develop/hyp3_autorift/vend/netcdf_output.py#L410-L411
        dims = cropped_ds.dims
        chunk_lines = np.min([np.ceil(8192 / dims['y']) * 128, dims['y']])
        two_dim_chunks_settings = (chunk_lines, dims['x'])

        encoding = ENCODING_TEMPLATE.copy()
        for _, attributes in encoding.items():
            if attributes['_FillValue'] is not None:
                attributes['chunksizes'] = two_dim_chunks_settings

    cropped_ds.to_netcdf(netcdf_file, engine='h5netcdf', encoding=encoding)
