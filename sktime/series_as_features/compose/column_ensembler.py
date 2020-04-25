""" ColumnEnsembleClassifier: For Multivariate Time Series Classification.
Builds classifiers on each dimension (column) independently

"""

__author__ = ["Aaron Bostrom"]
__all__ = ["ColumnEnsembleClassifier"]

from itertools import chain

import numpy as np
from sklearn.preprocessing import LabelEncoder
from sktime.base import BaseHeterogenousMetaEstimator
from sktime.classification.base import BaseClassifier


class BaseColumnEnsembleClassifier(BaseClassifier):

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.estimators = None
        self.remainder = "drop"
        super(BaseColumnEnsembleClassifier, self).__init__()

    @property
    def _estimators(self):
        return [(name, estim) for name, estim, _ in self.estimators]

    @_estimators.setter
    def _estimators(self, value):
        self.estimators = [
            (name, estim, col) for ((name, estim), (_, _, col))
            in zip(value, self.estimators)]

    def _validate_estimators(self):
        if not self.estimators:
            return

        names, estimators, _ = zip(*self.estimators)

        self._check_names(names)

        # validate estimators
        for t in estimators:
            if t == 'drop':
                continue
            if not (hasattr(t, "fit") or hasattr(t, "predict_proba")):
                raise TypeError("All estimators should implement fit and predict proba"
                                "or can be 'drop' "
                                "specifiers. '%s' (type %s) doesn't." %
                                (t, type(t)))

    # this check whether the column input was a slice object or a tuple.
    def _validate_column_callables(self, X):
        """
        Converts callable column specifications.
        """
        columns = []
        for _, _, column in self.estimators:
            if callable(column):
                column = column(X)
            columns.append(column)
        self._columns = columns

    def _validate_remainder(self, X):
        """
        Validates ``remainder`` and defines ``_remainder`` targeting
        the remaining columns.
        """
        is_estimator = (hasattr(self.remainder, "fit")
                        or hasattr(self.remainder, "predict_proba"))
        if (self.remainder not in ('drop')
                and not is_estimator):
            raise ValueError("The remainder keyword needs to be 'drop', '%s' was passed instead" % self.remainder)

        n_columns = X.shape[1]
        cols = []
        for columns in self._columns:
            cols.extend(_get_column_indices(X, columns))
        remaining_idx = sorted(list(set(range(n_columns)) - set(cols))) or None

        self._remainder = ('remainder', self.remainder, remaining_idx)

    def _iter(self, replace_strings=False):
        """
        Generate (name, trans, column, weight) tuples.

        If fitted=True, use the fitted transformers, else use the
        user specified transformers updated with converted column names
        and potentially appended with transformer for remainder.

        """

        # interleave the validated column specifiers
        estimators = [
            (name, estims, column) for (name, estims, _), column
            in zip(self.estimators, self._columns)
        ]
        # add transformer tuple for remainder
        if self._remainder[2] is not None:
            estimators = chain(estimators, [self._remainder])

        for name, trans, column in estimators:
            if replace_strings:
                # skip in case of 'drop'
                if trans == 'drop':
                    continue
                elif _is_empty_column_selection(column):
                    continue

            yield (name, trans, column)

    def fit(self, X, y, input_checks=True):
        # the data passed in could be an array of dataframes?
        """Fit all estimators, fit the data

        Parameters
        ----------
        X : array-like or DataFrame of shape [n_samples, n_dimensions, n_length]
            Input data, of which specified subsets are used to fit the
            transformers.

        y : array-like, shape (n_samples, ...), optional
            Targets for supervised learning.

        """

        if self.estimators is None or len(self.estimators) == 0:
            raise AttributeError('Invalid `estimators` attribute, `estimators`'
                                 ' should be a list of (string, estimator)'
                                 ' tuples')

        # X = _check_X(X)
        self._validate_estimators()
        self._validate_column_callables(X)
        self._validate_remainder(X)

        self.le_ = LabelEncoder().fit(y)
        self.classes_ = self.le_.classes_
        transformed_y = self.le_.transform(y)

        for name, estim, column in self._iter(replace_strings=True):
            estim.fit(_get_column(X, column), transformed_y)

        return self

    def _collect_probas(self, X):
        return np.asarray(
            [estim.predict_proba(_get_column(X, column)) for (name, estim, column) in self._iter(replace_strings=True)])

    # TODO: check if it is fitted
    def predict_proba(self, X, input_checks=True):
        """Predict class probabilities for X in 'soft' voting """
        avg = np.average(self._collect_probas(X), axis=0)
        return avg

    def _predict(self, X):
        """Collect results from clf.predict calls. """
        return np.asarray(
            [estim.predict_proba(_get_column(X, column)) for (name, estim, column) in self._iter(replace_strings=True)])

    def predict(self, X, input_checks=True):
        maj = np.argmax(self.predict_proba(X), axis=1)
        return self.le_.inverse_transform(maj)


class ColumnEnsembleClassifier(BaseHeterogenousMetaEstimator, BaseColumnEnsembleClassifier):
    _required_parameters = ["estimators"]

    """Applies estimators to columns of an array or pandas DataFrame.

        This estimator allows different columns or column subsets of the input
        to be transformed separately and the features generated by each transformer
        will be ensembled to form a single output.

        Parameters
        ----------
        estimators : list of tuples
            List of (name, transformer, column(s)) tuples specifying the
            transformer objects to be applied to subsets of the data.

            name : string
                Like in Pipeline and FeatureUnion, this allows the transformer and
                its parameters to be set using ``set_params`` and searched in grid
                search.
            Estimator : estimator or {'drop'}
                Estimator must support `fit` and `predict_proba`. Special-cased
                strings 'drop' and 'passthrough' are accepted as well, to
                indicate to drop the columns
            column(s) : string or int, array-like of string or int, slice, \
                boolean mask array or callable


        remainder : {'drop', 'passthrough'} or estimator, default 'drop'
            By default, only the specified columns in `transformers` are
            transformed and combined in the output, and the non-specified
            columns are dropped. (default of ``'drop'``).
            By specifying ``remainder='passthrough'``, all remaining columns that
            were not specified in `transformers` will be automatically passed
            through. This subset of columns is concatenated with the output of
            the transformers.
            By setting ``remainder`` to be an estimator, the remaining
            non-specified columns will use the ``remainder`` estimator. The
            estimator must support :term:`fit` and :term:`transform`.

    """

    def __init__(self, estimators, remainder='drop', verbose=False):
        super(ColumnEnsembleClassifier, self).__init__(verbose=verbose)
        self.estimators = estimators
        self.remainder = remainder

    def get_params(self, deep=True):
        """Get parameters for this estimator.

        Parameters
        ----------
        deep : boolean, optional
            If True, will return the parameters for this estimator and
            contained subobjects that are estimators.

        Returns
        -------
        params : mapping of string to any
            Parameter names mapped to their values.
        """
        return self._get_params('_estimators', deep=deep)

    def set_params(self, **kwargs):
        """Set the parameters of this estimator.

        Valid parameter keys can be listed with ``get_params()``.

        Returns
        -------
        self
        """
        self._set_params('_estimators', **kwargs)
        return self


def _get_column(X, key):
    """
    Get feature column(s) from input data X.

    Supported input types (X): numpy arrays, sparse arrays and DataFrames

    Supported key types (key):
    - scalar: output is 1D
    - lists, slices, boolean masks: output is 2D
    - callable that returns any of the above

    Supported key data types:

    - integer or boolean mask (positional):
        - supported for arrays, sparse matrices and dataframes
    - string (key-based):
        - only supported for dataframes
        - So no keys other than strings are allowed (while in principle you
          can use any hashable object as key).

    """
    # check whether we have string column names or integers
    if _check_key_type(key, int):
        column_names = False
    elif _check_key_type(key, str):
        column_names = True
    elif hasattr(key, 'dtype') and np.issubdtype(key.dtype, np.bool_):
        # boolean mask
        column_names = False
        if hasattr(X, 'loc'):
            # pandas boolean masks don't work with iloc, so take loc path
            column_names = True
    else:
        raise ValueError("No valid specification of the columns. Only a "
                         "scalar, list or slice of all integers or all "
                         "strings, or boolean mask is allowed")

    if column_names:
        if hasattr(X, 'loc'):
            # pandas dataframes
            return X.loc[:, key]
        else:
            raise ValueError("Specifying the columns using strings is only "
                             "supported for pandas DataFrames")
    else:
        if hasattr(X, 'iloc'):
            # pandas dataframes
            return X.iloc[:, key]
        else:
            # numpy arrays, sparse arrays
            return X[:, key]


def _check_key_type(key, superclass):
    """
    Check that scalar, list or slice is of a certain type.

    This is only used in _get_column and _get_column_indices to check
    if the `key` (column specification) is fully integer or fully string-like.

    Parameters
    ----------
    key : scalar, list, slice, array-like
        The column specification to check
    superclass : int or str
        The type for which to check the `key`

    """
    if isinstance(key, superclass):
        return True
    if isinstance(key, slice):
        return (isinstance(key.start, (superclass, type(None))) and
                isinstance(key.stop, (superclass, type(None))))
    if isinstance(key, list):
        return all(isinstance(x, superclass) for x in key)
    if hasattr(key, 'dtype'):
        if superclass is int:
            return key.dtype.kind == 'i'
        else:
            # superclass = str
            return key.dtype.kind in ('O', 'U', 'S')
    return False


def _get_column_indices(X, key):
    """
    Get feature column indices for input data X and key.

    For accepted values of `key`, see the docstring of _get_column

    """
    n_columns = X.shape[1]

    if (_check_key_type(key, int)
            or hasattr(key, 'dtype') and np.issubdtype(key.dtype, np.bool_)):
        # Convert key into positive indexes
        idx = np.arange(n_columns)[key]
        return np.atleast_1d(idx).tolist()
    elif _check_key_type(key, str):
        try:
            all_columns = list(X.columns)
        except AttributeError:
            raise ValueError("Specifying the columns using strings is only "
                             "supported for pandas DataFrames")
        if isinstance(key, str):
            columns = [key]
        elif isinstance(key, slice):
            start, stop = key.start, key.stop
            if start is not None:
                start = all_columns.index(start)
            if stop is not None:
                # pandas indexing with strings is endpoint included
                stop = all_columns.index(stop) + 1
            else:
                stop = n_columns + 1
            return list(range(n_columns)[slice(start, stop)])
        else:
            columns = list(key)

        return [all_columns.index(col) for col in columns]
    else:
        raise ValueError("No valid specification of the columns. Only a "
                         "scalar, list or slice of all integers or all "
                         "strings, or boolean mask is allowed")


def _is_empty_column_selection(column):
    """
    Return True if the column selection is empty (empty list or all-False
    boolean array).

    """
    if hasattr(column, 'dtype') and np.issubdtype(column.dtype, np.bool_):
        return not column.any()
    elif hasattr(column, '__len__'):
        return len(column) == 0
    else:
        return False
