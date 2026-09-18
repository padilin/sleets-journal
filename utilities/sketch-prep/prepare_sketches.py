#!/usr/bin/env python3
"""Prepare photographed pencil sketches for archival and web use."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


@dataclass(frozen=True)
class Detection:
    corners: np.ndarray | None
    confidence: float
    method: str


@dataclass(frozen=True)
class ContentDetection:
    bounds: tuple[int, int, int, int] | None
    confidence: float
    mask: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect, rectify, and render natural and clean versions of photographed sketches."
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="Image files or directories to process")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("config.yaml"),
        help="YAML configuration file (default: config.yaml beside this script)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("output"),
        help="Output directory (default: output beside this script)",
    )
    parser.add_argument("--force", action="store_true", help="Replace existing output folders")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    for section in ("processing", "natural", "clean", "cutout"):
        if section not in config or not isinstance(config[section], dict):
            raise ValueError(f"Missing mapping in configuration: {section}")
    config.setdefault("overrides", {})
    config["_config_directory"] = str(path.resolve().parent)
    return config


def override_path(config: dict[str, Any], source: Path) -> Path:
    return Path(config["_config_directory"]) / "overrides" / f"{source.name}.yaml"


def load_override(config: dict[str, Any], source: Path) -> dict[str, Any]:
    override = dict(config["overrides"].get(source.name, {}))
    sidecar = override_path(config, source)
    if sidecar.exists():
        with sidecar.open("r", encoding="utf-8") as handle:
            sidecar_data = yaml.safe_load(handle) or {}
        if not isinstance(sidecar_data, dict):
            raise ValueError(f"Manual override must be a mapping: {sidecar}")
        override.update(sidecar_data)
    return override


def validate_manual_bounds(bounds: Iterable[int], width: int, height: int) -> tuple[int, int, int, int]:
    values = tuple(int(value) for value in bounds)
    if len(values) != 4:
        raise ValueError("Manual bounds must contain left, top, right, and bottom")
    left, top, right, bottom = values
    if left < 0 or top < 0 or right > width or bottom > height:
        raise ValueError(f"Manual bounds {list(values)} exceed the oriented image dimensions {width}x{height}")
    if right - left < 20 or bottom - top < 20:
        raise ValueError("Manual crop must be at least 20 by 20 pixels")
    return values


def collect_inputs(paths: Iterable[Path], output_root: Path) -> list[Path]:
    found: list[Path] = []
    resolved_output = output_root.resolve()
    for path in paths:
        resolved = path.resolve()
        if resolved.is_file() and resolved.suffix.lower() in SUPPORTED_EXTENSIONS:
            found.append(resolved)
        elif resolved.is_dir():
            for candidate in sorted(resolved.rglob("*")):
                if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                    try:
                        candidate.resolve().relative_to(resolved_output)
                    except ValueError:
                        found.append(candidate.resolve())
        else:
            raise FileNotFoundError(f"No supported image or directory found at {path}")
    return list(dict.fromkeys(found))


def read_oriented_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        return np.asarray(image)


def rotate_clockwise(image: np.ndarray, degrees: int) -> np.ndarray:
    degrees %= 360
    if degrees == 0:
        return image.copy()
    rotations = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    if degrees not in rotations:
        raise ValueError("rotation_degrees_clockwise must be one of 0, 90, 180, or 270")
    return cv2.rotate(image, rotations[degrees])


def order_corners(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float32).reshape(4, 2)
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(-1)
    return np.array(
        [points[np.argmin(sums)], points[np.argmin(differences)], points[np.argmax(sums)], points[np.argmax(differences)]],
        dtype=np.float32,
    )


def right_angle_score(corners: np.ndarray) -> float:
    scores: list[float] = []
    ordered = order_corners(corners)
    for index in range(4):
        previous = ordered[(index - 1) % 4] - ordered[index]
        following = ordered[(index + 1) % 4] - ordered[index]
        denominator = np.linalg.norm(previous) * np.linalg.norm(following)
        if denominator == 0:
            return 0.0
        cosine = abs(float(np.dot(previous, following) / denominator))
        scores.append(max(0.0, 1.0 - cosine))
    return float(np.mean(scores))


def detect_page(image_rgb: np.ndarray, settings: dict[str, Any]) -> Detection:
    height, width = image_rgb.shape[:2]
    maximum = int(settings["detection_max_dimension"])
    scale = min(1.0, maximum / max(height, width))
    preview = cv2.resize(image_rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(preview, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    median = float(np.median(blurred))
    lower = int(max(0, 0.55 * median))
    upper = int(min(255, max(lower + 1, 1.35 * median)))
    edges = cv2.Canny(blurred, lower, upper)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = preview.shape[0] * preview.shape[1]
    minimum_ratio = float(settings["minimum_page_area_ratio"])
    best: tuple[float, np.ndarray] | None = None

    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:30]:
        perimeter = cv2.arcLength(contour, True)
        approximation = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approximation) != 4 or not cv2.isContourConvex(approximation):
            continue
        area_ratio = cv2.contourArea(approximation) / image_area
        if area_ratio < minimum_ratio:
            continue
        corners = order_corners(approximation.reshape(4, 2))
        rectangle = cv2.minAreaRect(corners)
        box_area = rectangle[1][0] * rectangle[1][1]
        rectangularity = 0.0 if box_area == 0 else min(1.0, cv2.contourArea(corners) / box_area)
        angles = right_angle_score(corners)
        area_score = min(1.0, area_ratio / 0.72)
        confidence = 0.45 * area_score + 0.30 * rectangularity + 0.25 * angles
        if best is None or confidence > best[0]:
            best = (confidence, corners / scale)

    if best is None:
        return Detection(None, 0.0, "full-frame-fallback")
    return Detection(order_corners(best[1]), float(best[0]), "automatic-contour")


def detect_content(image_rgb: np.ndarray, settings: dict[str, Any]) -> ContentDetection:
    """Find the densest connected group of locally dark, stroke-like marks."""
    height, width = image_rgb.shape[:2]
    maximum = int(settings["detection_max_dimension"])
    scale = min(1.0, maximum / max(height, width))
    preview = cv2.resize(image_rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(preview, cv2.COLOR_RGB2GRAY)

    sigma = max(15.0, max(gray.shape) / 35.0)
    local_background = cv2.GaussianBlur(gray, (0, 0), sigmaX=sigma, sigmaY=sigma)
    darkness = cv2.subtract(local_background, gray)
    threshold = int(settings["content_darkness_threshold"])
    raw_mask = np.where(darkness >= threshold, 255, 0).astype(np.uint8)

    line_length = round(max(preview.shape) * 0.16)
    detected_lines = cv2.HoughLinesP(
        raw_mask,
        rho=1,
        theta=np.pi / 180,
        threshold=max(35, line_length // 4),
        minLineLength=line_length,
        maxLineGap=round(max(preview.shape) * 0.025),
    )
    if detected_lines is not None:
        # Be conservative: a broad erasure can mistake long intentional pencil
        # contours for environmental lines. Manual mode can refine the rare
        # nearby seam later without risking lost artwork in a batch.
        erase_width = max(7, round(max(preview.shape) * 0.007))
        for line in detected_lines[:, 0]:
            x1, y1, x2, y2 = (int(value) for value in line)
            cv2.line(raw_mask, (x1, y1), (x2, y2), 0, erase_width)

    # Frame edges and notebook/page boundaries are often darker than the
    # drawing. Remove border-touching and extremely long thin components before
    # grouping nearby pencil strokes.
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(raw_mask, connectivity=8)
    stroke_mask = np.zeros_like(raw_mask)
    preview_area = preview.shape[0] * preview.shape[1]
    minimum_area = max(3, round(preview_area * 0.000002))
    border_x = max(2, round(preview.shape[1] * 0.01))
    border_y = max(2, round(preview.shape[0] * 0.01))
    for label in range(1, component_count):
        x, y, component_width, component_height, area = stats[label]
        if area < minimum_area:
            continue
        aspect = max(component_width / max(component_height, 1), component_height / max(component_width, 1))
        long_line = aspect > 12 and (
            component_width > preview.shape[1] * 0.22 or component_height > preview.shape[0] * 0.22
        )
        touches_frame = (
            x <= border_x
            or y <= border_y
            or x + component_width >= preview.shape[1] - border_x
            or y + component_height >= preview.shape[0] - border_y
        )
        if long_line or touches_frame:
            continue
        stroke_mask[labels == label] = 255

    grouping_size = max(9, round(max(preview.shape) * float(settings["content_grouping_radius"])))
    if grouping_size % 2 == 0:
        grouping_size += 1
    grouping_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grouping_size, grouping_size))
    grouped = cv2.dilate(stroke_mask, grouping_kernel, iterations=1)
    group_count, group_labels, group_stats, _ = cv2.connectedComponentsWithStats(grouped, connectivity=8)

    best_label = 0
    best_score = 0.0
    best_ink = 0
    for label in range(1, group_count):
        x, y, group_width, group_height, _ = group_stats[label]
        region = group_labels[y : y + group_height, x : x + group_width] == label
        ink = int(np.count_nonzero(stroke_mask[y : y + group_height, x : x + group_width][region]))
        if ink == 0:
            continue
        span_bonus = 1.0 + min(0.6, (group_width * group_height) / preview_area)
        score = ink * span_bonus
        if score > best_score:
            best_label = label
            best_score = score
            best_ink = ink

    diagnostic_mask = cv2.cvtColor(stroke_mask, cv2.COLOR_GRAY2RGB)
    if best_label == 0:
        return ContentDetection(None, 0.0, diagnostic_mask)

    selected = np.where(group_labels == best_label, 255, 0).astype(np.uint8)
    selected_strokes = cv2.bitwise_and(stroke_mask, selected)
    y_values, x_values = np.where(selected_strokes > 0)
    # Robust bounds prevent a few connected paper fibers or residual seam
    # fragments from determining the whole crop. Padding restores breathing
    # room around faint outer strokes after the percentile trim.
    left, right = (int(value) for value in np.percentile(x_values, (2.0, 98.0)))
    top, bottom = (int(value) for value in np.percentile(y_values, (2.0, 98.0)))
    right += 1
    bottom += 1
    padding = round(min(right - left, bottom - top) * float(settings["content_padding"]))
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(preview.shape[1], right + padding)
    bottom = min(preview.shape[0], bottom + padding)

    confidence = min(1.0, best_ink / max(1.0, preview_area * 0.006))
    bounds = (
        round(left / scale),
        round(top / scale),
        round(right / scale),
        round(bottom / scale),
    )
    return ContentDetection(bounds, confidence, diagnostic_mask)


def warp_page(image_rgb: np.ndarray, corners: np.ndarray) -> np.ndarray:
    top_left, top_right, bottom_right, bottom_left = order_corners(corners)
    width = int(round(max(np.linalg.norm(top_right - top_left), np.linalg.norm(bottom_right - bottom_left))))
    height = int(round(max(np.linalg.norm(bottom_left - top_left), np.linalg.norm(bottom_right - top_right))))
    width = max(width, 2)
    height = max(height, 2)
    destination = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(order_corners(corners), destination)
    return cv2.warpPerspective(image_rgb, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def percentile_stretch(channel: np.ndarray, lower: float = 1.0, upper: float = 99.0) -> np.ndarray:
    low, high = np.percentile(channel, (lower, upper))
    if high <= low:
        return channel.copy()
    stretched = (channel.astype(np.float32) - low) * (255.0 / (high - low))
    return np.clip(stretched, 0, 255).astype(np.uint8)


def correct_lightness(lightness: np.ndarray, strength: float, target: float = 238.0) -> np.ndarray:
    sigma = max(15.0, min(lightness.shape) / 22.0)
    background = cv2.GaussianBlur(lightness, (0, 0), sigmaX=sigma, sigmaY=sigma)
    corrected = lightness.astype(np.float32) * target / np.maximum(background.astype(np.float32), 1.0)
    corrected = np.clip(corrected, 0, 255).astype(np.uint8)
    return cv2.addWeighted(lightness, 1.0 - strength, corrected, strength, 0)


def render_natural(master_rgb: np.ndarray, settings: dict[str, Any]) -> Image.Image:
    lab = cv2.cvtColor(master_rgb, cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = correct_lightness(lab[:, :, 0], float(settings["illumination_correction"]))
    corrected = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    image = Image.fromarray(corrected)
    image = ImageEnhance.Color(image).enhance(float(settings["saturation"]))
    image = ImageEnhance.Contrast(image).enhance(float(settings["contrast"]))
    sharpen = float(settings["sharpen"])
    if sharpen > 0:
        image = image.filter(ImageFilter.UnsharpMask(radius=1.1, percent=round(100 * sharpen), threshold=3))
    return image


def clean_grayscale(master_rgb: np.ndarray, settings: dict[str, Any]) -> np.ndarray:
    gray = cv2.cvtColor(master_rgb, cv2.COLOR_RGB2GRAY)
    sigma = max(21.0, min(gray.shape) / 18.0)
    background = cv2.GaussianBlur(gray, (0, 0), sigmaX=sigma, sigmaY=sigma)
    target = float(settings["background_value"])
    normalized = gray.astype(np.float32) * target / np.maximum(background.astype(np.float32), 1.0)
    normalized = np.clip(normalized, 0, 255).astype(np.uint8)
    # Set a stable white point without pulling the darkest paper fibers down to
    # black. A full contrast stretch makes pencil darker, but also exaggerates
    # every bit of paper grain.
    white_point = max(1.0, float(np.percentile(normalized, 99.5)))
    normalized = np.clip(normalized.astype(np.float32) * (250.0 / white_point), 0, 255).astype(np.uint8)
    clahe = cv2.createCLAHE(clipLimit=float(settings["clahe_clip_limit"]), tileGridSize=(8, 8))
    return clahe.apply(normalized)


def find_content_bounds(gray: np.ndarray, padding_ratio: float) -> tuple[int, int, int, int]:
    height, width = gray.shape
    threshold = min(218, int(np.median(gray) - 18))
    mask = (gray < threshold).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    minimum_area = max(24, int(height * width * 0.00001))
    keep = np.zeros_like(mask)
    for label in range(1, count):
        if stats[label, cv2.CC_STAT_AREA] >= minimum_area:
            keep[labels == label] = 255
    y_values, x_values = np.where(keep > 0)
    if len(x_values) < 20:
        return 0, 0, width, height
    left, right = int(x_values.min()), int(x_values.max()) + 1
    top, bottom = int(y_values.min()), int(y_values.max()) + 1
    padding = round(max(right - left, bottom - top) * padding_ratio)
    return max(0, left - padding), max(0, top - padding), min(width, right + padding), min(height, bottom + padding)


def render_clean(master_rgb: np.ndarray, settings: dict[str, Any]) -> tuple[Image.Image, tuple[int, int, int, int]]:
    gray = clean_grayscale(master_rgb, settings)
    bounds = find_content_bounds(gray, float(settings["content_padding"]))
    left, top, right, bottom = bounds
    image = Image.fromarray(gray[top:bottom, left:right])
    image = ImageEnhance.Contrast(image).enhance(float(settings["contrast"]))
    sharpen = float(settings["sharpen"])
    if sharpen > 0:
        image = image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=round(100 * sharpen), threshold=2))
    return image.convert("RGB"), bounds


def parse_hex_color(value: str) -> tuple[int, int, int]:
    color = value.removeprefix("#")
    if len(color) != 6:
        raise ValueError(f"Expected a six-digit hex color, received {value!r}")
    try:
        return tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError as error:
        raise ValueError(f"Invalid hex color: {value!r}") from error


def render_cutout(
    master_rgb: np.ndarray,
    cutout_settings: dict[str, Any],
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    gray = cv2.cvtColor(master_rgb, cv2.COLOR_RGB2GRAY)
    sigma = max(15.0, min(gray.shape) / 18.0)
    local_background = cv2.GaussianBlur(gray, (0, 0), sigmaX=sigma, sigmaY=sigma)
    darkness = np.maximum(local_background.astype(np.float32) - gray.astype(np.float32), 0.0)
    noise_floor = float(cutout_settings["noise_floor"])
    full_opacity = float(cutout_settings["full_opacity"])
    if full_opacity <= noise_floor:
        raise ValueError("cutout.full_opacity must be greater than cutout.noise_floor")

    opacity = np.clip((darkness - noise_floor) / (full_opacity - noise_floor), 0.0, 1.0)
    opacity = np.power(opacity, float(cutout_settings["opacity_gamma"]))
    alpha = np.round(opacity * 255.0).astype(np.uint8)
    alpha[alpha < 5] = 0

    # Remove isolated paper flecks while keeping connected pencil strokes.
    binary = np.where(alpha > 0, 255, 0).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    minimum_area = max(6, round(alpha.shape[0] * alpha.shape[1] * 0.000003))
    retained = np.zeros_like(alpha)
    for label in range(1, count):
        x, y, component_width, component_height, area = stats[label]
        touches_border = (
            x <= 1
            or y <= 1
            or x + component_width >= alpha.shape[1] - 1
            or y + component_height >= alpha.shape[0] - 1
        )
        aspect = max(component_width / max(component_height, 1), component_height / max(component_width, 1))
        border_line = touches_border and aspect > 8 and (
            component_width > alpha.shape[1] * 0.20 or component_height > alpha.shape[0] * 0.20
        )
        if area >= minimum_area and not border_line:
            retained[labels == label] = alpha[labels == label]
    alpha = retained

    y_values, x_values = np.where(alpha > 0)
    if len(x_values) == 0:
        bounds = (0, 0, alpha.shape[1], alpha.shape[0])
    else:
        left, right = int(x_values.min()), int(x_values.max()) + 1
        top, bottom = int(y_values.min()), int(y_values.max()) + 1
        padding = round(min(right - left, bottom - top) * float(cutout_settings["content_padding"]))
        bounds = (
            max(0, left - padding),
            max(0, top - padding),
            min(alpha.shape[1], right + padding),
            min(alpha.shape[0], bottom + padding),
        )

    red, green, blue = parse_hex_color(str(cutout_settings["ink_color"]))
    rgba = np.empty((*alpha.shape, 4), dtype=np.uint8)
    rgba[:, :, 0] = red
    rgba[:, :, 1] = green
    rgba[:, :, 2] = blue
    rgba[:, :, 3] = alpha
    left, top, right, bottom = bounds
    return Image.fromarray(rgba[top:bottom, left:right], mode="RGBA"), bounds


def resize_for_web(image: Image.Image, width: int) -> Image.Image:
    if image.width <= width:
        return image.copy()
    height = round(image.height * width / image.width)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def make_comparison(natural: Image.Image, clean: Image.Image, cutout: Image.Image) -> Image.Image:
    panel_width = 600
    label_height = 60
    panels: list[Image.Image] = []
    for label, source in (("Natural page", natural), ("Clean sketch", clean), ("Transparent cutout", cutout)):
        image = resize_for_web(source, panel_width)
        panel = Image.new("RGB", (panel_width, image.height + label_height), "#f3f0e7")
        panel.paste(image, ((panel_width - image.width) // 2, label_height), image if image.mode == "RGBA" else None)
        draw = ImageDraw.Draw(panel)
        draw.text((24, 20), label, fill="#18252e")
        panels.append(panel)
    common_height = max(panel.height for panel in panels)
    comparison = Image.new("RGB", (panel_width * 3 + 8, common_height), "#f3f0e7")
    for index, panel in enumerate(panels):
        comparison.paste(panel, (index * (panel_width + 4), 0))
    return comparison


def debug_overlay(
    image_rgb: np.ndarray,
    corners: np.ndarray | None = None,
    bounds: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    maximum = 1800
    scale = min(1.0, maximum / max(image_rgb.shape[:2]))
    preview = cv2.resize(image_rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if corners is not None:
        points = np.round(corners * scale).astype(np.int32).reshape((-1, 1, 2))
        cv2.polylines(preview, [points], True, (29, 181, 217), max(2, round(4 * scale)))
        for index, point in enumerate(points.reshape(4, 2), start=1):
            cv2.circle(preview, tuple(point), 9, (232, 92, 55), -1)
            cv2.putText(preview, str(index), tuple(point + (12, -12)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (232, 92, 55), 2)
    if bounds is not None:
        left, top, right, bottom = (round(value * scale) for value in bounds)
        cv2.rectangle(preview, (left, top), (right, bottom), (29, 181, 217), 5)
    return Image.fromarray(preview)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_one(source: Path, output_root: Path, config: dict[str, Any], force: bool) -> dict[str, Any]:
    destination = output_root / source.stem
    if destination.exists() and any(destination.iterdir()) and not force:
        raise FileExistsError(f"{destination} already contains output; pass --force to replace generated files")
    destination.mkdir(parents=True, exist_ok=True)

    override = load_override(config, source)
    rotation = int(override.get("rotation_degrees_clockwise", 0))
    oriented = rotate_clockwise(read_oriented_rgb(source), rotation)
    mode = str(override.get("mode", config["processing"]["default_mode"]))
    threshold = float(config["processing"]["confidence_threshold"])
    corners: np.ndarray | None = None
    content_bounds: tuple[int, int, int, int] | None = None
    content_mask: np.ndarray | None = None
    if mode == "content":
        content_detection = detect_content(oriented, config["processing"])
        confidence = content_detection.confidence
        content_bounds = content_detection.bounds
        content_mask = content_detection.mask
        review_required = content_bounds is None or confidence < threshold
        geometry_applied = content_bounds is not None and not review_required
        if geometry_applied:
            left, top, right, bottom = content_bounds
            master = oriented[top:bottom, left:right]
        else:
            master = oriented
        method = "automatic-content"
    elif mode == "page":
        page_detection = detect_page(oriented, config["processing"])
        corners = page_detection.corners
        confidence = page_detection.confidence
        review_required = corners is None or confidence < threshold
        geometry_applied = corners is not None and not review_required
        master = warp_page(oriented, corners) if geometry_applied else oriented
        method = page_detection.method
    elif mode == "manual":
        content_bounds = validate_manual_bounds(override.get("bounds", []), oriented.shape[1], oriented.shape[0])
        left, top, right, bottom = content_bounds
        master = oriented[top:bottom, left:right]
        confidence = 1.0
        review_required = False
        geometry_applied = True
        method = "manual-bounds"
    else:
        raise ValueError(f"Unsupported processing mode: {mode!r}; expected 'content', 'page', or 'manual'")

    natural = render_natural(master, config["natural"])
    clean, clean_bounds = render_clean(master, config["clean"])
    cutout, cutout_bounds = render_cutout(master, config["cutout"])
    output_width = int(config["processing"]["output_width"])
    quality = int(config["processing"]["webp_quality"])
    natural_web = resize_for_web(natural, output_width)
    clean_web = resize_for_web(clean, output_width)
    cutout_web = resize_for_web(cutout, output_width)

    Image.fromarray(master).save(destination / "rectified.png", format="PNG", optimize=True)
    natural_web.save(destination / "natural.webp", format="WEBP", quality=quality, method=6)
    clean_web.save(destination / "clean.webp", format="WEBP", quality=quality, method=6)
    cutout_web.save(destination / "cutout.png", format="PNG", optimize=True)
    make_comparison(natural_web, clean_web, cutout_web).save(
        destination / "comparison.jpg", format="JPEG", quality=90, optimize=True
    )
    debug_overlay(oriented, corners=corners, bounds=content_bounds).save(
        destination / "detection-debug.jpg", format="JPEG", quality=88, optimize=True
    )
    if content_mask is not None:
        Image.fromarray(content_mask).save(destination / "content-mask.png", format="PNG", optimize=True)

    metadata = {
        "source": str(source),
        "source_sha256": file_sha256(source),
        "source_dimensions": {"width": int(oriented.shape[1]), "height": int(oriented.shape[0])},
        "rotation_degrees_clockwise": rotation,
        "detection": {
            "mode": mode,
            "method": method,
            "confidence": round(confidence, 4),
            "threshold": threshold,
            "review_required": review_required,
            "geometry_applied": geometry_applied,
            "bounds": None if content_bounds is None else list(content_bounds),
            "corners": None if corners is None else np.round(corners, 2).tolist(),
        },
        "rectified_dimensions": {"width": int(master.shape[1]), "height": int(master.shape[0])},
        "clean_content_bounds": list(clean_bounds),
        "cutout_content_bounds": list(cutout_bounds),
        "outputs": [
            "rectified.png",
            "natural.webp",
            "clean.webp",
            "cutout.png",
            "comparison.jpg",
            "detection-debug.jpg",
            *(["content-mask.png"] if content_mask is not None else []),
        ],
    }
    with (destination / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
        handle.write("\n")
    return metadata


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        sources = collect_inputs(args.inputs, args.output)
        if not sources:
            raise ValueError("No supported images found")
        failures = 0
        for source in sources:
            try:
                metadata = prepare_one(source, args.output.resolve(), config, args.force)
                review = " — review detection" if metadata["detection"]["review_required"] else ""
                print(f"Prepared {source.name}{review}")
            except Exception as error:  # continue a batch even when one source fails
                failures += 1
                print(f"Failed {source}: {error}", file=sys.stderr)
        return 1 if failures else 0
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
