import numpy as np
from PIL import Image

from hyp3_autorift import image


def test_make_browse(tmp_path):
    out_file = tmp_path / 'test.png'
    data = np.random.rand(10, 10) * 700

    image.make_browse(out_file, data)
    assert out_file.is_file()
    with Image.open(out_file) as img:
        assert img.format == 'PNG'
