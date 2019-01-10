"""This package contains the FitResult object"""

import typing

import numpy as np
import xarray as xr
from lmfit.minimizer import Minimizer

from glotaran.model.parameter_group import ParameterGroup


from .grouping import create_group, create_data_group
from .grouping import calculate_group_item
from .variable_projection import residual_variable_projection
from .nnls import residual_nnls


class FitResult:
    """The result of a fit."""

    def __init__(self,
                 model: typing.Type["glotaran.model.BaseModel"],
                 data: typing.Union[xr.DataArray, xr.Dataset],
                 initital_parameter: ParameterGroup,
                 nnls: bool,
                 atol: float = 0,
                 ):
        self.model = model
        self.data = {}
        for label, dataset in data.items():
            if model.calculated_axis not in dataset.dims:
                raise Exception("Missing coordinates for dimension "
                                f"'{model.calculated_axis}' in data for dataset "
                                f"'{label}'")
            if model.estimated_axis not in dataset.dims:
                raise Exception("Missing coordinates for dimension "
                                f"'{model.estimated_axis}' in data for dataset "
                                f"'{label}'")
            if isinstance(dataset, xr.DataArray):
                dataset = dataset.to_dataset(name="data")

            if 'weight' in dataset:
                dataset['weighted_data'] = np.multiply(dataset.data, dataset.weight)
            self.data[label] = dataset.transpose(model.calculated_axis, model.estimated_axis)
        self.initial_parameter = initital_parameter
        self.nnls = nnls
        self._group = create_group(model, self.data, atol)
        self._data_group = create_data_group(model, self._group, self.data)
        self._lm_result = None

    @classmethod
    def from_parameter(cls, model, data, parameter, nnls=False, atol=0):
        cls = cls(model, data, parameter, nnls, atol=atol)
        cls._calculate_residual(parameter)
        cls._finalize()
        return cls

    def minimize(self, verbose: int = 2, max_nfev: int = None):
        parameter = self.initial_parameter.as_parameter_dict(only_fit=True)
        minimizer = Minimizer(
            self._calculate_residual,
            parameter,
            fcn_args=[],
            fcn_kws=None,
            iter_cb=self._iter_cb,
            scale_covar=True,
            nan_policy='omit',
            reduce_fcn=None,
            **{})

        self._lm_result = minimizer.minimize(method='least_squares',
                                             verbose=verbose,
                                             max_nfev=max_nfev)

        self._finalize()

    @property
    def nfev(self):
        return self._lm_result.nfev

    @property
    def nvars(self):
        return self._lm_result.nvarys

    @property
    def ndata(self):
        return self._lm_result.ndata

    @property
    def nfree(self):
        return self._lm_result.nfree

    @property
    def chisqr(self):
        return self._lm_result.chisqr

    @property
    def red_chisqr(self):
        return self._lm_result.redchi

    @property
    def var_names(self):
        return self._lm_result.var_names

    @property
    def covar(self):
        return self._lm_result.covar

    @property
    def best_fit_parameter(self) -> ParameterGroup:
        """The best fit parameters."""
        if self._lm_result is None:
            return self.initial_parameter
        return ParameterGroup.from_parameter_dict(self._lm_result.params)

    def _get_group_indices(self, dataset_label):
        return [index for index, item in self._group.items()
                if dataset_label in [val[1].label for val in item]]

    def _get_dataset_idx(self, index, dataset):
            datasets = [val[1].label for val in self._group[index]]
            return datasets.index(dataset)

    def _iter_cb(self, params, i, resid, *args, **kws):
        pass

    def _calculate_residual(self, parameter):

        if not isinstance(parameter, ParameterGroup):
            parameter = ParameterGroup.from_parameter_dict(parameter)

        residuals = []
        for index, item in self._group.items():
            clp_labels, matrix = calculate_group_item(item, self.model, parameter, self.data)

            clp = None
            residual = None
            if self.nnls:
                clp, residual = residual_nnls(
                        matrix,
                        self._data_group[index]
                    )
            else:
                clp, residual = residual_variable_projection(
                        matrix,
                        self._data_group[index]
                    )

            start = 0
            for i, dataset in item:
                dataset = self.data[dataset.label]
                if 'residual' not in dataset:
                    dataset['residual'] = dataset.data.copy()
                size = dataset.coords[self.model.calculated_axis].size
                dataset.residual.loc[{self.model.estimated_axis: i}] = residual[start:size]
                start += size

                if 'clp' not in dataset:
                    dim1 = dataset.coords[self.model.estimated_axis].size
                    dim2 = dataset.coords['clp_label'].size
                    dataset['clp'] = (
                        (self.model.estimated_axis, 'clp_label'),
                        np.zeros((dim1, dim2), dtype=np.float64)
                    )
                dataset.clp.loc[{self.model.estimated_axis: i}] = \
                    np.array([clp[clp_labels.index(i)] for i in
                             dataset.coords['clp_label'].values])

            residuals.append(residual)

        additionals = self.model.additional_residual_function(
            self.model, self._clp, self._concentrations) \
            if self.model.additional_residual_function is not None else []

        return np.concatenate(residuals + additionals)

    def _finalize(self):
        for label, dataset in self.data.items():

            if 'weight' in dataset:
                dataset['weighted_residual'] = dataset.residual
                dataset.residual = np.multiply(dataset.weighted_residual, dataset.weight**-1)

            # reconstruct fitted data

            dataset['fitted_data'] = dataset.data - dataset.residual

        if callable(self.model.finalize_result):
            self.model.finalize_result(self)

    def __str__(self):
        string = "# Fitresult\n\n"

        # pylint: disable=invalid-name

        ll = 32
        lr = 13

        string += "Optimization Result".ljust(ll-1)
        string += "|"
        string += "|".rjust(lr)
        string += "\n"
        string += "|".rjust(ll, "-")
        string += "|".rjust(lr, "-")
        string += "\n"

        string += "Number of residual evaluation |".rjust(ll)
        string += f"{self._lm_result.nfev} |".rjust(lr)
        string += "\n"
        string += "Number of variables |".rjust(ll)
        string += f"{self._lm_result.nvarys} |".rjust(lr)
        string += "\n"
        string += "Number of datapoints |".rjust(ll)
        string += f"{self._lm_result.ndata} |".rjust(lr)
        string += "\n"
        string += "Negrees of freedom |".rjust(ll)
        string += f"{self._lm_result.nfree} |".rjust(lr)
        string += "\n"
        string += "Chi Square |".rjust(ll)
        string += f"{self._lm_result.chisqr:.6f} |".rjust(lr)
        string += "\n"
        string += "Reduced Chi Square |".rjust(ll)
        string += f"{self._lm_result.redchi:.6f} |".rjust(lr)
        string += "\n"

        string += "\n"
        string += "## Best Fit Parameter\n\n"
        string += f"{self.best_fit_parameter}"
        string += "\n"

        return string
