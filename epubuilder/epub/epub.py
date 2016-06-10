import string
import uuid
import zipfile

import os
import random
from hooky import List, Dict

import xl
from epubuilder.tools import identify_mime
from xl import insert_spaces_for_pretty
from .metadata import Metadata
from .metadata.dcmes import Identifier, URI_DC

CONTAINER_PATH = 'META-INF' + os.sep + 'container.xml'


media_table = [

    # Image Types
    ['image/gif', ['.gif'], 'Images'],
    ['image/jpeg', ['.jpg', 'jpeg'], 'Images'],
    ['image/png', ['.png'], 'Images'],
    ['image/svg+xml', ['.svg'], 'Images'],

    # Application Types
    ['application/xhtml+xml', ['.html', '.xhtml'], 'Text'],
    ['application/font-sfnt', ['.otf', '.ttf', '.ttc'], 'Fonts'],  # old 'application/vnd.ms-opentype'
    ['application/font-woff', ['.woff'], 'Fonts'],
    ['application/smil+xml', [], 'Text'],  # EPUB Media Overlay documents
    ['application/pls+xml', [], ''],  # Text-to-Speech (TTS) Pronunciation lexicons

    # Audio Types
    ['audio/mpeg', [], ''],
    ['audio/mp4', ['.mp4'], ''],

    # Text Types
    ['text/html', [], 'Text'],
    ['text/css', ['.css'], 'Styles'],
    ['text/javascript', ['.js'], 'Scripts'],

    # Font Types
    ['font/woff2', ['.woff2'], 'Fonts'],
]


##################################################
# toc

class Toc(List):
    def __init__(self):
        super().__init__()
        self.title = None

    def _before_add(self, key=None, item=None):
        if not isinstance(item, Section):
            raise TypeError


class Section:
    def __init__(self, title, href=None):
        self._title = title
        self._href = href
        self._subsections = []

        self._hidden_sub = None

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value

    @property
    def href(self):
        return self._href

    @href.setter
    def href(self, value):
        self._href = value

    @property
    def subsections(self):
        return self._subsections

    @property
    def hidden_sub(self):
        return self._hidden_sub

    @hidden_sub.setter
    def hidden_sub(self, value):
        if value not in (True, False):
            raise ValueError
        else:
            self._hidden_sub = value

    def to_element(self):
        li = xl.Element('li')

        if self.href:
            a_or_span = xl.Element((None, 'a'))
            a_or_span.attributes[(None, 'href')] = self.href
        else:
            a_or_span = xl.Element((None, 'span'))

        a_or_span.children.append(xl.Text(self.title))

        if self.subsections:
            ol = xl.Element('ol')
            for one in self.subsections:
                ol.children.append(one.to_element())

            a_or_span.children.append(ol)

        li.children.append(a_or_span)

        return li


####################################
# for Manifest and zip files

class Files(Dict):
    def _before_add(self, key=None, item=None):
        if not isinstance(item, File):
            raise TypeError

    def to_elements(self):
        elements = []
        for path, file in self.items():
            item = xl.Element((None, 'item'), attributes={(None, 'href'): path, (None, 'media-type'): file.mime})
            if file.identification is not None:
                item.attributes[(None, 'id')] = file.identification

            elements.append(item)

        return elements


class File:
    def __init__(self, binary, mime=None, identification=None):
        self._binary = binary
        self.mime = mime or identify_mime(self.binary)
        self.identification = identification or 'id_' + uuid.uuid4().hex

    @property
    def binary(self):
        return self._binary


#####################################
# for Spine

class Spine(List):
    def _before_add(self, key=None, item=None):
        if not isinstance(item, Itemref):
            raise TypeError


class Itemref:
    def __init__(self, idref, linear=None):
        self._idref = idref
        self._linear = linear

    @property
    def idref(self):
        return self._idref

    def to_element(self):
        e = xl.Element((None, 'itemref'), attributes={(None, 'idref'): self.idref})

        if self._linear is True:
            e.attributes[(None, 'linear')] = 'yes'
        elif self._linear is False:
            e.attributes[(None, 'linear')] = 'no'

        return e


#####################################

ROOT_OF_OPF = 'EPUB'


class Epub:
    def __init__(self):

        self._files = Files()

        self._metadata = Metadata()

        self._spine = Spine()

        # nav
        self._toc = Toc()
        self._landmark = List()
        self._pagelist = List()

        # self._package_element.descriptor = package_descriptor

    @property
    def files(self):
        return self._files

    @property
    def metadata(self):
        return self._metadata

    @property
    def spine(self):
        return self._spine

    @property
    def toc(self):
        return self._toc

    @property
    def landmark(self):
        return self._landmark

    @property
    def pagelist(self):
        return self._pagelist

    def _xmlstr_toc(self):
        default_ns = 'http://www.w3.org/1999/xhtml'
        epub_ns = 'http://www.idpf.org/2007/ops'

        html = xl.Element((None, 'html'), prefixes={default_ns: None, epub_ns: 'epub'})

        head = xl.Element('head')

        if self.toc.title:
            _title = xl.Element('title')
            _title.children.append(xl.Text(self.toc.title))

        html.children.append(head)

        body = xl.Element((None, 'body'))

        if self.toc:
            nav = xl.Element((None, 'nav'), prefixes={epub_ns: 'epub'}, attributes={(epub_ns, 'type'): 'toc'})
            ol = xl.Element((None, 'ol'))

            for section in self.toc:
                ol.children.append(section.to_element())

            nav.children.append(ol)
            body.children.append(nav)

        html.children.append(body)

        return insert_spaces_for_pretty(html).xml_string()

    def _xmlstr_opf(self, nav_toc_path=None):
        def_ns = 'http://www.idpf.org/2007/opf'
        # dcterms_ns = 'http://purl.org/metadata/terms/'

        package = xl.Element((None, 'package'),
                             prefixes={def_ns: None},
                             attributes={(None, 'version'): '3.0', (xl.URI_XML, 'lang'): 'en'})

        for m in self.metadata:
            if isinstance(m, Identifier):
                package.attributes['unique-identifier'] = m.as_element().attributes[(None, 'id')]

        # unique - identifier = "pub-id"
        # metadata
        metadata_e = xl.Element((None, 'metadata'),
                                prefixes={URI_DC: 'dc'})

        for m in self.metadata:
            metadata_e.children.append(m.as_element())

        package.children.append(metadata_e)

        # manifest
        manifest = xl.Element((None, 'manifest'))
        manifest.children.extend(self.files.to_elements())
        # nav_toc
        if nav_toc_path:
            nav_toc_item_e = xl.Element((None, 'item'),
                                        attributes={(None, 'href'): nav_toc_path,
                                                    (None, 'id'): 'id' + uuid.uuid4().hex,
                                                    (None, 'properties'): 'nav',
                                                    (None, 'media-type'): 'application/xhtml+xml'})
            manifest.children.insert(0, nav_toc_item_e)

        package.children.append(manifest)

        # spine
        spine = xl.Element((None, 'spine'))
        for itemref in self.spine:
            spine.children.append(itemref.to_element())

        package.children.append(spine)

        return insert_spaces_for_pretty(package, one_child_dont_do=False).xml_string()

    @staticmethod
    def _xmlstr_container(opf_path):
        e = xl.Element((None, 'container'))

        e.attributes[(None, 'version')] = '1.0'

        e.prefixes['urn:oasis:names:tc:opendocument:xmlns:container'] = None

        rootfiles = xl.Element('rootfiles')
        e.children.append(rootfiles)

        rootfile = xl.Element('rootfile')
        rootfiles.children.append(rootfile)

        rootfile.attributes['full-path'] = opf_path

        rootfile.attributes['media-type'] = 'application/oebps-package+xml'

        return xl.xml_header() + insert_spaces_for_pretty(e, one_child_dont_do=False).xml_string()

    def write(self, filename, version=None):
        # version = version or '3.1'

        z = zipfile.ZipFile(filename, 'w')
        z.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)

        for filename, file in self.files.items():
            z.writestr(ROOT_OF_OPF + os.sep + filename, file.binary, zipfile.ZIP_DEFLATED)

        def get_unused_filename(dire, filename_ext):
            only_name, ext = os.path.splitext(filename_ext)
            unused_filename = filename_ext

            while ROOT_OF_OPF + '/' + unused_filename in [ROOT_OF_OPF + '/' + path for path in self.files.keys()]:
                unused_filename = '_{){}'.format(
                    random.random(''.join(random.sample(string.ascii_letters + string.digits, 8))),
                    ext
                )

            return unused_filename

        nav_toc_filename = get_unused_filename(ROOT_OF_OPF, 'nav.xhtml')
        z.writestr(ROOT_OF_OPF + '/' + nav_toc_filename,
                   self._xmlstr_toc().encode(),
                   zipfile.ZIP_DEFLATED)

        opf_filename = get_unused_filename(ROOT_OF_OPF, 'package.opf')
        z.writestr(ROOT_OF_OPF + '/' + opf_filename,
                   self._xmlstr_opf(nav_toc_filename).encode(),
                   zipfile.ZIP_DEFLATED)

        z.writestr(CONTAINER_PATH,
                   self._xmlstr_container(ROOT_OF_OPF + '/' + opf_filename).encode(),
                   zipfile.ZIP_DEFLATED)
