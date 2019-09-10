from itreg.operators import NonlinearOperator
#from itreg.spaces import NGSolveDiscretization, UniformGrid

import numpy as np
#%gui tk
from ngsolve import *

class Reaction_Bdr(NonlinearOperator):


    def __init__(self, domain, g, codomain=None):

        codomain = codomain or domain
        self.N_domain=domain.coords.shape[1]
        self.g=g

        self.fes_domain=domain.fes
        self.fes_codomain=codomain.fes
        self.fes_dir=H1(self.fes_codomain.mesh, order=2, dirichlet="cyc")

        self.fes_in = H1(self.fes_codomain.mesh, order=1)
        self.gfu_in = GridFunction(self.fes_in)

        #grid functions for later use
        self.gfu = GridFunction(self.fes_codomain)  # solution, return value of _eval
        self.gfu_bdr=GridFunction(self.fes_codomain) #grid function holding boundary values, g/sigma=du/dn

        self.gfu_integrator = GridFunction(self.fes_domain) #grid function for defining integrator (bilinearform)
        self.gfu_integrator_codomain = GridFunction(self.fes_codomain)
        self.gfu_rhs = GridFunction(self.fes_codomain) #grid function for defining right hand side (linearform), f

        self.gfu_inner_domain=GridFunction(self.fes_domain) #grid function for reading in values in derivative
        self.gfu_inner=GridFunction(self.fes_codomain) #grid function for inner computation in derivative and adjoint
        self.gfu_deriv=GridFunction(self.fes_codomain) #grid function return value of derivative
        self.gfu_toret=GridFunction(self.fes_domain) #grid function for returning values in adjoint and derivative

        self.gfu_dir=GridFunction(self.fes_domain) #grid function for solving the dirichlet problem in adjoint
        self.gfu_error=GridFunction(self.fes_codomain) #grid function used in _target to compute the error in forward computation
        self.gfu_tar=GridFunction(self.fes_codomain) #grid function used in _target, holding the arguments
        self.gfu_adjtoret=GridFunction(self.fes_domain)

        u = self.fes_codomain.TrialFunction()  # symbolic object
        v = self.fes_codomain.TestFunction()   # symbolic object

        #Define Bilinearform, will be assembled later
        self.a = BilinearForm(self.fes_codomain, symmetric=True)
        self.a += SymbolicBFI(-grad(u)*grad(v)+u*v*self.gfu_integrator_codomain)

        self.fes_bdr=H1(self.fes_codomain.mesh, order=2, definedon=self.fes_codomain.mesh.Boundaries("cyc"))
        self.gfu_getbdr=GridFunction(self.fes_bdr)
        self.gfu_setbdr=GridFunction(self.fes_codomain)


        #Define Linearform, will be assembled later
        self.f=LinearForm(self.fes_codomain)
        self.f += SymbolicLFI(self.gfu_rhs*v)

        self.r=self.f.vec.CreateVector()

        self.b=LinearForm(self.fes_codomain)
        self.gfu_b = GridFunction(self.fes_codomain)
        self.b+=SymbolicLFI(-self.gfu_b*v.Trace(), definedon=self.fes_codomain.mesh.Boundaries("cyc"))

        self.f_deriv=LinearForm(self.fes_codomain)
        self.f_deriv += SymbolicLFI(-self.gfu_rhs*self.gfu*v)

#        self.b2=LinearForm(self.fes)
#        self.b2+=SymbolicLFI(div(v*grad(self.gfu))

        super().__init__(domain, codomain)

    def _eval(self, diff, differentiate, **kwargs):
        #Assemble Bilinearform
        self.gfu_integrator.vec.FV().NumPy()[:]=diff
        self.gfu_integrator_codomain.Set(self.gfu_integrator)
        self.a.Assemble()

        #Assemble Linearform, boundary term
        self.gfu_b.Set(self.g)
        self.b.Assemble()

        #Solve system
        self.gfu.vec.data=self._solve(self.a, self.b.vec)

        #res=sco.minimize((lambda u: self._target(u, self.b.vec)), np.zeros(self.fes_codomain.ndof), constraints={"fun": self._constraint, "type": "eq"})

        if differentiate:
            sigma=CoefficientFunction(self.gfu_integrator)
            self.gfu_bdr.Set(self.g/sigma)

        #self.gfu.vec.FV().NumPy()[:]=res.x
        return self._get_boundary_values(self.gfu)


    def _derivative(self, h, **kwargs):
        #Bilinearform already defined from _eval

        #Translate arguments in Coefficient Function
        self.gfu_inner_domain.vec.FV().NumPy()[:]=h
        self.gfu_inner.Set(self.gfu_inner_domain)

        #Define rhs (f)
        rhs=self.gfu_inner
        self.gfu_rhs.Set(rhs)
        self.f_deriv.Assemble()

        #Define boundary term
        #self.gfu_b.Set(-self.gfu_inner*self.gfu_bdr)
        #self.b.Assemble()

        self.gfu_deriv.vec.data=self._solve(self.a, self.f_deriv.vec)

        #res=sco.minimize((lambda u: self._target(u, self.f.vec)), np.zeros(self.N_domain), constraints={"fun": self._constraint, "type": "eq"})

        #self.gfu_deriv.vec.FV().NumPy()[:]=res.x
#        return res.x
#        return self.gfu_toret.vec.FV().NumPy().copy()
        return self._get_boundary_values(self.gfu_deriv)



    def _adjoint(self, argument, **kwargs):
        #Bilinearform already defined from _eval

        #Definition of Linearform
        #But it only needs to be defined on boundary
        self._set_boundary_values(argument)
#        self.gfu_dir.Set(self.gfu_in)

        #Note: Here the linearform f for the dirichlet problem is just zero
        #Update for boundary values
#        self.r.data=-self.a.mat * self.gfu_dir.vec

        #Solve system
#        self.gfu_toret.vec.data=self.gfu_dir.vec.data+self._solve_dir(self.a, self.r)

        #return self.gfu_toret.vec.FV().NumPy().copy()

#        self.gfu_adjtoret.Set(-self.gfu_toret*self.gfu)
#        return self.gfu_adjtoret.vec.FV().NumPy().copy()

        self.gfu_b.Set(self.gfu_in)
        self.b.Assemble()

        self.gfu_toret.vec.data=self._solve(self.a, self.b.vec)

        self.gfu_adjtoret.Set(self.gfu_toret*self.gfu)

        return self.gfu_adjtoret.vec.FV().NumPy().copy()



    def _solve(self, bilinear, rhs, boundary=False):
        return bilinear.mat.Inverse(freedofs=self.fes_codomain.FreeDofs()) * rhs

    def _solve_dir(self, bilinear, rhs, boundary=False):
        return bilinear.mat.Inverse(freedofs=self.fes_dir.FreeDofs()) * rhs

    def _get_boundary_values(self, gfu):
#        myfunc=CoefficientFunction(gfu)
#        vals = np.asarray([myfunc(self.fes_codomain.mesh(*p)) for p in self.pts_bdr])
#        return vals
        self.gfu_getbdr.Set(0)
        self.gfu_getbdr.Set(gfu, definedon=self.fes_codomain.mesh.Boundaries("cyc"))
        return self.gfu_getbdr.vec.FV().NumPy().copy()


    def _set_boundary_values(self, vals):
#        self.gfu_in.vec.FV().NumPy()[self.ind]=vals
#        return
        self.gfu_setbdr.vec.FV().NumPy()[:]=vals
        self.gfu_in.Set(0)
        self.gfu_in.Set(self.gfu_setbdr, definedon=self.fes_codomain.mesh.Boundaries("cyc"))
        return
