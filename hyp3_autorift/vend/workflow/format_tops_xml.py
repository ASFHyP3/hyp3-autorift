#!/usr/bin/env python3

def cmdLineParse():
    '''
    Command line parser.
    '''
    import argparse

    parser = argparse.ArgumentParser(description='construct xml file for ISCE TOPS run')
    parser.add_argument('-m', '--master', dest='master', type=str, required=True,
            help='Sentinel-1 safe zipped filename')
    parser.add_argument('-s', '--slave', dest='slave', type=str, required=True,
            help='Sentinel-1 safe zipped filename')
    parser.add_argument('-d', '--dem', dest='dem', type=str, required=True,
            help='DEM filename')
    

    return parser.parse_args()




if __name__ == '__main__':
    '''
    Main driver.
    '''

    inps = cmdLineParse()

    tops_xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <topsApp>
        <component name="topsinsar">
        <component name="reference">
        <property name="orbit directory">/Users/yanglei/orbit/S1A/precise</property>
        <property name="auxiliary data directory">/Users/yanglei/orbit/S1A/aux</property>
        <property name="output directory">reference</property>
        <property name="safe">['{0}']</property>
        <property name="polarization">hh</property>
        </component>
        <component name="secondary">
        <property name="orbit directory">/Users/yanglei/orbit/S1A/precise</property>
        <property name="auxiliary data directory">/Users/yanglei/orbit/S1A/aux</property>
        <property name="output directory">secondary</property>
        <property name="safe">['{1}']</property>
        <property name="polarization">hh</property>
        </component>
        <property name="demfilename">{2}</property>
        <property name="do interferogram">False</property>
        <property name="do dense offsets">True</property>
        <property name="do ESD">False</property>
        <property name="do unwrap">False</property>
        <property name="do unwrap 2 stage">False</property>
        <property name="ampcor skip width">32</property>
        <property name="ampcor skip height">32</property>
        <property name="ampcor search window width">51</property>
        <property name="ampcor search window height">51</property>
        <property name="ampcor window width">32</property>
        <property name="ampcor window height">32</property>
        </component>
        </topsApp>
        '''.format(inps.master,inps.slave,inps.dem)
    
    fid=open('topsApp.xml','w')

    fid.write(tops_xml)

    fid.close()
