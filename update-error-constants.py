#!/usr/bin/env python

import sys, os, os.path, re

BUILD_SOURCE_FILE = os.path.join("src", "lxml", "xmlerror.pxi")
BUILD_DEF_FILE    = os.path.join("src", "lxml", "xmlerror.pxd")

if len(sys.argv) < 2 or sys.argv[1].lower() in ('-h', '--help'):
    print "This script generates the constants in file", BUILD_SOURCE_FILE
    print "Call as"
    print sys.argv[0], "/path/to/libxml2-doc-dir"
    sys.exit(len(sys.argv) > 1)

HTML_FILE = os.path.join(sys.argv[1], 'html', 'libxml-xmlerror.html')
os.stat(HTML_FILE) # raise an error if we can't find it

sys.path.insert(0, 'src')
from lxml import etree

# map enum name to Python variable name and alignment for constant name
ENUM_MAP = {
    'xmlErrorLevel'   : ('__ERROR_LEVELS',  'XML_ERR_'),
    'xmlErrorDomain'  : ('__ERROR_DOMAINS', 'XML_FROM_'),
    'xmlParserErrors' : ('__ERROR_TYPES',   'XML_')
    }

ENUM_ORDER = ('xmlErrorLevel', 'xmlErrorDomain', 'xmlParserErrors')

COMMENT = """
# This section is generated by the script '%s'.

""" % os.path.basename(sys.argv[0])

def split(lines):
    lines = iter(lines)
    pre = []
    for line in lines:
        pre.append(line)
        if line.startswith('#') and "BEGIN: GENERATED CONSTANTS" in line:
            break
    pre.append('')
    for line in lines:
        if line.startswith('#') and "END: GENERATED CONSTANTS" in line:
            break
    post = ['', line]
    post.extend(lines)
    post.append('')
    return pre, post

def regenerate_file(filename, result):
    # read .pxi source file
    f = open(filename, 'r')
    pre, post = split(f)
    f.close()

    # write .pxi source file
    f = open(filename, 'w')
    f.write(''.join(pre))
    f.write(COMMENT)
    f.write('\n'.join(result))
    f.write(''.join(post))
    f.close()

def parse_enums(html_file):
    PARSE_ENUM_NAME  = re.compile('\s*enum\s+(\w+)\s*{', re.I).match
    PARSE_ENUM_VALUE = re.compile('\s*=\s+([0-9]+)\s*(?::\s*(.*))?').match
    tree = etree.parse(html_file)
    xpath = etree.XPathEvaluator(tree, {'html' : 'http://www.w3.org/1999/xhtml'})

    enum_dict = {}
    enums = xpath.evaluate("//html:pre[@class = 'programlisting' and contains(text(), 'Enum') and html:a[@name]]")
    for enum in enums:
        enum_name = PARSE_ENUM_NAME(enum.text).group(1)
        print "Found enum", enum_name
        entries = []
        enum_dict[enum_name] = entries
        for child in enum:
            name = child.text
            value, descr = PARSE_ENUM_VALUE(child.tail).groups()
            entries.append((name, int(value), descr))
    return enum_dict

enum_dict = parse_enums(HTML_FILE)

# regenerate source files
pxi_result = []
append_pxi = pxi_result.append
pxd_result = []
append_pxd = pxd_result.append

append_pxd('cdef extern from "libxml/xmlerror.h":')
append_pxi('''\
# Constants are stored in tuples of strings, for which Pyrex generates very
# efficient setup code.  To parse them, iterate over the tuples and parse each
# line in each string independently.  Tuples of strings (instead of a plain
# string) are required as some C-compilers of a certain well-known OS vendor
# cannot handle strings that are a few thousand bytes in length.
''')

ctypedef_indent = ' '*4
constant_indent = ctypedef_indent*2

for enum_name in ENUM_ORDER:
    constants = enum_dict[enum_name]
    pxi_name, prefix = ENUM_MAP[enum_name]

    append_pxd(ctypedef_indent + 'ctypedef enum %s:' % enum_name)
    append_pxi('cdef object %s' % pxi_name)
    append_pxi('%s = ("""\\' % pxi_name)

    prefix_len = len(prefix)
    length = 2 # each string ends with '\n\0'
    for name, val, descr in constants:
        if descr:
            line = '%-50s = %7d # %s' % (name, val, descr)
        else:
            line = '%-50s = %7d' % (name, val)
        append_pxd(constant_indent + line)

        if name[:prefix_len] == prefix and len(name) > prefix_len:
            name = name[prefix_len:]
        line = '%s=%d' % (name, val)
        if length + len(line) >= 2040: # max string length in MSVC is 2048
            append_pxi('""",')
            append_pxi('"""\\')
            length = 2 # each string ends with '\n\0'
        append_pxi(line)
        length += len(line) + 2 # + '\n\0'

    append_pxd('')
    append_pxi('""",)')
    append_pxi('')

# write source files
print "Updating file", BUILD_SOURCE_FILE
regenerate_file(BUILD_SOURCE_FILE, pxi_result)

print "Updating file", BUILD_DEF_FILE
regenerate_file(BUILD_DEF_FILE,    pxd_result)

print "Done"
