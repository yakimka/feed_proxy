from unittest.mock import ANY

import pytest
from pytest_mock import MockerFixture

from feed_proxy.db import __main__ as dunder_main


def test_run_main(mocker: MockerFixture):
    m_parser = mocker.patch.object(dunder_main.argparse, 'ArgumentDefaultsHelpFormatter')
    m_CommandLine = mocker.patch.object(dunder_main, 'CommandLine')
    parser = m_CommandLine.return_value.parser

    with pytest.raises(SystemExit):
        dunder_main.main()

    assert parser.formatter_class == m_parser
    parser.add_argument.assert_called_once_with('--db-url', default=ANY, help=ANY)


def test_run_main_cmd_not_in_options(mocker: MockerFixture):
    alembic = mocker.patch.object(dunder_main, 'CommandLine').return_value
    alembic.parser.parse_args.return_value = ['cmd']
    m_make_alembic_config = mocker.patch.object(dunder_main, 'make_alembic_config')

    with pytest.raises(SystemExit):
        dunder_main.main()

    m_make_alembic_config.assert_called_once_with(['cmd'])
    alembic.run_cmd.assert_called_once_with(m_make_alembic_config.return_value, ['cmd'])


def test_run_main_cmd_in_options(mocker: MockerFixture):
    mocker.patch.object(dunder_main, 'CommandLine')

    with pytest.raises(SystemExit) as e:
        dunder_main.main()

    assert e.value.code == 128
