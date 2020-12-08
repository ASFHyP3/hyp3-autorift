from pathlib import Path
from typing import Union

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.colors import ListedColormap, Normalize

COLOR_MAP = ListedColormap(
    np.array([
        # R, G, B, A
        [255, 255, 255, 0, ],
        [166, 238, 255, 255, ],
        [97, 195, 219, 255, ],
        [84, 169, 254, 255, ],
        [84, 130, 254, 255, ],
        [84, 85, 254, 255, ],
        [50, 119, 220, 255, ],
        [16, 153, 186, 255, ],
        [16, 186, 153, 255, ],
        [50, 220, 119, 255, ],
        [84, 254, 85, 255, ],
        [118, 221, 51, 255, ],
        [153, 186, 16, 255, ],
        [187, 152, 17, 255, ],
        [221, 118, 51, 255, ],
        [255, 85, 85, 255, ],
        [255, 25, 85, 255, ],
        [213, 1, 72, 255, ],
        [158, 1, 66, 255, ],
        [140, 0, 51, 255, ],
        [122, 0, 166, 255, ],
        [140, 0, 191, 255, ],
        [159, 0, 217, 255, ],
        [213, 0, 255, 255, ],
        [255, 0, 138, 255, ],
    ]) / 256
)


def make_browse(out_name: Union[str, Path], data: np.ndarray,
                min_value: float = 0., max_value: float = 625) -> Union[str, Path]:
    norm = Normalize(vmin=min_value, vmax=max_value)
    image = COLOR_MAP(norm(data))
    plt.imsave(out_name, image, cmap=COLOR_MAP)
    return out_name
