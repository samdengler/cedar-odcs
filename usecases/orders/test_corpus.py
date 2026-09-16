import pytest

from cedar_osdc.engine.corpus import cases, check
from usecases.orders.usecase import ROOT


@pytest.mark.parametrize("policies,entities,request_spec", list(cases(ROOT)))
def test_case(policies, entities, request_spec):
    check(policies, entities, request_spec)
