from copy import copy

import numpy as np

from itreg.spaces import discrs
from itreg import util, operators, functionals


class HilbertSpace:
    log = util.classlogger

    def __init__(self, discr):
        assert isinstance(discr, discrs.Discretization)
        self.discr = discr

    @property
    def gram(self):
        """The gram matrix as a LinearOperator
        """
        raise NotImplementedError

    @property
    def gram_inv(self):
        """The inverse of the gram matrix as a LinearOperator
        """
        return self.gram.inverse

    def inner(self, x, y):
        """Compute the inner product between to elements.

        This is a convenience wrapper around :meth:`gram`.

        Parameters
        ----------
        x, y : arrays
            The elements for which the inner product should be computed.

        Returns
        -------
        float
            The inner product.
        """
        return np.real(np.vdot(x, self.gram(y)))

    def norm(self, x):
        """Compute the norm of an element.

        This is a convenience wrapper around :meth:`norm`.

        Parameters
        ----------
        x : array
            The elements for which the norm should be computed.

        Returns
        -------
        float
            The norm.
        """
        return np.sqrt(self.inner(x, x))

    @util.memoized_property
    def norm_functional(self):
        return functionals.HilbertNorm(self)

    def __add__(self, other):
        if isinstance(other, HilbertSpace):
            return DirectSum(self, other, flatten=True)
        else:
            return NotImplemented

    def __radd__(self, other):
        if isinstance(other, HilbertSpace):
            return DirectSum(other, self, flatten=True)
        else:
            return NotImplemented

    def __rmul__(self, other):
        if np.isreal(other):
            return DirectSum((other, self), flatten=True)
        else:
            return NotImplemented


class HilbertPullBack(HilbertSpace):
    """Pullback of a hilbert space on the codomain of an operator to its
    domain.

    For `op : X -> Y` with Y a Hilbert space, the inner product on X is defined
    as

        <a, b> := <op(x), op(b)>

    (This really only works in finite dimensions due to completeness). The gram
    matrix of the pullback space is simply `G_X = op^* G_Y op`.

    Note that computation of the inverse of `G_Y` is not trivial.

    Parameters
    ----------
    space : `~itreg.spaces.hilbert.HilbertSpace`
        Hilbert space on the codomain of `op`.
    op : `~itreg.operators.Operator`
        The operator along which to pull back `space`
    inverse : one of None, 'conjugate' or 'cholesky'
        How to compute the inverse gram matrix.
        - None: no inverse will be implemented.
        - 'conjugate': the inverse will be computed as `op^* G_Y^{-1} op`.
          **This is in general not correct**, but may in some cases be an
          efficient approximation.
        - 'cholesky': Implement the inverse via Cholesky decomposition. This
          requires assembling the full matrix.
    """

    def __init__(self, space, op, inverse=None):
        assert op.linear
        if not isinstance(space, HilbertSpace) and callable(space):
            space = space(op.codomain)
        assert isinstance(space, HilbertSpace)
        assert op.codomain == space.discr
        self.op = op
        self.space = space
        super().__init__(op.domain)
        # TODO only compute on demand
        if not inverse:
            self.inverse = None
        elif inverse == 'conjugate':
            self.log.info(
                'Note: Using using T* G^{-1} T as inverse of T* G T. This is probably not correct.')
            self.inverse = op.adjoint * space.gram_inv * op
        elif inverse == 'cholesky':
            self.inverse = operators.CholeskyInverse(self.gram)

    @util.memoized_property
    def gram(self):
        return self.op.adjoint * self.space.gram * self.op

    @property
    def gram_inv(self):
        if self.inverse:
            return self.inverse
        raise NotImplementedError


class DirectSum(HilbertSpace):
    """The direct sum of an arbirtary number of hilbert spaces, with optional
    scaling of the respective norms. The underlying discretization will be the
    :class:`itreg.spaces.discrs.DirectSum` of the underlying discretizations of the
    summands.

    Note that constructing DirectSum instances can be done more comfortably
    simply by adding :class:`~itreg.spaces.hilbert.HilbertSpace` instances and
    by multiplying them with scalars, but see the documentation for
    :class:`itreg.spaces.discrs.DirectSum` for the `flatten` parameter.

    Parameters
    ----------
    *summands : HilbertSpace tuple
        The Hilbert spaces to be summed. Alternatively, summands can be given
        as tuples `(scalar, HilbertSpace)`, which will scale the norm the
        respective summand. The gram matrices and hence the inner products will
        be scaled by `scalar**2`.
    flatten : bool, optional
        Whether summands that are themselves DirectSums should be merged into
        this instance. Default: False.
    discr : discrs.Discretization or callable, optional
        Either the underlying discretization or a factory function that will be
        called with all summands' discretizations passed as arguments and should
        return a discrs.DirectSum instance. Default: discrs.DirectSum.
    """

    def __init__(self, *args, flatten=False, discr=discrs.DirectSum):
        self.summands = []
        self.weights = []
        for arg in args:
            if isinstance(arg, tuple):
                w, s = arg
            else:
                w, s = 1, arg
            assert w > 0
            assert isinstance(s, HilbertSpace)
            if flatten and isinstance(s, type(self)):
                self.summands.extend(s.summands)
                self.weights.extend(w * sw for sw in s.weights)
            else:
                self.summands.append(s)
                self.weights.append(w)

        if isinstance(discr, discrs.Discretization):
            pass
        elif callable(discr):
            discr = discr(*(s.discr for s in self.summands))
        else:
            raise TypeError('discr={} is neither a Discretization nor callable'.format(discr))
        assert all(s.discr == d for s, d in zip(self.summands, discr))

        super().__init__(discr)

    def __eq__(self, other):
        return (
            isinstance(other, type(self)) and
            len(self.summands) == len(other.summands) and
            all(s == t for s, t in zip(self.summands, other.summands)) and
            all(v == w for v, w in zip(self.weights, other.weights))
        )

    @util.memoized_property
    def gram(self):
        ops = []
        for w, s in zip(self.weights, self.summands):
            if w == 1:
                ops.append(s.gram)
            else:
                ops.append(w**2 * s.gram)
        return operators.DirectSum(*ops, domain=self.discr, codomain=self.discr)

    def __getitem__(self, item):
        return self.summands[item]

    def __iter__(self):
        return iter(self.summands)


class AbstractSpace:
    """Class representing abstract hilbert spaces without reference to a
    concrete implementation.

    The motivation for using this construction is to be able to specify e.g. a
    Thikhonov penalty without requiring knowledge of the concrete discretization
    the forward operator uses. See the documentation of
    :class:`~itreg.spaces.hilbert.AbstractSpaceDispatcher` for more details.

    Abstract spaces do not have elements, their sole purpose is to pick the
    proper concrete implementation for a given discretization.

    This class only implements operator overloads so that scaling and adding
    abstract spaces works analogously to the concrete
    :class:`~itreg.spaces.hilbert.HilbertSpace` instances, returning
    :class:`~itreg.spaces.hilbert.AbstractSum` instances.
    """

    def __add__(self, other):
        if callable(other):
            return AbstractSum(self, other, flatten=True)
        else:
            return NotImplemented

    def __radd__(self, other):
        if callable(other):
            return AbstractSum(other, self, flatten=True)
        else:
            return NotImplemented

    def __rmul__(self, other):
        if np.isreal(other):
            return AbstractSum((other, self), flatten=True)
        else:
            return NotImplemented


class AbstractSpaceDispatcher(AbstractSpace):
    """An abstract Hilbert space that can be called on a discretization to get
    the corresponding concrete implementation.

    AbstractSpaceDispatchers provide two kinds of functionality:

    - A decorator method `register(discr_type)` that can be used to declare
      some class or function as the concrete implementation of this abstract
      space for discretizations of type `discr_type` or subclasses thereof,
      e.g.:

          @Sobolev.register(discrs.UniformGrid)
          class SobolevUniformGrid(HilbertSpace):
              ...

    - AbstractSpaces are callable. Calling them on a discretization and
      arbitrary optional keyword arguments finds the corresponding concrete
      :class:`~itreg.spaces.hilbert.HilbertSpace` among all registered
      implementations. If there are implementations for multiple base classes
      of the discretization type, the most specific one will be chosen. The
      chosen implementation will then be called with the discretization and the
      keyword arguments, and the result will be returned.

      If called without a discretization as positional argument, it returns a
      new abstract space with all passed keyword arguments remembered as
      defaults. This allows one e.g. to write

          H = Sobolev(index=2)

      after which `H(grid)` is the same as `Sobolev(grid, index=2)` (which in
      turn will be the same as something like `SobolevUniformGrid(grid, index=2)`,
      depending on the type of `grid`).

    Parameters
    ----------
    name : str
        A name for this abstract space. Currently, this is only used in error
        messages, when no implementation was found for some discretization.
    """

    def __init__(self, name):
        self._registry = {}
        self.name = name
        self.args = {}

    def register(self, discr_type, impl=None):
        if impl is None:
            def decorator(i):
                self._registry[discr_type] = i
                return i
            return decorator
        else:
            self._registry[discr_type] = impl

    def __call__(self, discr=None, **kwargs):
        if discr is None:
            clone = copy(self)
            clone.args = copy(self.args)
            clone.args.update(kwargs)
            return clone
        for cls in type(discr).mro():
            try:
                impl = self._registry[cls]
            except KeyError:
                continue
            kws = copy(self.args)
            kws.update(kwargs)
            result = impl(discr, **kws)
            assert isinstance(result, HilbertSpace)
            return result
        raise NotImplementedError(
            '{} not implemented on {}'.format(self.name, discr)
        )


class AbstractSum(AbstractSpace):
    """Weighted sum of abstract Hilbert spaces.

    The constructor arguments work like for concrete
    :class:`~itreg.spaces.hilbert.HilbertSpace`s, which see. Adding and scaling
    :class:`~itreg.spaces.hilbert.AbstractSpace` instances is again a more
    convenient way to construct AbstractSums.

    This abstract space can only be called on a
    :class:`itreg.spaces.discrs.DirectSum`, in which case it constructs the
    corresponding :class:`itreg.spaces.hilbert.DirectSum` obtained by matching
    up summands, e.g.

        (L2 + 2 * Sobolev(index=1))(grid1 + grid2) == L2(grid1) + 2 * Sobolev(grid2, index=1)
    """

    def __init__(self, *args, flatten=False):
        self.summands = []
        self.weights = []
        for arg in args:
            if isinstance(arg, tuple):
                w, s = arg
            else:
                w, s = 1, arg
            assert w > 0
            assert callable(s)
            if flatten and isinstance(s, type(self)):
                self.summands.extend(s.summands)
                self.weights.extend(w * sw for sw in s.weights)
            else:
                self.summands.append(s)
                self.weights.append(w)

    def __call__(self, discr):
        assert isinstance(discr, discrs.DirectSum)
        return DirectSum(
            *((w, s(d)) for w, s, d in zip(self.weights, self.summands, discr.summands)),
            discr=discr
        )

    def __getitem__(self, item):
        return self.weights[item], self.summands[item]

    def __iter__(self):
        return iter(zip(self.weights, self.summands))


L2 = AbstractSpaceDispatcher('L2')
Sobolev = AbstractSpaceDispatcher('Sobolev')
L2Boundary = AbstractSpaceDispatcher('L2Boundary')
SobolevBoundary = AbstractSpaceDispatcher('SobolevBoundary')


def componentwise(dispatcher, cls=DirectSum):
    def factory(discr):
        return cls(*(dispatcher(s) for s in discr), discr=discr)
    return factory


L2.register(discrs.DirectSum, componentwise(L2))
Sobolev.register(discrs.DirectSum, componentwise(Sobolev))
L2Boundary.register(discrs.DirectSum, componentwise(L2Boundary))
SobolevBoundary.register(discrs.DirectSum, componentwise(SobolevBoundary))


@L2.register(discrs.Discretization)
class L2Generic(HilbertSpace):
    @property
    def gram(self):
        return self.discr.identity

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.discr == other.discr


@L2.register(discrs.UniformGrid)
class L2UniformGrid(HilbertSpace):
    @util.memoized_property
    def gram(self):
        return self.discr.volume_elem * self.discr.identity


@Sobolev.register(discrs.UniformGrid)
class SobolevUniformGrid(HilbertSpace):
    def __init__(self, discr, index=1, axes=None):
        super().__init__(discr)
        self.index = index
        if axes is None:
            axes = range(discr.ndim)
        self.axes = list(axes)

    def __eq__(self, other):
        return (
            isinstance(other, type(self)) and
            self.discr == other.discr and
            self.index == other.index
        )

    @util.memoized_property
    def gram(self):
        ft = operators.FourierTransform(self.discr, axes=self.axes)
        mul = operators.Multiplication(
            ft.codomain,
            self.discr.volume_elem * (
                1 + np.linalg.norm(ft.codomain.coords[self.axes], axis=0)**2
            )**self.index
        )
        return ft.adjoint * mul * ft
