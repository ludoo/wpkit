import re
import datetime
import htmlentitydefs

from functools import partial

from ..lib.external.phpserialize import loads, phpobject


RE_STRIP = re.compile("(?s)<[^>]*>|&#?\w+;")


def strtobool(s):
    """Damn WP and its habit of using strings instead of ints for bools in MySQL"""
    try:
        i = int(s)
    except (TypeError, ValueError):
        return s
    return bool(i)


def kwargs_to_filter(kw):
    """Converts key/values in the form year=yyyy to key/values usable as queryset
       filters, pretty inefficient and with no checks on data.
    """
    
    d = {}
    for k in ('year', 'month', 'day', 'hour', 'minute', 'second'):
        if k in kw:
            try:
                d['date__'+k] = int(kw[k])
            except (TypeError, ValueError):
                continue
    return d


def kwargs_to_datetime(kw, as_date=False):
    """Converts key/values in the form year=yyyy to a date or datetime object.
       If a datetime is needed and we don't have enough arguments to obtain
       a complete datetime, return a range.
    """

    dt_args = []
    for k in ('year', 'month', 'day', 'hour', 'minute', 'second'):
        if k not in kw:
            break
        try:
            dt_args.append(int(kw[k]))
        except (TypeError, ValueError):
            break
    
    if not dt_args:
        return
    
    dt_args_len = len(dt_args)
    while len(dt_args) < 3:
        dt_args.append(1)
    
    try:
        start = datetime.datetime(*dt_args)
    except ValueError:
        return
    
    if as_date:
        return start.date()
        
    if dt_args_len == 6: # exact datetime
        return start

    if dt_args_len == 1: # year range
        return (start, start.replace(year=start.year+1))
    
    if dt_args_len == 2: # month range
        return (start, (start+datetime.timedelta(days=31)).replace(day=1))
    
    if dt_args_len == 3: # day range
        return (start, start+datetime.timedelta(days=1))
    
    # hour/minute ranges
    return (start, start+datetime.timedelta(minutes=60 if dt_args_len == 4 else 1))


# http://effbot.org/zone/re-sub.htm#strip-html


def strip_html(text, encoding='utf8'):
    if not isinstance(text, unicode):
        text = text.decode(encoding, 'ignore')
    def fixup(m):
        text = m.group(0)
        if text[:1] == "<":
            return "" # ignore tags
        if text[:2] == "&#":
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        elif text[:1] == "&":
            entity = htmlentitydefs.entitydefs.get(text[1:-1])
            if entity:
                if entity[:2] == "&#":
                    try:
                        return unichr(int(entity[2:-1]))
                    except ValueError:
                        pass
                else:
                    return entity.decode('iso-8859-1', 'ignore')
        return text # leave as is
    return RE_STRIP.sub(fixup, RE_STRIP.sub(fixup, text))
    #return re.sub("(?s)<[^>]*>|&#?\w+;", fixup, text)


php_unserialize = partial(loads, object_hook=phpobject)
