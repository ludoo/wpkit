#!/usr/bin/env python

from setuptools import setup


__revision__ = '0.1'


setup(
    name                = 'WPkit',
    version             = __revision__,
    description         = 'WP toolkit for Django',
    author              = 'Ludovico Magnocavallo',
    author_email        = 'ludo@qix.it',
    packages            = ['wpkit'],
    install_requires    = [
        'Django==1.7',
        'MySQL-python>=1.2.5',
        'rfc3339>=5',
    ]
)