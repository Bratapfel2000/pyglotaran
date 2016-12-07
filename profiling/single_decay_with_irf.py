
import numpy as np

from lmfit import Parameters

from glotaran_tools.specification_parser import parse_yml
from glotaran_models.kinetic import KineticSeperableModel

fitspec = '''
type: kinetic

parameter: {}

compartments: [s1]

megacomplexes:
- label: mc1
  k_matrices: [k1]

k_matrices:
  - label: "k1"
    matrix: {{
      '("s1","s1")': 1,
    }}

initial_concentrations: []

irf:
  - label: irf1
    type: gaussian
    center: 2
    width: 3


datasets:
- label: dataset1
  type: spectral
  megacomplexes: [mc1]
  path: ''
  irf: irf1
'''

initial_parameter = [101e-4, 0, 5]
times = np.asarray(np.arange(-100, 1500, 1.5))
x = np.arange(12820, 15120, 4.6)

wanted_params = Parameters()
wanted_params.add("p1", 101e-3)
wanted_params.add("p2", 0.3)
wanted_params.add("p3", 10)

model = parse_yml(fitspec.format(initial_parameter))

fitmodel = KineticSeperableModel(model)
data = fitmodel.eval(wanted_params, *times, **{'dataset': 'dataset1',
                                               'dataset1_x': x,
                                               })


def fit():
    fitmodel.fit(fitmodel.get_initial_fitting_parameter(),
                 *times, **{"dataset1": data})


if __name__ == '__main__':
    fit()
