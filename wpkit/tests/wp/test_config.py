from django.conf import settings
from django.test import TestCase
from django_nose.tools import *

from wpkit.wp.config import parse_config


class TestConfig(TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.wp_root = getattr(settings, 'WPKIT_WP_ROOT', '/var/www')
        if cls.wp_root.endswith('/'):
            cls.wp_root = cls.wp_root[:-1]
        cls.config = parse_config(cls.wp_root)
    
    def test_noconfig(self):
        assert_raises_regexp(
            ValueError, "No wp config found in '/dummy/wp-config.php'",
            parse_config, '/dummy'
        )
        
    def test_paths(self):
        assert_equals(
            self.config,
            parse_config(self.wp_root+'/')
        )
        
    def test_result_type(self):
        assert_equals(type(parse_config(self.wp_root)), dict)
        
    def test_string(self):
        assert_equals(type(self.config['AUTH_KEY']), str)
        assert_equals(len(self.config['AUTH_KEY']), 64)
        
    def test_bool(self):
        assert_equals(type(self.config['WP_DEBUG']), bool)
        assert_equals(self.config['WP_DEBUG'], False)
        assert_true(self.config['WP_ALLOW_MULTISITE'])
        
    def test_int(self):
        assert_equals(self.config['SITE_ID_CURRENT_SITE'], 1)
        
    def test_prefix(self):
        assert_equals(self.config['table_prefix'], 'wp_')
