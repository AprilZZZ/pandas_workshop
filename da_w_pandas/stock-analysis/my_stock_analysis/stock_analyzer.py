"""Classes for technical analysis of assets."""

import math

from .utils import validate_df

class StockAnalyzer:
    """Provides metrics for technical analysis of a stock."""

    @validate_df(columns={'open', 'high', 'low', 'close'})
    def __init__(self, df):
        """Create a `StockAnalyzer` object with OHLC data"""
        self.data = df

    @property
    def close(self):
        """Get the close column of the data."""
        return self.data.close

    @property
    def pct_change(self):
        """Get the percent change of the close column."""
        return self.close.pct_change()

    @property
    def pivot_point(self):
        """Calculate the pivot point."""
        return (self.last_close + self.last_high + self.last_low) / 3

    @property
    def last_close(self):
        """Get the value of the last close in the data."""
        return self.data.last('1D').close.iat[0]

    @property
    def last_high(self):
        """Get the value of the last high in the data."""
        return self.data.last('1D').high.iat[0]

    @property
    def last_low(self):
        """Get the value of the last low in the data."""
        return self.data.last('1D').low.iat[0]

    def resistance(self, level=1):
        """Calculate the resistance at the given level."""
        if level == 1:
            res = (2 * self.pivot_point) - self.last_low
        elif level == 2:
            res = self.pivot_point + (self.last_high - self.last_low)
        elif level == 3:
            res = self.last_high + 2 * (self.pivot_point - self.last_low)
        else:
            raise ValueError('Not a valid level.')
        return res

    def support(self):
        """Calculate the support at the given level."""
        if level == 1:
            sup = (2 * self.pivot_point) - self.last_high
        elif level == 2:
            sup = self.pivot_point - (self.last_high - self.last_low)
        elif level == 3:
            sup = self.last_low - 2 * (self.last_high - self.pivot_point)
        else:
            raise ValueError('Not a valid level.')
        return sup

    @property
    def _max_periods(self):
        """Get the number of trading periods in the data."""
        return self.data.shape[0]

    def daily_std(self, periods=252):
        """Calculate daily standard deviation of percent change.

        Parameters:
            - periods: The number of periods to use for the calculation;
              default is 252 for the trading days in a year.
              Note if you provide a number greater than the number of
              trading periods in the data, self._max_periods` will be used instead.

        Returns: The standard deviation.
        """
        return self.pct_change\
            [min(periods, self._max_periods) * -1:].std()

    def annualized_volatility(self):
        """Calculate the annualized volatility."""
        return self.daily_std() * math.sqrt(252)

    def volatility(self, periods=252):
        """Calculate the rolling volatility.

        Parameters: - periods: The number of periods to use for the
                      calculation; default is 252 for the trading
                      days in a year. Note if you provide a number
                      greater than the number of trading periods in the
                      data, `self._max_periods` will be used instead.

        Returns: A `pandas.Series` object.
        """
        periods = min(periods, self._max_periods)
        return self.close.rolling(periods).std() / math.sqrt(periods)

    def corr_with(self, other):
        """Calculate the correlations between dataframes.

        Parameters:
            - other: The other dataframe.

        Returns: A `pandas.Series` object
        """
        return self.data.pct_change().corrwith(other.pct_change())

    def cv(self):
        """
        Calculate the coefficient of variation for the asset.
        The lower this is, the better the risk/return tradeoff.
        """
        return self.close.std() / self.close.mean()

    def qcd(self):
        """Calculate the quantile coefficient of dispersion."""
        q1, q3 = self.close.quantile([0.25, 0.75])
        return (q3 - q1) / (q3 + q1)

    def beta(self, index):
        """
        Calculate the beta of the asset.

        Parameters:
            - index: The data for the index to compare to.

        Returns: Beta, a float.
        """
        index_change = index.close.pct_change()
        beta = self.pct_change.cov(index_change) / index_change.var()
        return beta

    def cumulative_returns(self):
        """Calculate cumulative returns for plotting."""
        return (1 + self.pct_change).cumprod()

    @staticmethod
    def portfolio_return(df):
        """
        Calculate return assuming no distribution per share.

        Parameters:
            - df: The asset's dataframe.

        Returns: The return, as a float.
        """
        start, end = df.close[0], df.close[-1]
        return (end - start) / start

    def alpha(self, index, r_f):
        """
        Calculates the asset's alpha.

        Parameters:
            - index: The index to compare to.
            - r_f: The risk-free rate of return.

        Returns: Alpha, as a float.
        """
        r_f /= 100
        r_m = self.portfolio_return(index)
        beta = self.beta(index)
        r = self.portfolio_return(self.data)
        alpha = r - r_f - beta * (r_m - r_f)
        return alpha

    def is_bear_market(self):
        """
        Determine if a stock is in a bear market, meaning its
        return in the last 2 months is a decline of 20% or more
        """
        return self.portfolio_return(self.data.last('2M')) <= -.2

    def is_bull_market(self):
        """
        Determine if a stock is in a bull market, meaning its
        return in the last 2 months is an increase of >= 20%.
        """
        return self.portfolio_return(self.data.last('2M')) >= .2

    def sharpe_ratio(self, r_f):
        """
        Calculates the asset's Sharpe ratio.

        Parameters:
            - r_f: The risk-free rate of return.

        Returns: The Sharpe ratio, as a float.
        """
        return (self.cumulative_returns().last('1D').iat[0] - r_f) / self.cumulative_returns().std()

class AssetGroupAnalyzer:
    """Analyzes many assets in a dataframe."""

    @validate_df(columns={'open', 'high', 'low', 'close'})
    def __init__(self, df, group_by='name'):
        """
        Create an `AssetGroupAnalyzer` object with a dataframe of OHLC data and column to group by.
        Args:
            df: The dataframe for the assets.
            group_by: The name of the grouping column.
        """
        self.data = df
        if group_by not in self.data.columns:
            raise ValueError(
                f'`group_by` column "{group_by}" not in df.'
            )
        self.group_by = group_by
        self.analyzers = self._composition_handler()

    def _composition_handler(self):
        """
        Create a dictionary mapping each group to its analyzer,
        taking advantage of composition instead of inheritance.

        Returns: A dictionary of StockAnalyzer objects (one for each asset).
        """
        return {
            group: StockAnalyzer(data)
            for group, data in self.data.groupby(self.group_by)
        }

    def analyze(self, func_name, **kwargs):
        """
        Run a `StockAnalyzer` method on all assets.

        Args:
            func_name: The name of the method to run.
            **kwargs: Additional arguments to pass down.

        Returns:
            A dictionary mapping each asset to the result
            of the calculation of that function.
        """
        if not hasattr(StockAnalyzer, func_name):
            raise ValueError(
                f'StockAnalyzer has no "{func_name}" method.'
            )

        if not kwargs:
            kwargs = {}

        return {
            group: getattr(analyzer, func_name)(**kwargs)
            for group, analyzer in self.analyzers.items()
        }