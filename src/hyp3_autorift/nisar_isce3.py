"""
Prototyping the usage of NISAR data with autoRIFT
"""

import argparse
import copy
import time
from datetime import datetime
from pathlib import Path

import asf_search as asf
import cv2
import numpy as np
from hyp3lib.dem import prepare_dem_geotiff
from nisar.products.readers import product
from nisar.workflows import geo2rdr, rdr2geo, resample_slc
from numpy import datetime64, timedelta64
from osgeo import gdal, ogr, osr
from shapely import Polygon

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
    polarization: str = 'HH',
):
    """Get the runconfig for co-registering a NISAR RSLC pair using ISCE3."""
    config = {
        'input_file_group': {'reference_rslc_file': reference_path, 'secondary_rslc_file': secondary_path},
        'dynamic_ancillary_file_group': {
            'dem_file': dem_path,
            'orbit_files': {'reference_orbit_file': None, 'secondary_orbit_file': None},
        },
        'product_path_group': {'scratch_path': 'scratch'},
        'processing': {
            'rdr2geo': {
                'threshold': 1e-8,
                'numiter': 25,
                'extraiter': 10,
                'lines_per_block': 10000,
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
                'lines_per_block': 10000,
                'topo_path': 'scratch/',
                'maxiter': 10,
            },
            f'{resample_type}_resample': {
                'offsets_dir': 'scratch/',
                'lines_per_tile': 10000,
                'flatten': False,
            },
            'input_subset': {'list_of_frequencies': {frequency: [polarization]}},
        },
        'worker': {'internet_access': True, 'gpu_enabled': False, 'gpu_id': 0},
    }

    return config


def polygon_from_envelope(geom) -> ogr.Geometry:
    """Create a polygon from the given polygons envelope.

    Args:
        geom: An OGR geometry object
    """
    minx, maxx, miny, maxy = geom.GetEnvelope()

    ring = ogr.Geometry(ogr.wkbLinearRing)
    ring.AddPoint(minx, miny)
    ring.AddPoint(maxx, miny)
    ring.AddPoint(maxx, maxy)
    ring.AddPoint(minx, maxy)
    ring.AddPoint(minx, miny)  # close ring

    poly = ogr.Geometry(ogr.wkbPolygon)
    poly.AddGeometry(ring)

    return poly


def get_scene_polygon(
    reference_path: str,
    epsg_code: int = 4326,
    bounds_from_ds: bool = False,
    return_in_utm: bool = False,
    geom_from_envelope: bool = False,
) -> ogr.Geometry:
    """Get the bounding polygon for a NISAR product."""
    filename = f'NETCDF:{reference_path}://science/LSAR/GSLC/grids/frequencyA/HH'

    if bounds_from_ds:
        ds = gdal.Open(filename)
        xmin, ymin, xmax, ymax, _ = get_bounds(ds)
        poly = Polygon.from_bounds(xmin, ymin, xmax, ymax)
        epsg_code = get_epsg_code(ds)
        ds = None
    else:
        slc = product.open_product(reference_path)
        poly = slc.identification.boundingPolygon

    geom = ogr.CreateGeometryFromWkt(str(poly))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg_code)
    geom.AssignSpatialReference(srs)

    if bounds_from_ds and not return_in_utm:
        out_srs = osr.SpatialReference()
        out_srs.ImportFromEPSG(4326)
        out_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(srs, out_srs)
        geom.Transform(transform)

    if not bounds_from_ds and return_in_utm:
        ds = gdal.Open(filename)
        epsg_code = get_epsg_code(ds)
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        out_srs = osr.SpatialReference()
        out_srs.ImportFromEPSG(epsg_code)
        transform = osr.CoordinateTransformation(srs, out_srs)
        geom.Transform(transform)

    # The polygon provided by `slc.identification.boundingPolygon` can be fairly complicated,
    # so creating a more simple polygon from it's envelope may be helpful.
    if geom_from_envelope:
        geom = polygon_from_envelope(geom)

    return geom


def get_dem(scene_poly: ogr.Geometry, dem_path: str = 'dem.tif') -> str:
    """Download a DEM covering a given polygon."""
    return str(
        prepare_dem_geotiff(
            output_name=dem_path, geometry=scene_poly, epsg_code=4326, pixel_size=0.001, height_above_ellipsoid=True
        )
    )


def mock_s1_orbit_file(reference_path: str) -> str:
    """Create a mock Sentinel-1 Orbit file from the orbit info in a NISAR product."""
    orbit_path = Path(reference_path).with_suffix('.EOF')
    ds = product.open_product(reference_path)
    orbit = ds.getOrbit()
    count = len(orbit.position)
    ref_epoch = datetime64(orbit.reference_epoch, 'ns')

    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n',
        '<Earth_Explorer_File>\n',
        '\t<Data_Block type="xml">\n',
        f'\t\t<List_of_OSVs count="{count}">\n',
    ]

    for t, velocity, position in zip(orbit.time, orbit.velocity, orbit.position):
        utc_time = ref_epoch + timedelta64(int(t * 1e9), 'ns')
        lines.append('\t\t\t<OSV>\n')
        lines.append(f'\t\t\t\t<UTC>UTC={utc_time}</UTC>\n')
        lines.append(f'\t\t\t\t<X unit="m">{position[0]}</X>\n')
        lines.append(f'\t\t\t\t<Y unit="m">{position[1]}</Y>\n')
        lines.append(f'\t\t\t\t<Z unit="m">{position[2]}</Z>\n')
        lines.append(f'\t\t\t\t<VX unit="m/s">{velocity[0]}</VX>\n')
        lines.append(f'\t\t\t\t<VY unit="m/s">{velocity[1]}</VY>\n')
        lines.append(f'\t\t\t\t<VZ unit="m/s">{velocity[2]}</VZ>\n')
        lines.append('\t\t\t</OSV>\n')

    lines.extend(
        [
            '\t\t</List_of_OSVs>\n',
            '\t</Data_Block>\n',
            '</Earth_Explorer_File>\n',
        ]
    )

    with open(orbit_path, 'w') as orbit_file:
        orbit_file.writelines(lines)

    return str(orbit_path)


def get_epsg_code(ds):
    """Get the EPSG code from a gdal dataset."""
    wkt = ds.GetProjection()
    srs = osr.SpatialReference()
    srs.ImportFromWkt(wkt)
    srs.AutoIdentifyEPSG()
    return int(srs.GetAuthorityCode('PROJCS'))


def get_bounds(ds):
    """Get the bounding box info for a GeoTIFF."""
    gt = ds.GetGeoTransform()
    xsize = ds.RasterXSize
    ysize = ds.RasterYSize

    xmin = gt[0]
    ymax = gt[3]
    xmax = xmin + gt[1] * xsize
    ymin = ymax + gt[5] * ysize

    return xmin, ymin, xmax, ymax, gt


def srcwin_for_intersection(xmin, ymin, xmax, ymax, gt):
    """Create a srcwin from bounds and a geotransform."""
    px_w = gt[1]
    px_h = gt[5]

    xoff = int(round((xmin - gt[0]) / px_w))
    yoff = int(round((ymax - gt[3]) / px_h))

    xsize = int(round((xmax - xmin) / px_w))
    ysize = int(round((ymin - ymax) / px_h))

    return xoff, yoff, xsize, ysize


def crop_gslcs(reference, secondary):
    """Crop the reference and secondary GeoTIFFs to their overlap."""
    geom = get_scene_polygon(
        reference_path=reference, bounds_from_ds=False, return_in_utm=True, geom_from_envelope=True
    )

    reference = f'NETCDF:{reference}://science/LSAR/GSLC/grids/frequencyA/HH'
    secondary = f'NETCDF:{secondary}://science/LSAR/GSLC/grids/frequencyA/HH'

    ds1 = gdal.Open(reference)
    ds2 = gdal.Open(secondary)

    xmin, xmax, ymin, ymax = geom.GetEnvelope()

    _, _, _, _, gt1 = get_bounds(ds1)
    _, _, _, _, gt2 = get_bounds(ds2)

    xoff1, yoff1, xsize1, ysize1 = srcwin_for_intersection(xmin, ymin, xmax, ymax, gt1)
    xoff2, yoff2, xsize2, ysize2 = srcwin_for_intersection(xmin, ymin, xmax, ymax, gt2)

    out1 = 'reference_cropped.tif'
    out2 = 'secondary_cropped.tif'

    gdal.Translate(out1, ds1, srcWin=[xoff1, yoff1, xsize1, ysize1])
    gdal.Translate(out2, ds2, srcWin=[xoff2, yoff2, xsize2, ysize2])

    print('Cropped the reference and secondary images to their intersection.')

    return out1, out2


def convert_slc_to_uint8_amplitude(in_filename: str, out_filename: str, wallis_filter_width=21, is_gslc: bool = False):
    """Convert CFloat32 rslc image to uint8 amplitude data, and write it to a GeoTIFF file."""
    ds = gdal.Open(in_filename, gdal.GA_ReadOnly)
    gt = ds.GetGeoTransform(can_return_null=True)
    proj = ds.GetProjectionRef()

    band = ds.GetRasterBand(1)
    num_rows = band.YSize
    num_cols = band.XSize

    driver = gdal.GetDriverByName('GTIFF')
    out_ds = driver.Create(out_filename, xsize=num_cols, ysize=num_rows, bands=1, eType=gdal.GDT_Byte)
    out_band = out_ds.GetRasterBand(1)

    if is_gslc:
        out_ds.SetGeoTransform(gt)
        out_ds.SetProjection(proj)

    img = np.zeros((num_rows, num_cols), dtype=np.float32)

    block_size = 10000

    # Read SLC data progressively to avoid memory issues
    for row in range(0, num_rows, block_size):
        print(f'Reading Block {row / block_size}')

        start = time.time()
        if row + block_size > num_rows:
            block_size = num_rows - row

        encoded = band.ReadRaster(
            xoff=0,
            yoff=row,
            xsize=num_cols,
            ysize=block_size,
            buf_xsize=num_cols,
            buf_ysize=block_size,
            buf_type=gdal.GDT_CFloat32,
        )
        img[row : row + block_size] = (
            np.abs(np.frombuffer(encoded, np.complex64)).reshape((block_size, num_cols)).astype(np.float32)
        )
        end = time.time()
        print(f'Reading SLC Block took {end - start}s')

    print('Setting Invalid to 0')
    if is_gslc:
        img[np.isnan(img)] = 0
        img[np.isinf(img)] = 0
    valid_data = img != 0

    print('Preprocess with HPS Filter')
    kernel = -np.ones((wallis_filter_width, wallis_filter_width), dtype=np.float32)
    kernel[int((wallis_filter_width - 1) / 2), int((wallis_filter_width - 1) / 2)] = kernel.size - 1
    kernel = kernel / kernel.size
    img[:] = cv2.filter2D(img, -1, kernel, borderType=cv2.BORDER_CONSTANT)

    print('Scale Values')
    S1 = np.std(img[valid_data]) * np.sqrt(img[valid_data].size / (img[valid_data].size - 1.0))
    M1 = np.mean(img[valid_data])
    img -= M1 - 3 * S1
    img /= 6 * S1
    img *= 256
    del S1, M1
    np.clip(img, 0, 255, out=img)
    np.rint(img, out=img)
    img[:] = img.astype(np.uint8)

    print('Setting Invalid to 0')
    if is_gslc:
        img[np.isnan(img)] = 0
        img[np.isinf(img)] = 0
    img[~valid_data] = 0

    out_band.WriteArray(img)


def download_product(granule_name: str):
    """Download a NISAR product using asf_search."""
    res = asf.granule_search([granule_name])

    if len(res) == 0:
        raise ValueError(f'`asf_search` was unable to find {granule_name}')

    res.download(path='.')


def run_isce3(
    reference: str,
    secondary: str,
    dem: str,
    resample_type: str,
):
    """Use ISCE3 to co-register a NISAR RSLC pair."""
    run_cfg = get_config(reference_path=reference, secondary_path=secondary, dem_path=dem, resample_type=resample_type)

    print(f'ISCE3 Config: {run_cfg}')

    rdr2geo.run(run_cfg)
    geo2rdr.run(run_cfg)
    resample_slc.run(run_cfg, resample_type)


class GSLCMetadata:
    def __init__(self, filename, scene_name):
        self.filename = filename

        self.time = scene_name.split('_')[11]
        self.sensingStart = datetime.strptime(self.time, '%Y%m%dT%H%M%S')

        cycle = int(scene_name.split('_')[4])
        rel_orb = int(scene_name.split('_')[5])

        # TODO: Confirm this equation
        self.absoluteOrbitNumber = 618 + cycle * 173 + rel_orb
        self.orbitPassDirection = 'ASCENDING' if scene_name.split('_')[6] == 'A' else 'DESCENDING'

        ds = gdal.Open(filename)
        trans = ds.GetGeoTransform()

        self.XSize = trans[1]
        self.YSize = trans[5]

        self.numberOfLines = ds.RasterYSize
        self.numberOfSamples = ds.RasterXSize

        self.startingX = trans[0]
        self.startingY = trans[3]


def get_polarizations(filename: str, frequency: str = 'A'):
    """Retrieve the available polarizations for a NISAR product."""
    slc = product.open_product(filename)
    return slc.polarizations[frequency]


def process_nisar_rslc(
    reference: str,
    secondary: str,
    frequency: str = 'A',
    polarization: str = 'HH',
) -> str:
    """Run autoRIFT processing on a NISAR RSLC pair."""
    resample_type = 'coarse'

    print(f'Reference RSLC: {reference}')
    print(f'Secondary RSLC: {secondary}')
    print(f'Frequency: {frequency}')
    print(f'Polarization: {polarization}')
    print(f'Resample type: {resample_type}')

    scene_poly = get_scene_polygon(reference)
    dem_path = get_dem(scene_poly)

    print(f'Scene Polygon: {scene_poly}')
    print(f'DEM Path: {dem_path}')

    run_isce3(
        reference=reference,
        secondary=secondary,
        dem=dem_path,
        resample_type=resample_type,
    )

    print(f'Centroid: {scene_poly.Centroid()}')

    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file=DEFAULT_PARAMETER_FILE, flip_point=False)

    print(f'Paramenter Info: {parameter_info}')

    reference_data_path = f'HDF5:{reference}://science/LSAR/RSLC/swaths/frequency{frequency}/{polarization}'
    secondary_data_path = f'scratch/coarse_resample_slc/freq{frequency}/{polarization}/coregistered_secondary.slc'

    ref_amplitude_path = 'reference.tif'
    sec_amplitude_path = 'secondary.tif'

    paths = [(reference_data_path, ref_amplitude_path), (secondary_data_path, sec_amplitude_path)]
    for in_path, out_path in paths:
        print(f'Creating {out_path} from {in_path}')
        start_time = time.time()
        convert_slc_to_uint8_amplitude(in_path, out_path)
        end_time = time.time()
        print(f'Creating {out_path} took {end_time - start_time}s')

    orbit_path = mock_s1_orbit_file(reference)
    meta_r = loadMetadataRslc(reference, orbit_path=orbit_path)
    meta_temp = loadMetadataRslc(secondary)
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

    print('Finished Geogrid')

    # Geogrid seems to De-register Drivers
    gdal.AllRegister()

    netcdf_file = generateAutoriftProduct(
        ref_amplitude_path,
        sec_amplitude_path,
        nc_sensor='NISAR_RSLC',
        optical_flag=False,
        ncname=None,
        geogrid_run_info=geogrid_info,
        **parameter_info['autorift'],
        parameter_file=DEFAULT_PARAMETER_FILE.replace('/vsicurl/', ''),
    )

    return netcdf_file


def process_nisar_gslc(
    reference: str,
    secondary: str,
    frequency: str = 'A',
    polarization: str = 'HH',
) -> str:
    """Run autoRIFT processing on a NISAR GSLC pair."""
    print(f'Reference GSLC: {reference}')
    print(f'Secondary GSLC: {secondary}')
    print(f'Frequency: {frequency}')
    print(f'Polarization: {polarization}')

    scene_poly = get_scene_polygon(reference, geom_from_envelope=True)
    dem_path = get_dem(scene_poly)

    print(f'Scene Polygon: {scene_poly}')
    print(f'DEM Path: {dem_path}')

    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file=DEFAULT_PARAMETER_FILE, flip_point=False)

    print(f'Paramenter Info: {parameter_info}')

    ref_cropped, sec_cropped = crop_gslcs(reference, secondary)

    ref_amplitude = 'reference_adjusted.tif'
    sec_amplitude = 'secondary_adjusted.tif'

    paths = [(ref_cropped, ref_amplitude), (sec_cropped, sec_amplitude)]
    for in_path, out_path in paths:
        print(f'Creating {out_path} from {in_path}')
        start_time = time.time()
        convert_slc_to_uint8_amplitude(in_path, out_path, is_gslc=True)
        end_time = time.time()
        print(f'Creating {out_path} took {end_time - start_time}s')

    meta_r = GSLCMetadata(ref_amplitude, reference)
    meta_s = GSLCMetadata(sec_amplitude, secondary)

    geogrid_info = runGeogrid(
        info=meta_r,
        info1=meta_s,
        optical_flag=1,
        epsg=parameter_info['epsg'],
        **parameter_info['geogrid'],
    )

    print('Finished Geogrid')

    # Geogrid seems to De-register Drivers
    gdal.AllRegister()

    netcdf_file = generateAutoriftProduct(
        ref_amplitude,
        sec_amplitude,
        nc_sensor='NISAR_GSLC',
        optical_flag=1,
        ncname=None,
        geogrid_run_info=geogrid_info,
        **parameter_info['autorift'],
        parameter_file=DEFAULT_PARAMETER_FILE.replace('/vsicurl/', ''),
    )

    return netcdf_file


def process_nisar_pair(
    reference: str,
    secondary: str,
    frequency: str = 'A',
) -> str:
    """Run autoRIFT processing on a NISAR SLC pair."""
    download_product(reference)
    download_product(secondary)

    reference += '.h5'
    secondary += '.h5'

    ref_pols = get_polarizations(reference, frequency)

    if 'HH' in ref_pols:
        polarization = 'HH'
    else:
        polarization = 'VV'

    assert polarization in get_polarizations(secondary, frequency)

    if 'RSLC' in reference:
        netcdf_file = process_nisar_rslc(
            reference=reference,
            secondary=secondary,
            frequency=frequency,
            polarization=polarization,
        )
    elif 'GSLC' in reference:
        netcdf_file = process_nisar_gslc(
            reference=reference,
            secondary=secondary,
            frequency=frequency,
            polarization=polarization,
        )
    else:
        raise ValueError(f'Only RSLC and GSLC NISAR products are supported: {reference}')

    return netcdf_file


def main():
    """CLI entrypoint for autoRIFT processing on a NISAR SLC pair."""
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--reference',
        type=str,
        help='List of reference Sentinel-1, Sentinel-1 Burst, Sentinel-2, or Landsat-8 Collection 2 granules (scenes) '
        'to process. Cannot be used with the `granules` arguments.',
    )
    parser.add_argument(
        '--secondary',
        type=str,
        help='List of secondary Sentinel-1, Sentinel-1 Burst, Sentinel-2, or Landsat-8 Collection 2 granules (scenes) '
        'to process. Cannot be used with the `granules` arguments.',
    )
    args = parser.parse_args()

    reference = args.reference
    secondary = args.secondary

    process_nisar_pair(reference, secondary)


if __name__ == '__main__':
    main()
