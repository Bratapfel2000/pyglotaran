from glotaran.model import DatasetDescriptor
from glotaran.model import model_attribute

class KineticImageDatasetDescriptor(DatasetDescriptor):
    @property
    def initial_concentration(self) -> str:
        ...

    @property
    def irf(self) -> str:
        ...

    @property
    def baseline(self) -> bool:
        ...

    def get_k_matrices(self):
        ...

    def compartments(self):
        ...
