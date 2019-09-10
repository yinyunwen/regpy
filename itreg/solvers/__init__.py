from ..util import classlogger
from ..spaces import HilbertSpace


class Solver:
    """Abstract base class for solvers.

    Attributes
    ----------
    x : array
        The current iterate.
    y : array or `None`
        The value at the current iterate. May be needed by stopping rules, but
        callers should handle the case when it is not available.
    deriv : :class:`~itreg.operators.LinearOperator` or `None`
        The derivative of the operator at the current point. Optional.
    """

    log = classlogger

    def __init__(self):
        self.x = None
        self.y = None
        self.__converged = False

    def converge(self):
        """Mark the solver as converged.

        This is intended to be used by child classes implementing the
        :meth:`_next` method.
        """
        self.__converged = True

    def next(self):
        """Perform a single iteration.

        Returns
        -------
        boolean
            False if the solver already converged and no step was performed.
            True otherwise.
        """
        if self.__converged:
            return False
        self._next()
        return True

    def _next(self):
        """Perform a single iteration.

        This is an abstract method called from the public method :meth:`next`.
        Child classes should override it.

        The main difference to :meth:`next` is that :meth:`_next` does not have
        a return value. If the solver converged, :meth:`converge` should be
        called.
        """
        raise NotImplementedError

    def __iter__(self):
        """Return and iterator on the iterates of the solver.

        Yields
        ------
        tuple of array
            The (x, y) pair of the current iteration.
        """
        while self.next():
            yield self.x, self.y

    def until(self, stoprule=None):
        """Run the solver with the given stopping rule.

        This is convenience method that implements a simple generator loop
        running the solver until it either converges or the stopping rule
        triggers.

        Parameters
        ----------
        stoprule : :class:`~itreg.stoprules.StopRule`, optional
            The stopping rule to be used. If omitted, stopping will only be
            based on the return value of :meth:`next`.

        Yields
        ------
        tuple of arrays
            The (x, y) pair of the current iteration, or the solution chosen by
            the stopping rule.
        """
        for x, y in self:
            yield x, y
            if stoprule is not None and stoprule.stop(x, y):
                self.log.info('Stopping rule triggered.')
                yield x, y
                return
        self.log.info('Solver converged.')

    def run(self, stoprule=None):
        """Run the solver with the given stopping rule.

        This method simply runs the generator :meth:`until` and returns the
        final (x, y) pair.
        """
        for x, y in self.until(stoprule):
            pass
        return x, y


class HilbertSpaceSetting:
    def __init__(self, op, Hdomain, Hcodomain):
        if not isinstance(Hdomain, HilbertSpace) and callable(Hdomain):
            Hdomain = Hdomain(op.domain)
        assert isinstance(Hdomain, HilbertSpace)
        assert Hdomain.discr == op.domain

        if not isinstance(Hcodomain, HilbertSpace) and callable(Hcodomain):
            Hcodomain = Hcodomain(op.codomain)
        assert isinstance(Hcodomain, HilbertSpace)
        assert Hcodomain.discr == op.codomain

        self.op = op
        self.Hdomain = Hdomain
        self.Hcodomain = Hcodomain


from .landweber import Landweber
from .cg import TikhonovCG
from .irgnm_cg import IrgnmCG
from .newton_cg_frozen import Newton_CG_Frozen
from .newton_semismooth import NewtonSemiSmooth
from .irgnm_cg_lanczos import IRGNM_CG_Lanczos
