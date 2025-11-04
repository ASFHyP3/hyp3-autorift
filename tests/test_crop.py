import numpy as np

from hyp3_autorift import crop
from hyp3_autorift.crop import CHUNK_SIZE, PIXEL_SIZE


# Equivalent to baseline differences in the range of -600m to 600m
OFFSETS = np.arange(-5 * PIXEL_SIZE, 5 * PIXEL_SIZE, PIXEL_SIZE)
GRID_SPACING = CHUNK_SIZE * PIXEL_SIZE
TEST_VALS = [0, GRID_SPACING, -1203402.3, 320.5, 3125638.7]


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
    ref1_x_min = 491572.500
    ref1_y_min = 4362187.500
    ref1_x_max = 798772.500
    ref1_y_max = 4669387.500

    ref2_x_min = -3179707.5
    ref2_y_min = 1058347.5
    ref2_x_max = -2755267.5
    ref2_y_max = 665107.5

    ref1_aligned, _, ref1_x_values, ref1_y_values = crop.get_alignment_info(
        ref1_x_min, ref1_y_min, ref1_x_max, ref1_y_max
    )
    ref2_aligned, _, ref2_x_values, ref2_y_values = crop.get_alignment_info(
        ref2_x_min, ref2_y_min, ref2_x_max, ref2_y_max
    )

    for x_offset in OFFSETS:
        for y_offset in OFFSETS:
            sec_aligned, _, sec_x_values, sec_y_values = crop.get_alignment_info(
                ref1_x_min + x_offset, ref1_y_min + y_offset, ref1_x_max + x_offset, ref1_y_max + y_offset
            )

            for ref, sec in zip(ref1_aligned, sec_aligned):
                assert (ref - sec) % CHUNK_SIZE == 0

            assert np.all(ref1_x_values) == np.all(sec_x_values)
            assert np.all(ref1_y_values) == np.all(sec_y_values)

            sec_aligned, _, sec_x_values, sec_y_values = crop.get_alignment_info(
                ref2_x_min + x_offset, ref2_y_min + y_offset, ref2_x_max + x_offset, ref2_y_max + y_offset
            )

            assert ref2_aligned == sec_aligned

            assert np.all(ref2_x_values) == np.all(sec_x_values)
            assert np.all(ref2_y_values) == np.all(sec_y_values)
