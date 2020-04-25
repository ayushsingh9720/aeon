#!/usr/bin/env python3 -u
# coding: utf-8

__author__ = ["Markus Löning"]
__all__ = ["TEST_CONSTRUCT_CONFIG_LOOKUP"]

from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sktime.classification.interval_based import TimeSeriesForest
from sktime.forecasting.compose import DirectRegressionForecaster, RecursiveRegressionForecaster, \
    DirectTimeSeriesRegressionForecaster, RecursiveTimeSeriesRegressionForecaster, TransformedTargetForecaster, \
    EnsembleForecaster, StackingForecaster
from sktime.forecasting.exp_smoothing import ExponentialSmoothing
from sktime.forecasting.model_selection import ForecastingGridSearchCV, SingleWindowSplitter
from sktime.forecasting.naive import NaiveForecaster
from sktime.forecasting.theta import ThetaForecaster
from sktime.performance_metrics.forecasting import sMAPE
from sktime.series_as_features.compose import ColumnEnsembleClassifier
from sktime.transformers.compose import RowTransformer
from sktime.transformers.compose import Tabulariser
from sktime.transformers.detrend import Detrender, SingleSeriesTransformAdaptor
from sktime.transformers.summarise import FittedParamExtractor
from sktime.transformers.compose import ColumnTransformer

TRANSFORMER = StandardScaler()
TRANSFORMERS = [
    ("t1", TRANSFORMER),
    ("t2", TRANSFORMER),
]
REGRESSOR = LinearRegression()
TIME_SERIES_CLASSIFIER = TimeSeriesForest()
TIME_SERIES_CLASSIFIERS = [
    ("tsf1", TIME_SERIES_CLASSIFIER),
    ("tsf2", TIME_SERIES_CLASSIFIER)
]
FORECASTER = ExponentialSmoothing()
FORECASTERS = [
    ("ses1", FORECASTER),
    ("ses2", FORECASTER)
]
STEPS = [
    ("t", Detrender(ThetaForecaster())),
    ("f", NaiveForecaster())
]
TEST_CONSTRUCT_CONFIG_LOOKUP = {
    DirectRegressionForecaster:
        {"regressor": REGRESSOR},
    RecursiveRegressionForecaster:
        {"regressor": REGRESSOR},
    DirectTimeSeriesRegressionForecaster:
        {"regressor": make_pipeline(Tabulariser(), REGRESSOR)},
    RecursiveTimeSeriesRegressionForecaster:
        {"regressor": make_pipeline(Tabulariser(), REGRESSOR)},
    TransformedTargetForecaster:
        {"steps": STEPS},
    EnsembleForecaster:
        {"forecasters": FORECASTERS},
    StackingForecaster:
        {"forecasters": FORECASTERS, "final_regressor": REGRESSOR},
    Detrender:
        {"forecaster": FORECASTER},
    ForecastingGridSearchCV: {
        "forecaster": NaiveForecaster(strategy="mean"),
        "cv": SingleWindowSplitter(fh=1),
        "param_grid": {"window_length": [2, 5]},
        "scoring": sMAPE()},
    SingleSeriesTransformAdaptor:
        {"transformer": StandardScaler()},
    ColumnEnsembleClassifier:
        {"estimators": [(name, estimator, i) for i, (name, estimator) in enumerate(TIME_SERIES_CLASSIFIERS)]},
    FittedParamExtractor:
        {"forecaster": FORECASTER, "param_names": ["smoothing_level"]},
    RowTransformer:
        {"transformer": TRANSFORMER},
    ColumnTransformer:
        {"transformers": [(name, estimator, i) for i, (name, estimator) in enumerate(TRANSFORMERS)]}
}
