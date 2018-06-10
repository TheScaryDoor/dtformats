# -*- coding: utf-8 -*-
"""GZip files."""

# Note: do not rename file to gzip.py this can cause the exception:
# AttributeError: 'module' object has no attribute 'GzipFile'
# when using pip.

from __future__ import unicode_literals

import os
import zlib

from dtformats import data_format
from dtformats import errors


class GZipFile(data_format.BinaryDataFile):
  """GZip (.gz) file."""

  _DEFINITION_FILE = 'gzipfile.yaml'

  _GZIP_SIGNATURE = 0x8b1f

  _COMPRESSION_METHOD_DEFLATE = 8

  _FLAG_FTEXT = 0x01
  _FLAG_FHCRC = 0x02
  _FLAG_FEXTRA = 0x04
  _FLAG_FNAME = 0x08
  _FLAG_FCOMMENT = 0x10

  _BUFFER_SIZE = 16 * 1024 * 1024

  def _DebugPrintMemberHeader(self, member_header):
    """Prints member header debug information.

    Args:
      member_header (gzip_member_header): member header.
    """
    value_string = '0x{0:04x}'.format(member_header.signature)
    self._DebugPrintValue('Signature', value_string)

    value_string = '{0:d}'.format(member_header.compression_method)
    self._DebugPrintValue('Compression method', value_string)

    value_string = '0x{0:02x}'.format(member_header.flags)
    self._DebugPrintValue('Flags', value_string)

    value_string = '{0:d}'.format(member_header.modification_time)
    self._DebugPrintValue('Modification time', value_string)

    value_string = '{0:d}'.format(member_header.operating_system)
    self._DebugPrintValue('Operating system', value_string)

    value_string = '0x{0:02x}'.format(member_header.compression_flags)
    self._DebugPrintValue('Compression flags', value_string)

    self._DebugPrintText('\n')

  def _DebugPrintMemberFooter(self, member_footer):
    """Prints member footer debug information.

    Args:
      member_footer (gzip_member_footer): member footer.
    """
    value_string = '0x{0:08x}'.format(member_footer.checksum)
    self._DebugPrintValue('Checksum', value_string)

    value_string = '{0:d}'.format(member_footer.uncompressed_data_size)
    self._DebugPrintValue('Uncompressed data size', value_string)

    self._DebugPrintText('\n')

  def _ReadMemberHeader(self, file_object):
    """Reads a member header.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the member header cannot be read.
    """
    file_offset = file_object.tell()
    data_type_map = self._GetDataTypeMap('gzip_member_header')

    member_header, _ = self._ReadStructureFromFileObject(
        file_object, file_offset, data_type_map, 'member header')

    if self._debug:
      self._DebugPrintMemberHeader(member_header)

    if member_header.signature != self._GZIP_SIGNATURE:
      raise errors.ParseError(
          'Unsupported signature: 0x{0:04x}.'.format(member_header.signature))

    if member_header.compression_method != self._COMPRESSION_METHOD_DEFLATE:
      raise errors.ParseError(
          'Unsupported compression method: {0:d}.'.format(
              member_header.compression_method))

    if member_header.flags & self._FLAG_FEXTRA:
      file_offset = file_object.tell()
      data_type_map = self._GetDataTypeMap('uint16le')

      extra_field_data_size, _ = self._ReadStructureFromFileObject(
          file_object, file_offset, data_type_map, 'extra field data size')

      file_object.seek(extra_field_data_size, os.SEEK_CUR)

    if member_header.flags & self._FLAG_FNAME:
      file_offset = file_object.tell()
      data_type_map = self._GetDataTypeMap('cstring')

      value_string, _ = self._ReadStructureFromFileObject(
          file_object, file_offset, data_type_map, 'original filename')

      if self._debug:
        self._DebugPrintValue('Original filename', value_string)

    if member_header.flags & self._FLAG_FCOMMENT:
      file_offset = file_object.tell()
      data_type_map = self._GetDataTypeMap('cstring')

      value_string, _ = self._ReadStructureFromFileObject(
          file_object, file_offset, data_type_map, 'comment')

      if self._debug:
        self._DebugPrintValue('Comment', value_string)

    if member_header.flags & self._FLAG_FHCRC:
      file_object.read(2)

  def _ReadMemberFooter(self, file_object):
    """Reads a member footer.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the member footer cannot be read.
    """
    file_offset = file_object.tell()
    data_type_map = self._GetDataTypeMap('gzip_member_footer')

    member_footer, _ = self._ReadStructureFromFileObject(
        file_object, file_offset, data_type_map, 'member footer')

    if self._debug:
      self._DebugPrintMemberFooter(member_footer)

  def _ReadCompressedData(self, zlib_decompressor, compressed_data):
    """Reads compressed data.

    Args:
      zlib_decompressor (zlib.Decompress): zlib decompressor.
      compressed_data (bytes): compressed data.

    Returns:
      tuple[bytes, bytes]: decompressed data and remaining data.
    """
    data_segments = []
    while compressed_data:
      data = zlib_decompressor.decompress(compressed_data)
      if not data:
        break

      data_segments.append(data)
      compressed_data = getattr(zlib_decompressor, 'unused_data', b'')

    return b''.join(data_segments), compressed_data

  def _ReadMemberCompressedData(self, file_object):
    """Reads a member compressed data.

    Args:
      file_object (file): file-like object.
    """
    zlib_decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
    compressed_data = file_object.read(self._BUFFER_SIZE)
    while compressed_data:
      data, compressed_data = self._ReadCompressedData(
          zlib_decompressor, compressed_data)
      if compressed_data:
        file_object.seek(-len(compressed_data), os.SEEK_CUR)

      if not data:
        break

      compressed_data = file_object.read(self._BUFFER_SIZE)

  def ReadFileObject(self, file_object):
    """Reads a GZip file-like object.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the file cannot be read.
    """
    file_offset = 0
    while file_offset < self._file_size:
      self._ReadMemberHeader(file_object)
      self._ReadMemberCompressedData(file_object)
      self._ReadMemberFooter(file_object)

      file_offset = file_object.tell()
