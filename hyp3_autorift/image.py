from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from scipy.interpolate import PchipInterpolator

COLOR_MAP = np.array([
    # data value, R, G, B, A
    [0, 255, 255, 255, 0],
    [2, 166, 238, 255, 255],
    [4, 97, 195, 219, 255],
    [9, 84, 169, 254, 255],
    [16, 84, 130, 254, 255],
    [25, 84, 85, 254, 255],
    [36, 50, 119, 220, 255],
    [49, 16, 153, 186, 255],
    [64, 16, 186, 153, 255],
    [81, 50, 220, 119, 255],
    [100, 84, 254, 85, 255],
    [121, 118, 221, 51, 255],
    [144, 153, 186, 16, 255],
    [169, 187, 152, 17, 255],
    [196, 221, 118, 51, 255],
    [225, 255, 85, 85, 255],
    [289, 255, 25, 85, 255],
    [324, 213, 1, 72, 255],
    [361, 158, 1, 66, 255],
    [400, 140, 0, 51, 255],
    [441, 122, 0, 166, 255],
    [484, 140, 0, 191, 255],
    [529, 159, 0, 217, 255],
    [576, 213, 0, 255, 255],
    [625, 255, 0, 138, 255],
])


def make_browse(out_file: Path, data: np.ndarray,
                min_value: Optional[float] = None, max_value: Optional[float] = 625.) -> Path:
    data_values = COLOR_MAP[:, 0]
    pchip = PchipInterpolator(data_values, np.linspace(0, 1, len(data_values)))
    image = pchip(np.clip(data, min_value, max_value))

    rgb_values = COLOR_MAP[:, 1:] / 255
    cmap = LinearSegmentedColormap.from_list('its-live', rgb_values)
    plt.imsave(out_file, image, cmap=cmap)

    return out_file
