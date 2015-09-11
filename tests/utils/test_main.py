# -*- coding: utf-8 -*-

import logging
import os
import platform
import stat

import click
from click.testing import CliRunner

import click_log

import pytest

import requests

from vdirsyncer import utils
from vdirsyncer.cli import pass_context
from vdirsyncer.cli.config import Config

# These modules might be uninitialized and unavailable if not explicitly
# imported
import vdirsyncer.utils.compat  # noqa
import vdirsyncer.utils.http  # noqa


from .. import blow_up


@pytest.fixture(autouse=True)
def no_debug_output(request):
    logger = click_log.basic_config('vdirsyncer')
    logger.setLevel(logging.WARNING)
    old = logger.level

    def teardown():
        logger.setLevel(old)

    request.addfinalizer(teardown)


def test_get_class_init_args():
    class Foobar(object):
        def __init__(self, foo, bar, baz=None):
            pass

    all, required = utils.get_class_init_args(Foobar)
    assert all == {'foo', 'bar', 'baz'}
    assert required == {'foo', 'bar'}


def test_get_class_init_args_on_storage():
    from vdirsyncer.storage.memory import MemoryStorage

    all, required = utils.get_class_init_args(MemoryStorage)
    assert all == set(['fileext', 'collection', 'read_only', 'instance_name'])
    assert not required


def test_request_ssl(httpsserver):
    httpsserver.serve_content('')  # we need to serve something

    with pytest.raises(requests.exceptions.SSLError) as excinfo:
        utils.http.request('GET', httpsserver.url)
    assert 'certificate verify failed' in str(excinfo.value)

    utils.http.request('GET', httpsserver.url, verify=False)


def _fingerprints_broken():
    from pkg_resources import parse_version as ver
    tolerant_python = (
        utils.compat.PY2 and platform.python_implementation() != 'PyPy'
    )
    broken_urllib3 = ver(requests.__version__) <= ver('2.5.1')
    return broken_urllib3 and not tolerant_python


@pytest.mark.skipif(_fingerprints_broken(),
                    reason='https://github.com/shazow/urllib3/issues/529')
@pytest.mark.parametrize('fingerprint', [
    '94:FD:7A:CB:50:75:A4:69:82:0A:F8:23:DF:07:FC:69:3E:CD:90:CA',
    '19:90:F7:23:94:F2:EF:AB:2B:64:2D:57:3D:25:95:2D'
])
def test_request_ssl_fingerprints(httpsserver, fingerprint):
    httpsserver.serve_content('')  # we need to serve something

    utils.http.request('GET', httpsserver.url, verify=False,
                       verify_fingerprint=fingerprint)
    with pytest.raises(requests.exceptions.SSLError) as excinfo:
        utils.http.request('GET', httpsserver.url,
                           verify_fingerprint=fingerprint)

    with pytest.raises(requests.exceptions.SSLError) as excinfo:
        utils.http.request('GET', httpsserver.url, verify=False,
                           verify_fingerprint=''.join(reversed(fingerprint)))
    assert 'Fingerprints did not match' in str(excinfo.value)
