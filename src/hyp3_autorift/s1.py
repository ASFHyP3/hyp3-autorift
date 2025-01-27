def get_s1_primary_polarization(granule_name):
    if '-BURST' in granule_name:
        return granule_name.split('_')[-2].lower()

    polarization = granule_name[14:16]
    if polarization in ['SV', 'DV']:
        return 'vv'
    if polarization in ['SH', 'DH']:
        return 'hh'
    raise ValueError(f'Cannot determine co-polarization of granule {granule_name}')
