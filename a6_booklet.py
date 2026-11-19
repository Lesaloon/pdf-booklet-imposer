#!/usr/bin/env python3
"""Impose portrait PDF pages as a folded ISO A-series booklet."""

import argparse
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter, Transformation
    from pypdf.errors import PdfReadError
except ImportError:
    raise SystemExit("Install pypdf with: python -m pip install 'pypdf>=5'") from None


POINTS_PER_MM = 72 / 25.4
A6_WIDTH = 105 * POINTS_PER_MM
A6_HEIGHT = 148 * POINTS_PER_MM
ISO_A_MM = {
    "A0": (841, 1189), "A1": (594, 841), "A2": (420, 594),
    "A3": (297, 420), "A4": (210, 297), "A5": (148, 210),
    "A6": (105, 148), "A7": (74, 105), "A8": (52, 74),
    "A9": (37, 52), "A10": (26, 37),
}
INPUT_FORMATS = tuple(f"A{i}" for i in range(1, 11))


def place_page(spread, source, slot, slot_width=A6_WIDTH, slot_height=A6_HEIGHT):
    """Fit the visible source page into the left (0) or right (1) half."""
    if source.rotation:
        source.transfer_rotation_to_content()

    box = source.cropbox
    width, height = float(box.width), float(box.height)
    if not 0 < width <= height:
        raise ValueError("Each source page must have a valid portrait page box.")

    # Accommodate PDF dimensions rounded to whole points.
    scale = min(slot_width / width, slot_height / height)
    x = slot * slot_width + (slot_width - width * scale) / 2
    y = (slot_height - height * scale) / 2
    transform = Transformation().translate(-float(box.left), -float(box.bottom))
    transform = transform.scale(scale).translate(x, y)
    spread.merge_transformed_page(source, transform)


def make_booklet(input_path, output_path, page_format="A6"):
    if page_format not in INPUT_FORMATS:
        raise ValueError("Choose an ISO A-series input format from A1 to A10.")
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Choose a different filename for the output PDF.")

    reader = PdfReader(input_path)
    if reader.is_encrypted:
        raise ValueError("Remove the PDF password before creating a booklet.")
    page_count = len(reader.pages)
    if not page_count:
        raise ValueError("The input PDF contains no pages.")

    padded_count = ((page_count + 3) // 4) * 4
    # Use the exact parent sheet dimensions (ISO sizes have rounded edges).
    sheet_format = f"A{int(page_format[1:]) - 1}"
    sheet_short, sheet_long = ISO_A_MM[sheet_format]
    sheet_width = sheet_long * POINTS_PER_MM
    sheet_height = sheet_short * POINTS_PER_MM
    writer = PdfWriter()
    for outer in range(0, padded_count // 2, 2):
        inner = padded_count - 1 - outer
        # Zero-based page indexes, with the front side followed by the back.
        for left, right in ((inner, outer), (outer + 1, inner - 1)):
            spread = writer.add_blank_page(width=sheet_width, height=sheet_height)
            for slot, index in enumerate((left, right)):
                if index < page_count:
                    place_page(spread, reader.pages[index], slot, sheet_width / 2, sheet_height)

    with output_path.open("xb") as output:
        writer.write(output)
    return padded_count // 4, padded_count - page_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="portrait PDF in reading order")
    parser.add_argument("output", type=Path, help="new landscape booklet PDF")
    parser.add_argument("--format", choices=INPUT_FORMATS, default="A6", help="source page format (default: A6)")
    args = parser.parse_args()

    try:
        sheets, blanks = make_booklet(args.input, args.output, args.format)
    except (OSError, ValueError, PdfReadError) as error:
        parser.exit(1, f"Error: {error}\n")
    print(f"Wrote {args.output} ({sheets} duplex sheet(s), {blanks} blank A6 page(s)).")


if __name__ == "__main__":
    main()
