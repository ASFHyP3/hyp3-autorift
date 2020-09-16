# Turned off flake8 because we haven't refactored 3rd party provided functions
# flake8: noqa

import datetime

import netCDF4
import numpy as np


def netCDF_packaging(VX, VY, DX, DY, INTERPMASK, CHIPSIZEX, CHIPSIZEY, SSM, SX, SY,
                     offset2vx_1, offset2vx_2, offset2vy_1, offset2vy_2, MM, VXref, VYref,
                     rangePixelSize, azimuthPixelSize, dt, epsg, srs, tran, out_nc_filename, pair_type,
                     detection_method, coordinates, IMG_INFO_DICT, stable_count, stable_shift_applied,
                     dx_mean_shift, dy_mean_shift, error_vector):

    V = np.sqrt(VX**2+VY**2)

    NoDataValue = -32767
    noDataMask = np.isnan(VX) | np.isnan(VY)

    CHIPSIZEX = CHIPSIZEX * rangePixelSize
    CHIPSIZEY = CHIPSIZEY * azimuthPixelSize

    VX[noDataMask] = NoDataValue
    VY[noDataMask] = NoDataValue
    V[noDataMask] = NoDataValue
    CHIPSIZEX[noDataMask] = 0
    CHIPSIZEY[noDataMask] = 0
    INTERPMASK[noDataMask] = 0

    title = 'autoRIFT surface velocities'
    author = 'Alex S. Gardner, JPL/NASA; Yang Lei, GPS/Caltech'
    institution = 'NASA Jet Propulsion Laboratory (JPL), California Institute of Technology'

    VX = np.round(np.clip(VX, -32768, 32767)).astype(np.int16)
    VY = np.round(np.clip(VY, -32768, 32767)).astype(np.int16)
    V = np.round(np.clip(V, -32768, 32767)).astype(np.int16)
    CHIPSIZEX = np.round(np.clip(CHIPSIZEX, 0, 65535)).astype(np.uint16)
    CHIPSIZEY = np.round(np.clip(CHIPSIZEY, 0, 65535)).astype(np.uint16)
    INTERPMASK = np.round(np.clip(INTERPMASK, 0, 255)).astype(np.uint8)

    if pair_type is 'radar':
        VR = DX * rangePixelSize / dt * 365.0 * 24.0 * 3600.0
        VA = (-DY) * azimuthPixelSize / dt * 365.0 * 24.0 * 3600.0
        VR[noDataMask] = NoDataValue
        VA[noDataMask] = NoDataValue
        VR = np.round(np.clip(VR, -32768, 32767)).astype(np.int16)
        VA = np.round(np.clip(VA, -32768, 32767)).astype(np.int16)

    tran = [tran[0],tran[1],tran[3],tran[5]]

    clobber = True     # overwrite existing output nc file

    nc_outfile = netCDF4.Dataset(out_nc_filename,'w',clobber=clobber,format='NETCDF4')

    # First set global attributes that GDAL uses when it reads netCFDF files
    nc_outfile.setncattr('GDAL_AREA_OR_POINT','Area')
    nc_outfile.setncattr('Conventions','CF-1.6')
    nc_outfile.setncattr('date_created',datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S"))
    nc_outfile.setncattr('title',title)
    nc_outfile.setncattr('author',author)
    nc_outfile.setncattr('institution',institution)
    nc_outfile.setncattr('scene_pair_type',pair_type)
    nc_outfile.setncattr('motion_detection_method',detection_method)
    nc_outfile.setncattr('motion_coordinates',coordinates)

    varname='img_pair_info'
    datatype=np.dtype('S1')
    dimensions=()
    FillValue=None

    var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue)

    for key in IMG_INFO_DICT:
        var.setncattr(key,IMG_INFO_DICT[key])

    # set dimensions
    dimidY, dimidX = VX.shape
    nc_outfile.createDimension('x',dimidX)
    nc_outfile.createDimension('y',dimidY)
    x = np.arange(tran[0],tran[0]+tran[1]*(dimidX),tran[1])
    y = np.arange(tran[2],tran[2]+tran[3]*(dimidY),tran[3])
    chunk_lines = np.min([np.ceil(8192/dimidY)*128, dimidY])
    ChunkSize = [chunk_lines, dimidX]

    varname='x'
    datatype=np.dtype('float64')
    dimensions=('x')
    FillValue=None
    var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue)
    var.setncattr('standard_name','projection_x_coordinate')
    var.setncattr('long_name','x coordinate of projection')
    var.setncattr('units','m')
    var.setncattr('scene_pair_type',pair_type)
    var.setncattr('motion_detection_method',detection_method)
    var.setncattr('motion_coordinates',coordinates)
    var[:] = x

    varname='y'
    datatype=np.dtype('float64')
    dimensions=('y')
    FillValue=None
    var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue)
    var.setncattr('standard_name','projection_y_coordinate')
    var.setncattr('long_name','y coordinate of projection')
    var.setncattr('units','m')
    var.setncattr('scene_pair_type',pair_type)
    var.setncattr('motion_detection_method',detection_method)
    var.setncattr('motion_coordinates',coordinates)
    var[:] = y

    if (srs.GetAttrValue('PROJECTION') == 'Polar_Stereographic'):
        mapping_name='Polar_Stereographic'
        grid_mapping='polar_stereographic'  # need to set this as an attribute for the image variables
        datatype=np.dtype('S1')
        dimensions=()
        FillValue=None

        var = nc_outfile.createVariable(mapping_name,datatype,dimensions, fill_value=FillValue)
        # variable made, now add attributes

        var.setncattr('grid_mapping_name',grid_mapping)
        var.setncattr('straight_vertical_longitude_from_pole',srs.GetProjParm('central_meridian'))
        var.setncattr('false_easting',srs.GetProjParm('false_easting'))
        var.setncattr('false_northing',srs.GetProjParm('false_northing'))
        # could hardcode this to be -90 for landsat - just making it more general, maybe...
        var.setncattr('latitude_of_projection_origin',np.sign(srs.GetProjParm('latitude_of_origin'))*90.0)
        var.setncattr('latitude_of_origin',srs.GetProjParm('latitude_of_origin'))
        var.setncattr('semi_major_axis',float(srs.GetAttrValue('GEOGCS|SPHEROID',1)))
        var.setncattr('scale_factor_at_projection_origin',1)
        var.setncattr('inverse_flattening',float(srs.GetAttrValue('GEOGCS|SPHEROID',2)))
        var.setncattr('spatial_ref',srs.ExportToWkt())
        var.setncattr('spatial_proj4',srs.ExportToProj4())
        var.setncattr('spatial_epsg',epsg)
        # note this has pixel size in it - set  explicitly above
        var.setncattr('GeoTransform',' '.join(str(x) for x in tran))

    elif (srs.GetAttrValue('PROJECTION') == 'Transverse_Mercator'):

        mapping_name='UTM_projection'
        grid_mapping='universal_transverse_mercator'  # need to set this as an attribute for the image variables
        datatype=np.dtype('S1')
        dimensions=()
        FillValue=None

        var = nc_outfile.createVariable(mapping_name,datatype,dimensions, fill_value=FillValue)
        # variable made, now add attributes

        var.setncattr('grid_mapping_name',grid_mapping)
        zone = epsg - np.floor(epsg/100)*100
        var.setncattr('utm_zone_number',zone)
        var.setncattr('CoordinateTransformType','Projection')
        var.setncattr('CoordinateAxisTypes','GeoX GeoY')
        var.setncattr('semi_major_axis',float(srs.GetAttrValue('GEOGCS|SPHEROID',1)))
        var.setncattr('inverse_flattening',float(srs.GetAttrValue('GEOGCS|SPHEROID',2)))
        var.setncattr('spatial_ref',srs.ExportToWkt())
        var.setncattr('spatial_proj4',srs.ExportToProj4())
        var.setncattr('spatial_epsg',epsg)
        # note this has pixel size in it - set  explicitly above
        var.setncattr('GeoTransform',' '.join(str(x) for x in tran))
    else:
        raise Exception('Projection {0} not recognized for this program'.format(srs.GetAttrValue('PROJECTION')))

    varname='vx'
    datatype=np.dtype('int16')
    dimensions=('y','x')
    FillValue=NoDataValue
    var = nc_outfile.createVariable(varname,datatype,dimensions,
                                    fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)
    var.setncattr('grid_mapping',mapping_name)
    var.setncattr('standard_name','x_velocity')
    var.setncattr('units','m/y')
    var[:] = np.round(np.clip(VX, -32768, 32767)).astype(np.int16)
    var.setncattr('missing_value',np.int16(NoDataValue))

    varname='vy'
    datatype=np.dtype('int16')
    dimensions=('y','x')
    FillValue=NoDataValue
    var = nc_outfile.createVariable(varname,datatype,dimensions,
                                    fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)
    var.setncattr('grid_mapping',mapping_name)
    var.setncattr('standard_name','y_velocity')
    var.setncattr('units','m/y')
    var[:] = np.round(np.clip(VY, -32768, 32767)).astype(np.int16)
    var.setncattr('missing_value',np.int16(NoDataValue))

    varname='v'
    datatype=np.dtype('int16')
    dimensions=('y','x')
    FillValue=NoDataValue
    var = nc_outfile.createVariable(varname,datatype,dimensions,
                                    fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)
    var.setncattr('grid_mapping',mapping_name)
    var.setncattr('standard_name','velocity')
    var.setncattr('units','m/y')
    var[:] = np.round(np.clip(V, -32768, 32767)).astype(np.int16)
    var.setncattr('missing_value',np.int16(NoDataValue))

    if pair_type is 'radar':

        varname='vr'
        datatype=np.dtype('int16')
        dimensions=('y','x')
        FillValue=NoDataValue
        var = nc_outfile.createVariable(
            varname,datatype,dimensions,
            fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize
        )
        var.setncattr('grid_mapping',mapping_name)
        var.setncattr('standard_name','range_velocity')
        var.setncattr('units','m/y')
        var[:] = np.round(np.clip(VR, -32768, 32767)).astype(np.int16)
        var.setncattr('missing_value',np.int16(NoDataValue))

        varname='va'
        datatype=np.dtype('int16')
        dimensions=('y','x')
        FillValue=NoDataValue
        var = nc_outfile.createVariable(
            varname,datatype,dimensions,
            fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize
        )
        var.setncattr('grid_mapping',mapping_name)
        var.setncattr('standard_name','azimuth_velocity')
        var.setncattr('units','m/y')
        var[:] = np.round(np.clip(VA, -32768, 32767)).astype(np.int16)
        var.setncattr('missing_value',np.int16(NoDataValue))

    varname='chip_size_width'
    datatype=np.dtype('uint16')
    dimensions=('y','x')
    FillValue=0
    var = nc_outfile.createVariable(
        varname,datatype,dimensions,
        fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize
    )
    var.setncattr('grid_mapping',mapping_name)
    if pair_type is 'radar':
        var.setncattr('range_pixel_size',rangePixelSize)
        var.setncattr('chip_size_coordinates','radar geometry: width = range, height = azimuth')
    else:
        var.setncattr('x_pixel_size',rangePixelSize)
        var.setncattr('chip_size_coordinates','image projection geometry: width = x, height = y')
    var.setncattr('standard_name','chip_size_width')
    var.setncattr('units','m')
    var[:] = np.round(np.clip(CHIPSIZEX, 0, 65535)).astype('uint16')
    var.setncattr('missing_value',np.uint16(0))

    varname='chip_size_height'
    datatype=np.dtype('uint16')
    dimensions=('y','x')
    FillValue=0
    var = nc_outfile.createVariable(
        varname,datatype,dimensions,
        fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize
    )
    var.setncattr('grid_mapping',mapping_name)
    if pair_type is 'radar':
        var.setncattr('azimuth_pixel_size',azimuthPixelSize)
        var.setncattr('chip_size_coordinates','radar geometry: width = range, height = azimuth')
    else:
        var.setncattr('y_pixel_size',azimuthPixelSize)
        var.setncattr('chip_size_coordinates','image projection geometry: width = x, height = y')
    var.setncattr('standard_name','chip_size_height')
    var.setncattr('units','m')
    var[:] = np.round(np.clip(CHIPSIZEY, 0, 65535)).astype('uint16')
    var.setncattr('missing_value',np.uint16(0))

    varname='interp_mask'
    datatype=np.dtype('uint8')
    dimensions=('y','x')
    FillValue=None
    var = nc_outfile.createVariable(
        varname,datatype,dimensions,
        fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize
    )
    var.setncattr('grid_mapping',mapping_name)
    var.setncattr('standard_name','interpolated_value_mask')
    var.setncattr('units','binary')
    var[:] = np.round(np.clip(INTERPMASK, 0, 255)).astype('uint8')
    var.setncattr('missing_value',np.uint8(0))

    nc_outfile.sync()  # flush data to disk
    nc_outfile.close()
