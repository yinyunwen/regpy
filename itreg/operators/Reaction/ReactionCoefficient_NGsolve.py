# -*- coding: utf-8 -*-
"""
Created on Thu Apr  4 13:31:15 2019

@author: Hendrik Müller
"""

from itreg.operators import NonlinearOperator, OperatorImplementation, Params
from itreg.util import instantiate

import numpy as np
import math as mt
import scipy as scp
import scipy.ndimage
import netgen.gui
from ngsolve import *
from netgen.geom2d import unit_square
import matplotlib.pyplot as plt


class ReactionCoefficient_2D(NonlinearOperator):
    

    def __init__(self, domain, rhs, bc_top=None, bc_bottom=None, bc_left=None, bc_right=None, codomain=None, spacing=1):
        codomain = codomain or domain
        if bc_top is None:
            bc_top=rhs[0, :]
        if bc_bottom is None:
            bc_bottom=rhs[-1, :]
        if bc_left is None:
            bc_left=rhs[:, 0]
        if bc_right is None:
            bc_right=rhs[:, -1]
        mesh = Mesh(unit_square.GenerateMesh(maxh=0.1))
        mesh.GetBoundaries()
        #assert len(domain.shape) == 1
        #assert domain.shape == codomain.shape
        super().__init__(Params(domain, codomain, rhs=rhs, bc_top=bc_top, bc_bottom=bc_bottom, bc_left=bc_left, bc_right=bc_right, mesh=mesh, spacing=spacing))
        
    @instantiate
    class operator(OperatorImplementation):
        def eval(self, params, c, data, differentiate, **kwargs):
#            B=B_builder(params, c)
            r_c=rc(params, c)
#            rhs=rhs_builder(params, r_c)
            rhs=FunctoSymbolic(params, r_c)
#            coeff= np.linalg.solve(B, rhs)
            myfunc=FunctoSymbolic(params, c)
            fes = H1(params.mesh, order=2, dirichlet="bottom|right|top|left")


            u = fes.TrialFunction()  # symbolic object
            v = fes.TestFunction()   # symbolic object
            gfu = GridFunction(fes)  # solution
            
            a = BilinearForm(fes, symmetric=True)
            a += SymbolicBFI(grad(u)*grad(v)+myfunc*u*v)
            a.Assemble()
            
            f = LinearForm(fes)
            f += SymbolicLFI(rhs*v)
            f.Assemble()
            #solve the system
            gfu.vec.data = a.mat.Inverse(freedofs=fes.FreeDofs()) * f.vec

            if differentiate:
                data.u=SymbolictoFunc(params, gfu)+tilde_g_builder(params)
                data.c=c
            return SymbolictoFunc(params, gfu)+tilde_g_builder(params)

    @instantiate
    class derivative(OperatorImplementation):
        def eval(self, params, x, data, **kwargs):
            print(data.u*x)
            rhs=FunctoSymbolic(params, -data.u*x)
            myfunc=FunctoSymbolic(params, data.c)
            fes = H1(params.mesh, order=2, dirichlet="bottom|right|top|left")


            u = fes.TrialFunction()  # symbolic object
            v = fes.TestFunction()   # symbolic object
            gfu = GridFunction(fes)  # solution
            
            a = BilinearForm(fes, symmetric=True)
            a += SymbolicBFI(grad(u)*grad(v)+myfunc*u*v)
            a.Assemble()
            
            f = LinearForm(fes)
            f += SymbolicLFI(rhs*v)
            f.Assemble()
            #solve the system
            gfu.vec.data = a.mat.Inverse(freedofs=fes.FreeDofs()) * f.vec
            return SymbolictoFunc(params, gfu)
            

        def adjoint(self, params, y, data, **kwargs):
            rhs=FunctoSymbolic(params, y)
            
            myfunc=FunctoSymbolic(params, data.c)
            fes = H1(params.mesh, order=2, dirichlet="bottom|right|top|left")


            u = fes.TrialFunction()  # symbolic object
            v = fes.TestFunction()   # symbolic object
            gfu = GridFunction(fes)  # solution
            
            a = BilinearForm(fes, symmetric=True)
            a += SymbolicBFI(grad(u)*grad(v)+myfunc*u*v)
            a.Assemble()
            
            f = LinearForm(fes)
            f += SymbolicLFI(rhs*v)
            f.Assemble()
            #solve the system
            gfu.vec.data = a.mat.Inverse(freedofs=fes.FreeDofs()) * f.vec
            
            return -data.u*SymbolictoFunc(gfu)
            
            
            
def tilde_g_builder(params):
    tilde_g=np.zeros((params.domain.coords.shape[1], params.domain.coords.shape[1]))
    tilde_g[0, :]=params.bc_top
    tilde_g[-1, :]=params.bc_bottom
    tilde_g[:, 0]=params.bc_left
    tilde_g[:, -1]=params.bc_right
    for i in range(1, params.domain.coords.shape[1]-1):
        tilde_g[:, i]=np.interp(params.domain.coords[1, :], np.asarray([params.domain.coords[1, 0], params.domain.coords[1, -1]]), np.asarray([params.bc_top[i], params.bc_bottom[i]]))
    v_star=tilde_g
    return v_star    


def basisfunc(params, i, j):
    return np.dot((np.sin((i+1)*mt.pi*params.domain.coords[0, :])).reshape((params.domain.coords.shape[1], 1)), (np.sin((j+1)*mt.pi*params.domain.coords[1, :])).reshape((1, params.domain.coords.shape[1])))  

def FunctoSymbolic(params, func):
    coeff=np.zeros((params.domain.coords.shape[1], params.domain.coords.shape[1]))
    for i in range(0, params.domain.coords.shape[1]):
        for j in range(0, params.domain.coords.shape[1]):
            coeff[i, j]=np.trapz(np.trapz(func*basisfunc(params, i, j), params.domain.coords[0, :], axis=1), params.domain.coords[1, :])
    Symfunc=0
    for i in range(0, params.domain.coords.shape[1]):
        for j in range(0, params.domain.coords.shape[1]):
            Symfunc=Symfunc+coeff[i, j]*sin((i+1)*mt.pi*x)*sin((j+1)*mt.pi*y)
    return Symfunc
            
def basisfuncSym(params, i, j):
    return sin((i+1)*mt.pi*x)*sin((j+1)*mt.pi*y)

#We have to define the mesh            
def SymbolictoFunc(params, Symfunc):
    coeff=np.zeros((params.domain.coords.shape[1], params.domain.coords.shape[1])) 
    for i in range(0, params.domain.coords.shape[1]):
        for j in range(0, params.domain.coords.shape[1]):
            coeff[i, j]=Integrate(basisfuncSym(params, i, j), params.mesh)
    func=0
    for i in range(0, params.domain.coords.shape[1]):
        for j in range(0, params.domain.coords.shape[1]):
            func=func+coeff[i, j]*basisfunc(params, i, j)
    return func
           
def rc(params, c):
    res=mylaplace(params, tilde_g_builder(params))
    return params.rhs+res-c*tilde_g_builder(params)    



def mylaplace(params, func):
    N=params.domain.coords.shape[1]
    der=np.zeros((N,N))
    for i in range(1, N-1):
        for j in range(1, N-1):
            der[i, j]=(func[i+1, j]+func[i-1, j]-4*func[i, j]+func[i, j+1]+func[i, j-1])/(1/N**2)
    for i in range(1, N-1):       
        der[0, i]=(func[0, i+1]+func[0, i-1]-2*func[0, i])*N**2
        der[-1, i]=(func[-1, i+1]+func[-1, i-1]-2*func[-1, i])*N**2
        der[i,0]=(func[ i+1, 0]+func[i-1, 0]-2*func[i, 0])*N**2
        der[i,-1]=(func[ i+1, -1]+func[i-1, -1]-2*func[i, -1])*N**2
    der[0,0]=(der[0,1]+der[1, 0])/2
    der[-1, 0]=(der[-2, 0]+der[-1, 1])/2
    der[-1, -1]=(der[-2, -1]+der[-1, -2])/2
    der[0, -1]=(der[1, -1]+der[0, -2])/2
    return der  








