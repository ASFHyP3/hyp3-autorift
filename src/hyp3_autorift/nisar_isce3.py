"""
Prototyping the usage of NISAR data with autoRIFT
"""

import argparse
import copy
import subprocess
from pathlib import Path

import cv2
import numpy as np

from hyp3lib.dem import prepare_dem_geotiff
from nisar.workflows import geo2rdr, rdr2geo, resample_slc, stage_dem
from nisar.products.readers import product
from numpy import datetime64, timedelta64
from osgeo import osr, ogr, gdal

from hyp3_autorift import utils
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE
from hyp3_autorift.vend.testGeogrid import loadMetadataRslc, runGeogrid
from hyp3_autorift.vend.testautoRIFT import generateAutoriftProduct


def get_config(
    reference_path: str,
    secondary_path: str,
    dem_path: str = 'dem.tif',
    resample_type: str = 'coarse',
    frequency: str = 'A',
    polarization: str = 'HH'
):
    return {
        'input_file_group': {
            'reference_rslc_file': reference_path,
            'secondary_rslc_file': secondary_path
        },
        'dynamic_ancillary_file_group': {
            'dem_file': dem_path,
            'orbit_files': {
                'reference_orbit_file': None,
                'secondary_orbit_file': None
            }
        },
        'product_path_group': {
            'scratch_path': 'scratch'
        },
        'processing': {
            'rdr2geo': {
                'threshold': 1e-8,
                'numiter': 25,
                'extraiter': 10,
                'lines_per_block': 1000,
                'write_x': True,
                'write_y': True,
                'write_z': True,
                'write_incidence': False,
                'write_heading': False,
                'write_local_incidence': False,
                'write_local_psi': False,
                'write_simulated_amplitude': False,
                'write_layover_shadow': False,
            },
            'geo2rdr': {
                'threshold': 1e-8,
                'numiter': 25,
                'extraiter': 10,
                'lines_per_block': 1000,
                'topo_path': 'scratch/',
                'maxiter': 10,
            },
            f'{resample_type}_resample': {
                'offsets_dir': 'scratch/',
                'lines_per_tile': 1000,
                'flatten': False,
            },
            'input_subset': {
                'list_of_frequencies': {
                    frequency: [polarization]
                }
            }
        },
        'worker': {
            'internet_access': True,
            'gpu_enabled': False,
            'gpu_id': 0
        }
    }


def get_scene_polygon(reference_path: str, epsg_code: int = 4326) -> ogr.Geometry:
    poly = stage_dem.determine_polygon(reference_path)
    poly = stage_dem.apply_margin_polygon(poly)
    geom = ogr.CreateGeometryFromWkt(str(poly))

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg_code)
    geom.AssignSpatialReference(srs)

    return geom


def get_dem(scene_poly: ogr.Geometry, dem_path: str = 'dem.tif') -> str:
    return str(prepare_dem_geotiff(
        output_name=dem_path,
        geometry=scene_poly,
        epsg_code=4326,
        pixel_size=0.001,
    ))


def mock_s1_orbit_file(reference_path: str) -> str:
    orbit_path = Path(reference_path).with_suffix('.EOF')
    ds = product.open_product(reference_path)
    orbit = ds.getOrbit()
    count = len(orbit.position)
    ref_epoch = datetime64(orbit.reference_epoch, 'ns')

    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n',
        '<Earth_Explorer_File>\n',
        '\t<Data_Block type="xml">\n',
        f'\t\t<List_of_OSVs count="{count}">\n'
    ]

    for time, velocity, position in zip(orbit.time, orbit.velocity, orbit.position):
        utc_time = ref_epoch + timedelta64(int(time * 1e9), 'ns')
        lines.append('\t\t\t<OSV>\n')
        lines.append(f'\t\t\t\t<UTC>UTC={utc_time}</UTC>\n')
        lines.append(f'\t\t\t\t<X unit="m">{position[0]}</X>\n')
        lines.append(f'\t\t\t\t<Y unit="m">{position[1]}</Y>\n')
        lines.append(f'\t\t\t\t<Z unit="m">{position[2]}</Z>\n')
        lines.append(f'\t\t\t\t<VX unit="m/s">{velocity[0]}</VX>\n')
        lines.append(f'\t\t\t\t<VY unit="m/s">{velocity[1]}</VY>\n')
        lines.append(f'\t\t\t\t<VZ unit="m/s">{velocity[2]}</VZ>\n')
        lines.append('\t\t\t</OSV>\n')

    lines.extend([
        f'\t\t</List_of_OSVs>\n',
        '\t</Data_Block>\n',
        '</Earth_Explorer_File>\n',
    ])

    with open(orbit_path, 'w') as orbit_file:
        orbit_file.writelines(lines)

    return str(orbit_path)


def create_amplitude_geotiffs(
    reference_h5_path: str,
    secondary_isce3_path: str,
    reference_out_path: str = 'reference.tif',
    secondary_out_path: str = 'secondary.tif'
) -> None: 
    paths = [(reference_h5_path, reference_out_path), (secondary_isce3_path, secondary_out_path)]

    for in_path, out_path in paths:
        # This must be used, as opposed to the Python bindings (gdal.Open + np.abs), as the 
        # images get read in as Python's 128 bit complex datatype (even when using .astype(np.complex64)) 
        # which requires >64GB memory usage.
        cmd = [
            'gdal_translate',
            '-of',
            'GTIFF',
            f'DERIVED_SUBDATASET:AMPLITUDE:{in_path}',
            f'{out_path}'
        ]
        subprocess.call(" ".join(cmd), shell=True)

        convert_amplitude_to_uint8(out_path)


def convert_amplitude_to_uint8(filename, wallis_filter_width=21):
    ds = gdal.Open(filename, gdal.GA_ReadOnly)
    band = ds.GetRasterBand(1)
    img = band.ReadAsArray().astype(np.float32)
    del band, ds

    valid_data = img != 0

    # Preprocess with HPS Filter
    kernel = -np.ones((wallis_filter_width, wallis_filter_width), dtype=np.float32)
    kernel[int((wallis_filter_width - 1) / 2), int((wallis_filter_width - 1) / 2)] = kernel.size - 1
    kernel = kernel / kernel.size
    img[:] = cv2.filter2D(img, -1, kernel, borderType=cv2.BORDER_CONSTANT)

    # Scale values to [0, 255]
    S1 = np.std(img[valid_data]) * np.sqrt(img[valid_data].size / (img[valid_data].size - 1.0))
    M1 = np.mean(img[valid_data])
    img[:] = (img - (M1 - 3 * S1)) / (6 * S1) * (2**8 - 0)
    del S1, M1
    img[:] = np.round(np.clip(img, 0, 255)).astype(np.uint8)

    img[~valid_data] = 0

    driver = gdal.GetDriverByName('GTIFF')
    ds = driver.Create(filename, xsize=img.shape[1], ysize=img.shape[0], bands=1, eType=gdal.GDT_Byte)
    ds.GetRasterBand(1).WriteArray(img)


# TODO: This main function should be replaced with an interface for `process.py`.
def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('reference', help='Path to reference RSLC')
    parser.add_argument('secondary', help='Path to secondary RSLC')
    # TODO: Will A and B be the values in the final products?
    parser.add_argument('--frequency', default='A', help='Desired frequency band to process - A or B')
    # TODO: What will the possible pol codes be in the final products?
    parser.add_argument('--polarization', default='HH', help='Desired polarization - HH or VV')
    args = parser.parse_args()

    reference_path=args.reference
    secondary_path=args.secondary
    frequency = args.frequency.upper()
    polarization = args.polarization.upper()
    resample_type = 'coarse'

    print(f'Reference RSLC: {reference_path}')
    print(f'Secondary RSLC: {secondary_path}')
    print(f'Frequency: {frequency}')
    print(f'Polarization: {polarization}')
    print(f'Resample type: {resample_type}')

    scene_poly = get_scene_polygon(reference_path)
    dem_path = get_dem(scene_poly)

    print(f'Scene Polygon: {scene_poly}')
    print(f'DEM Path: {dem_path}')

    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file=DEFAULT_PARAMETER_FILE, flip_point=False)

    print(f'Paramenter Info: {parameter_info}')

    run_cfg = get_config(
        reference_path=reference_path,
        secondary_path=secondary_path,
        dem_path=dem_path,
        resample_type=resample_type
    )

    print(f'ISCE3 Config: {run_cfg}')

    rdr2geo.run(run_cfg)
    geo2rdr.run(run_cfg)
    resample_slc.run(run_cfg, resample_type)

    reference_data_path = f'HDF5:{reference_path}://science/LSAR/RSLC/swaths/frequency{frequency}/{polarization}'
    secondary_isce3_path = f'scratch/coarse_resample_slc/freq{frequency}/{polarization}/coregistered_secondary.slc'

    create_amplitude_geotiffs(reference_data_path, secondary_isce3_path)
    orbit_path = mock_s1_orbit_file(reference_path)

    meta_r = loadMetadataRslc(reference_path, orbit_path=orbit_path)
    meta_temp = loadMetadataRslc(secondary_path)
    meta_s = copy.copy(meta_r)
    meta_s.sensingStart = meta_temp.sensingStart
    meta_s.sensingStop = meta_temp.sensingStop

    geogrid_info = runGeogrid(
        info=meta_r,
        info1=meta_s,
        optical_flag=0,
        epsg=parameter_info['epsg'],
        **parameter_info['geogrid'],
    )

    # Geogrid seems to De-register Drivers
    gdal.AllRegister()

    netcdf_file = generateAutoriftProduct(
        'reference.tif',
        'secondary.tif',
        nc_sensor='NISAR',
        optical_flag=False,
        ncname=None,
        geogrid_run_info=geogrid_info,
        **parameter_info['autorift'],
        parameter_file=DEFAULT_PARAMETER_FILE.replace('/vsicurl/', ''),
    )

    return netcdf_file


if __name__ == '__main__':
    main()
