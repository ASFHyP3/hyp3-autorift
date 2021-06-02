#!/usr/bin/env python3

########
#Yang Lei, Jet Propulsion Laboratory
#November 2017

import xml.etree.ElementTree as ET
#from numpy import *
import numpy as np
import scipy.io as sio
##import commands
import subprocess
import os
import time
import argparse
import pdb
import os
import isce
import isceobj
import shelve
import string
import sys
import datetime
import netCDF4
from scipy import stats

#def cmdLineParse():
#    '''
#    Command line parser.
#    '''
#    parser = argparse.ArgumentParser(description="Single-pair InSAR processing of Sentinel-1 data using ISCE modules")
#
#    return parser.parse_args()


def runCmd(cmd):
    out = subprocess.getoutput(cmd)
    return out

def v_error_cal(vx_error, vy_error):
    vx = np.random.normal(0, vx_error, 1000000)
    vy = np.random.normal(0, vy_error, 1000000)
    v = np.sqrt(vx**2 + vy**2)
    return np.std(v)





def netCDF_packaging(VX, VY, DX, DY, INTERPMASK, CHIPSIZEX, CHIPSIZEY, SSM, SSM1, SX, SY, offset2vx_1, offset2vx_2, offset2vy_1, offset2vy_2, MM, VXref, VYref, rangePixelSize, azimuthPixelSize, dt, epsg, srs, tran, out_nc_filename, pair_type, detection_method, coordinates, IMG_INFO_DICT, stable_count, stable_count1, stable_shift_applied, dx_mean_shift, dy_mean_shift, dx_mean_shift1, dy_mean_shift1, error_vector):
    
    
    vx_mean_shift = offset2vx_1 * dx_mean_shift + offset2vx_2 * dy_mean_shift
    temp = vx_mean_shift
    temp[np.logical_not(SSM)] = np.nan
#        vx_mean_shift = np.median(temp[(temp > -500)&(temp < 500)])
    vx_mean_shift = np.median(temp[np.logical_not(np.isnan(temp))])
    vy_mean_shift = offset2vy_1 * dx_mean_shift + offset2vy_2 * dy_mean_shift
    temp = vy_mean_shift
    temp[np.logical_not(SSM)] = np.nan
#        vy_mean_shift = np.median(temp[(temp > -500)&(temp < 500)])
    vy_mean_shift = np.median(temp[np.logical_not(np.isnan(temp))])
    
    
    vx_mean_shift1 = offset2vx_1 * dx_mean_shift1 + offset2vx_2 * dy_mean_shift1
    temp = vx_mean_shift1
    temp[np.logical_not(SSM1)] = np.nan
    vx_mean_shift1 = np.median(temp[np.logical_not(np.isnan(temp))])
    vy_mean_shift1 = offset2vy_1 * dx_mean_shift1 + offset2vy_2 * dy_mean_shift1
    temp = vy_mean_shift1
    temp[np.logical_not(SSM1)] = np.nan
    vy_mean_shift1 = np.median(temp[np.logical_not(np.isnan(temp))])
    
    

    V = np.sqrt(VX**2+VY**2)
    
    if pair_type is 'radar':
        VR = DX * rangePixelSize / dt * 365.0 * 24.0 * 3600.0
        VA = (DY) * azimuthPixelSize / dt * 365.0 * 24.0 * 3600.0
        VR = VR.astype(np.float32)
        VA = VA.astype(np.float32)
        
        
        vr_mean_shift = dx_mean_shift * rangePixelSize / dt * 365.0 * 24.0 * 3600.0
        va_mean_shift = (dy_mean_shift) * azimuthPixelSize / dt * 365.0 * 24.0 * 3600.0
        
        vr_mean_shift1 = dx_mean_shift1 * rangePixelSize / dt * 365.0 * 24.0 * 3600.0
        va_mean_shift1 = (dy_mean_shift1) * azimuthPixelSize / dt * 365.0 * 24.0 * 3600.0
        
        # create the (slope parallel & reference) flow-based range-projected result
        alpha_sp = DX / (offset2vy_2 / (offset2vx_1 * offset2vy_2 - offset2vx_2 * offset2vy_1) * (-SX) - offset2vx_2 / (offset2vx_1 * offset2vy_2 - offset2vx_2 * offset2vy_1) * (-SY))
        alpha_ref = DX / (offset2vy_2 / (offset2vx_1 * offset2vy_2 - offset2vx_2 * offset2vy_1) * VXref - offset2vx_2 / (offset2vx_1 * offset2vy_2 - offset2vx_2 * offset2vy_1) * VYref)
        VXS = alpha_sp * (-SX)
        VYS = alpha_sp * (-SY)
        VXR = alpha_ref * VXref
        VYR = alpha_ref * VYref

        zero_flag_sp = (SX == 0)&(SY == 0)
        zero_flag_ref = (VXref == 0)&(VYref == 0)
        VXS[zero_flag_sp] = np.nan
        VYS[zero_flag_sp] = np.nan
        VXR[zero_flag_ref] = np.nan
        VYR[zero_flag_ref] = np.nan
        
        rngX = offset2vx_1
        rngY = offset2vy_1
        angle_df_S = np.arccos((-SX * rngX - SY * rngY) / (np.sqrt(SX**2 + SY**2) * np.sqrt(rngX**2+rngY**2)))
        angle_df_S = np.abs(np.real(angle_df_S) - np.pi / 2)
        angle_df_R = np.arccos((VXref * rngX + VYref * rngY) / (np.sqrt(VXref**2 + VYref**2) * np.sqrt(rngX**2+rngY**2)))
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
        VP = np.sqrt(VXP**2+VYP**2)

        VXPP = VX.copy()
        VYPP = VY.copy()
    
        stable_count_p = np.sum(SSM & np.logical_not(np.isnan(VXP)))
        stable_count1_p = np.sum(SSM1 & np.logical_not(np.isnan(VXP)))

        vxp_mean_shift = 0.0
        vyp_mean_shift = 0.0
        vxp_mean_shift1 = 0.0
        vyp_mean_shift1 = 0.0
        
        if stable_count_p != 0:
            temp = VXP.copy() - VX.copy()
            temp[np.logical_not(SSM)] = np.nan
            bias_mean_shift = np.median(temp[(temp > -500)&(temp < 500)])
            vxp_mean_shift = vx_mean_shift + bias_mean_shift / 2
            
            temp = VYP.copy() - VY.copy()
            temp[np.logical_not(SSM)] = np.nan
            bias_mean_shift = np.median(temp[(temp > -500)&(temp < 500)])
            vyp_mean_shift = vy_mean_shift + bias_mean_shift / 2
        
        if stable_count1_p != 0:
            temp = VXP.copy() - VX.copy()
            temp[np.logical_not(SSM1)] = np.nan
            bias_mean_shift1 = np.median(temp[(temp > -500)&(temp < 500)])
            vxp_mean_shift1 = vx_mean_shift1 + bias_mean_shift1 / 2
            
            temp = VYP.copy() - VY.copy()
            temp[np.logical_not(SSM1)] = np.nan
            bias_mean_shift1 = np.median(temp[(temp > -500)&(temp < 500)])
            vyp_mean_shift1 = vy_mean_shift1 + bias_mean_shift1 / 2
        
        if stable_count_p == 0:
            if stable_count1_p == 0:
                stable_shift_applied_p = 0
            else:
                stable_shift_applied_p = 2
        else:
            stable_shift_applied_p = 1
            


    CHIPSIZEX = CHIPSIZEX * rangePixelSize
    CHIPSIZEY = CHIPSIZEY * azimuthPixelSize
    
    NoDataValue = -32767
    noDataMask = np.isnan(VX) | np.isnan(VY)
    

#    VXref[noDataMask] = NoDataValue
#    VYref[noDataMask] = NoDataValue

#    if pair_type is 'radar':
#        VRref[noDataMask] = NoDataValue
#        VAref[noDataMask] = NoDataValue

    CHIPSIZEX[noDataMask] = 0
    CHIPSIZEY[noDataMask] = 0
    INTERPMASK[noDataMask] = 0

    title = 'autoRIFT surface velocities'
    author = 'Alex S. Gardner, JPL/NASA; Yang Lei, GPS/Caltech'
    institution = 'NASA Jet Propulsion Laboratory (JPL), California Institute of Technology'

#    VX = np.round(np.clip(VX, -32768, 32767)).astype(np.int16)
#    VY = np.round(np.clip(VY, -32768, 32767)).astype(np.int16)
#    V = np.round(np.clip(V, -32768, 32767)).astype(np.int16)
#    if pair_type is 'radar':
#        VR = np.round(np.clip(VR, -32768, 32767)).astype(np.int16)
#        VA = np.round(np.clip(VA, -32768, 32767)).astype(np.int16)
#    CHIPSIZEX = np.round(np.clip(CHIPSIZEX, 0, 65535)).astype(np.uint16)
#    CHIPSIZEY = np.round(np.clip(CHIPSIZEY, 0, 65535)).astype(np.uint16)
#    INTERPMASK = np.round(np.clip(INTERPMASK, 0, 255)).astype(np.uint8)

    
    tran = [tran[0] + tran[1]/2, tran[1], 0.0, tran[3] + tran[5]/2, 0.0, tran[5]]
    
    clobber = True     # overwrite existing output nc file

    nc_outfile = netCDF4.Dataset(out_nc_filename,'w',clobber=clobber,format='NETCDF4')
    
    # First set global attributes that GDAL uses when it reads netCFDF files
    nc_outfile.setncattr('GDAL_AREA_OR_POINT','Area')
    nc_outfile.setncattr('Conventions','CF-1.6')
    nc_outfile.setncattr('date_created',datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S"))
    nc_outfile.setncattr('title',title)
    nc_outfile.setncattr('author',author)
    nc_outfile.setncattr('institution',institution)
#    nc_outfile.setncattr('Software',version)
    nc_outfile.setncattr('scene_pair_type',pair_type)
    nc_outfile.setncattr('motion_detection_method',detection_method)
    nc_outfile.setncattr('motion_coordinates',coordinates)

    # if we were copying from an nc file, we would...
    # for attr in vv_nc_basefile.ncattrs():
    #     nc_outfile.setncattr(attr,vv_nc_basefile.getncattr(attr))
    
#    from topsApp import TopsInSAR
#    insar = TopsInSAR(name="topsApp")
#    insar.configure()
#    master_filename = os.path.basename(insar.master.safe[0])
#    slave_filename = os.path.basename(insar.slave.safe[0])

#    import topsinsar_filename as tf
#    master_filename, slave_filename = tf.loadXml()


#    runCmd('topsinsar_filename.py')
#    import scipy.io as sio
#    conts = sio.loadmat('topsinsar_filename.mat')
#    master_filename = conts['master_filename'][0]
#    slave_filename = conts['slave_filename'][0]
#    master_split = str.split(master_filename,'_')
#    slave_split = str.split(slave_filename,'_')


    varname='img_pair_info'
#    datatype=np.dtype('S1')
    datatype='U1'
    dimensions=()
    FillValue=None
    
    var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue)
    # variable made, now add attributes
    
#    var.setncattr('mission_img1',master_split[0][0])
#    var.setncattr('sensor_img1','C')
#    var.setncattr('satellite_img1',master_split[0][1:3])
#    var.setncattr('acquisition_img1',master_split[5][0:8])
#    var.setncattr('absolute_orbit_number_img1',master_split[7])
#    var.setncattr('mission_data_take_ID_img1',master_split[8])
#    var.setncattr('product_unique_ID_img1',master_split[9][0:4])
#
#    var.setncattr('mission_img2',slave_split[0][0])
#    var.setncattr('sensor_img2','C')
#    var.setncattr('satellite_img2',slave_split[0][1:3])
#    var.setncattr('acquisition_img2',slave_split[5][0:8])
#    var.setncattr('absolute_orbit_number_img2',slave_split[7])
#    var.setncattr('mission_data_take_ID_img2',slave_split[8])
#    var.setncattr('product_unique_ID_img2',slave_split[9][0:4])
#
#    from datetime import date
#    d0 = date(np.int(master_split[5][0:4]),np.int(master_split[5][4:6]),np.int(master_split[5][6:8]))
#    d1 = date(np.int(slave_split[5][0:4]),np.int(slave_split[5][4:6]),np.int(slave_split[5][6:8]))
#    date_dt = d1 - d0
#    var.setncattr('date_dt',np.float64(np.abs(date_dt.days)))
#    if date_dt.days < 0:
#        date_ct = d1 + (d0 - d1)/2
#        var.setncattr('date_center',date_ct.strftime("%Y%m%d"))
#    else:
#        date_ct = d0 + (d1 - d0)/2
#        var.setncattr('date_center',date_ct.strftime("%Y%m%d"))
##    var.setncattr('date_center',np.abs(np.int(slave_split[5][0:8])+np.int(master_split[5][0:8]))/2)
#
#    var.setncattr('roi_valid_percentage',roi_valid_percentage)
#    var.setncattr('autoRIFT_software_version',version)

    for key in IMG_INFO_DICT:
        var.setncattr(key,IMG_INFO_DICT[key])

    
    

    # set dimensions
    dimidY, dimidX = VX.shape
    nc_outfile.createDimension('x',dimidX)
    nc_outfile.createDimension('y',dimidY)
#    pdb.set_trace()
    x = np.arange(tran[0],tran[0]+tran[1]*(dimidX),tran[1])
    y = np.arange(tran[3],tran[3]+tran[5]*(dimidY),tran[5])
#    pdb.set_trace()
    chunk_lines = np.min([np.ceil(8192/dimidY)*128, dimidY])
#    ChunkSize = [dimidX, chunk_lines]
    ChunkSize = [chunk_lines, dimidX]


    varname='x'
    datatype=np.dtype('float64')
    dimensions=('x')
    FillValue=None
    var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue)
    var.setncattr('standard_name','projection_x_coordinate')
    var.setncattr('description','x coordinate of projection')
    var.setncattr('units','m')
#    var.setncattr('scene_pair_type',pair_type)
#    var.setncattr('motion_detection_method',detection_method)
#    var.setncattr('motion_coordinates',coordinates)
#    pdb.set_trace()
    var[:] = x
    
    varname='y'
    datatype=np.dtype('float64')
    dimensions=('y')
    FillValue=None
    var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue)
    var.setncattr('standard_name','projection_y_coordinate')
    var.setncattr('description','y coordinate of projection')
    var.setncattr('units','m')
#    var.setncattr('scene_pair_type',pair_type)
#    var.setncattr('motion_detection_method',detection_method)
#    var.setncattr('motion_coordinates',coordinates)
    var[:] = y



    if (srs.GetAttrValue('PROJECTION') == 'Polar_Stereographic'):

#        mapping_name='Polar_Stereographic'
        mapping_name='mapping'
        grid_mapping='polar_stereographic'  # need to set this as an attribute for the image variables
#        datatype=np.dtype('S1')
        datatype='U1'
        dimensions=()
        FillValue=None

        var = nc_outfile.createVariable(mapping_name,datatype,dimensions, fill_value=FillValue)
        # variable made, now add attributes

        var.setncattr('grid_mapping_name',grid_mapping)
        var.setncattr('straight_vertical_longitude_from_pole',srs.GetProjParm('central_meridian'))
        var.setncattr('false_easting',srs.GetProjParm('false_easting'))
        var.setncattr('false_northing',srs.GetProjParm('false_northing'))
        var.setncattr('latitude_of_projection_origin',np.sign(srs.GetProjParm('latitude_of_origin'))*90.0)  # could hardcode this to be -90 for landsat - just making it more general, maybe...
        var.setncattr('latitude_of_origin',srs.GetProjParm('latitude_of_origin'))
#        var.setncattr('longitude_of_prime_meridian',float(srs.GetAttrValue('GEOGCS|PRIMEM',1)))
        var.setncattr('semi_major_axis',float(srs.GetAttrValue('GEOGCS|SPHEROID',1)))
#        var.setncattr('semi_minor_axis',float(6356.752))
        var.setncattr('scale_factor_at_projection_origin',1)
        var.setncattr('inverse_flattening',float(srs.GetAttrValue('GEOGCS|SPHEROID',2)))
        var.setncattr('spatial_ref',srs.ExportToWkt())
        var.setncattr('spatial_proj4',srs.ExportToProj4())
        var.setncattr('spatial_epsg',epsg)
        var.setncattr('GeoTransform',' '.join(str(x) for x in tran))  # note this has pixel size in it - set  explicitly above

    elif (srs.GetAttrValue('PROJECTION') == 'Transverse_Mercator'):

#        mapping_name='UTM_projection'
        mapping_name='mapping'
        grid_mapping='universal_transverse_mercator'  # need to set this as an attribute for the image variables
#        datatype=np.dtype('S1')
        datatype='U1'
        dimensions=()
        FillValue=None

        var = nc_outfile.createVariable(mapping_name,datatype,dimensions, fill_value=FillValue)
        # variable made, now add attributes


        var.setncattr('grid_mapping_name',grid_mapping)
        zone = epsg - np.floor(epsg/100)*100
        var.setncattr('utm_zone_number',zone)
        var.setncattr('CoordinateTransformType','Projection')
        var.setncattr('CoordinateAxisTypes','GeoX GeoY')
#        var.setncattr('longitude_of_central_meridian',srs.GetProjParm('central_meridian'))
#        var.setncattr('false_easting',srs.GetProjParm('false_easting'))
#        var.setncattr('false_northing',srs.GetProjParm('false_northing'))
#        var.setncattr('latitude_of_projection_origin',srs.GetProjParm('latitude_of_origin'))
#        var.setncattr('scale_factor_at_central_meridian',srs.GetProjParm('scale_factor'))
#        var.setncattr('longitude_of_prime_meridian',float(srs.GetAttrValue('GEOGCS|PRIMEM',1)))
        var.setncattr('semi_major_axis',float(srs.GetAttrValue('GEOGCS|SPHEROID',1)))
        var.setncattr('inverse_flattening',float(srs.GetAttrValue('GEOGCS|SPHEROID',2)))
        var.setncattr('spatial_ref',srs.ExportToWkt())
        var.setncattr('spatial_proj4',srs.ExportToProj4())
        var.setncattr('spatial_epsg',epsg)
        var.setncattr('GeoTransform',' '.join(str(x) for x in tran))  # note this has pixel size in it - set  explicitly above
    else:
        raise Exception('Projection {0} not recognized for this program'.format(srs.GetAttrValue('PROJECTION')))


    varname='vx'
    datatype=np.dtype('int16')
    dimensions=('y','x')
    FillValue=NoDataValue
    var = nc_outfile.createVariable(varname,datatype,dimensions, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize, fill_value=FillValue)


    var.setncattr('standard_name','x_velocity')
    if pair_type is 'radar':
        var.setncattr('description','velocity component in x direction from radar range and azimuth measurements')
    else:
        var.setncattr('description','velocity component in x direction')
    var.setncattr('units','m/y')


    if stable_count != 0:
        temp = VX.copy()
        temp[np.logical_not(SSM)] = np.nan
        vx_error_mask = np.std(temp[(temp > -500)&(temp < 500)])
    else:
        vx_error_mask = np.nan
    if stable_count1 != 0:
        temp = VX.copy()
        temp[np.logical_not(SSM1)] = np.nan
        vx_error_slow = np.std(temp[(temp > -500)&(temp < 500)])
    else:
        vx_error_slow = np.nan
    if pair_type is 'radar':
        vx_error_mod = (error_vector[0][0]*IMG_INFO_DICT['date_dt']+error_vector[1][0])/IMG_INFO_DICT['date_dt']*365
    else:
        vx_error_mod = error_vector[0]/IMG_INFO_DICT['date_dt']*365
    if stable_shift_applied == 1:
        vx_error = vx_error_mask
    elif stable_shift_applied == 2:
        vx_error = vx_error_slow
    else:
        vx_error = vx_error_mod
    var.setncattr('vx_error',int(round(vx_error*10))/10)
    var.setncattr('vx_error_description','best estimate of x_velocity error: vx_error is populated according to the approach used for the velocity bias correction as indicated in "flag_stable_shift"')

    if stable_shift_applied == 2:
        var.setncattr('stable_shift',int(round(vx_mean_shift1*10))/10)
    elif stable_shift_applied == 1:
        var.setncattr('stable_shift',int(round(vx_mean_shift*10))/10)
    else:
        var.setncattr('stable_shift',np.nan)
    var.setncattr('flag_stable_shift',stable_shift_applied)
    var.setncattr('flag_stable_shift_description','flag for applying velocity bias correction: 0 = no correction; 1 = correction from overlapping stable surface mask (stationary or slow-flowing surfaces with velocity < 15 m/yr)(top priority); 2 = correction from slowest 25% of overlapping velocities (second priority)')


    var.setncattr('stable_count_mask',stable_count)
    var.setncattr('stable_count_slow',stable_count1)
    if stable_count != 0:
        var.setncattr('stable_shift_mask',int(round(vx_mean_shift*10))/10)
    else:
        var.setncattr('stable_shift_mask',np.nan)
    if stable_count1 != 0:
        var.setncattr('stable_shift_slow',int(round(vx_mean_shift1*10))/10)
    else:
        var.setncattr('stable_shift_slow',np.nan)

    if stable_count != 0:
        var.setncattr('vx_error_mask',int(round(vx_error_mask*10))/10)
    else:
        var.setncattr('vx_error_mask',np.nan)
    var.setncattr('vx_error_mask_description','RMSE over stable surfaces, stationary or slow-flowing surfaces with velocity < 15 m/yr identified from an external mask')
    if stable_count1 != 0:
        var.setncattr('vx_error_slow',int(round(vx_error_slow*10))/10)
    else:
        var.setncattr('vx_error_slow',np.nan)
    var.setncattr('vx_error_slow_description','RMSE over slowest 25% of retrieved velocities')
    var.setncattr('vx_error_modeled',int(round(vx_error_mod*10))/10)
    var.setncattr('vx_error_modeled_description','1-sigma error calculated using a modeled error-dt relationship')

    var.setncattr('grid_mapping',mapping_name)

    VX[noDataMask] = NoDataValue
    var[:] = np.round(np.clip(VX, -32768, 32767)).astype(np.int16)
#    var.setncattr('_FillValue',np.int16(FillValue))



    varname='vy'
    datatype=np.dtype('int16')
    dimensions=('y','x')
    FillValue=NoDataValue
    var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)

    var.setncattr('standard_name','y_velocity')
    if pair_type is 'radar':
        var.setncattr('description','velocity component in y direction from radar range and azimuth measurements')
    else:
        var.setncattr('description','velocity component in y direction')
    var.setncattr('units','m/y')


    if stable_count != 0:
        temp = VY.copy()
        temp[np.logical_not(SSM)] = np.nan
        vy_error_mask = np.std(temp[(temp > -500)&(temp < 500)])
    else:
        vy_error_mask = np.nan
    if stable_count1 != 0:
        temp = VY.copy()
        temp[np.logical_not(SSM1)] = np.nan
        vy_error_slow = np.std(temp[(temp > -500)&(temp < 500)])
    else:
        vy_error_slow = np.nan
    if pair_type is 'radar':
        vy_error_mod = (error_vector[0][1]*IMG_INFO_DICT['date_dt']+error_vector[1][1])/IMG_INFO_DICT['date_dt']*365
    else:
        vy_error_mod = error_vector[1]/IMG_INFO_DICT['date_dt']*365
    if stable_shift_applied == 1:
        vy_error = vy_error_mask
    elif stable_shift_applied == 2:
        vy_error = vy_error_slow
    else:
        vy_error = vy_error_mod
    var.setncattr('vy_error',int(round(vy_error*10))/10)
    var.setncattr('vy_error_description','best estimate of y_velocity error: vy_error is populated according to the approach used for the velocity bias correction as indicated in "flag_stable_shift"')


    if stable_shift_applied == 2:
        var.setncattr('stable_shift',int(round(vy_mean_shift1*10))/10)
    elif stable_shift_applied == 1:
        var.setncattr('stable_shift',int(round(vy_mean_shift*10))/10)
    else:
        var.setncattr('stable_shift',np.nan)
    var.setncattr('flag_stable_shift',stable_shift_applied)
    var.setncattr('flag_stable_shift_description','flag for applying velocity bias correction: 0 = no correction; 1 = correction from overlapping stable surface mask (stationary or slow-flowing surfaces with velocity < 15 m/yr)(top priority); 2 = correction from slowest 25% of overlapping velocities (second priority)')


    var.setncattr('stable_count_mask',stable_count)
    var.setncattr('stable_count_slow',stable_count1)
    if stable_count != 0:
        var.setncattr('stable_shift_mask',int(round(vy_mean_shift*10))/10)
    else:
        var.setncattr('stable_shift_mask',np.nan)
    if stable_count1 != 0:
        var.setncattr('stable_shift_slow',int(round(vy_mean_shift1*10))/10)
    else:
        var.setncattr('stable_shift_slow',np.nan)

    if stable_count != 0:
        var.setncattr('vy_error_mask',int(round(vy_error_mask*10))/10)
    else:
        var.setncattr('vy_error_mask',np.nan)
    var.setncattr('vy_error_mask_description','RMSE over stable surfaces, stationary or slow-flowing surfaces with velocity < 15 m/yr identified from an external mask')
    if stable_count1 != 0:
        var.setncattr('vy_error_slow',int(round(vy_error_slow*10))/10)
    else:
        var.setncattr('vy_error_slow',np.nan)
    var.setncattr('vy_error_slow_description','RMSE over slowest 25% of retrieved velocities')
    var.setncattr('vy_error_modeled',int(round(vy_error_mod*10))/10)
    var.setncattr('vy_error_modeled_description','1-sigma error calculated using a modeled error-dt relationship')


    var.setncattr('grid_mapping',mapping_name)

    VY[noDataMask] = NoDataValue
    var[:] = np.round(np.clip(VY, -32768, 32767)).astype(np.int16)
#    var.setncattr('missing_value',np.int16(NoDataValue))




    varname='v'
    datatype=np.dtype('int16')
    dimensions=('y','x')
    FillValue=NoDataValue
    var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)
    var.setncattr('standard_name','velocity')
    if pair_type is 'radar':
        var.setncattr('description','velocity magnitude from radar range and azimuth measurements')
    else:
        var.setncattr('description','velocity magnitude')
    var.setncattr('units','m/y')

    var.setncattr('grid_mapping',mapping_name)

    V[noDataMask] = NoDataValue
    var[:] = np.round(np.clip(V, -32768, 32767)).astype(np.int16)
#    var.setncattr('missing_value',np.int16(NoDataValue))




    v_error = v_error_cal(vx_error, vy_error)
    varname='v_error'
    datatype=np.dtype('int16')
    dimensions=('y','x')
    FillValue=NoDataValue
    var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)
    var.setncattr('standard_name','velocity_error')
    if pair_type is 'radar':
        var.setncattr('description','velocity magnitude error from radar range and azimuth measurements')
    else:
        var.setncattr('description','velocity magnitude error')
    var.setncattr('units','m/y')

    var.setncattr('grid_mapping',mapping_name)

    V_error = np.sqrt((vx_error * VX / V)**2 + (vy_error * VY / V)**2)
    V_error[V==0] = v_error
    V_error[noDataMask] = NoDataValue
    var[:] = np.round(np.clip(V_error, -32768, 32767)).astype(np.int16)
#    var.setncattr('missing_value',np.int16(NoDataValue))





    if pair_type is 'radar':
        
        varname='vr'
        datatype=np.dtype('int16')
        dimensions=('y','x')
        FillValue=NoDataValue
        var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)
        
        
        var.setncattr('standard_name','range_velocity')
        var.setncattr('description','velocity in radar range direction')
        var.setncattr('units','m/y')
        
        if stable_count != 0:
            temp = VR.copy()
            temp[np.logical_not(SSM)] = np.nan
            vr_error_mask = np.std(temp[(temp > -500)&(temp < 500)])
        else:
            vr_error_mask = np.nan
        if stable_count1 != 0:
            temp = VR.copy()
            temp[np.logical_not(SSM1)] = np.nan
            vr_error_slow = np.std(temp[(temp > -500)&(temp < 500)])
        else:
            vr_error_slow = np.nan
        vr_error_mod = (error_vector[0][2]*IMG_INFO_DICT['date_dt']+error_vector[1][2])/IMG_INFO_DICT['date_dt']*365
        if stable_shift_applied == 1:
            vr_error = vr_error_mask
        elif stable_shift_applied == 2:
            vr_error = vr_error_slow
        else:
            vr_error = vr_error_mod
        var.setncattr('vr_error',int(round(vr_error*10))/10)
        var.setncattr('vr_error_description','best estimate of range_velocity error: vr_error is populated according to the approach used for the velocity bias correction as indicated in "flag_stable_shift"')
        
        
        if stable_shift_applied == 2:
            var.setncattr('stable_shift',int(round(vr_mean_shift1*10))/10)
        elif stable_shift_applied == 1:
            var.setncattr('stable_shift',int(round(vr_mean_shift*10))/10)
        else:
            var.setncattr('stable_shift',np.nan)
        var.setncattr('flag_stable_shift',stable_shift_applied)
        var.setncattr('flag_stable_shift_description','flag for applying velocity bias correction: 0 = no correction; 1 = correction from overlapping stable surface mask (stationary or slow-flowing surfaces with velocity < 15 m/yr)(top priority); 2 = correction from slowest 25% of overlapping velocities (second priority)')


        var.setncattr('stable_count_mask',stable_count)
        var.setncattr('stable_count_slow',stable_count1)
        if stable_count != 0:
            var.setncattr('stable_shift_mask',int(round(vr_mean_shift*10))/10)
        else:
            var.setncattr('stable_shift_mask',np.nan)
        if stable_count1 != 0:
            var.setncattr('stable_shift_slow',int(round(vr_mean_shift1*10))/10)
        else:
            var.setncattr('stable_shift_slow',np.nan)

        if stable_count != 0:
            var.setncattr('vr_error_mask',int(round(vr_error_mask*10))/10)
        else:
            var.setncattr('vr_error_mask',np.nan)
        var.setncattr('vr_error_mask_description','RMSE over stable surfaces, stationary or slow-flowing surfaces with velocity < 15 m/yr identified from an external mask')
        if stable_count1 != 0:
            var.setncattr('vr_error_slow',int(round(vr_error_slow*10))/10)
        else:
            var.setncattr('vr_error_slow',np.nan)
        var.setncattr('vr_error_slow_description','RMSE over slowest 25% of retrieved velocities')
        var.setncattr('vr_error_modeled',int(round(vr_error_mod*10))/10)
        var.setncattr('vr_error_modeled_description','1-sigma error calculated using a modeled error-dt relationship')


        var.setncattr('grid_mapping',mapping_name)

        VR[noDataMask] = NoDataValue
        var[:] = np.round(np.clip(VR, -32768, 32767)).astype(np.int16)
#        var.setncattr('missing_value',np.int16(NoDataValue))



        varname='va'
        datatype=np.dtype('int16')
        dimensions=('y','x')
        FillValue=NoDataValue
        var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)


        var.setncattr('standard_name','azimuth_velocity')
        var.setncattr('description','velocity in radar azimuth direction')
        var.setncattr('units','m/y')


        if stable_count != 0:
            temp = VA.copy()
            temp[np.logical_not(SSM)] = np.nan
            va_error_mask = np.std(temp[(temp > -500)&(temp < 500)])
        else:
            va_error_mask = np.nan
        if stable_count1 != 0:
            temp = VA.copy()
            temp[np.logical_not(SSM1)] = np.nan
            va_error_slow = np.std(temp[(temp > -500)&(temp < 500)])
        else:
            va_error_slow = np.nan
        va_error_mod = (error_vector[0][3]*IMG_INFO_DICT['date_dt']+error_vector[1][3])/IMG_INFO_DICT['date_dt']*365
        if stable_shift_applied == 1:
            va_error = va_error_mask
        elif stable_shift_applied == 2:
            va_error = va_error_slow
        else:
            va_error = va_error_mod
        var.setncattr('va_error',int(round(va_error*10))/10)
        var.setncattr('va_error_description','best estimate of azimuth_velocity error: va_error is populated according to the approach used for the velocity bias correction as indicated in "flag_stable_shift"')


        if stable_shift_applied == 2:
            var.setncattr('stable_shift',int(round(va_mean_shift1*10))/10)
        elif stable_shift_applied == 1:
            var.setncattr('stable_shift',int(round(va_mean_shift*10))/10)
        else:
            var.setncattr('stable_shift',np.nan)
        var.setncattr('flag_stable_shift',stable_shift_applied)
        var.setncattr('flag_stable_shift_description','flag for applying velocity bias correction: 0 = no correction; 1 = correction from overlapping stable surface mask (stationary or slow-flowing surfaces with velocity < 15 m/yr)(top priority); 2 = correction from slowest 25% of overlapping velocities (second priority)')

        
        var.setncattr('stable_count_mask',stable_count)
        var.setncattr('stable_count_slow',stable_count1)
        if stable_count != 0:
            var.setncattr('stable_shift_mask',int(round(va_mean_shift*10))/10)
        else:
            var.setncattr('stable_shift_mask',np.nan)
        if stable_count1 != 0:
            var.setncattr('stable_shift_slow',int(round(va_mean_shift1*10))/10)
        else:
            var.setncattr('stable_shift_slow',np.nan)

        if stable_count != 0:
            var.setncattr('va_error_mask',int(round(va_error_mask*10))/10)
        else:
            var.setncattr('va_error_mask',np.nan)
        var.setncattr('va_error_mask_description','RMSE over stable surfaces, stationary or slow-flowing surfaces with velocity < 15 m/yr identified from an external mask')
        if stable_count1 != 0:
            var.setncattr('va_error_slow',int(round(va_error_slow*10))/10)
        else:
            var.setncattr('va_error_slow',np.nan)
        var.setncattr('va_error_slow_description','RMSE over slowest 25% of retrieved velocities')
        var.setncattr('va_error_modeled',int(round(va_error_mod*10))/10)
        var.setncattr('va_error_modeled_description','1-sigma error calculated using a modeled error-dt relationship')


        var.setncattr('grid_mapping',mapping_name)

        VA[noDataMask] = NoDataValue
        var[:] = np.round(np.clip(VA, -32768, 32767)).astype(np.int16)
#        var.setncattr('missing_value',np.int16(NoDataValue))





        # fuse the (slope parallel & reference) flow-based range-projected result with the raw observed range/azimuth-based result
        if stable_count_p != 0:
            temp = VXP.copy()
            temp[np.logical_not(SSM)] = np.nan
            vxp_error_mask = np.std(temp[(temp > -500)&(temp < 500)])

            temp = VYP.copy()
            temp[np.logical_not(SSM)] = np.nan
            vyp_error_mask = np.std(temp[(temp > -500)&(temp < 500)])
        if stable_count1_p != 0:
            temp = VXP.copy()
            temp[np.logical_not(SSM1)] = np.nan
            vxp_error_slow = np.std(temp[(temp > -500)&(temp < 500)])

            temp = VYP.copy()
            temp[np.logical_not(SSM1)] = np.nan
            vyp_error_slow = np.std(temp[(temp > -500)&(temp < 500)])
        vxp_error_mod = (error_vector[0][4]*IMG_INFO_DICT['date_dt']+error_vector[1][4])/IMG_INFO_DICT['date_dt']*365
        vyp_error_mod = (error_vector[0][5]*IMG_INFO_DICT['date_dt']+error_vector[1][5])/IMG_INFO_DICT['date_dt']*365

        if stable_shift_applied_p == 1:
            vxp_error = vxp_error_mask
            vyp_error = vyp_error_mask
        elif stable_shift_applied_p == 2:
            vxp_error = vxp_error_slow
            vyp_error = vyp_error_slow
        else:
            vxp_error = vxp_error_mod
            vyp_error = vyp_error_mod
        
        VP_error = np.sqrt((vxp_error * VXP / VP)**2 + (vyp_error * VYP / VP)**2)


        VXPP[V_error > VP_error] = VXP[V_error > VP_error]
        VYPP[V_error > VP_error] = VYP[V_error > VP_error]
        VXP = VXPP.astype(np.float32)
        VYP = VYPP.astype(np.float32)
        VP = np.sqrt(VXP**2+VYP**2)


        stable_count_p = np.sum(SSM & np.logical_not(np.isnan(VXP)))
        stable_count1_p = np.sum(SSM1 & np.logical_not(np.isnan(VXP)))

        vxp_mean_shift = 0.0
        vyp_mean_shift = 0.0
        vxp_mean_shift1 = 0.0
        vyp_mean_shift1 = 0.0
        
        if stable_count_p != 0:
            temp = VXP.copy() - VX.copy()
            temp[np.logical_not(SSM)] = np.nan
            bias_mean_shift = np.median(temp[(temp > -500)&(temp < 500)])
            vxp_mean_shift = vx_mean_shift + bias_mean_shift / 2
            
            temp = VYP.copy() - VY.copy()
            temp[np.logical_not(SSM)] = np.nan
            bias_mean_shift = np.median(temp[(temp > -500)&(temp < 500)])
            vyp_mean_shift = vy_mean_shift + bias_mean_shift / 2

        if stable_count1_p != 0:
            temp = VXP.copy() - VX.copy()
            temp[np.logical_not(SSM1)] = np.nan
            bias_mean_shift1 = np.median(temp[(temp > -500)&(temp < 500)])
            vxp_mean_shift1 = vx_mean_shift1 + bias_mean_shift1 / 2
            
            temp = VYP.copy() - VY.copy()
            temp[np.logical_not(SSM1)] = np.nan
            bias_mean_shift1 = np.median(temp[(temp > -500)&(temp < 500)])
            vyp_mean_shift1 = vy_mean_shift1 + bias_mean_shift1 / 2
        
        if stable_count_p == 0:
            if stable_count1_p == 0:
                stable_shift_applied_p = 0
            else:
                stable_shift_applied_p = 2
        else:
            stable_shift_applied_p = 1







        varname='vxp'
        datatype=np.dtype('int16')
        dimensions=('y','x')
        FillValue=NoDataValue
        var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)


        var.setncattr('standard_name','projected_x_velocity')
        var.setncattr('description','x-direction velocity determined by projecting radar range measurements onto an a priori flow vector. Where projected errors are larger than those determined from range and azimuth measurements, unprojected vx estimates are used')
        var.setncattr('units','m/y')


        if stable_count_p != 0:
            temp = VXP.copy()
            temp[np.logical_not(SSM)] = np.nan
            vxp_error_mask = np.std(temp[(temp > -500)&(temp < 500)])
        else:
            vxp_error_mask = np.nan
        if stable_count1_p != 0:
            temp = VXP.copy()
            temp[np.logical_not(SSM1)] = np.nan
            vxp_error_slow = np.std(temp[(temp > -500)&(temp < 500)])
        else:
            vxp_error_slow = np.nan
        if stable_shift_applied_p == 1:
            vxp_error = vxp_error_mask
        elif stable_shift_applied_p == 2:
            vxp_error = vxp_error_slow
        else:
            vxp_error = vxp_error_mod
        var.setncattr('vxp_error',int(round(vxp_error*10))/10)
        var.setncattr('vxp_error_description','best estimate of projected_x_velocity error: vxp_error is populated according to the approach used for the velocity bias correction as indicated in "flag_stable_shift"')


        if stable_shift_applied_p == 2:
            var.setncattr('stable_shift',int(round(vxp_mean_shift1*10))/10)
        elif stable_shift_applied_p == 1:
            var.setncattr('stable_shift',int(round(vxp_mean_shift*10))/10)
        else:
            var.setncattr('stable_shift',np.nan)
        var.setncattr('flag_stable_shift',stable_shift_applied_p)
        var.setncattr('flag_stable_shift_description','flag for applying velocity bias correction: 0 = no correction; 1 = correction from overlapping stable surface mask (stationary or slow-flowing surfaces with velocity < 15 m/yr)(top priority); 2 = correction from slowest 25% of overlapping velocities (second priority)')


        var.setncattr('stable_count_mask',stable_count_p)
        var.setncattr('stable_count_slow',stable_count1_p)
        if stable_count_p != 0:
            var.setncattr('stable_shift_mask',int(round(vxp_mean_shift*10))/10)
        else:
            var.setncattr('stable_shift_mask',np.nan)
        if stable_count1_p != 0:
            var.setncattr('stable_shift_slow',int(round(vxp_mean_shift1*10))/10)
        else:
            var.setncattr('stable_shift_slow',np.nan)

        if stable_count_p != 0:
            var.setncattr('vxp_error_mask',int(round(vxp_error_mask*10))/10)
        else:
            var.setncattr('vxp_error_mask',np.nan)
        var.setncattr('vxp_error_mask_description','RMSE over stable surfaces, stationary or slow-flowing surfaces with velocity < 15 m/yr identified from an external mask')
        if stable_count1_p != 0:
            var.setncattr('vxp_error_slow',int(round(vxp_error_slow*10))/10)
        else:
            var.setncattr('vxp_error_slow',np.nan)
        var.setncattr('vxp_error_slow_description','RMSE over slowest 25% of retrieved velocities')
        var.setncattr('vxp_error_modeled',int(round(vxp_error_mod*10))/10)
        var.setncattr('vxp_error_modeled_description','1-sigma error calculated using a modeled error-dt relationship')
        

        var.setncattr('grid_mapping',mapping_name)

        VXP[noDataMask] = NoDataValue
        var[:] = np.round(np.clip(VXP, -32768, 32767)).astype(np.int16)
#        var.setncattr('missing_value',np.int16(NoDataValue))






        varname='vyp'
        datatype=np.dtype('int16')
        dimensions=('y','x')
        FillValue=NoDataValue
        var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)


        var.setncattr('standard_name','projected_y_velocity')
        var.setncattr('description','y-direction velocity determined by projecting radar range measurements onto an a priori flow vector. Where projected errors are larger than those determined from range and azimuth measurements, unprojected vy estimates are used')
        var.setncattr('units','m/y')


        if stable_count_p != 0:
            temp = VYP.copy()
            temp[np.logical_not(SSM)] = np.nan
            vyp_error_mask = np.std(temp[(temp > -500)&(temp < 500)])
        else:
            vyp_error_mask = np.nan
        if stable_count1_p != 0:
            temp = VYP.copy()
            temp[np.logical_not(SSM1)] = np.nan
            vyp_error_slow = np.std(temp[(temp > -500)&(temp < 500)])
        else:
            vyp_error_slow = np.nan
        if stable_shift_applied_p == 1:
            vyp_error = vyp_error_mask
        elif stable_shift_applied_p == 2:
            vyp_error = vyp_error_slow
        else:
            vyp_error = vyp_error_mod
        var.setncattr('vyp_error',int(round(vyp_error*10))/10)
        var.setncattr('vyp_error_description','best estimate of projected_y_velocity error: vyp_error is populated according to the approach used for the velocity bias correction as indicated in "flag_stable_shift"')


        if stable_shift_applied_p == 2:
            var.setncattr('stable_shift',int(round(vyp_mean_shift1*10))/10)
        elif stable_shift_applied_p == 1:
            var.setncattr('stable_shift',int(round(vyp_mean_shift*10))/10)
        else:
            var.setncattr('stable_shift',np.nan)
        var.setncattr('flag_stable_shift',stable_shift_applied_p)
        var.setncattr('flag_stable_shift_description','flag for applying velocity bias correction: 0 = no correction; 1 = correction from overlapping stable surface mask (stationary or slow-flowing surfaces with velocity < 15 m/yr)(top priority); 2 = correction from slowest 25% of overlapping velocities (second priority)')


        var.setncattr('stable_count_mask',stable_count_p)
        var.setncattr('stable_count_slow',stable_count1_p)
        if stable_count_p != 0:
            var.setncattr('stable_shift_mask',int(round(vyp_mean_shift*10))/10)
        else:
            var.setncattr('stable_shift_mask',np.nan)
        if stable_count1_p != 0:
            var.setncattr('stable_shift_slow',int(round(vyp_mean_shift1*10))/10)
        else:
            var.setncattr('stable_shift_slow',np.nan)

        if stable_count_p != 0:
            var.setncattr('vyp_error_mask',int(round(vyp_error_mask*10))/10)
        else:
            var.setncattr('vyp_error_mask',np.nan)
        var.setncattr('vyp_error_mask_description','RMSE over stable surfaces, stationary or slow-flowing surfaces with velocity < 15 m/yr identified from an external mask')
        if stable_count1_p != 0:
            var.setncattr('vyp_error_slow',int(round(vyp_error_slow*10))/10)
        else:
            var.setncattr('vyp_error_slow',np.nan)
        var.setncattr('vyp_error_slow_description','RMSE over slowest 25% of retrieved velocities')
        var.setncattr('vyp_error_modeled',int(round(vyp_error_mod*10))/10)
        var.setncattr('vyp_error_modeled_description','1-sigma error calculated using a modeled error-dt relationship')


        var.setncattr('grid_mapping',mapping_name)

        VYP[noDataMask] = NoDataValue
        var[:] = np.round(np.clip(VYP, -32768, 32767)).astype(np.int16)
#        var.setncattr('missing_value',np.int16(NoDataValue))






        varname='vp'
        datatype=np.dtype('int16')
        dimensions=('y','x')
        FillValue=NoDataValue
        var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)
        var.setncattr('standard_name','projected_velocity')
        var.setncattr('description','velocity magnitude determined by projecting radar range measurements onto an a priori flow vector. Where projected errors are larger than those determined from range and azimuth measurements, unprojected v estimates are used')
        var.setncattr('units','m/y')

        var.setncattr('grid_mapping',mapping_name)

        VP[noDataMask] = NoDataValue
        var[:] = np.round(np.clip(VP, -32768, 32767)).astype(np.int16)
#        var.setncattr('missing_value',np.int16(NoDataValue))





        vp_error = v_error_cal(vxp_error, vyp_error)
        varname='vp_error'
        datatype=np.dtype('int16')
        dimensions=('y','x')
        FillValue=NoDataValue
        var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)
        var.setncattr('standard_name','projected_velocity_error')
        var.setncattr('description','velocity magnitude error determined by projecting radar range measurements onto an a priori flow vector. Where projected errors are larger than those determined from range and azimuth measurements, unprojected v_error estimates are used')
        var.setncattr('units','m/y')

        var.setncattr('grid_mapping',mapping_name)

        VP_error = np.sqrt((vxp_error * VXP / VP)**2 + (vyp_error * VYP / VP)**2)
        VP_error[VP==0] = vp_error
        VP_error[noDataMask] = NoDataValue
        var[:] = np.round(np.clip(VP_error, -32768, 32767)).astype(np.int16)
#        var.setncattr('missing_value',np.int16(NoDataValue))





    varname='chip_size_width'
    datatype=np.dtype('uint16')
    dimensions=('y','x')
    FillValue=0
    var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)
    
    var.setncattr('standard_name','chip_size_width')
    var.setncattr('description','width of search window')
    var.setncattr('units','m')
    
    if pair_type is 'radar':
        var.setncattr('range_pixel_size',rangePixelSize)
        var.setncattr('chip_size_coordinates','radar geometry: width = range, height = azimuth')
    else:
        var.setncattr('x_pixel_size',rangePixelSize)
        var.setncattr('chip_size_coordinates','image projection geometry: width = x, height = y')

    var.setncattr('grid_mapping',mapping_name)
    # var[:] = np.flipud(vx_nomask).astype('float32')
    var[:] = np.round(np.clip(CHIPSIZEX, 0, 65535)).astype('uint16')
#    var.setncattr('missing_value',np.uint16(0))





    varname='chip_size_height'
    datatype=np.dtype('uint16')
    dimensions=('y','x')
    FillValue=0
    var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)

    var.setncattr('standard_name','chip_size_height')
    var.setncattr('description','height of search window')
    var.setncattr('units','m')

    if pair_type is 'radar':
        var.setncattr('azimuth_pixel_size',azimuthPixelSize)
        var.setncattr('chip_size_coordinates','radar geometry: width = range, height = azimuth')
    else:
        var.setncattr('y_pixel_size',azimuthPixelSize)
        var.setncattr('chip_size_coordinates','image projection geometry: width = x, height = y')

    var.setncattr('grid_mapping',mapping_name)

    # var[:] = np.flipud(vx_nomask).astype('float32')
    var[:] = np.round(np.clip(CHIPSIZEY, 0, 65535)).astype('uint16')
#    var.setncattr('missing_value',np.uint16(0))





    varname='interp_mask'
    datatype=np.dtype('uint8')
    dimensions=('y','x')
#    FillValue=None
    FillValue=0
    var = nc_outfile.createVariable(varname,datatype,dimensions, fill_value=FillValue, zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)

    var.setncattr('standard_name','interpolated_value_mask')
    var.setncattr('description','light interpolation mask')
    var.setncattr('units','binary')
    
    var.setncattr('grid_mapping',mapping_name)

    # var[:] = np.flipud(vx_nomask).astype('float32')
    var[:] = np.round(np.clip(INTERPMASK, 0, 255)).astype('uint8')
#    var.setncattr('missing_value',np.uint8(0))

    nc_outfile.sync() # flush data to disk
    nc_outfile.close()



#if __name__ == '__main__':
#
#        inps = cmdLineParse()
#
#        print (time.strftime("%H:%M:%S"))
#        from topsApp import TopsInSAR
#        insar = TopsInSAR(name="topsApp")
#
#
##        pdb.set_trace()
#
#        rangePixelSize = float(str.split(runCmd('fgrep "Range:" testGeogrid.txt'))[2])
#        prf = float(str.split(runCmd('fgrep "Azimuth:" testGeogrid.txt'))[2])
#        dt = float(str.split(runCmd('fgrep "Repeat Time:" testGeogrid.txt'))[2])
#        epsg = float(str.split(runCmd('fgrep "EPSG:" testGeogrid.txt'))[1])
#        satv = np.array([float(str.split(runCmd('fgrep "Center Satellite Velocity:" testGeogrid.txt'))[3]), float(str.split(runCmd('fgrep "Center Satellite Velocity:" testGeogrid.txt'))[4]), float(str.split(runCmd('fgrep "Center Satellite Velocity:" testGeogrid.txt'))[5])])
#        print (str(rangePixelSize)+"      "+str(prf)+"      "+str(satv)+"      "+str(dt))
#        azimuthPixelSize = np.sqrt(np.sum(satv**2)) / prf
#        print (str(rangePixelSize)+"      "+str(azimuthPixelSize))




        

