import unittest

import cv2
import numpy as np

from prepare_sketches import (
    detect_content,
    detect_page,
    find_content_bounds,
    order_corners,
    parse_hex_color,
    render_cutout,
    validate_manual_bounds,
    warp_page,
)


class SketchPreparationTests(unittest.TestCase):
    def test_orders_corners(self):
        points = np.array([[90, 90], [10, 10], [10, 90], [90, 10]], dtype=np.float32)
        ordered = order_corners(points)
        np.testing.assert_array_equal(ordered, [[10, 10], [90, 10], [90, 90], [10, 90]])

    def test_detects_and_rectifies_synthetic_page(self):
        image = np.full((900, 1200, 3), 45, dtype=np.uint8)
        page = np.array([[180, 120], [1050, 180], [980, 790], [120, 730]], dtype=np.int32)
        cv2.fillConvexPoly(image, page, (238, 240, 236))
        cv2.line(image, (350, 350), (780, 520), (45, 45, 45), 12)
        settings = {"detection_max_dimension": 1200, "minimum_page_area_ratio": 0.20}

        detection = detect_page(image, settings)

        self.assertIsNotNone(detection.corners)
        self.assertGreater(detection.confidence, 0.58)
        rectified = warp_page(image, detection.corners)
        self.assertGreater(rectified.shape[0], 500)
        self.assertGreater(rectified.shape[1], 700)

    def test_content_bounds_include_dark_marks(self):
        image = np.full((500, 800), 245, dtype=np.uint8)
        cv2.line(image, (240, 180), (560, 320), 70, 8)

        left, top, right, bottom = find_content_bounds(image, 0.10)

        self.assertLessEqual(left, 240)
        self.assertLessEqual(top, 180)
        self.assertGreaterEqual(right, 560)
        self.assertGreaterEqual(bottom, 320)
        self.assertLess(right - left, image.shape[1])

    def test_detects_sketch_content_without_page_edges(self):
        image = np.full((900, 1400, 3), 232, dtype=np.uint8)
        cv2.line(image, (0, 90), (1399, 120), (30, 30, 30), 10)
        cv2.circle(image, (590, 430), 125, (75, 75, 75), 12)
        cv2.line(image, (520, 390), (670, 500), (90, 90, 90), 8)
        settings = {
            "detection_max_dimension": 1400,
            "content_darkness_threshold": 8,
            "content_grouping_radius": 0.065,
            "content_padding": 0.12,
        }

        detection = detect_content(image, settings)

        self.assertIsNotNone(detection.bounds)
        left, top, right, bottom = detection.bounds
        self.assertGreater(left, 300)
        self.assertGreater(top, 200)
        self.assertLess(right, 900)
        self.assertLess(bottom, 700)
        self.assertGreater(detection.confidence, 0.58)

    def test_validates_manual_bounds(self):
        self.assertEqual(validate_manual_bounds([20, 30, 500, 400], 800, 600), (20, 30, 500, 400))
        with self.assertRaisesRegex(ValueError, "exceed"):
            validate_manual_bounds([20, 30, 900, 400], 800, 600)
        with self.assertRaisesRegex(ValueError, "at least"):
            validate_manual_bounds([20, 30, 25, 35], 800, 600)

    def test_transparent_cutout_preserves_stroke_opacity(self):
        image = np.full((240, 320, 3), 245, dtype=np.uint8)
        cv2.line(image, (80, 70), (240, 170), (65, 65, 65), 10)
        cutout_settings = {
            "ink_color": "#18252e",
            "noise_floor": 12,
            "full_opacity": 70,
            "opacity_gamma": 0.75,
            "content_padding": 0.08,
        }

        cutout, bounds = render_cutout(image, cutout_settings)

        self.assertEqual(cutout.mode, "RGBA")
        self.assertEqual(parse_hex_color("#18252e"), (24, 37, 46))
        alpha = np.asarray(cutout)[:, :, 3]
        self.assertEqual(int(alpha.min()), 0)
        self.assertGreater(int(alpha.max()), 200)
        self.assertGreater(bounds[0], 0)


if __name__ == "__main__":
    unittest.main()
