# encoding: utf-8

"""Functions that deal with WP's mix of text and tags in content.

These more or less mirror their WP counterparts except for texturize which has
been derived from smartypants.

They are mostly compatible with WP, producing comparable output. I did
not spend too much time fixing minor differences in output or re-engineering
them for performance (eg by using lxml to build an intermediate tree, etc.)
since you should use preformatting in production, and limit the use of
the functions below to development.

If you want to use your functions, simply place them somewhere reachable and
wrap them in a template tag library, then use it in templates. No magic in it.
"""

import re

from collections import deque


POST_MORE_RE = re.compile(r'(?sm)<!--\s*more\s*-->')

CHARREF = re.compile(r'&#([0-9]+);')

BALANCE_SINGLE = (
    'area', 'base', 'basefont', 'br', 'col', 'command', 'embed', 'frame', 'hr',
    'img', 'input', 'isindex', 'link', 'meta', 'param', 'source'
)
BALANCE_NESTABLE = (
    'blockquote', 'div', 'object', 'q', 'span'
)
BALANCE_SUBS = (
    (re.compile(r'<\s+!--'), '<!--'),
    (re.compile(r'<([0-9])'), r'&lt;\1'),
)
BALANCE_SCANNER = re.compile(r'(?sm)<(/?)([\w:]+)(\s+[^>]+)?>')

TXTR_VERBATIM = (
    'pre', 'code', 'kbd', 'style', 'script', 'tt'
)
TXTR_ESCAPES = (
    (re.compile(r"""\\\\"""), '&#92;'),
	(re.compile(r'''\\"'''), '&#34;'),
	(re.compile(r"""\\'"""), '&#39;'),
	(re.compile(r"""\\\."""), '&#46;'),
	(re.compile(r"""\\-"""), '&#45;'),
	(re.compile(r"""\\`"""), '&#96;')
)
TXTR_SINGLES = (
    (re.compile('&quot;'), '"'),
    # dashes
	(re.compile(r'(?<!!)---(?!>)'), u'–'),
	(re.compile(r'(?<!!)--(?!>)'), u'—'),
    (re.compile(r'\s-\s'), u' – '),
    # ellipses
	(re.compile(r'\.\.\.'), u'…'),
	(re.compile(r'\. \. \.'), u'…'),
    # backticks
	(re.compile(r'``'), u'“'),
	(re.compile(r"''"), u'”'),
    # misc
    (re.compile(r'([0-9]+)x([0-9]+)'), ur'\1×\2'),
    # TODO: smilies
    # <img src='/wp-includes/images/smilies/icon_smile.gif' alt=':)' class='wp-smiley' />
)
TXTR_NOSPACE = re.compile(r'\S', re.U)
TXTR_WORD = re.compile(r'\w', re.U)
TXTR_PUNCT_CLASS = r"""[!"#\$\%'()*+,-.\/:;<=>?\@\[\\\]\^_`{|}~]"""
TXTR_CLOSE_CLASS = r'[^\ \t\r\n\[\{\(\-]'
TXTR_DEC_DASHES = r'–|—'
TXTR_QUOTES = (
        # Special case if the very first character is a quote
        # followed by punctuation at a non-word-break. Close the quotes by brute force:
        (re.compile(r"^'(?=%s\\B)" % TXTR_PUNCT_CLASS, re.U), u'’'),
        (re.compile(r'^"(?=%s\\B)' % TXTR_PUNCT_CLASS, re.U), u'”'),
        # Special case for double sets of quotes, e.g.:
        #   <p>He said, "'Quoted' words in a larger quote."</p>
        (re.compile(r'''"'(?=\w)''', re.U), u'“‘'),
        (re.compile(r"""'"(?=\w)""", re.U), u'‘“'),
        # Special case for decade abbreviations (the '80s):
        (re.compile(r"\b'(?=\d{2}s)", re.U), u'’'),
        # opening_single_quotes_regex
        (re.compile(r"""
			(
				\s          |   # a whitespace char, or
				&nbsp;      |   # a non-breaking space entity, or
				--          |   # dashes, or
				&[mn]dash;  |   # named dash entities
				%s          |   # or decimal entities
				&\#x201[34];    # or hex
			)
			'                 # the quote
			(?=\w)            # followed by a word character
        """ % TXTR_DEC_DASHES, re.VERBOSE|re.U), ur'\1‘'),
        # closing_single_quotes_regex
        (re.compile(r"(%s)'(?!\s|s\b|\d)" % TXTR_CLOSE_CLASS, re.U), ur"\1’"),
        (re.compile(r"(%s)'(\s|s\b)" % TXTR_CLOSE_CLASS, re.U), ur'\1’\2'),
        # Any remaining single quotes should be opening ones:
        (re.compile("'"), u"‘"),
        # Get most opening double quotes
        (re.compile(r"""
			(
				\s          |   # a whitespace char, or
				&nbsp;      |   # a non-breaking space entity, or
				--          |   # dashes, or
				&[mn]dash;  |   # named dash entities
				%s          |   # or decimal entities
				&\#x201[34];    # or hex
			)
			"                 # the quote
			(?=\w)            # followed by a word character
        """ % TXTR_DEC_DASHES, re.VERBOSE|re.U), ur'\1“'),
        # Double closing quotes:
        (re.compile(r"""
			#(%s)?   # character that indicates the quote should be closing
			"
			(?=\s)
        """ % TXTR_CLOSE_CLASS, re.VERBOSE|re.U), u'”'),
        # closing_double_quotes_regex
        (re.compile(r"""
			(%s)   # character that indicates the quote should be closing
			"
        """ % TXTR_CLOSE_CLASS, re.VERBOSE|re.U), ur'\1”'),
        # Any remaining quotes should be opening ones.
        (re.compile('"'), u'“')
)

SHORTCODE_RE = re.compile(
    r'(?<!\[)\[(?P<shortcode>[a-z_-]+)(?:(?P<attrs>\s+[^\]]+))?\](?:[^\[]+\[/(?P=shortcode)\])?',
    re.S|re.M
)

AUTOP_ALLBLOCKS = '(?:%s)' % '|'.join((
    'table', 'thead', 'tfoot', 'caption', 'col', 'colgroup', 'tbody', 'tr', 'td',
    'th', 'div', 'dl', 'dd', 'dt', 'ul', 'ol', 'li', 'pre', 'form', 'map', 'area',
    'blockquote', 'address', 'math', 'style', 'p', 'h1', 'h2', 'h3', 'h4', 'h5',
    'h6', 'hr', 'fieldset', 'legend', 'section', 'article', 'aside', 'hgroup',
    'header', 'footer', 'nav', 'figure', 'details', 'menu', 'summary'
))
AUTOP_SUBS = {
    '0': (
        (re.compile(r'(?sm)<br />\s*<br />'), "\n\n"),
        # Space things out a little
        (re.compile(r'(<%s[^>]*>)' % AUTOP_ALLBLOCKS), r"\n\1"),
        (re.compile(r'(</%s>)' % AUTOP_ALLBLOCKS), r"\1\n\n"),
    ),
    'option': (
        (re.compile(r'(?sm)\s*<option'), '<option'),
        (re.compile(r'(?sm)</option>\s*'), '</option>'),
    ),
    'object': (
        (re.compile(r'(?sm)(<object[^>]*>)\s*'), r'\1'),
        (re.compile(r'(?sm)\s*</object>'), '</object>'),
        (re.compile(r'(?sm)\s*(</?(?:param|embed)[^>]*>)\s*'), r'\1'),
    ),
    'source': (
        (re.compile(r'(?sm)([<\[](?:audio|video)[^>\]]*[>\]])\s*'), r'\1'),
        (re.compile(r'(?sm)\s*([<\[]/(?:audio|video)[>\]])'), r'\1'),
        (re.compile(r'(?sm)\s*(<(?:source|track)[^>]*>)\s*'), r'\1'),
    ),
    '1': (
        # take care of duplicates
        (re.compile(r"(?sm)\n\n+"), "\n\n"),
    ),
    'splitter': re.compile(r'(?sm)\n\s*\n'),
    '2': (
        # under certain strange conditions it could create a P of entirely whitespace
	    (re.compile(r'(?sm)<p>\s*</p>'), ''),
        (re.compile(r'(?sm)<p>([^<]+)</(div|address|form)>'), r"<p>\1</p></\2>"),
        # don't pee all over a tag
        (re.compile(r'(?sm)<p>\s*(</?%s[^>]*>)\s*</p>' % AUTOP_ALLBLOCKS), r"\1"),
        # problem with nested lists
        (re.compile(r"(?sm)<p>(<li.+?)</p>"), r"\1"),
        (re.compile(r'(?smi)<p><blockquote([^>]*)>'), r"<blockquote\1><p>"),
        (re.compile(r'</blockquote></p>'), '</p></blockquote>'),
        (re.compile(r'(?sm)<p>\s*(</?%s[^>]*>)' % AUTOP_ALLBLOCKS), r"\1"),
        (re.compile(r'(?sm)(</?%s[^>]*>)\s*</p>' % AUTOP_ALLBLOCKS), r"\1"),
    ),
    'br': (
        (
            re.compile(r'(?sm)<(script|style).*?</\1>'),
            lambda m: m.group(0).replace('\n', '<WPPreserveNewline />')
        ),
        # optionally make line breaks
        (re.compile(r'(?sm)(?<!<br />)\s*\n'), "<br />\n"),
        (re.compile(r'<WPPreserveNewline />'), "\n"),
    ),
    '3': (
        (re.compile(r'(?sm)(</?%s[^>]*>)\s*<br />' % AUTOP_ALLBLOCKS), r"\1"),
        (re.compile(r'(?sm)<br />(\s*</?(?:p|li|div|dl|dd|dt|th|pre|td|ul|ol)[^>]*>)'), r'\1'),
        (re.compile(r"(?sm)\n</p>$"), '</p>'),
    ),
}


def _apply_patterns(source, patterns):
    for pattern, repl in patterns:
        source = pattern.sub(repl, source)
    return source


def balance_tags(content, texturize=True):
    
    if not content.strip():
        return content
    
    content = CHARREF.sub(lambda m: unichr(int(m.group(1))), content)
    
    content = _apply_patterns(content, BALANCE_SUBS)
    
    buffer = []
    offset = 0
    verbatim = 0
    last_char = ''
    tagstack = deque()
    scan = BALANCE_SCANNER.scanner(content)
    
    while True:
        
        m = scan.search()
        if not m:
            break
        
        closing, tag, attrs = m.groups()
        tag = tag.lower()
        attrs = attrs or u''
        text_block = content[offset:m.start()]
        offset = m.end()
        
        if texturize:
            if verbatim:
                last_char = ''
            else:
                text_block = texturize_block(text_block, last_char)
                last_char = '' if not text_block else text_block[-1]

        buffer.append(text_block)
        
        if closing:
            
            if not tagstack:
                # missing tag, skip it
                pass
            elif tagstack[-1] == tag:
                # all is well
                buffer.append(u'</%s>' % tag)
                tagstack.pop()
                if texturize and tag in TXTR_VERBATIM and verbatim:
                     verbatim -= 1
            else:
                # look for the tag in the stack
                i = len(tagstack)
                while i:
                    if tagstack[-i] == tag:
                        for j in range(i):
                            _tag = tagstack.pop()
                            if texturize and _tag in TXTR_VERBATIM and verbatim:
                                verbatim -= 1
                            buffer.append(u'</%s>' % _tag)
                        break
                    i -= 1

        else:
            
            if attrs.endswith('/'):
                # check if it really is a closing tag
                if tag not in BALANCE_SINGLE:
                    attrs = u'%s></%s' % (attrs[:-1], tag)
            elif tag in BALANCE_SINGLE:
                attrs += '/'
            else:
                if tagstack and tag not in BALANCE_NESTABLE and tagstack[-1] == tag:
                    buffer.append(u'</%s>' % tag)
                else:
                    tagstack.append(tag)
                if texturize and tag in TXTR_VERBATIM:
                    verbatim += 1

            buffer.append(u'<%s%s>' % (tag, attrs))

    if len(content) > offset:
        if texturize and not verbatim:
            buffer.append(texturize_block(content[offset:], last_char))
        else:
            buffer.append(content[offset:])

    while tagstack:
        buffer.append(u'</%s>' % tagstack.pop())
        
    return u''.join(buffer)


def texturize_block(text, previous_last_char=''):
    """Texturize a block of text, assuming it contains no tags."""
    
    text = _apply_patterns(text, TXTR_ESCAPES + TXTR_SINGLES)
        
    # quotes
    if text == "'":
        # Special case: single-character ' token
        return u"’" if TXTR_NOSPACE.match(previous_last_char) else u"‘"
    
    if text == '"':
        # Special case: single-character " token
        return u"”" if TXTR_NOSPACE.match(previous_last_char) else u"“"
    
    text = _apply_patterns(text, TXTR_QUOTES)

    # start a word, use a tag, apostrophe.
    if TXTR_WORD.match(previous_last_char) and text and text[0] == "'":
        text = u"’" + text[1:]

    return text


def convert_shortcodes(content):
    # TODO: implement basic WP shortcodes in wp-includes/media.php, and add
    # an optional WPKIT_SHORTCODES setting, that can be set to a
    # list of (re pattern, string or callable) tuples.
    # Pretty low on the list as preformatting takes care of shortcodes.
    return content


def strip_shortcodes(content):
    if '[' not in content:
        return content
    return SHORTCODE_RE.sub(u'', content)


def autop(pee, br=True):
    
    pre_tags = {}
    if not pee.strip():
        return

    pee += '\n' # just to make things a little easier, pad the end

    if '<pre' in pee:
        pee_parts = pee.split('</pre>')
        last_pee = pee_parts.pop()
        pee = ''
        i = 0
        
        for pee_part in pee_parts:
            start = pee_part.find('<pre')
            
            if (start < 0):
                pee += pee_part
                continue
            
            name = "<pre wp-pre-tag-%s></pre>" % i
            pre_tags[name] = pee_part[start:] + '</pre>'
            
            pee += pee_part[:start] + name
            i += 1

        pee += last_pee

    pee = _apply_patterns(pee, AUTOP_SUBS['0'])
    
    pee = pee.replace('\r\n', '\n') # cross-platform newlines
    pee = pee.replace('\r', '\n') # cross-platform newlines

    if '<option' in pee:
		# no P/BR around option
        pee = _apply_patterns(pee, AUTOP_SUBS['option'])

    if '</object>' in pee:
		# no P/BR around param and embed
        pee = _apply_patterns(pee, AUTOP_SUBS['object'])

    if '<source' in pee or '<track' in pee:
        # no P/BR around source and track
        pee = _apply_patterns(pee, AUTOP_SUBS['source'])

    pee = _apply_patterns(pee, AUTOP_SUBS['1'])

    # make paragraphs, including one at the end
    pees = [t for t in AUTOP_SUBS['splitter'].split(pee) if t]
    pee = ''
    
    for tinkle in pees:
        while tinkle.endswith('\n'):
            tinkle = tinkle[:-1]
        pee += '<p>%s</p>\n' % tinkle
	
    pee = _apply_patterns(pee, AUTOP_SUBS['2'])

    if br:
        pee = _apply_patterns(pee, AUTOP_SUBS['br'])

    pee = _apply_patterns(pee, AUTOP_SUBS['3'])

    for k, v in pre_tags.items():
        pee = pee.replace(k, v)

    return pee


def auto_excerpt(post):
    """Returns the user-defined excerpt if it's defined, an auto-generated
    one if it's not.
    """
    if post.excerpt:
        return post.excerpt
        
    if not post.content or not post.content.strip():
        return u''
        
    # quick and dirty, use preformatting for something better
    return u' '.join(strip_html(strip_shortcodes(post.content.strip())).split()[:55])
    
    

def format_content(content):
    return autop(balance_tags(convert_shortcodes(content)))


def formatted_part(post, part=None):
    # TODO: use a blog.format_content() method that can be overridden via settings
    
    if post.content_filtered:
        try:
            pubdate, excerpt, leader, trailer, content = post.content_filtered.split('\0\0')
            pubdate = datetime.datetime.fromtimestamp(pubdate)
        except (TypeError, ValueError):
            pass
        else:
            if pubdate == post.date_gmt:
                all_parts = {
                    'excerpt': excerpt, 'leader':leader,
                    'trailer': trailer, 'content':content
                }
                return all_parts if part is None else all_parts.get(part)

    all_parts = {
        'leader':post.content_leader,
        'trailer':post.content_trailer, 'content':post.content
    }
    
    if part == 'excerpt':
        return auto_excerpt(post)

    if part is not None:
        part = all_parts.get(part)
        return '' if not part else format_content(part)
    
    for k in all_parts:
        all_parts[k] = format_content(all_parts[k])
        
    all_parts['excerpt'] = auto_excerpt(post)
    
    return all_parts
    

if __name__ == '__main__':
    print repr(autop(
        u'''<div style="float: left;margin-left: 10px;margin-bottom: 10px">\n <a href="http://www.flickr.com/photos/ludoo/9023529/" title="photo sharing"><img src="http://photos8.flickr.com/9023529_b96d7afa1a_m.jpg" alt="" style="border: solid 2px #000000" /></a>\n</div>\nAnche a Milano comincia a farsi strada la moda di ristrutturare spazi industriali dismessi, che in citt\xe0 un po\' meno "bacchettone" \xe8 ormai consolidata da anni. Nonostante l\'allergia verso tutto ci\xf2 che appunto "va di moda", devo ammettere che spazi di questo tipo hanno dei pregi innegabili: costano poco (per quanto poco pu\xf2 costare una casa a Milano), sono spesso pittoreschi, e permettono una grande libert\xe0 nella disposizione.<br />\n<br />\nNella foto vedete la casa-ufficio di un amico architetto, che dopo aver girovagato tra Stati Uniti e Italia si \xe8 deciso prendere una dimora fissa in uno spazio industriale imboscato tra il Naviglio Grande e quello Pavese. La sistemazione \xe8 sua (ovvio, dato che fa l\'architetto), e le <a href="http://www.flickr.com/photos/ludoo/tags/officewest/">poche immagini</a> oltre a essere incomplete non gli rendono giustizia.\n<br />'''
    ))
