from datetime import date, timedelta
import os

from scipy import optimize
import numpy as np
import pandas as pd
import matplotlib.pylab as plt
import matplotlib.ticker as ticker

def download_data(data_path):
    """
    This function  download data from MZCR, form single dataframe, store it and return it.
    
    :param data_path:
    :return:
    """
    URL_BASE = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/nakazeni-vyleceni-umrti-testy.csv'
    URL_HOSP = 'https://onemocneni-aktualne.mzcr.cz/api/v2/covid-19/hospitalizace.csv'
    dataframe_base = pd.read_csv(URL_BASE, index_col="datum")
    dataframe_hosp = pd.read_csv(URL_HOSP, index_col="datum")
    dataframe = dataframe_base.join(dataframe_hosp)
    dataframe.to_pickle(data_path)
    return dataframe

def handle_fig(func):
    """
    This is a wrapper for drawing functions.
    All drawing functions should use it as a decorator.
    It display and/or save figure.
    
    :param func:
    :return:
    """
    def wrapper(*args, **kwargs):
        fig = func(*args, **kwargs)
        if "filename" in kwargs:
            filepath = os.path.join(FIG_PATH, kwargs["filename"])
            fig.savefig(filepath, dpi=100)
        if not kwargs["display"]:
            plt.close(fig)
            fig.clf()
    return wrapper


def get_exponential(dataset, col_name, new_col_name, start=False, stop=False, horizon=14):
    """
    This si a function, that add new series to the given dataset.
    The added series is a exponential "prediction" of the target series.
    Note: it also extends the dataset by prediction horizon.
    
    :param dataset: pandas dataframe
    :param col_name: name of the series to "predict"
    :param new_col_name: name for the new series - the "predicted" one
    :param start: string date - from when to start the exponential fit
    :param stop: string date - the end of the data for exponential fit
    :param horizon: how many dates should be predicted after the last date in the dataset (not from stop date!)
    :return:
    """
    start = start if start else dataset.index[-28]
    stop = stop if stop else dataset.index[-1]
    subset = dataset[(stop >= dataset.index) & (dataset.index >= start)]
    x = range(len(subset.index))
    y = subset[col_name].values
    (a,b), trash = optimize.curve_fit(
        lambda t, a, b: a * np.exp(b * t), x, y, p0=(0, 0))
    dataset = dataset.assign(new_col_name=np.nan)
    index_extension = pd.date_range(dataset.index[-1], periods=horizon+1)[1:].strftime('%Y-%m-%d')
    dataset_extension = pd.DataFrame(index=index_extension, columns=dataset.keys())
    dataset = dataset.append(dataset_extension)
    x_e = range(len(dataset.loc[(dataset.index >= start)]))
    dataset.loc[(dataset.index >= start), new_col_name] = a * np.exp(b * x_e)
    return dataset

@handle_fig
def basic_view(dataframe, **kwargs):
    """
    The basic overview. It creates subset from the given date.
    It draws some basic series and their "prediction" for short horizon.
    
    :param dataframe:
    :param kwargs:
    :return:
    """
    FIGSIZE = (19, 8)
    WINDOWNAME = "Základní přehled"
    dataframe["aktualne_nakazenych"] = dataframe["kumulativni_pocet_nakazenych"] - dataframe["kumulativni_pocet_umrti"] - dataframe["kumulativni_pocet_vylecenych"]
    subset = dataframe[dataframe.index > DATES["new_age"]]

    fig = plt.figure(WINDOWNAME, figsize=FIGSIZE)
    ax = plt.gca()

    to_draw = [
        # "n: column name, "l": plot label, "c": plot color
        {"n": "aktualne_nakazenych", "l": "Aktualně nakažení", "c": "r"},
        {"n": "pocet_hosp", "l": "Počet hospitalizovaných", "c": "k"},
        {"n": "prirustkovy_pocet_nakazenych", "l": "Přírustkový počet hospitalizovaných", "c": "b"},
        {"n": "prirustkovy_pocet_provedenych_testu", "l": "Počet testů", "c": "y"},
    ]

    for td in to_draw:
        new_column_name = "{}_exp".format(td["n"])
        augmented_subset = get_exponential(subset, td["n"], new_column_name, start=DATES["wave3"], horizon=14)
        ax.plot(augmented_subset.index, augmented_subset[td["n"]], td["c"], linestyle="-", marker="x", label=td["l"])
        ax.plot(augmented_subset.index, augmented_subset[new_column_name], ':{}'.format(td["c"]))
    plt.xlim(augmented_subset.index[0], augmented_subset.index[-1])
    plt.ylim(0, subset["aktualne_nakazenych"].max()*1.05)
    ax.xaxis.set_major_locator(plt.MaxNLocator(100))
    ax.yaxis.set_major_locator(plt.MaxNLocator(25))
    plt.xticks(rotation=90)
    plt.grid()
    plt.legend()
    ax.get_yaxis().set_major_formatter(ticker.FuncFormatter(lambda x, p: "{}k".format(int(int(x) / 1000))))
    plt.tight_layout()
    return fig

@handle_fig
def hospi_view(dataframe, **kwargs):
    """
    The overview of all hospitalized patients by severity. It creates subset from the given date.
    It draws some basic series and their "prediction" for short horizon.
    
    :param dataframe:
    :param kwargs:
    :return:
    """
    FIGSIZE = (19, 8)
    WINDOWNAME = "Hospitalizace"

    fig = plt.figure(WINDOWNAME, figsize=FIGSIZE)
    ax = plt.gca()

    to_draw = [
        # "n: column name, "l": plot label, "c": plot color
        {"n": "stav_tezky", "l": "Hospitalizováni ve vážném stavu", "c": "k"},
        {"n": "stav_stredni", "l": "Hospitalizováni se středně těžkými příznaky", "c": "r"},
        {"n": "stav_lehky", "l": "Hospitalizováni s lehkými příznaky", "c": "y"},
        {"n": "stav_bez_priznaku", "l": "Hospitalizováni bez příznaků", "c": "g"},
    ]

    subset = dataframe[dataframe.index > DATES["new_age"]].copy()
    subset["sum td next"] = subset["pocet_hosp"] - subset["pocet_hosp"]
    for td in to_draw:
        subset["sum td prev"] = subset["sum td next"]
        subset["sum td next"] += subset[td["n"]]
        new_column_name = "{}_exp".format(td["n"])
        augmented_subset = get_exponential(subset, "sum td next", new_column_name, start=DATES["wave3"], horizon=14)
        ax.fill_between(subset.index, subset["sum td prev"], subset["sum td next"], color=td["c"], label=td["l"])
        ax.plot(augmented_subset.index, augmented_subset[new_column_name], ':{}'.format(td["c"]))
    plt.xlim(augmented_subset.index[0], augmented_subset.index[-1])
    plt.ylim(0, subset["pocet_hosp"].max()*1.05)
    ax.xaxis.set_major_locator(plt.MaxNLocator(100))
    ax.yaxis.set_major_locator(plt.MaxNLocator(25))
    plt.xticks(rotation=90)
    plt.grid()
    plt.legend()
    ax.yaxis.set_major_formatter(ticker.ScalarFormatter())
    plt.tight_layout()
    return fig

@handle_fig
def incrm_view(dataframe, **kwargs):
    """
    Change per day. It creates subset from the given date.
    It draws some basic series and their "prediction" for short horizon.
    
    :param dataframe:
    :param kwargs:
    :return:
    """
    FIGSIZE = (19, 8)
    WINDOWNAME = "Denní přírůstky"
    dataframe.loc[:,"aktualne_nakazenych"] = dataframe["kumulativni_pocet_nakazenych"] - dataframe["kumulativni_pocet_umrti"] - dataframe["kumulativni_pocet_vylecenych"]
    subset = dataframe[dataframe.index > DATES["new_age"]].copy()

    fig = plt.figure(WINDOWNAME, figsize=FIGSIZE)
    ax = plt.gca()

    to_draw = [
        # "n: column name, "l": plot label, "c": plot color
        #{"n": "kumulativni_pocet_umrti", "l": "Mrtví celkem", "c": "r"},
        #{"n": "umrti", "l": "Denně mrtví", "c": "k"}
        {"n": "prirustkovy_pocet_nakazenych", "l": "Denně nakažení", "c": "b"},
        {"n": "prirustkovy_pocet_vylecenych", "l": "Denně vyléčení", "c": "g"},
        {"n": "pacient_prvni_zaznam", "l": "Nově hospitalizovaní", "c": "r"},
        {"n": "prirustkovy_pocet_umrti", "l": "Denně mrtví", "c": "k"}
    ]

    for td in to_draw:
        new_column_name = "{}_exp".format(td["n"])
        augmented_subset = get_exponential(subset, td["n"], new_column_name, start=DATES["wave3"], horizon=14)
        ax.plot(augmented_subset.index, augmented_subset[td["n"]], td["c"], linestyle="-", marker="+", label=td["l"])
        ax.plot(augmented_subset.index, augmented_subset[new_column_name], ':{}'.format(td["c"]))
    plt.xlim(augmented_subset.index[0], augmented_subset.index[-1])
    plt.ylim(0, subset["prirustkovy_pocet_nakazenych"].max()*1.05)
    ax.xaxis.set_major_locator(plt.MaxNLocator(100))
    ax.yaxis.set_major_locator(plt.MaxNLocator(25))
    plt.xticks(rotation=90)
    plt.grid()
    plt.legend()
    ax.yaxis.set_major_formatter(ticker.ScalarFormatter())
    plt.tight_layout()
    return fig

def robot_export(path=False):
    """
    This is the function for discord robot - it makes some drawings and save them without displaying.
    
    :param path:
    :return:
    """
    path = path if path else FIG_PATH
    dataframe = download_data(data_path="data.pckl")
    basic_view(dataframe, display=False, filename="basic_overview.png")

# where to store the potentional output figures
FIG_PATH = os.path.join("figs")

# dates used in the ploting functions (dataset selection, etc.)
DATES = {
    "new_age": "2020-09-01",
    "wave3": "2021-08-30",
}

if __name__ == "__main__":

    dataframe = download_data(data_path="data.pckl")
    # dataframe = pd.read_pickle("data.pckl")

    # print(dataframe.keys())

    basic_view(dataframe, display=True, filename="basic_overview.png")
    hospi_view(dataframe, display=False, filename="hospi_overview.png")
    incrm_view(dataframe, display=False, filename="incrm_overview.png")

    plt.show()
