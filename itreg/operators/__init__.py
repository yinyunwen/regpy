import numpy as np
from scipy.linalg import cho_factor, cho_solve

from .. import spaces
from .. import util


class Revocable:
    def __init__(self, val):
        self.__val = val

    @classmethod
    def take(cls, other):
        return cls(other.revoke())

    def get(self):
        try:
            return self.__val
        except AttributeError:
            raise RuntimeError('Attempted to use revoked reference')

    def revoke(self):
        val = self.get()
        del self.__val
        return val


class BaseOperator:
    log = util.classlogger

    def __init__(self, domain, codomain, *, cloneparams=[]):
        assert isinstance(domain, spaces.GenericDiscretization)
        assert isinstance(codomain, spaces.GenericDiscretization)
        self.domain, self.codomain = domain, codomain
        for attr in self.__dict__:
            if attr.startswith('_'):
                self.log.warn(
                    'Data attribute {} set in constructor, should probably be set in _alloc method'
                    .format(attr))
        for attr in cloneparams:
            assert not attr.startswith('_'), 'Data attribute {} listed in cloneparams'.format(attr)
        self._cloneparams = cloneparams
        self._frozen = True
        self._alloc()

    def _alloc(self):
        pass

    def __setattr__(self, name, value):
        try:
            if self._frozen and not name.startswith('_'):
                raise RuntimeError(
                    'Attempted to set parameter attribute \'{}\' outside __init__'
                    .format(name))
        except AttributeError:
            pass
        object.__setattr__(self, name, value)

    def clone(self):
        cls = type(self)
        instance = cls.__new__(cls)
        for attr, val in self.__dict__.items():
            if not attr.startswith('_'):
                instance.__dict__[attr] = val
        for attr in self._cloneparams:
            setattr(instance, attr, getattr(self, attr).clone())
        instance._frozen = True
        instance._alloc()
        return instance

    def _ensure_initialized(self):
        try:
            self._frozen
        except AttributeError:
            raise RuntimeError(
                'Attempted to use operator before base class __init__ was called'
            ) from None

    def __call__(self, x):
        raise NotImplementedError

    def linearize(self, x):
        raise NotImplementedError


class NonlinearOperator(BaseOperator):
    def __call__(self, x):
        assert x in self.domain
        self._ensure_initialized()
        self.__revoke()
        y = self._eval(x, differentiate=False)
        assert y in self.codomain
        return y

    def linearize(self, x):
        assert x in self.domain
        self._ensure_initialized()
        self.__revoke()
        y = self._eval(x, differentiate=True)
        assert y in self.codomain
        deriv = Derivative(self.__get_handle())
        return y, deriv

    def __revoke(self):
        try:
            self.__handle = Revocable.take(self.__handle)
        except AttributeError:
            pass

    def __get_handle(self):
        try:
            return self.__handle
        except AttributeError:
            self.__handle = Revocable(self)
            return self.__handle

    def _eval(self, x, differentiate=False):
        raise NotImplementedError

    def _derivative(self, x):
        raise NotImplementedError

    def _adjoint(self, y):
        raise NotImplementedError

    def __mul__(self, other):
        if isinstance(other, BaseOperator):
            return NonlinearOperatorComposition(self, other)
        else:
            return NotImplemented

    def __rmul__(self, other):
        if isinstance(other, BaseOperator):
            return NonlinearOperatorComposition(other, self)
        else:
            return NotImplemented


class LinearOperator(BaseOperator):
    def __call__(self, x):
        assert x in self.domain
        self._ensure_initialized()
        y = self._eval(x)
        assert y in self.codomain
        return y

    def linearize(self, x):
        return self(x), self

    @util.memoized_property
    def adjoint(self):
        self._ensure_initialized()
        return Adjoint(self)

    def norm(self, iterations=10):
        h = self.domain.rand()
        norm = np.sqrt(np.real(np.vdot(h, h)))
        for i in range(iterations):
            h = h / norm
            h = self.hermitian(self(h))
            norm = np.sqrt(np.real(np.vdot(h, h)))
        return np.sqrt(norm)

    def _eval(self, x):
        raise NotImplementedError

    def _adjoint(self, x):
        raise NotImplementedError

    def __mul__(self, other):
        if isinstance(other, LinearOperator):
            return LinearOperatorComposition(self, other)
        else:
            return NotImplemented

    def __rmul__(self, other):
        if isinstance(other, LinearOperator):
            return LinearOperatorComposition(other, self)
        else:
            return NotImplemented


class Adjoint(LinearOperator):
    def __init__(self, op):
        self.op = op
        super().__init__(op.codomain, op.domain, cloneparams=['op'])

    def _eval(self, x):
        return self.op._adjoint(x)

    def _adjoint(self, x):
        return self.op._eval(x)

    @property
    def adjoint(self):
        return self.op


class Derivative(LinearOperator):
    def __init__(self, op):
        if not isinstance(op, Revocable):
            # Wrap plain operators in a Revocable that will never be revoked to
            # avoid case distinctions below.
            op = Revocable(op)
        self.op = op
        _op = op.get()
        super().__init__(_op.domain, _op.codomain)

    def clone(self):
        raise RuntimeError("Derivatives can't be cloned")

    def _eval(self, x):
        return self.op.get()._derivative(x)

    def _adjoint(self, x):
        return self.op.get()._adjoint(x)


class NonlinearOperatorComposition(NonlinearOperator):
    def __init__(self, f, g):
        assert f.domain == g.codomain
        self.f, self.g = f, g
        super().__init__(g.domain, f.codomain, cloneparams=['f', 'g'])

    def _eval(self, x, differentiate=False):
        if differentiate:
            gx, dg_x = self.g.linearize(x)
            y, df_gx = self.f.linearize(gx)
            self._dg_x = dg_x
            self._df_gx = df_gx
            return y
        else:
            return self.f(self.g(x))

    def _derivative(self, x):
        return self._df_gx(self._dg_x(x))

    def _adjoint(self, y):
        return self._dg_x.adjoint(self._df_gx.adjoint(y))


class LinearOperatorComposition(LinearOperator):
    def __init__(self, f, g):
        assert f.domain == g.codomain
        self.f, self.g = f, g
        super().__init__(g.domain, f.codomain, cloneparams=['f', 'g'])

    def _eval(self, x):
        return self.f(self.g(x))

    def _adjoint(self, y):
        return self.g.adjoint(self.f.adjoint(y))


class Identity(LinearOperator):
    def __init__(self, domain):
        super().__init__(domain, domain)

    def _eval(self, x):
        return x

    def _adjoint(self, x):
        return x


class CholeskyInverse(LinearOperator):
    def __init__(self, op):
        assert op.domain == op.codomain
        domain = op.domain
        matrix = np.empty((domain.size,) * 2, dtype=float)
        for j, elm in enumerate(domain.iter_basis()):
            matrix[j, :] = domain.flatten(op(elm))
        self.factorization = cho_factor(matrix)
        super().__init__(
            domain=domain,
            codomain=domain)

    def _eval(self, x):
        return self.domain.fromflat(
            cho_solve(self.factorization, self.domain.flatten(x)))

    def _adjoint(self, x):
        return self._eval(x)


class CoordinateProjection(LinearOperator):
    def __init__(self, domain, mask):
        mask = np.asarray(mask)
        assert mask.dtype == bool
        assert mask.shape == domain.shape
        self.mask = mask
        super().__init__(
            domain=domain,
            codomain=spaces.GenericDiscretization(np.sum(mask), dtype=domain.dtype))

    def _eval(self, x):
        return x[self.mask]

    def _adjoint(self, x):
        y = self.domain.zeros()
        y[self.mask] = x
        return y


class PointwiseMultiplication(LinearOperator):
    def __init__(self, domain, factor):
        factor = np.asarray(factor)
        # Check that factor can broadcast against domain elements without
        # increasing their size.
        assert factor.ndim <= domain.ndim
        for sf, sd in zip(factor.shape[::-1], domain.shape[::-1]):
            assert sf == sd or sf == 1
        assert domain.is_complex or not util.is_complex_dtype(factor)
        self.factor = factor
        super().__init__(domain, domain)

    def _eval(self, x):
        return self.factor * x

    def _adjoint(self, x):
        return np.conj(self.factor) * x


class FourierTransform(LinearOperator):
    def __init__(self, domain):
        assert isinstance(domain, spaces.UniformGrid)
        super().__init__(domain, domain.dualgrid)

    def _eval(self, x):
        return self.domain.fft(x)

    def _adjoint(self, y):
        return self.domain.ifft(y)


from .mediumscattering import MediumScattering
from .volterra import Volterra, NonlinearVolterra
