def get_cononical_paramter_file(parameter_file):
    """Get the canonical parameter file URL from an alternate copy's URL"""
    return parameter_file.replace('.jpl.nasa.gov', '').replace('its-live-data-eu', 'its-live-data')
