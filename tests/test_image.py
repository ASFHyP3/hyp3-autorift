import numpy as np
from PIL import Image

from hyp3_autorift import image


def test_make_browse(tmp_path):
    image_file = tmp_path / 'test.png'
    data = np.random.rand(10, 10) * 700

    out_file = image.make_browse(image_file, data)
    assert out_file == image_file
    assert out_file.is_file()

    with Image.open(out_file) as img:
        assert img.format == 'PNG'
        assert img.size == data.shape
