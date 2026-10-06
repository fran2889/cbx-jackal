"""Regenerate the binary fixtures. Run from tests/fixtures/.

The page JPEGs and the PNG are produced with ImageMagick; the truncated JPEG is
cut from a real page so `cjxl` rejects it exactly as it rejects a genuinely
damaged archive member. The fixture archives are built here too, so the bytes
are reproducible rather than being whatever happened to be committed.

    magick -size 600x900 ... -quality 88 page001.jpg
    python3 make_fixtures.py
"""

import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

#: An archive with three pages plus metadata, in a deliberately unsorted order
#: so order-preservation is actually exercised rather than incidentally.
SAMPLE_ENTRIES = [
    ("ComicInfo.xml", None),
    ("readme.txt", None),
    ("page002.jpg", "page002.jpg"),
    ("page001.jpg", "page001.jpg"),
    ("page003.jpg", "page003.jpg"),
]

COMIC_INFO = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<ComicInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
    b"  <Title>Fixture Book</Title>\n"
    b"  <Series>Fixture</Series>\n"
    b"  <Number>1</Number>\n"
    b"  <Pages Count=\"3\"/>\n"
    b"</ComicInfo>\n"
)
README = b"Sample fixture for cbx-jackal.\nNot a page.\n"


def main() -> None:
    with zipfile.ZipFile(os.path.join(HERE, "sample.cbz"), "w") as archive:
        for name, source in SAMPLE_ENTRIES:
            if source is None:
                data = COMIC_INFO if name.endswith(".xml") else README
            else:
                with open(os.path.join(HERE, source), "rb") as handle:
                    data = handle.read()
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, data)
    print("wrote sample.cbz")


if __name__ == "__main__":
    main()
