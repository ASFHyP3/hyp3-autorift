"""
Prototyping the usage of NISAR data with autoRIFT
"""

import argparse

from hyp3lib.dem import prepare_dem_geotiff
from nisar.workflows import geo2rdr, rdr2geo, resample_slc, stage_dem
from osgeo import osr, ogr

from hyp3_autorift import geometry, utils
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE
from hyp3_autorift.vend.testGeogrid import getPol, loadMetadata, loadMetadataSlc, runGeogrid
from hyp3_autorift.vend.testautoRIFT import generateAutoriftProduct


# NOTE: There doesn't seem to be a YAML schema that works for these processes,
# but we can just generate this dict and pass it directly to the workflows.
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
        pixel_size=0.0001,
    ))


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
    frequency = args.frequency
    polarization = args.polarization
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

    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file=DEFAULT_PARAMETER_FILE)

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

    # TODO:
    # meta_r = loadMetadataRslc(reference_path)
    # meta_temp = loadMetadataRslc(secondary_path)
    # meta_s = copy.copy(meta_r)
    # meta_s.sensingStart = meta_temp.sensingStart
    # meta_s.sensingStop = meta_temp.sensingStop

if __name__ == '__main__':
    main()
