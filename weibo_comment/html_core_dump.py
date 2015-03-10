#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import codecs

import html.parser
import html.entities

##############################################################################

class HTMLTextDecoder:

    def __init__(self):
        self.error_mode = 'replace'
        self.verbose = False
        self.default_encoding = 'utf_8'
        self.resolved_encoding = 'utf_8'

    def decode(self, data):
        encoding, data = self._detect_encoding_by_bom(data)
        if not encoding:
            encoding = self._detect_encoding_by_charset(data)
        if not encoding:
            encoding = self.default_encoding
        self.resolved_encoding = encoding
        return data.decode(encoding, errors=self.error_mode)

    def _detect_encoding_by_bom(self, data):
        if data[:4] == codecs.BOM_UTF32_LE:
            return ('utf_32_le', data[4:])
        elif data[:4] == codecs.BOM_UTF32_BE:
            return ('utf_32_be', data[4:])
        elif data[:3] == codecs.BOM_UTF8:
            return ('utf_8', data[3:])
        elif data[:2] == codecs.BOM_UTF16_LE:
            return ('utf_16_le', data[2:])
        elif data[:2] == codecs.BOM_UTF16_BE:
            return ('utf_16_be', data[2:])
        else:
            return (None, data)
        
    HTML_CHARSET = re.compile( \
        br'<meta' \
        br'[^>]*?http[^>]*?equiv[^>]*?content[^>]*?type' \
        br'[^>]*?content[^>]*?text[^>]*?html[^>]*?charset\s*=\s*(?P<charset>[_\-0-9a-z]+)' \
        br'[^>]*?>', \
        re.IGNORECASE)

    CHARSET_TO_ENCODING = {
        'utf8'      : 'utf_8',
        'u8'        : 'utf_8',
        'gbk'       : 'gbk',
        'gb'        : 'gbk',
        'gb2312'    : 'gbk',
        'gb231280'  : 'gbk',
        'gb18030'   : 'gbk',
        'csgb'      : 'gbk',
        'hzgb'      : 'gbk',
        'hzgb2312'  : 'gbk',
        'hzgbk'     : 'gbk',
        '936'       : 'gbk',
        'cp936'     : 'gbk',
        'ms936'     : 'gbk',
        'big5'      : 'big5',
        'big5tw'    : 'big5',
        'csbig5'    : 'big5',
        'hzbig5'    : 'big5',
        '950'       : 'big5',
        'cp950'     : 'big5',
        'ms950'     : 'big5',
        'utf16le'   : 'utf_16_le',
        'u16le'     : 'utf_16_le',
        'utf16be'   : 'utf_16_be',
        'u16be'     : 'utf_16_be',
        'utf32le'   : 'utf_32_le',
        'u32le'     : 'utf_32_le',
        'utf32be'   : 'utf_32_be',
        'u32be'     : 'utf_32_be',
        }
    
    def _detect_encoding_by_charset(self, data):
        match = self.HTML_CHARSET.search(data)
        if match:
            charset = match.group('charset').decode('ascii')
            name = re.sub('[^0-9a-z]+', '', charset.lower())
            if name in self.CHARSET_TO_ENCODING:
                return self.CHARSET_TO_ENCODING[name]
            try:
                data.decode(charset, errors='ignore')
            except LookupError:
                pass
            else:
                return charset
            if self.verbose:
                print('Warning: unknown charset "%s"' % charset)
        else:
            if self.verbose:
                print('Warning: charset meta tag not found')

##############################################################################

TAG_TEXT = '%%text%%'

class ParserError(Exception):

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message
        
class Token:

    def __init__(self, tag, name):
        assert((name == tag) or (name == '/' + tag))
        self.tag = tag
        self.name = name
        self.text = ''
        self.attrs = ''
        self.score = 'undefined'
        self.line_num = 0
        self.line_pos = 0
        self.parent = None
        self.children = [ ]
        self.index = -1
        self.end_tag_index = -1

    def __str__(self):
        return '%s, idx %d, end %d, pos %d-%d, score %s, parent %s, child %s, attr %s' % \
               (self.name, self.index, self.end_tag_index, \
               self.line_num, self.line_pos, str(self.score), \
               str(self.parent), str(self.children), self.attrs)
    
    def is_end(self):
        return self.name[0] == '/'

    def is_text(self):
        return self.name == TAG_TEXT

    def set_attrs(self, attrs):
        chunks = [ ]
        for key, val in attrs:
            if (key == 'id') or (key == 'class'):
                chunks.append(val)
        self.attrs = ' '.join(chunks)

    def count_sentence(self):
        # 常见中文标点符号 + 西文句号
        return len(re.findall('，|。|？|！|、|：|；|,', self.text))
    
class HTMLDumpParser(html.parser.HTMLParser):

    def __init__(self):
        html.parser.HTMLParser.__init__(self)
        self.debug = None   # debug output file path
        self.verbose = False

    def decode_html_text(self, data):
        decoder = HTMLTextDecoder()
        decoder.verbose = self.verbose
        return decoder.decode(data)

    def encode_html_text(self, text):
        return text.encode('utf_8', errors='replace')

    def dump_raw(self, data):
        text = self.decode_html_text(data)
        text = self.dump_text(text)
        return self.encode_html_text(text)

    def dump_text(self, text):
        self.parse_tokens(text)
        self.build_title_text()
        chunks = [ ]
        if self.title_text:
            chunks.append('<%%title%%>')
            chunks.append(self.title_text)
            chunks.append('</%%title%%>')
        self.build_body_text()
        if self.body_text:
            chunks.append('<%%body%%>')
            chunks.append(self.body_text)
            chunks.append('</%%body%%>')
        return '\n'.join(chunks)

    def build_title_text(self):
        self.title_text = ''
        i = 0
        while i + 2 < len(self.tokens):
            if (self.tokens[i].name == 'title') and \
               self.tokens[i+1].is_text() and \
               (self.tokens[i+2].name == '/title'):
                self.title_text = self.tokens[i+1].text
                return
            i += 1

    def build_body_text(self):
        self.body_text = ''

        if not self.tokens:
            return  # empty document

        # assign index for each token

        for i, t in enumerate(self.tokens):
            t.index = i
        
        # build token tree

        self.search_root_token()
        self.build_token_tree()

        # assign score for tokens

        for t in self.tokens[self.root.index : self.root.end_tag_index]:
            self.update_token_score(t)

        # find token with maximum score

        top = None
        for t in self.tokens[self.root.index : self.root.end_tag_index]:
            if t.score != 'undefined':
                if (top == None) or (t.score > top.score):
                    top = t
        if top == None:
            top = self.root
        
        # generate text

        chunks = [ ]
        for t in self.tokens[top.index : top.end_tag_index]:
            if t.is_text():
                chunks.append(t.text)
        self.body_text = '\n'.join(chunks)

        if self.debug:
            chunks = [ ]
            for t in self.tokens:
                chunks.append(str(t))
            chunks.append('ROOT = %s' % str(self.root))
            chunks.append('TOP  = %s' % str(top))
            text = '\n'.join(chunks)
            data = text.encode('utf_8', errors='replace')
            open(self.debug + '_tokens.txt', 'wb').write(data)
            
    def update_token_score(self, t):
        if not (t.name in {'p', 'div'}):
            return
        if t.parent == None:
            return
        parent = self.tokens[t.parent]
        if parent.score == 'undefined':
            parent.score = 0
            if re.search(r'comment|meta|footer|footnote|页脚|注释|备注', parent.attrs, re.IGNORECASE):
                parent.score -= 50
            if re.search(r'post|entry|content|text|body|article', parent.attrs, re.IGNORECASE):
                parent.score += 25
        for i in t.children:
            child = self.tokens[i]
            if child.is_text():
                parent.score += child.count_sentence()

    def search_root_token(self):
        self.root = None
        for t in self.tokens:
            if t.name == 'body':
                self.root = t
                break
        if self.root == None:
            if self.verbose:
                print('Warning: missing tag <body>')
            self.root = self.tokens[0]

    def build_token_tree(self):
        stack = [self.root]
        i = self.root.index + 1
        while i < len(self.tokens):
            assert(len(stack) > 0)
            top = stack[-1]
            t = self.tokens[i]
            if t.is_text():
                t.parent = top.index
                top.children.append(i)    
            elif t.is_end():
                if t.tag == top.tag:
                    top.end_tag_index = i
                    del stack[-1]
                else:
                    if self.verbose:
                        print('Warning: line %d, pos %d: mismatched tag </%s>' \
                            % (t.line_num, t.line_pos, t.tag))
                    # error recovery
                    if (len(stack) >= 2) and (t.tag == stack[-2].tag):
                        # force close tag
                        stack[-1].end_tag_index = i
                        stack[-2].end_tag_index = i
                        del stack[-2:]
                    else:
                        # ignore mismatched tag
                        pass
                if not stack:
                    break   # root token matched, we are done
            else:
                t.parent = top.index
                top.children.append(i)    
                stack.append(t)
            i += 1

        if self.verbose:
            for t in reversed(stack):
                print('Warning: line %d, pos %d: open tag <%s>' \
                    % (t.line_num, t.line_pos, t.tag))

    def parse_tokens(self, text):
        self.tokens = [ ]
        self.text_chunks = [ ]
        self.tag_level = 0
        self.debug_tags = [ ]

        self.reset()
        self.feed(text)
        self.close()
        self.flush_text_chunks()

        if self.debug:
            text = '\n'.join(self.debug_tags)
            data = text.encode('utf_8', errors='replace')
            open(self.debug + '_tags.txt', 'wb').write(data)

    IGNORE_TAGS = { \
        'a', 'b', 'base', 'basefont', 'em', 'font', 'i', 'iframe', \
        'link', 'meta', 's', 'script', 'small', 'strike', 'strong', 'style', 'u', \
        }
    
    SPACE_TAGS = { \
        'iframe', \
        }
    
    def handle_starttag(self, tag, attrs):
        line_num, line_pos = self.getpos()
        self.debug_tags.append('<%s> line %d, pos %d, level %d, attr %s' \
            % (tag, line_num, line_pos, self.tag_level, str(attrs)))
        self.tag_level += 1

        if tag in self.IGNORE_TAGS:
            return
        if tag in self.SPACE_TAGS:
            self.text_chunks.append(' ')
            return

        self.flush_text_chunks()
        t = Token(tag, tag)
        t.set_attrs(attrs)
        t.line_num = line_num
        t.line_pos = line_pos
        self.tokens.append(t)

    def handle_endtag(self, tag):
        self.tag_level -= 1
        line_num, line_pos = self.getpos()
        self.debug_tags.append('</%s> line %d, pos %d, level %d' \
            % (tag, line_num, line_pos, self.tag_level))

        if tag in self.IGNORE_TAGS:
            return
        if tag in self.SPACE_TAGS:
            self.text_chunks.append(' ')
            return

        self.flush_text_chunks()
        if self.tokens:
            # discard empty tag pair
            last = self.tokens[-1]
            if (last.tag == tag) and (not last.is_end()):
                del self.tokens[-1]
                return
        t = Token(tag, '/'+tag)
        t.line_num = line_num
        t.line_pos = line_pos
        self.tokens.append(t)

    def handle_data(self, text):
        if text:
            self.text_chunks.append(text)

    def handle_entityref(self, name):
        text = '&' + name + ';'
        try:
            if not (name in html.entities.name2codepoint):
                raise ValueError
            code_point = html.entities.name2codepoint[name]
            if (code_point < 0) or (code_point > 0x10FFFF):
                raise ValueError
            text = chr(code_point)
        except ValueError:
            if self.verbose:
                line_num, line_pos = self.getpos()
                print('Warning: line %d, pos%d: unknown entity ref "%s"' \
                    % (line_num, line_pos, text))
        self.text_chunks.append(text)

    def handle_charref(self, name):
        text = '&#' + name + ';'
        try:
            if name.startswith('x'):
                code_point = int(name[1:], 16)
            else:
                code_point = int(name)
            if (code_point < 0) or (code_point > 0x10FFFF):
                raise ValueError
            text = chr(code_point)
        except ValueError:
            if self.verbose:
                line_num, line_pos = self.getpos()
                print('Warning: line %d, pos%d: invalid char ref "%s"' \
                    % (line_num, line_pos, text))
        self.text_chunks.append(text)

    def flush_text_chunks(self):
        text = ''.join(self.text_chunks)
        text = text.strip()
        if text:
            t = Token(TAG_TEXT, TAG_TEXT)
            t.text = text
            self.tokens.append(t)
        self.text_chunks = []

if __name__ == '__main__':
    import os
    import sys

    if len(sys.argv) != 2:
        print('usage: html_core_dump html_file')
        sys.exit(0)

    html_file = sys.argv[1]
    if not os.path.isfile(html_file):
        print('Error: file not found')
        sys.exit(1)

    root, ext = os.path.splitext(html_file)
    
    parser = HTMLDumpParser()
    parser.verbose = True
    parser.debug = root

    data = open(html_file, 'rb').read()
    data = parser.dump_raw(data)
    open(root + '.txt', 'wb').write(data)
