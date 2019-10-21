from regpy.operators.volterra import Volterra
from regpy.hilbert import L2
from regpy.discrs import UniformGrid
from regpy.solvers import HilbertSpaceSetting
from regpy.solvers.irgnm import IrgnmCGLanczos
import regpy.stoprules as rules

import numpy as np
import logging
import matplotlib.pyplot as plt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)-40s :: %(message)s')

grid = UniformGrid(np.linspace(0, 2*np.pi, 200))
op = Volterra(grid)

exact_solution = np.sin(grid.coords[0])
exact_data = op(exact_solution)
noise = 0.03 * np.random.normal(size=grid.shape)
data = exact_data + noise
init=op.domain.ones()


setting=HilbertSpaceSetting(op=op, Hdomain=L2, Hcodomain=L2)

irgnm_cg = IrgnmCGLanczos(setting, data, init, cgmaxit = 50, alpha0 = 1, alpha_step = 0.9, cgtol = [0.3, 0.3, 1e-6])
stoprule = (
    rules.CountIterations(20) +
    rules.Discrepancy(setting.Hcodomain.norm, data,
                      noiselevel=setting.Hcodomain.norm(noise), tau=1.1))

reco, reco_data = irgnm_cg.run(stoprule)

reco, reco_data = irgnm_cg.run(stoprule)
plt.plot(grid.coords[0], exact_solution.T, label='exact solution')
plt.plot(grid.coords[0], reco, label='reco')
plt.plot(grid.coords[0], exact_data, label='exact data')
plt.plot(grid.coords[0], data, label='data')
plt.plot(grid.coords[0], reco_data, label='reco data')
plt.legend()
plt.show()
