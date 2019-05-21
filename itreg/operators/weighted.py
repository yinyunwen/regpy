from . import LinearOperator
from itreg.util import instantiate


class Weighted(LinearOperator):
    """Weight the given linear operator in a certain way.

    Parameters
    ----------
    op : :class:`itreg.operators.~LinearOperator`
        The operator.
    weight : array
        The weight.
    """

    def __init__(self, op, weight):
        super().__init__(
            op.params.domain, op.params.codomain, op=op, weight=weight)

    @instantiate
    class operator:
        def eval(self, params, x, **kwargs):
            return params.weight * params.op(x)

        def adjoint(self, params, y, **kwargs):
            return params.weight * params.op.adjoint(y)
