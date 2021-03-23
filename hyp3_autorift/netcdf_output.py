# Turned off flake8 because we haven't refactored 3rd party provided functions
# flake8: noqa

import datetime
import subprocess

import netCDF4
import numpy as np

import hyp3_autorift


def v_error_cal(vx_error, vy_error):
    vx = np.random.normal(0, vx_error, 1000000)
    vy = np.random.normal(0, vy_error, 1000000)
    v = np.sqrt(vx**2 + vy**2)
    return np.std(v)


def netCDF_packaging(VX, VY, DX, DY, INTERPMASK, CHIPSIZEX, CHIPSIZEY, SSM, SX, SY,
                     offset2vx_1, offset2vx_2, offset2vy_1, offset2vy_2, MM, VXref, VYref,
                     rangePixelSize, azimuthPixelSize, dt, epsg, srs, tran, out_nc_filename, pair_type,
                     detection_method, coordinates, IMG_INFO_DICT, stable_count, stable_shift_applied,
                     dx_mean_shift, dy_mean_shift, error_vector):
    if stable_shift_applied == 1:
        vx_mean_shift = offset2vx_1 * dx_mean_shift + offset2vx_2 * dy_mean_shift
        temp = vx_mean_shift
        temp[np.logical_not(SSM)] = np.nan
        vx_mean_shift = np.median(temp[np.logical_not(np.isnan(temp))])
        vy_mean_shift = offset2vy_1 * dx_mean_shift + offset2vy_2 * dy_mean_shift
        temp = vy_mean_shift
        temp[np.logical_not(SSM)] = np.nan
        vy_mean_shift = np.median(temp[np.logical_not(np.isnan(temp))])
    else:
        vx_mean_shift = 0.0
        vy_mean_shift = 0.0

    V = np.sqrt(VX ** 2 + VY ** 2)

    if pair_type is 'radar':
        VR = DX * rangePixelSize / dt * 365.0 * 24.0 * 3600.0
        VA = (-DY) * azimuthPixelSize / dt * 365.0 * 24.0 * 3600.0
        VR = VR.astype(np.float32)
        VA = VA.astype(np.float32)

        if stable_shift_applied == 1:
            vr_mean_shift = dx_mean_shift * rangePixelSize / dt * 365.0 * 24.0 * 3600.0
            va_mean_shift = (-dy_mean_shift) * azimuthPixelSize / dt * 365.0 * 24.0 * 3600.0
        else:
            vr_mean_shift = 0.0
            va_mean_shift = 0.0

        # create the (slope parallel & reference) flow-based range-projected result
        alpha_sp = DX / (offset2vy_2 / (offset2vx_1 * offset2vy_2 - offset2vx_2 * offset2vy_1) * (-SX) - offset2vx_2 / (
                    offset2vx_1 * offset2vy_2 - offset2vx_2 * offset2vy_1) * (-SY))
        alpha_ref = DX / (
                    offset2vy_2 / (offset2vx_1 * offset2vy_2 - offset2vx_2 * offset2vy_1) * VXref - offset2vx_2 / (
                        offset2vx_1 * offset2vy_2 - offset2vx_2 * offset2vy_1) * VYref)
        VXS = alpha_sp * (-SX)
        VYS = alpha_sp * (-SY)
        VXR = alpha_ref * VXref
        VYR = alpha_ref * VYref

        zero_flag_sp = (SX == 0) & (SY == 0)
        zero_flag_ref = (VXref == 0) & (VYref == 0)
        VXS[zero_flag_sp] = np.nan
        VYS[zero_flag_sp] = np.nan
        VXR[zero_flag_ref] = np.nan
        VYR[zero_flag_ref] = np.nan

        rngX = offset2vx_1
        rngY = offset2vy_1
        angle_df_S = np.arccos((-SX * rngX - SY * rngY) / (np.sqrt(SX ** 2 + SY ** 2) * np.sqrt(rngX ** 2 + rngY ** 2)))
        angle_df_S = np.abs(np.real(angle_df_S) - np.pi / 2)
        angle_df_R = np.arccos(
            (VXref * rngX + VYref * rngY) / (np.sqrt(VXref ** 2 + VYref ** 2) * np.sqrt(rngX ** 2 + rngY ** 2)))
        angle_df_R = np.abs(np.real(angle_df_R) - np.pi / 2)

        angle_threshold_S = 0.75
        angle_threshold_R = 0.75

        VXS[angle_df_S < angle_threshold_S] = np.nan
        VYS[angle_df_S < angle_threshold_S] = np.nan
        VXR[angle_df_R < angle_threshold_R] = np.nan
        VYR[angle_df_R < angle_threshold_R] = np.nan

        VXP = VXS
        VXP[MM == 1] = VXR[MM == 1]
        VYP = VYS
        VYP[MM == 1] = VYR[MM == 1]

        VXP = VXP.astype(np.float32)
        VYP = VYP.astype(np.float32)
        VP = np.sqrt(VXP ** 2 + VYP ** 2)

        VXPP = VX.copy()
        VYPP = VY.copy()

        stable_count_p = np.sum(SSM & np.logical_not(np.isnan(VXP)))

        if stable_count_p == 0:
            stable_shift_applied_p = 0
        else:
            stable_shift_applied_p = 1

        if stable_shift_applied_p == 1:
            temp = VXP.copy() - VX.copy()
            temp[np.logical_not(SSM)] = np.nan
            bias_mean_shift = np.median(temp[(temp > -500) & (temp < 500)])
            vxp_mean_shift = vx_mean_shift + bias_mean_shift / 2

            temp = VYP.copy() - VY.copy()
            temp[np.logical_not(SSM)] = np.nan
            bias_mean_shift = np.median(temp[(temp > -500) & (temp < 500)])
            vyp_mean_shift = vy_mean_shift + bias_mean_shift / 2
        else:
            vxp_mean_shift = 0.0
            vyp_mean_shift = 0.0

    CHIPSIZEX = CHIPSIZEX * rangePixelSize
    CHIPSIZEY = CHIPSIZEY * azimuthPixelSize

    NoDataValue = -32767
    noDataMask = np.isnan(VX) | np.isnan(VY)

    CHIPSIZEX[noDataMask] = 0
    CHIPSIZEY[noDataMask] = 0
    INTERPMASK[noDataMask] = 0

    title = 'autoRIFT surface velocities'
    author = 'Alex S. Gardner, JPL/NASA; Yang Lei, GPS/Caltech'
    institution = 'NASA Jet Propulsion Laboratory (JPL), California Institute of Technology'

    isce_version = subprocess.check_output('conda list | grep isce | awk \'{print $2}\'', shell=True, text=True)
    source = f'ASF DAAC HyP3 {datetime.datetime.now().year} using the {hyp3_autorift.__name__} plugin version ' \
             f'{hyp3_autorift.__version__} running autoRIFT version {IMG_INFO_DICT["autoRIFT_software_version"]} as ' \
             f'distributed with ISCE version {isce_version.strip()}. Contains modified Copernicus Sentinel data ' \
             f'{IMG_INFO_DICT["date_center"][0:4]}, processed by ESA.'
    references = 'When using this data, please acknowledge the source (see global source attribute), and cite:\n' \
                 '* Gardner, A. S., Moholdt, G., Scambos, T., Fahnstock, M., Ligtenberg, S., van den Broeke, M.,\n' \
                 '  and Nilsson, J., 2018. Increased West Antarctic and unchanged East Antarctic ice discharge over\n' \
                 '  the last 7 years. The Cryosphere, 12, p.521. https://doi.org/10.5194/tc-12-521-2018\n' \
                 '* Lei, Y., Gardner, A. and Agram, P., 2021. Autonomous Repeat Image Feature Tracking (autoRIFT)\n' \
                 '  and Its Application for Tracking Ice Displacement. Remote Sensing, 13(4), p.749.\n' \
                 '  https://doi.org/10.3390/rs13040749\n' \
                 '\n' \
                 'Additionally, DOI\'s are provided for the software used to generate this data:\n' \
                 '* HyP3 processing environment: https://doi.org/10.5281/zenodo.3962581\n' \
                 '* HyP3 autoRIFT plugin: https://doi.org/10.5281/zenodo.4037016\n' \
                 '* autoRIFT: https://doi.org/10.5281/zenodo.4025445'
    tran = [tran[0] + tran[1]/2, tran[1], 0.0, tran[3] + tran[5]/2, 0.0, tran[5]]

    clobber = True  # overwrite existing output nc file

    nc_outfile = netCDF4.Dataset(out_nc_filename, 'w', clobber=clobber, format='NETCDF4')

    # First set global attributes that GDAL uses when it reads netCFDF files
    nc_outfile.setncattr('GDAL_AREA_OR_POINT', 'Area')
    nc_outfile.setncattr('Conventions', 'CF-1.6')
    nc_outfile.setncattr('date_created', datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S"))
    nc_outfile.setncattr('title', title)
    nc_outfile.setncattr('autoRIFT_software_version', IMG_INFO_DICT["autoRIFT_software_version"])
    nc_outfile.setncattr('scene_pair_type', pair_type)
    nc_outfile.setncattr('motion_detection_method', detection_method)
    nc_outfile.setncattr('motion_coordinates', coordinates)
    nc_outfile.setncattr('author', author)
    nc_outfile.setncattr('institution', institution)
    nc_outfile.setncattr('source', source)
    nc_outfile.setncattr('references', references)

    varname = 'img_pair_info'
    datatype = np.dtype('S1')
    dimensions = ()
    FillValue = None

    var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue)

    for key in IMG_INFO_DICT:
        if key == 'autoRIFT_software_version':
            continue
        var.setncattr(key, IMG_INFO_DICT[key])

    # set dimensions
    dimidY, dimidX = VX.shape
    nc_outfile.createDimension('x', dimidX)
    nc_outfile.createDimension('y', dimidY)
    x = np.arange(tran[0], tran[0] + tran[1] * (dimidX), tran[1])
    y = np.arange(tran[3], tran[3] + tran[5] * (dimidY), tran[5])
    chunk_lines = np.min([np.ceil(8192 / dimidY) * 128, dimidY])
    ChunkSize = [chunk_lines, dimidX]

    varname = 'x'
    datatype = np.dtype('float64')
    dimensions = ('x')
    FillValue = None
    var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue)
    var.setncattr('standard_name', 'projection_x_coordinate')
    var.setncattr('description', 'x coordinate of projection')
    var.setncattr('units', 'm')
    var[:] = x

    varname = 'y'
    datatype = np.dtype('float64')
    dimensions = ('y')
    FillValue = None
    var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue)
    var.setncattr('standard_name', 'projection_y_coordinate')
    var.setncattr('description', 'y coordinate of projection')
    var.setncattr('units', 'm')
    var[:] = y

    if (srs.GetAttrValue('PROJECTION') == 'Polar_Stereographic'):

        mapping_name = 'Polar_Stereographic'
        grid_mapping = 'polar_stereographic'  # need to set this as an attribute for the image variables
        datatype = np.dtype('S1')
        dimensions = ()
        FillValue = None

        var = nc_outfile.createVariable(mapping_name, datatype, dimensions, fill_value=FillValue)
        # variable made, now add attributes

        var.setncattr('grid_mapping_name', grid_mapping)
        var.setncattr('straight_vertical_longitude_from_pole', srs.GetProjParm('central_meridian'))
        var.setncattr('false_easting', srs.GetProjParm('false_easting'))
        var.setncattr('false_northing', srs.GetProjParm('false_northing'))
        var.setncattr('latitude_of_projection_origin', np.sign(srs.GetProjParm(
            'latitude_of_origin')) * 90.0)  # could hardcode this to be -90 for landsat - just making it more general, maybe...
        var.setncattr('latitude_of_origin', srs.GetProjParm('latitude_of_origin'))
        var.setncattr('semi_major_axis', float(srs.GetAttrValue('GEOGCS|SPHEROID', 1)))
        var.setncattr('scale_factor_at_projection_origin', 1)
        var.setncattr('inverse_flattening', float(srs.GetAttrValue('GEOGCS|SPHEROID', 2)))
        var.setncattr('spatial_ref', srs.ExportToWkt())
        var.setncattr('spatial_proj4', srs.ExportToProj4())
        var.setncattr('spatial_epsg', epsg)
        var.setncattr('GeoTransform',
                      ' '.join(str(x) for x in tran))  # note this has pixel size in it - set  explicitly above

    elif (srs.GetAttrValue('PROJECTION') == 'Transverse_Mercator'):

        mapping_name = 'UTM_projection'
        grid_mapping = 'universal_transverse_mercator'  # need to set this as an attribute for the image variables
        datatype = np.dtype('S1')
        dimensions = ()
        FillValue = None

        var = nc_outfile.createVariable(mapping_name, datatype, dimensions, fill_value=FillValue)

        var.setncattr('grid_mapping_name', grid_mapping)
        zone = epsg - np.floor(epsg / 100) * 100
        var.setncattr('utm_zone_number', zone)
        var.setncattr('CoordinateTransformType', 'Projection')
        var.setncattr('CoordinateAxisTypes', 'GeoX GeoY')
        var.setncattr('semi_major_axis', float(srs.GetAttrValue('GEOGCS|SPHEROID', 1)))
        var.setncattr('inverse_flattening', float(srs.GetAttrValue('GEOGCS|SPHEROID', 2)))
        var.setncattr('spatial_ref', srs.ExportToWkt())
        var.setncattr('spatial_proj4', srs.ExportToProj4())
        var.setncattr('spatial_epsg', epsg)
        var.setncattr('GeoTransform',
                      ' '.join(str(x) for x in tran))  # note this has pixel size in it - set  explicitly above
    else:
        raise Exception('Projection {0} not recognized for this program'.format(srs.GetAttrValue('PROJECTION')))

    varname = 'vx'
    datatype = np.dtype('int16')
    dimensions = ('y', 'x')
    FillValue = NoDataValue
    var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue, zlib=True, complevel=2,
                                    shuffle=True, chunksizes=ChunkSize)
    if stable_shift_applied == 1:
        temp = VX.copy()
        temp[np.logical_not(SSM)] = np.nan
        vx_error = np.std(temp[(temp > -500) & (temp < 500)])
    else:
        if pair_type is 'radar':
            vx_error = (error_vector[0][0] * IMG_INFO_DICT['date_dt'] + error_vector[1][0]) / IMG_INFO_DICT[
                'date_dt'] * 365
        else:
            vx_error = error_vector[0] / IMG_INFO_DICT['date_dt'] * 365
    var.setncattr('vx_error', int(round(vx_error * 10)) / 10)
    var.setncattr('stable_count', stable_count)
    var.setncattr('stable_shift', int(round(vx_mean_shift * 10)) / 10)
    var.setncattr('flag_stable_shift', stable_shift_applied)
    var.setncattr('flag_stable_shift_meanings',
                  'flag for applying velocity bias correction over stable surfaces (stationary or slow-flowing surfaces with velocity < 15 m/yr): 0 = there is no stable surface available and no correction is applied; 1 = there are stable surfaces and velocity bias is corrected')
    var.setncattr('grid_mapping', mapping_name)
    var.setncattr('standard_name', 'x_velocity')
    if pair_type is 'radar':
        var.setncattr('description', 'velocity component in x direction from radar range and azimuth measurements')
    else:
        var.setncattr('description', 'velocity component in x direction')
    var.setncattr('units', 'm/y')
    VX[noDataMask] = NoDataValue
    var[:] = np.round(np.clip(VX, -32768, 32767)).astype(np.int16)
    var.setncattr('missing_value', np.int16(NoDataValue))

    varname = 'vy'
    datatype = np.dtype('int16')
    dimensions = ('y', 'x')
    FillValue = NoDataValue
    var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue, zlib=True, complevel=2,
                                    shuffle=True, chunksizes=ChunkSize)
    if stable_shift_applied == 1:
        temp = VY.copy()
        temp[np.logical_not(SSM)] = np.nan
        vy_error = np.std(temp[(temp > -500) & (temp < 500)])
    else:
        if pair_type is 'radar':
            vy_error = (error_vector[0][1] * IMG_INFO_DICT['date_dt'] + error_vector[1][1]) / IMG_INFO_DICT[
                'date_dt'] * 365
        else:
            vy_error = error_vector[1] / IMG_INFO_DICT['date_dt'] * 365
    var.setncattr('vy_error', int(round(vy_error * 10)) / 10)
    var.setncattr('stable_count', stable_count)
    var.setncattr('stable_shift', int(round(vy_mean_shift * 10)) / 10)
    var.setncattr('flag_stable_shift', stable_shift_applied)
    var.setncattr('flag_stable_shift_meanings',
                  'flag for applying velocity bias correction over stable surfaces (stationary or slow-flowing surfaces with velocity < 15 m/yr): 0 = there is no stable surface available and no correction is applied; 1 = there are stable surfaces and velocity bias is corrected')
    var.setncattr('grid_mapping', mapping_name)
    var.setncattr('standard_name', 'y_velocity')
    if pair_type is 'radar':
        var.setncattr('description', 'velocity component in y direction from radar range and azimuth measurements')
    else:
        var.setncattr('description', 'velocity component in y direction')
    var.setncattr('units', 'm/y')
    VY[noDataMask] = NoDataValue
    var[:] = np.round(np.clip(VY, -32768, 32767)).astype(np.int16)
    var.setncattr('missing_value', np.int16(NoDataValue))

    varname = 'v'
    datatype = np.dtype('int16')
    dimensions = ('y', 'x')
    FillValue = NoDataValue
    var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue, zlib=True, complevel=2,
                                    shuffle=True, chunksizes=ChunkSize)
    var.setncattr('grid_mapping', mapping_name)
    var.setncattr('standard_name', 'velocity')
    if pair_type is 'radar':
        var.setncattr('description', 'velocity magnitude from radar range and azimuth measurements')
    else:
        var.setncattr('description', 'velocity magnitude')
    var.setncattr('units', 'm/y')
    V[noDataMask] = NoDataValue
    var[:] = np.round(np.clip(V, -32768, 32767)).astype(np.int16)
    var.setncattr('missing_value', np.int16(NoDataValue))

    v_error = v_error_cal(vx_error, vy_error)
    varname = 'v_error'
    datatype = np.dtype('int16')
    dimensions = ('y', 'x')
    FillValue = NoDataValue
    var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue, zlib=True, complevel=2,
                                    shuffle=True, chunksizes=ChunkSize)
    var.setncattr('grid_mapping', mapping_name)
    var.setncattr('standard_name', 'velocity_error')
    if pair_type is 'radar':
        var.setncattr('description', 'velocity magnitude error from radar range and azimuth measurements')
    else:
        var.setncattr('description', 'velocity magnitude error')
    var.setncattr('units', 'm/y')
    V_error = np.sqrt((vx_error * VX / V) ** 2 + (vy_error * VY / V) ** 2)
    V_error[V==0] = v_error
    V_error[noDataMask] = NoDataValue
    var[:] = np.round(np.clip(V_error, -32768, 32767)).astype(np.int16)
    var.setncattr('missing_value', np.int16(NoDataValue))

    if pair_type is 'radar':

        varname = 'vr'
        datatype = np.dtype('int16')
        dimensions = ('y', 'x')
        FillValue = NoDataValue
        var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue, zlib=True, complevel=2,
                                        shuffle=True, chunksizes=ChunkSize)
        if stable_shift_applied == 1:
            temp = VR.copy()
            temp[np.logical_not(SSM)] = np.nan
            vr_error = np.std(temp[(temp > -500) & (temp < 500)])
        else:
            vr_error = (error_vector[0][2] * IMG_INFO_DICT['date_dt'] + error_vector[1][2]) / IMG_INFO_DICT[
                'date_dt'] * 365
        var.setncattr('vr_error', int(round(vr_error * 10)) / 10)
        var.setncattr('stable_count', stable_count)
        var.setncattr('stable_shift', int(round(vr_mean_shift * 10)) / 10)
        var.setncattr('flag_stable_shift', stable_shift_applied)
        var.setncattr('flag_stable_shift_meanings',
                      'flag for applying velocity bias correction over stable surfaces (stationary or slow-flowing surfaces with velocity < 15 m/yr): 0 = there is no stable surface available and no correction is applied; 1 = there are stable surfaces and velocity bias is corrected')
        var.setncattr('grid_mapping', mapping_name)
        var.setncattr('standard_name', 'range_velocity')
        var.setncattr('description', 'velocity in radar range direction')
        var.setncattr('units', 'm/y')
        VR[noDataMask] = NoDataValue
        var[:] = np.round(np.clip(VR, -32768, 32767)).astype(np.int16)
        var.setncattr('missing_value', np.int16(NoDataValue))

        varname = 'va'
        datatype = np.dtype('int16')
        dimensions = ('y', 'x')
        FillValue = NoDataValue
        var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue, zlib=True, complevel=2,
                                        shuffle=True, chunksizes=ChunkSize)
        if stable_shift_applied == 1:
            temp = VA.copy()
            temp[np.logical_not(SSM)] = np.nan
            va_error = np.std(temp[(temp > -500) & (temp < 500)])
        else:
            va_error = (error_vector[0][3] * IMG_INFO_DICT['date_dt'] + error_vector[1][3]) / IMG_INFO_DICT[
                'date_dt'] * 365
        var.setncattr('va_error', int(round(va_error * 10)) / 10)
        var.setncattr('stable_count', stable_count)
        var.setncattr('stable_shift', int(round(va_mean_shift * 10)) / 10)
        var.setncattr('flag_stable_shift', stable_shift_applied)
        var.setncattr('flag_stable_shift_meanings',
                      'flag for applying velocity bias correction over stable surfaces (stationary or slow-flowing surfaces with velocity < 15 m/yr): 0 = there is no stable surface available and no correction is applied; 1 = there are stable surfaces and velocity bias is corrected')
        var.setncattr('grid_mapping', mapping_name)
        var.setncattr('standard_name', 'azimuth_velocity')
        var.setncattr('description', 'velocity in radar azimuth direction')
        var.setncattr('units', 'm/y')
        VA[noDataMask] = NoDataValue
        var[:] = np.round(np.clip(VA, -32768, 32767)).astype(np.int16)
        var.setncattr('missing_value', np.int16(NoDataValue))

        # fuse the (slope parallel & reference) flow-based range-projected result with the raw observed range/azimuth-based result
        if stable_shift_applied_p == 1:
            temp = VXP.copy()
            temp[np.logical_not(SSM)] = np.nan
            vxp_error = np.std(temp[(temp > -500) & (temp < 500)])

            temp = VYP.copy()
            temp[np.logical_not(SSM)] = np.nan
            vyp_error = np.std(temp[(temp > -500) & (temp < 500)])
        else:
            vxp_error = (error_vector[0][4] * IMG_INFO_DICT['date_dt'] + error_vector[1][4]) / IMG_INFO_DICT[
                'date_dt'] * 365
            vyp_error = (error_vector[0][5] * IMG_INFO_DICT['date_dt'] + error_vector[1][5]) / IMG_INFO_DICT[
                'date_dt'] * 365

        VP_error = np.sqrt((vxp_error * VXP / VP) ** 2 + (vyp_error * VYP / VP) ** 2)

        VXPP[V_error > VP_error] = VXP[V_error > VP_error]
        VYPP[V_error > VP_error] = VYP[V_error > VP_error]
        VXP = VXPP.astype(np.float32)
        VYP = VYPP.astype(np.float32)
        VP = np.sqrt(VXP ** 2 + VYP ** 2)

        varname = 'vxp'
        datatype = np.dtype('int16')
        dimensions = ('y', 'x')
        FillValue = NoDataValue
        var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue, zlib=True, complevel=2,
                                        shuffle=True, chunksizes=ChunkSize)
        if stable_shift_applied == 1:
            temp = VXP.copy()
            temp[np.logical_not(SSM)] = np.nan
            vxp_error = np.std(temp[(temp > -500) & (temp < 500)])
        else:
            vxp_error = (error_vector[0][4] * IMG_INFO_DICT['date_dt'] + error_vector[1][4]) / IMG_INFO_DICT[
                'date_dt'] * 365
        var.setncattr('vxp_error', int(round(vxp_error * 10)) / 10)
        var.setncattr('stable_count', stable_count)
        var.setncattr('stable_shift', int(round(vxp_mean_shift * 10)) / 10)
        var.setncattr('flag_stable_shift', stable_shift_applied)
        var.setncattr('flag_stable_shift_meanings',
                      'flag for applying velocity bias correction over stable surfaces (stationary or slow-flowing surfaces with velocity < 15 m/yr): 0 = there is no stable surface available and no correction is applied; 1 = there are stable surfaces and velocity bias is corrected')
        var.setncattr('grid_mapping', mapping_name)
        var.setncattr('standard_name', 'projected_x_velocity')
        var.setncattr('description',
                      'x-direction velocity determined by projecting radar range measurements onto an a priori flow vector. Where projected errors are larger than those determined from range and azimuth measurements, unprojected vx estimates are used')
        var.setncattr('units', 'm/y')
        VXP[noDataMask] = NoDataValue
        var[:] = np.round(np.clip(VXP, -32768, 32767)).astype(np.int16)
        var.setncattr('missing_value', np.int16(NoDataValue))

        varname = 'vyp'
        datatype = np.dtype('int16')
        dimensions = ('y', 'x')
        FillValue = NoDataValue
        var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue, zlib=True, complevel=2,
                                        shuffle=True, chunksizes=ChunkSize)
        if stable_shift_applied == 1:
            temp = VYP.copy()
            temp[np.logical_not(SSM)] = np.nan
            vyp_error = np.std(temp[(temp > -500) & (temp < 500)])
        else:
            vyp_error = (error_vector[0][5] * IMG_INFO_DICT['date_dt'] + error_vector[1][5]) / IMG_INFO_DICT[
                'date_dt'] * 365
        var.setncattr('vyp_error', int(round(vyp_error * 10)) / 10)
        var.setncattr('stable_count', stable_count)
        var.setncattr('stable_shift', int(round(vyp_mean_shift * 10)) / 10)
        var.setncattr('flag_stable_shift', stable_shift_applied)
        var.setncattr('flag_stable_shift_meanings',
                      'flag for applying velocity bias correction over stable surfaces (stationary or slow-flowing surfaces with velocity < 15 m/yr): 0 = there is no stable surface available and no correction is applied; 1 = there are stable surfaces and velocity bias is corrected')
        var.setncattr('grid_mapping', mapping_name)
        var.setncattr('standard_name', 'projected_y_velocity')
        var.setncattr('description',
                      'y-direction velocity determined by projecting radar range measurements onto an a priori flow vector. Where projected errors are larger than those determined from range and azimuth measurements, unprojected vy estimates are used')
        var.setncattr('units', 'm/y')
        VYP[noDataMask] = NoDataValue
        var[:] = np.round(np.clip(VYP, -32768, 32767)).astype(np.int16)
        var.setncattr('missing_value', np.int16(NoDataValue))

        varname = 'vp'
        datatype = np.dtype('int16')
        dimensions = ('y', 'x')
        FillValue = NoDataValue
        var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue, zlib=True, complevel=2,
                                        shuffle=True, chunksizes=ChunkSize)
        var.setncattr('grid_mapping', mapping_name)
        var.setncattr('standard_name', 'projected_velocity')
        var.setncattr('description',
                      'velocity magnitude determined by projecting radar range measurements onto an a priori flow vector. Where projected errors are larger than those determined from range and azimuth measurements, unprojected v estimates are used')
        var.setncattr('units', 'm/y')
        VP[noDataMask] = NoDataValue
        var[:] = np.round(np.clip(VP, -32768, 32767)).astype(np.int16)
        var.setncattr('missing_value', np.int16(NoDataValue))

        varname = 'vp_error'
        datatype = np.dtype('int16')
        dimensions = ('y', 'x')
        FillValue = NoDataValue
        var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue, zlib=True, complevel=2,
                                        shuffle=True, chunksizes=ChunkSize)
        var.setncattr('grid_mapping', mapping_name)
        var.setncattr('standard_name', 'projected_velocity_error')
        var.setncattr('description',
                      'velocity magnitude error determined by projecting radar range measurements onto an a priori flow vector. Where projected errors are larger than those determined from range and azimuth measurements, unprojected v_error estimates are used')
        var.setncattr('units', 'm/y')
        VP_error = np.sqrt((vxp_error * VXP / VP) ** 2 + (vyp_error * VYP / VP) ** 2)
        VP_error[noDataMask] = NoDataValue
        var[:] = np.round(np.clip(VP_error, -32768, 32767)).astype(np.int16)
        var.setncattr('missing_value', np.int16(NoDataValue))

    varname = 'chip_size_width'
    datatype = np.dtype('uint16')
    dimensions = ('y', 'x')
    FillValue = 0
    var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue, zlib=True, complevel=2,
                                    shuffle=True, chunksizes=ChunkSize)
    var.setncattr('grid_mapping', mapping_name)
    if pair_type is 'radar':
        var.setncattr('range_pixel_size', rangePixelSize)
        var.setncattr('chip_size_coordinates', 'radar geometry: width = range, height = azimuth')
    else:
        var.setncattr('x_pixel_size', rangePixelSize)
        var.setncattr('chip_size_coordinates', 'image projection geometry: width = x, height = y')
    var.setncattr('standard_name', 'chip_size_width')
    var.setncattr('description', 'width of search window')
    var.setncattr('units', 'm')
    var[:] = np.round(np.clip(CHIPSIZEX, 0, 65535)).astype('uint16')
    var.setncattr('missing_value', np.uint16(0))

    varname = 'chip_size_height'
    datatype = np.dtype('uint16')
    dimensions = ('y', 'x')
    FillValue = 0
    var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue, zlib=True, complevel=2,
                                    shuffle=True, chunksizes=ChunkSize)
    var.setncattr('grid_mapping', mapping_name)
    if pair_type is 'radar':
        var.setncattr('azimuth_pixel_size', azimuthPixelSize)
        var.setncattr('chip_size_coordinates', 'radar geometry: width = range, height = azimuth')
    else:
        var.setncattr('y_pixel_size', azimuthPixelSize)
        var.setncattr('chip_size_coordinates', 'image projection geometry: width = x, height = y')
    var.setncattr('standard_name', 'chip_size_height')
    var.setncattr('description', 'height of search window')
    var.setncattr('units', 'm')
    var[:] = np.round(np.clip(CHIPSIZEY, 0, 65535)).astype('uint16')
    var.setncattr('missing_value', np.uint16(0))

    varname = 'interp_mask'
    datatype = np.dtype('uint8')
    dimensions = ('y', 'x')
    FillValue = None
    var = nc_outfile.createVariable(varname, datatype, dimensions, fill_value=FillValue, zlib=True, complevel=2,
                                    shuffle=True, chunksizes=ChunkSize)
    var.setncattr('grid_mapping', mapping_name)
    var.setncattr('standard_name', 'interpolated_value_mask')
    var.setncattr('description', 'light interpolation mask')
    var.setncattr('units', 'binary')
    var[:] = np.round(np.clip(INTERPMASK, 0, 255)).astype('uint8')
    var.setncattr('missing_value', np.uint8(0))

    nc_outfile.sync()  # flush data to disk
    nc_outfile.close()

    return out_nc_filename
