import datetime

from django.test import TestCase
from django_nose.tools import *
from nose.tools import eq_

from wpkit.wp import utils


KWARGS_TO_FILTER_TESTS = (
    ({'year':'2015', 'a':1}, {'date__year':2015}),
    ({'year':'2015', 'month':'a', 'a':1}, {'date__year':2015}),
)

KWARGS_TO_DATETIME = (
    (
        {'year':'-1', 'a':1}, None
    ),
    (
        {'year':'2015', 'a':1},
        (datetime.datetime(2015, 1, 1, 0, 0), datetime.datetime(2016, 1, 1, 0, 0))
    ),
    (
        {'year':'2015', 'month':'a', 'a':1},
        (datetime.datetime(2015, 1, 1, 0, 0), datetime.datetime(2016, 1, 1, 0, 0))
    ),
    (
        {'year':'2015', 'month':'12'},
        (datetime.datetime(2015, 12, 1), datetime.datetime(2016, 1, 1))
    ),
    (
        {'year':'2015', 'month':'12', 'day':'15', 'a':1},
        (datetime.datetime(2015, 12, 15), datetime.datetime(2015, 12, 16))
    ),
    (
        {'year':'2015', 'month':'12', 'day':'15', 'minute':'1'},
        (datetime.datetime(2015, 12, 15), datetime.datetime(2015, 12, 16))
    ),
    (
        {'year':'2015', 'month':'12', 'day':'15', 'hour':'1'},
        (datetime.datetime(2015, 12, 15, 1), datetime.datetime(2015, 12, 15, 2))
    ),
    (
        {'year':'2015', 'month':'12', 'day':'15', 'hour':'1', 'seconds':15},
        (datetime.datetime(2015, 12, 15, 1), datetime.datetime(2015, 12, 15, 2))
    ),
)

KWARGS_TO_DATE = (
    ({'year':'-1', 'a':1}, None),
    ({'year':'2015', 'a':1}, datetime.date(2015, 1, 1)),
    ({'year':'2015', 'month':'a', 'a':1}, datetime.date(2015, 1, 1)),
    ({'year':'2015', 'month':'12'}, datetime.date(2015, 12, 1)),
    ({'year':'2015', 'month':'12', 'day':'15', 'a':1}, datetime.date(2015, 12, 15)),
    ({'year':'2015', 'month':'12', 'day':'15', 'minute':'1'}, datetime.date(2015, 12, 15)),
    ({'year':'2015', 'month':'12', 'day':'15', 'hour':'1'}, datetime.date(2015, 12, 15)),
    ({'year':'2015', 'month':'12', 'day':'15', 'hour':'1', 'seconds':15}, datetime.date(2015, 12, 15)),
)


class TestUtils(TestCase):
    
    def test_kwargs_to_filter(self):
        for kwargs, expected in KWARGS_TO_FILTER_TESTS:
            assert_equals(expected, utils.kwargs_to_filter(kwargs))

    def test_kwargs_to_datetime(self):
        for i, test in enumerate(KWARGS_TO_DATETIME):
            kwargs, expected = test
            result = utils.kwargs_to_datetime(kwargs)
            eq_(result, expected, "test %i failed: %s" % (i, result))

    def test_kwargs_to_date(self):
        for i, test in enumerate(KWARGS_TO_DATE):
            kwargs, expected = test
            result = utils.kwargs_to_datetime(kwargs, as_date=True)
            eq_(result, expected, "test %i failed: %s" % (i, result))
