# -*- coding: utf-8 -*-
"""
Created on Wed May 22 14:47:06 2019

@author: Bjoern Mueller
"""


import numpy as np
import random as rd
import scipy.optimize

class User_defined_prior(object):
    
    def __init__(self, setting, logprob, gradient, hessian, m_0):
        super().__init__()
        self.prior=logprob
        self.hessian=hessian
        self.gradient=gradient
        self.setting=setting
        self.m_0=m_0
        
class gaussian(object):  
    def __init__(self, gamma_prior, setting, m_0=None, offset=None, inv_offset=None):
        super().__init__()
        if gamma_prior is None:
                raise ValueError('Error: No prior covariance matrix')
        self.setting=setting
        if m_0 is None:
            self.m_0=np.zeros(self.setting.domain.coords.shape[0])
        else:
            self.m_0=m_0
        self.offset=offset or 1e-10
        self.inv_offset=inv_offset or 1e-5
        self.gamma_prior=gamma_prior
        self.gamma_prior_abs=np.linalg.det(self.gamma_prior)
        D, S=np.linalg.eig(self.gamma_prior)
        self.gamma_prior_half_inv=np.dot(S.transpose(), np.dot(np.diag(1/np.sqrt(D)+self.inv_offset), S))
        self.gamma_prior_inv=np.dot(S.transpose(), np.dot(np.diag(1/D+self.inv_offset), S))
        self.hessian=self.hessian_gaussian
        self.gradient=self.gradient_gaussian
        self.prior=self.gaussian
        self.len_domain=np.prod(self.setting.op.domain.shape)
        
    def gaussian(self, x):
#        return -np.log(np.sqrt(2*np.pi*self.gamma_prior_abs)+self.offset)-\
#            1/2*np.dot(x-self.m_0, np.dot(self.gamma_prior_inv, np.conjugate(x-self.m_0)))
        return -1/2*np.dot((x-self.m_0).reshape(self.len_domain), np.dot(self.gamma_prior_inv, np.conjugate((x-self.m_0).reshape(self.len_domain)))).real
    
    def gradient_gaussian(self, x):
        return -np.dot(self.gamma_prior_inv, x-self.m_0).real
    
    def hessian_gaussian(self, m, x):
        return -np.dot(self.gamma_prior_inv, x)
    
    

class l1(object):
    def __init__(self, l1_sigma, setting):
        super().__init__()
        if l1_sigma is None:
            raise ValueError('Error: Not all necessary parameters are specified')
        self.l1_sigma=l1_sigma
        self.setting=setting
        self.hessian=self.hessian_l1
        self.gradient=self.gradient_l1
        self.prior=self.l1
        
    def l1(self, x):
        return -self.l1_sigma*sum(abs(x))
    
    def gradient_l1(self, x):
        return -self.l1_sigma*np.sign(x)
    
    def hessian_l1(self, m, x):
        grad_mx=self.gradient_l1(m+x)
        grad_m=self.gradient_l1(m)
        return grad_mx-grad_m

        
class mean(object):       
    def __init__(self, setting, x_lower=None, x_upper=None):
        super().__init__()
        self.setting=setting
        self.x_lower=x_lower
        self.x_upper=x_upper
        self.prior=self.mean
        self.gradient=self.gradient_mean
        self.hessian=self.hessian_mean
        
    def mean(self, x):
        res=0
        if self.x_lower is not None:
            if not self.x_lower.all()<=x.all():
                res=float('inf')
        if self.x_upper is not None:
            if not self.x_upper.all()>=x.all():
                res=float('inf')
        return res
    
    def gradient_mean(self, x):
        return 0
    
    def hessian_mean(self, m, x):
        y, deriv=self.setting.op.linearize(m+x)
        grad_mx=0
        y, deriv=self.setting.op.linearize(m)
        grad_m=0
        return grad_mx-grad_m
        
class unity(object):
    def __init__(self, setting):
        super().__init__()
        self.setting=setting
        self.prior=(lambda x: 0)
        self.gradient=(lambda x: self.op.domain.zeros())
        self.hessian=(lambda x: self.op.domain.zeros())
        
class tikhonov(object):
    def __init__(self, setting, regpar):
        self.setting=setting
        self.regpar=regpar
        self.prior=self.tikhonov
        self.gradient=self.gradient_tikhonov
        self.hessian=self.hessian_tikhonov
        
#    def tikhonov(self, x):
#        y=self.setting.op(x)-self.rhs
#        return - 0.5 * (self.setting.codomain.inner(y, y)+self.regpar*self.setting.domain.inner(x, x))
    
    def tikhonov(self, x):
        return -0.5*self.regpar*self.setting.domain.inner(x, x)

    
    
#    def gradient_tikhonov(self, x):
#        y, deriv=self.setting.op.linearize(x)
#        y-=self.rhs
#        return -(deriv.adjoint(self.setting.codomain.gram(y))+self.regpar*self.setting.domain.gram(x))
    
    def gradient_tikhonov(self, x):
        return -self.regpar*self.setting.domain.gram(x)
    
    def hessian_tikhonov(self, m, x):
        grad_mx=self.gradient_tikhonov(m+x)
        grad_m=self.gradient_tikhonov(m)
        return grad_mx-grad_m