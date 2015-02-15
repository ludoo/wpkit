import os
import re


CONFIG_RE = re.compile(r'(?sm)^\s*define\s*\(\s*(\S+)\s*,\s*(.+?)\s*\);')
PREFIX_RE = re.compile(r'''(?sm)^\s*\$table_prefix\s*=\s*['"]([a-zA-Z0-9_]+)['"]\s*;''');


def parse_config(wp_root):
    
    config_path = os.path.join(wp_root, 'wp-config.php')
    
    try:
        config = file(config_path).read()
    except (OSError, IOError), e:
        raise ValueError("No wp config found in '%s': %s" % (config_path, e))
    
    data = {}
    
    for const_name, const_value in CONFIG_RE.findall(config):
        if const_name and const_name[0] in ("'\""):
            const_name = const_name[1:-1]
        if const_value and const_value[0] in ("'\""):
            const_value = const_value[1:-1]
        elif const_value in ('true', 'false'):
            const_value = const_value == 'true'
        else:
            try:
                const_value = int(const_value)
            except ValueError:
                pass
        if const_name.startswith('DB_'):
            continue
        data[const_name] = const_value
    
    prefix_match = PREFIX_RE.search(config)
    
    if prefix_match:
        data['table_prefix'] = prefix_match.group(1)
    else:
        raise ValueError("No table_prefix variable found in '%s'" % config_path)
    
    return data
