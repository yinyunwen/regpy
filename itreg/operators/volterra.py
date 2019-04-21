from . import LinearOperator, NonlinearOperator, Params

import numpy as np


class Volterra(LinearOperator):
    """The discrete Volterra operator.

    The discrete Volterra operator is essentially a cumulative sum as in
    :func:`numpy.cumsum`. See Notes below.

    Parameters
    ----------
    domain : :class:`~itreg.spaces.Space`
        The domain on which the operator is defined.
    range : :class:`~itreg.spaces.Space`, optional
        The operator's codomain. Defaults to `domain`.
    spacing : float, optional
        The grid spacing. Defaults to 1.

    Notes
    -----
    The Volterra operator :math:`V` is defined as

    .. math:: (Vf)(x) = \int_0^x f(t) dt.

    Its discrete form, using a Riemann sum, is simply

    .. math:: (Vx)_i = h \sum_{j \leq i} x_j,

    where :math:`h` is the grid spacing.
    """

    def __init__(self, domain, range=None, spacing=1):
        range = range or domain
        assert len(domain.shape) == 1
        assert domain.shape == range.shape
        super().__init__(Params(domain, range, spacing=spacing))

    def _eval(self, params, x):
        return params.spacing * np.cumsum(x)

    def _adjoint(self, params, y):
        return params.spacing * np.flipud(np.cumsum(np.flipud(y)))


class NonlinearVolterra(NonlinearOperator):
    """The non-linear discrete Volterra operator.

    This is like the linear :class:`~itreg.operators.Volterra` operator with an
    additional exponent:

    .. math:: (Vx)_i = h \sum_{j \leq i} x_j^n,

    Parameters
    ----------
    domain : :class:`~itreg.spaces.Space`
        The domain on which the operator is defined.
    exponent : float
        The exponent.
    range : :class:`~itreg.spaces.Space`, optional
        The operator's range. Defaults to `domain`.
    spacing : float, optional
        The grid spacing. Defaults to 1.
    """

    def __init__(self, domain, exponent, range=None, spacing=1):
        range = range or domain
        assert len(domain.shape) == 1
        assert domain.shape == range.shape
        super().__init__(
            Params(domain, range, exponent=exponent, spacing=spacing))

    def _eval(self, params, x, differentiate=False):
        if differentiate:
            self.factor = params.exponent * x**(params.exponent - 1)
        return params.spacing * np.cumsum(x**params.exponent)

    def _deriv(self, params, x):
        return params.spacing * np.cumsum(self.factor * x)

    def _adjoint(self, params, y):
        return params.spacing * np.flipud(np.cumsum(np.flipud(
            self.factor * y)))
