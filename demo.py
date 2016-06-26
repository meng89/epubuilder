#!/usr/bin/env python3

from epubuilder.epub3 import Epub, File, Joint, Section
from epubuilder.epubpublic import Section, File, Joint

from PIL import Image

import io

img_bytes = open('test/cover/cover.svg', 'rb').read()

img = Image.open(io.BytesIO(img_bytes))

print(img.size)
