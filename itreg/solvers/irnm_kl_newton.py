"""IRNM_KL_NEWTON solver """

import logging
import numpy as np
import numpy.linalg as LA

import setpath 
from itreg.util.cg_methods import CG
from . import Solver


__all__ = ['IRNM_KL_Newton']


class IRNM_KL_Newton(Solver):
    
    """The iteratively regularized Newton method with quadratic approximation
    of KL (Kullback-Leibler) divergence as data misfit term 
    The regularization parameter in k-th Newton step is alpha0 * alpha_step^k.
    
    Parameters
    ----------
    op : :class:`Operator <itreg.operators.Operator>`
        The forward operator.
    data : array
        The right hand side.
    init : array
        The initial guess.
    alpha0 : float, optional
        Starting reg. parameter for IRNM. Standard value: 5e-6
    alpha_step : float, optional
        Decreasing step for reg. parameter. Standard value: 2/3
    intensity : float, optional
        Intensity of the operator. Standard value: 1
    scaling : float, optional
        Standard value : 1
    offset : float, optional
        Parameter for KL. Standard value : 1e-4
    offset_step : float, optional
        Standard value : 5e-6
    inner_res : float, optional
        Standard value : 1e-10
    inner_it : int, optional
        Max. number of inner iterations. Standard value : 10
    cgmaxit : int, optional
        Max number of CG iterations. Standard value : 50

    Attributes
    ----------
    op : :class:`Operator <itreg.operators.Operator>`
        The forward operator.
    data : array
        The right hand side.
    x : array
        The current point.
    y : array
        The value at the current point.
    alpha_step : float
        Decreasing step for reg. parameter.
    alpha0 : float
        Starting reg. parameter for IRNM.
    intensity : float
        Intensity of the operator.
    scaling : float
    offset : float
    offset_step : float
    inner_res : float
    inner_it : int
        Max. number of inner iterations.
    cgmaxit : intIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII
        Max number of CG iterations.
    k : int
        Number of iterations.
    """
    
    def __init__(self, op, data, init, alpha0 =2e-6, alpha_step=2/3.,
                 intensity=1, scaling=1, offset=1e-4, offset_step=0.8,
                 inner_res=1e-10, inner_it=10, cgmaxit=50):
        """Initialize parameters """
        
        super().__init__(logging.getLogger(__name__))
        self.op = op
        self.data = data
        self.init = init
        self.x = self.init
        self.y = self.op(self.x)
        
        # Parameter for the outer iteration (Newton method)
        self.k = 0
        self.alpha_step = alpha_step
        self.intensity = intensity
        self.data = self.data / self.intensity
        self.scaling = scaling / np.abs(self.intensity)
        self.alpha = alpha0
        self.offset = offset
        self.offset_step = offset_step
        self.inner_res = inner_res
        self.inner_it = inner_it
        self.cgmaxit = cgmaxit
            
    def next(self):
        """Run a single IRNM_KL_NEWTON iteration.

        Returns
        -------
        bool
            Always True, as the IRNM_KL_NEWTON method never stops on its own.

        """

        self.k += 1
        self._h_n = np.zeros(np.shape(self.x))
        self._eta = np.zeros(np.shape(self.x))
        self._rhs = -self._grad(self._h_n)

        self._n = 1
        self._res = self.op.domx.norm(self._rhs)
        
        """ Minimize 
        
        int(exp(frakF(x) + frakF'(x;h))-(frakF(x) +  frakF'(x;h))*data)
            + alpha ||x + h - init||^2 
        
        in every step.        
        This problem is strictly convex, differentiable and no side condition
        in the image space is necessary i.e. we need to solve grad = 0.
        """
    
        while self._res > self.inner_res and self._n <= self.inner_it:
            #normalize rhs before calling CG
            self._eta = CG(self._Ax, self._rhs/self._res,
                           np.zeros(np.shape(self._eta)), 1e-2, self.cgmaxit)
            #renormalize solution
            self._eta = self._res * self._eta
            self._h_n += self._eta
            self._rhs = -self._grad(self._h_n)
            self._res = LA.norm(self._rhs)
            
            self._n += 1
        
        self._h = self._h_n   
        # update
        self.x += self._h
        self.y = self.op(self.x)
        self.alpha = self.alpha * self.alpha_step
        self.offset = self.offset * self.offset_step
        return True
        
    #define some help functions 
    def _frakF(self, x):
        return np.log(self.op(x) + self.offset)
    
    def _A(self, h): 
        return self.op.derivative()(h)/(self.y + self.offset)
    
    def _Ast(self, h):
        return self.op.adjoint(h/(self.y + self.offset))

    def _grad(self, h):
        return (self._Ast((self.y + self.offset) * np.exp(self._A(h)) 
                - self.data - self.offset) 
                + 2 * self.alpha * self.op.domx.gram(self.x + h - self.init))
        
    def _Dgrad(self, h, eta):
        return (self._Ast((self.y + self.offset) * np.exp(self._A(h)) 
                * self._A(eta)) + 2 * self.alpha * self.op.domx.gram(eta))
        
    def _Ax(self, eta):
        return self._Dgrad(self._h_n, eta)
        