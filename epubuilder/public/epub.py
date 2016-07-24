# coding=utf-8

import string

import os
import random
from abc import abstractmethod
from hooky import List, Dict

from epubuilder.public import mimes
from epubuilder.public.metas import Identifier
from epubuilder.xl import Xl, Element, pretty_insert


from PIL import Image
from epubuilder.tools import relative_path
import io


CONTAINER_PATH = 'META-INF' + os.sep + 'container.xml'
ROOT_OF_OPF = 'EPUB'


class FatherEpub:
    def __init__(self):
        pass

    @property
    def _epub(self):
        return self.__epub

    @_epub.setter
    def _epub(self, value):
        self.__epub = value


class Metadata(List):
    """list-like.

    Store metadata, such as author, publisher etc.

    see :mod:`epubuilder.public.metas`"""

    pass


########################################################################################################################
# Files File
########################################################################################################################
class Files(Dict):
    """dict-like.

    Store file path and :class:`epubuilder.public.File` objects from `key` and `item`.
    Any file you want to package them into the book, you have to use this."""
    def _before_add(self, key=None, item=None):
        if not isinstance(item, File):
            raise TypeError


########################################################################################################################
class File:
    def __init__(self, binary, mime=None, fallback=None):
        """
        :param binary: binary data
        :type binary: bytes
        :param mime: mime
        :type mime: str
        :param fallback: file path
        :type fallback: str
        """

        self._binary = binary
        self.mime = mime
        # self.identification = identification or 'id_' + uuid.uuid4().hex
        self.fallback = fallback

    @property
    def binary(self):
        """as class parmeter"""
        return self._binary


########################################################################################################################
# Spine Joint
########################################################################################################################
class Spine(List):
    """list-like.

    "The spine defines the default reading order"

    store :class:`epubuilder.public.Joint` objects.
    """

    def _before_add(self, key=None, item=None):
        if not isinstance(item, Joint):
            raise TypeError


class Joint:
    def __init__(self, path, linear=None):
        """
        :param path: file path, in Epub.Files.keys()
        :type path: str
        :param linear: I don't know what is this mean. visit http://idpf.org to figure out by yourself.
        :type linear: bool
        """
        self._path = path
        self.linear = linear

    @property
    def path(self):
        """as class parmeter"""
        return self._path


########################################################################################################################
# Epub
########################################################################################################################
class Epub:
    def __init__(self):
        self._metadata = Metadata()
        setattr(self._metadata, '_epub', self)

        self._files = Files()
        setattr(self._files, '_epub', self)

        self._spine = Spine()
        setattr(self._spine, '_epub', self)

        # for opf etc.
        self._temp_files = Files()
        setattr(self._temp_files, '_epub', self)

    metadata = property(lambda self: self._metadata, doc=str(Metadata.__doc__ if Metadata.__doc__ else ''))

    files = property(lambda self: self._files, doc=str(Files.__doc__ if Files.__doc__ else ''))

    spine = property(lambda self: self._spine, doc=str(Spine.__doc__ if Spine.__doc__ else ''))

    @staticmethod
    def _find_ncx_id(items):
        ncx_id = None
        for item in items:
            if item.attributes[(None, 'media-type')] == mimes.NCX:
                ncx_id = item.attributes[(None, 'id')]
                break
        return ncx_id

    def _find_unique_id(self):
        """
        :return:
         :rtype: str or none
        """
        for m in self.metadata:
            if isinstance(m, Identifier):
                return m.to_element().attributes[(None, 'id')]
        return None

    def _find_id(self, filepath):
        for item in self._make_manifest_element().children:
            if item.attributes[(None, 'href')] == filepath:
                return item.attributes[(None, 'id')]
        return None

    def _make_manifest_element(self):
        """
        :return: Manifest Element
         :rtype: Element
        """
        manifest = Element('manifest')

        ids = []

        item_dict = {}

        pathes = list(self.files.keys())

        def make_item(path, file_):
            item = Element('item', attributes={(None, 'href'): path})

            item.attributes[(None, 'media-type')] = file_.mime or mimes.map_from_extension[
                os.path.splitext(path)[1]]

            identification = xml_identify(path)
            new_id = identification
            i = 1
            while new_id in ids:
                new_id = identification + '_' + str(i)

            item.attributes[(None, 'id')] = new_id
            ids.append(new_id)

            return item

        while pathes:
            for _path in pathes:
                if self.files[_path].fallback is not None:
                    if self.files[_path].fallback in item_dict.keys():
                        _item = make_item(_path, self.files[_path])
                        _item.attributes[(None, 'fallback')] = item_dict[_path].attributes[(None, 'id')]
                        item_dict[_path] = _item

                        manifest.children.append(_item)
                        pathes.remove(_path)
                else:
                    _item = make_item(_path, self.files[_path])
                    item_dict[_path] = _item

                    manifest.children.append(_item)
                    pathes.remove(_path)

        for _path, _file in self._temp_files.items():
            manifest.children.append(make_item(_path, _file))

        return manifest

    def _make_spine_element(self):
        spine = Element('spine')

        for joint in self.spine:

            itemref = Element('itemref', attributes={(None, 'idref'): self._find_id(joint.path)})

            if joint.linear is True:
                itemref.attributes[(None, 'linear')] = 'yes'
            elif joint.linear is False:
                itemref.attributes[(None, 'linear')] = 'no'

            spine.children.append(itemref)

        return spine

    @staticmethod
    def _get_container_xmlstring(opf_path):
        e = Element('container')

        e.attributes['version'] = '1.0'

        e.prefixes['urn:oasis:names:tc:opendocument:xmlns:container'] = None

        rootfiles = Element('rootfiles')
        e.children.append(rootfiles)

        rootfile = Element('rootfile')
        rootfiles.children.append(rootfile)

        rootfile.attributes['full-path'] = opf_path

        rootfile.attributes['media-type'] = 'application/oebps-package+xml'

        return Xl(root=pretty_insert(e, dont_do_when_one_child=True)).string()

    def _get_unused_filename(self, dire, filename):
        dire = dire or ''

        only_name, ext = os.path.splitext(filename)
        unused_filename = filename

        while ROOT_OF_OPF + dire + '/' + unused_filename in [ROOT_OF_OPF + '/' + path for path in self.files.keys()] +\
                [ROOT_OF_OPF + '/' + path for path in self._temp_files.keys()]:

            unused_filename = '_{}{}'.format(
                random.random(''.join(random.sample(string.ascii_letters + string.digits, 8))),
                ext
            )

        return unused_filename

    @abstractmethod
    def write(self, filename):
        """Write to file.

        :param filename: file name.
        :type filename: str
        """

    ####################################################################################################################
    # Add-ons
    def addons_make_image_page(self, image_path, cover_page_path=None, width=None, heigth=None):
        """Make xhtml cover page contain the image you given.

        You must put the returned file to :class:`Epub2.files` by yourself

        :param image_path: Image path in your Epub2.files
        :param cover_page_path: Use this to get relative path to the image path
        :param width: Image width, automatic recognition if None
        :param heigth: Image heigth, automatic recognition if None
        :return: Cover xhtml page file.
        :rtype: File
        """

        img = Image.open(io.BytesIO(self.files[image_path].binary))
        width = width or img.size[0]
        height = heigth or img.size[1]

        relative = relative_path(os.path.split(cover_page_path or '')[0], image_path)

        xhtml_string = open(os.path.join(os.path.dirname(__file__), 'static', 'cover.xhtml')).read()
        cover_page = xhtml_string.format(title='Cover', width=width, height=height, image_href=relative).encode()

        return File(cover_page)


def xml_identify(s):
    """
    :param s:
    :type s: str
    :return:
    :rtype: str
    """
    new_string = ''

    for char in s:
        if char.isalpha() or char.isdigit() or char in (':', '.', '_', '-'):
            new_string += char

        else:
            new_string += ':'

    if not new_string[0].isalpha():
        new_string = 'P_' + new_string

    return new_string


OPF_NS = 'http://www.idpf.org/2007/opf'
