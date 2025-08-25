import numpy as np

from hyp3_autorift import crop
from hyp3_autorift.crop import CHUNK_SIZE, PIXEL_SIZE


# Equivalent to baseline differences in the range of -600m to 600m
OFFSETS = np.arange(-5 * PIXEL_SIZE, 5 * PIXEL_SIZE, PIXEL_SIZE)
GRID_SPACING = CHUNK_SIZE * PIXEL_SIZE
TEST_VALS = [0, GRID_SPACING - 1203402.3, 320.5, 3125638.7]


def test_get_aligned_min():
    for val in TEST_VALS:
        for offset in OFFSETS:
            ref_aligned, _ = crop.get_aligned_min(val, GRID_SPACING)
            sec_aligned, _ = crop.get_aligned_min(val + offset, GRID_SPACING)
            assert (ref_aligned - sec_aligned) % CHUNK_SIZE == 0


def test_get_aligned_max():
    for val in TEST_VALS:
        for offset in OFFSETS:
            ref_aligned, _ = crop.get_aligned_max(val, GRID_SPACING)
            sec_aligned, _ = crop.get_aligned_max(val + offset, GRID_SPACING)
            assert (ref_aligned - sec_aligned) % CHUNK_SIZE == 0


def test_get_alignment_info():
    ref_x_min = 491572.500
    ref_y_min = 4362187.500
    ref_x_max = 798772.500
    ref_y_max = 4669387.500

    ref_aligned, _, ref_x_values, ref_y_values = crop.get_alignment_info(ref_x_min, ref_y_min, ref_x_max, ref_y_max)

    # -600m to 600m
    offsets = np.arange(-5 * PIXEL_SIZE, 5 * PIXEL_SIZE, PIXEL_SIZE)

    for x_offset in offsets:
        for y_offset in offsets:
            sec_aligned, _, sec_x_values, sec_y_values = crop.get_alignment_info(
                ref_x_min + x_offset, ref_y_min + y_offset, ref_x_max + x_offset, ref_y_max + y_offset
            )

            assert (ref_aligned[0] - sec_aligned[0]) % CHUNK_SIZE == 0
            assert (ref_aligned[1] - sec_aligned[1]) % CHUNK_SIZE == 0
            assert (ref_aligned[2] - sec_aligned[2]) % CHUNK_SIZE == 0
            assert (ref_aligned[3] - sec_aligned[3]) % CHUNK_SIZE == 0

            assert np.all(ref_x_values) == np.all(sec_x_values)
            assert np.all(ref_y_values) == np.all(sec_y_values)
