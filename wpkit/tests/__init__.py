from difflib import unified_diff


class Differ(object):
    
    def __init__(self, expected, result):
        self.expected = expected if isinstance(expected, str) else expected.encode('utf-8')
        self.result = result if isinstance(result, str) else result.encode('utf-8')
        
    def __str__(self):
        diff = list(unified_diff(
            self.expected.split("\n"), self.result.split("\n"), 'expected', 'result'
        ))
        if diff:
            return "\n" + "\n".join(diff)
        return '[--- no differences found ---]'
