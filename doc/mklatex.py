# The script builds the LaTeX documentation.
# Testing:
#    python mklatex.py latex .. 1.0

from docstructure import SITE_STRUCTURE, HREF_MAP, BASENAME_MAP
import os, shutil, re, sys

TARGET_FILE = "lxmldoc.tex"

RST2LATEX_OPTIONS = " ".join([
#    "--no-toc-backlinks",
    "--strip-comments",
    "--language en",
#    "--date",
    "--use-latex-footnotes",
    "--use-latex-citations",
    "--use-latex-toc",
    #"--font-encoding=T1",
    ])

htmlnsmap = {"h" : "http://www.w3.org/1999/xhtml"}

replace_invalid = re.compile(r'[-_/.\s\\]').sub

# LaTeX snippets

DOCUMENT_CLASS = r"""
\documentclass[10pt,english]{report}
\usepackage[a4paper]{geometry}
\parindent0pt
\parskip1ex
"""

PYGMENTS_IMPORT = r"""
\usepackage{fancyvrb}
\input{_part_pygments.tex}
"""

def write_chapter(master, title, outname):
    master.write(r"""
\chapter{%s}
\label{_part_%s}
\input{_part_%s}
""".replace('            ', '') % (title, outname, outname))


# the program ----

def rest2latex(script, source_path, dest_path):
    command = ('%s %s %s  %s > %s' %
               (sys.executable, script, RST2LATEX_OPTIONS,
                source_path, dest_path))
    os.system(command)

def build_pygments_macros(filename):
    from pygments.formatters import LatexFormatter
    text = LatexFormatter().get_style_defs()
    f = file(filename, "w")
    f.write(text)
    f.close()

def noop(input):
    return input

counter_no = 0

def tex_postprocess(src, dest, want_header = False, process_line=noop):
    """
    Postprocessing of the LaTeX file generated from ReST.

    Reads file src and saves to dest only the true content
    (without the document header and final) - so it is suitable
    to be used as part of the longer document.

    Returns the title of document

    If want_header is set, returns also the document header (as
    the list of lines).
    """
    title = ''
    header = []
    global counter_no
    counter_no = counter_no + 1
    counter_text = "listcnt%d" % counter_no

    search_title = re.compile(r'\\title{([^}]*)}').search
    skipping = re.compile(r'(\\end{document}|\\tableofcontents)').search

    src = file(src)
    dest = file(dest, "w")

    iter_lines = iter(src.readlines())
    for l in iter_lines:
        l = process_line(l)
        if want_header:
            header.append(l)
        m = search_title(l)
        if m:
            title = m.group(0)
        if l.startswith("\\maketitle"):
            break

    for l in iter_lines:
        l = process_line(l)
        if skipping(l):
            # To-Do minitoc instead of tableofcontents
            pass
        else:
            l = l.replace("listcnt0", counter_text)
            dest.write(l)

    if not title:
        raise Exception("Bueee, no title")
    return title, header

def publish(dirname, lxml_path, release):
    if not os.path.exists(dirname):
        os.mkdir(dirname)

    book_title = "lxml %s" % release

    doc_dir = os.path.join(lxml_path, 'doc')
    script = os.path.join(doc_dir, 'rest2latex.py')
    pubkey = os.path.join(doc_dir, 'pubkey.asc')

    shutil.copy(pubkey, dirname)

    href_map = HREF_MAP.copy()
    changelog_basename = 'changes-%s' % release
    href_map['Release Changelog'] = changelog_basename + '.tex'

    # build pygments macros
    build_pygments_macros(os.path.join(dirname, '_part_pygments.tex'))

    # Used in postprocessing of generated LaTeX files
    header = []
    titles = {}

    replace_interdoc_hyperrefs = re.compile(
        r'\\href\{([^/}]+)[.]([^./}]+)\}\{([^}]+)\}').sub
    replace_docinternal_hyperrefs = re.compile(
        r'\\href\{\\#([^}]+)\}').sub
    def build_hyperref(match):
        basename, extension, linktext = match.groups()
        outname = BASENAME_MAP.get(basename, basename)
        if '#' in extension:
            anchor = extension.split('#')[-1]
            return r"\hyperref[%s]{%s}" % (anchor, linktext)
        elif extension != 'html':
            return r'\href{http://codespeak.net/lxml/%s.%s}{%s}' % (
                outname, extension, linktext)
        else:
            return r"\hyperref[_part_%s.tex]{%s}" % (outname, linktext)
    def fix_relative_hyperrefs(line):
        if r'\href' not in line:
            return line
        line = replace_interdoc_hyperrefs(build_hyperref, line)
        return replace_docinternal_hyperrefs(r'\hyperref[\1]', line)

    # Building pages
    for section, text_files in SITE_STRUCTURE:
        for filename in text_files:
            if filename.startswith('@'):
                print "Not yet implemented: %s" % filename[1:]
                #page_title = filename[1:]
                #url = href_map[page_title]
                #build_menu_entry(page_title, url, section_head)
            else:
                path = os.path.join(doc_dir, filename)
                basename = os.path.splitext(os.path.basename(filename))[0]
                basename = BASENAME_MAP.get(basename, basename)
                outname = basename + '.tex'
                outpath = os.path.join(dirname, outname)

                print "Creating %s" % outname
                rest2latex(script, path, outpath)

                final_name = os.path.join(dirname, "_part_%s" % outname)

                title, hd = tex_postprocess(outpath, final_name, not header,
                                            process_line=fix_relative_hyperrefs)
                if not header:
                    header = hd
                titles[outname] = title

    # also convert CHANGES.txt
    find_version_title = re.compile(
        r'(.*\\section\{)([0-9][^\} ]*)\s+\(([^)]+)\)(\}.*)').search
    def fix_changelog(line):
        m = find_version_title(line)
        if m:
            line = "%sChanges in version %s, released %s%s" % m.groups()
        else:
            line = line.replace(r'\subsection{', r'\subsection*{')
        return line

    chgname = 'changes-%s.tex' % release
    chgpath = os.path.join(dirname, chgname)
    rest2latex(script,
               os.path.join(lxml_path, 'CHANGES.txt'),
               chgpath)
    tex_postprocess(chgpath, os.path.join(dirname, "_part_%s" % chgname),
                    process_line=fix_changelog)

    # Writing a master file
    print "Building %s\n" % TARGET_FILE
    master = file( os.path.join(dirname, TARGET_FILE), "w")
    for hln in header:
        if hln.startswith(r"\documentclass"):
            #hln = hln.replace('article', 'book')
            hln = DOCUMENT_CLASS
        elif hln.startswith(r"\begin{document}"):
            # pygments support
            master.write(PYGMENTS_IMPORT)
        elif hln.startswith(r"\title{"):
            hln = re.sub("\{[^\}]*\}",
                         r'{%s\\\\\\vspace{1em}\\includegraphics{../html/tagpython.png}}' % book_title, hln)
        elif hln.startswith("pdftitle"):
            hln = re.sub("\{[^\}]*\}", r'{%s}' % book_title, hln)
        master.write(hln)

    master.write("\\tableofcontents\n")

    for section, text_files in SITE_STRUCTURE:
        master.write("\n\n\\part{%s}\n" % section)
        for filename in text_files:
            if filename.startswith('@'):
                pass
                #print "Not yet implemented: %s" % filename[1:]
                #page_title = filename[1:]
                #url = href_map[page_title]
                #build_menu_entry(page_title, url, section_head)
            else:
                basename = os.path.splitext(os.path.basename(filename))[0]
                basename = BASENAME_MAP.get(basename, basename)
                outname = basename + '.tex'
                write_chapter(master, titles[outname], outname)

    write_chapter(master, "Changes", chgname)

    master.write("\\end{document}\n")
                
if __name__ == '__main__':
    publish(sys.argv[1], sys.argv[2], sys.argv[3])
