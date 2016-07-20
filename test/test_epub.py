import uuid
import os

import zipfile
from xml.etree import ElementTree as ET

from epubuilder.public import Joint, File

from epubuilder.public.metas.dcmes import Title, Language, Identifier

XHTML_TEMPLATE = """
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>{title}</title>
</head>
<body><p>{content}</p></body></html>
"""

cur_path = os.path.dirname(__file__)

BUILT_BOOK_DIR = '_test_built_book'
if not os.path.exists(BUILT_BOOK_DIR):
    os.makedirs(BUILT_BOOK_DIR)


def make_epub(epub, section):
    book = epub()

    # metadata
    book.metadata.append(Title('EPUB demo'))
    book.metadata.append(Language('en'))
    book.metadata.append(Identifier('identifier_' + uuid.uuid4().hex))

    # book.metadata.append(get('modified')(w3c_utc_date()))

    def make_page(title, html_path=None, content=None):
        if html_path and content:
            _file = File(XHTML_TEMPLATE.format(title=title, content=content).encode(), mime='application/xhtml+xml')
            book.files[html_path] = _file

            book.spine.append(Joint(html_path))

        sec = section(title, href=html_path)
        return sec

    sec1 = make_page('Part I', 'Part_I.xhtml',  content='This is Part I content')
    sec1_1 = make_page('Chapter 1', 'pi_c1.xhtml', content='This is Chapter 1 content')
    sec1_2 = make_page('Chapter 2', 'pi_c2.xhtml', content='This is Chapter 2 content')
    sec1.hidden_subs = True
    sec1.subs.extend([sec1_1, sec1_2])

    sec2 = make_page('Part II')
    sec2_1 = make_page('Chapter 1', 'pii_c1.xhtml', content='This is Chapter 1 content')
    sec2_2 = make_page('Chapter 2', 'pii_c2.xhtml', content='This is Chapter 2 content')
    sec2.subs.extend([sec2_1, sec2_2])

    sec3 = make_page('Part III', 'Part_III.xhtml', content='This is Part III content')
    sec3_1 = make_page('Chapter 1', 'piii_c1.xhtml', content='This is Chapter 1 content')
    sec3_2 = make_page('Chapter 2', 'piii_c2.xhtml', content='This is Chapter 2 content')
    sec3.subs.extend([sec3_1, sec3_2])

    book.toc.extend([sec1, sec2, sec3])

    return book


def check_xml(book_path):
    z = zipfile.ZipFile(book_path, 'r')
    container = ET.fromstring(z.read('META-INF/container.xml').decode())
    for rootfile in container[0]:
        if rootfile.attrib['media-type'] == 'application/oebps-package+xml':
            ET.fromstring(z.read(rootfile.attrib['full-path']))


def test_epub3():
    from epubuilder.epub3 import Epub3, Section

    book = make_epub(Epub3, Section)
    book.files['cover.png'] = File(open(os.path.join(cur_path, 'cover', 'cover.png'), 'rb').read())
    book.cover_path = 'cover.png'

    # make user toc
    user_toc_page = book.addons_make_user_toc_page()
    user_toc_path = 'user_toc.xhtml'
    book.files[user_toc_path] = File(user_toc_page)
    book.spine.insert(0, Joint(user_toc_path))
    book.toc.insert(0, Section('Table of Contents', href=user_toc_path))

    book_path = os.path.join(BUILT_BOOK_DIR, '3.epub')
    book.write(book_path)

    check_xml(book_path)


def test_epub2():
    from epubuilder.epub2 import Epub2, Section
    from epubuilder.epub2.metas import Cover

    book = make_epub(Epub2, Section)

    cover_img_file = File(open(os.path.join(cur_path, 'cover', 'cover.png'), 'rb').read())
    cover_img_path = 'cover.png'
    book.files['cover.png'] = cover_img_file
    book.metadata.append(Cover(cover_img_path))

    cover_page_path = 'cover.xhtml'
    cover_page = book.addons_make_cover_page(image_path='cover.png', cover_page_path=cover_page_path)
    book.files[cover_page_path] = File(cover_page)
    book.spine.insert(0, Joint(cover_page_path))

    book.toc.ncx_depth = 1

    book_path = os.path.join(BUILT_BOOK_DIR, '2.epub')
    book.write(book_path)

    check_xml(book_path)
