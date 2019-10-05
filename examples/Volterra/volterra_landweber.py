import setpath

import logging

import matplotlib.pyplot as plt
import numpy as np

import itreg.stoprules as rules
from itreg.operators.volterra import NonlinearVolterra
from itreg.solvers import HilbertSpaceSetting, Landweber
from itreg.spaces import L2, UniformGrid

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)-20s :: %(message)s')

grid = UniformGrid(np.linspace(0, 2 * np.pi, 200))
op = NonlinearVolterra(grid, exponent=3)

exact_solution = np.sin(grid.coords[0])
exact_data = op(exact_solution)
noise = 0.03 * op.domain.randn()
data = exact_data + noise
init = op.domain.ones()

setting = HilbertSpaceSetting(op=op, Hdomain=L2, Hcodomain=L2)

landweber = Landweber(setting, data, init, stepsize=0.01)
stoprule = (
        rules.CountIterations(1000) +
        rules.Discrepancy(
            setting.Hcodomain.norm, data,
            noiselevel=setting.Hcodomain.norm(noise),
            tau=1.1
        )
)

reco, reco_data = landweber.run(stoprule)

plt.plot(grid.coords[0], exact_solution.T, label='exact solution')
plt.plot(grid.coords[0], reco, label='reco')
plt.plot(grid.coords[0], exact_data, label='exact data')
plt.plot(grid.coords[0], data, label='data')
plt.plot(grid.coords[0], reco_data, label='reco data')
plt.legend()
plt.show()
