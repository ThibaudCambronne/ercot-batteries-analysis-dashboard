import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# specifies colors for the statuses
DICT_COLORS = {
    "UNKNOWN STATUS": "silver",
    "OUT" : "gold",
    "ONTEST" : "mediumseagreen",
    "ON" : "tab:green",
    "OFF" : "tab:red",
    "ONREG" : "tab:blue",
    "ONOS" : "green"
}

FIG_SIZE = (10, 3)

def get_data():
    """Load data from feather files. We also parse the dates to datetime format."""
    path = "./data"

    files = [
        'gen_price_as',
        'load_price_as',
        'dam_gen',
        'dam_load',
        'bess_lmps',
        'rtm_pwr',
    ]

    dfs = {f: pd.read_feather(f"{path}/{f}.feather") for f in files}
    for k, v in dfs.items():
        v.set_index(['timestamp', 'resource_name'], inplace=True)

    # merge as price data from gen and load since they are the same in the two files
    dfs["price_as"] = get_df_as_prices(dfs)

    return dfs


def get_df_as_prices(dfs):
    # merge as price data from gen and load
    df_as_prices = pd.DataFrame()

    for column in dfs["gen_price_as"].columns:
        df_as_price_column = dfs["gen_price_as"][column].combine_first(dfs["load_price_as"][column])
        df_as_prices[column] = df_as_price_column

    return df_as_prices


def get_batteries(dfs):
    """Get list of batteries from the first dataframe in dfs (it's the same in all the dataframes)"""
    list_batteries = dfs[list(dfs.keys())[0]].index.get_level_values(1).unique().sort_values()
    return list_batteries


def plot_battery_status(dfs, battery_name):
    """Plot the status of a battery"""
    df = pd.DataFrame()
    df["status"] = dfs["dam_gen"]["resource_status"].unstack()[battery_name]
    df["status"] = df["status"].fillna("UNKNOWN STATUS")
    df["Height rectangles"] = 1

    statuses = df["status"].unique()

    fig, ax = plt.subplots(figsize=FIG_SIZE)

    for status in statuses:
        sub_df = df[df["status"] == status]
        ax.fill_between(sub_df.index, sub_df["Height rectangles"], label=status, color=DICT_COLORS[status])

    # remove y axis
    ax.yaxis.set_visible(False)

    ax.legend(loc='upper left')
    ax.set_title(f"Status timeline of the battery {battery_name}")
    return fig


def get_list_new_batteries(dfs):
    df_status = dfs["dam_gen"]["resource_status"].unstack()
    # for each column (i.e. battery), we get the first timestamp where the value is not NaN
    batteries_online_start_date = df_status.apply(lambda x: x[(pd.notna(x))].index[0], axis=0)

    new_batteries_2021 = batteries_online_start_date[batteries_online_start_date != df_status.index[0]].index.tolist()
    return new_batteries_2021


def plot_energy_price_per_battery(df_price):
    # we calculate the average hourly price of energy for each battery

    # reorder the columns to put the battery with the highest average price of energy first
    df_price = df_price[df_price.median().sort_values(ascending=False).index]

    # plot a box plot the average hourly price of energy for each battery
    fig, ax = plt.subplots(figsize=FIG_SIZE)
    df_price.plot(kind="box", ax=ax, showfliers=False, color= "black", medianprops={"color":"orange"})
    plt.xticks(rotation=75)
    ax.set_title("Median hourly price of energy in 2021 for each battery, from highest to lowest")
    ax.set_ylabel("Price of energy ($/MWh)")

    return fig


def get_hourly_percentage_variation(df_price):
    df_hourly_variation = pd.DataFrame()
    df_hourly_variation["min"] = df_price.min(axis=1)
    df_hourly_variation["max"] = df_price.max(axis=1)
    df_hourly_variation["mean"] = df_price.mean(axis=1)
    # df_hourly_variation["std"] = df_price.std(axis=1)
    df_hourly_variation["variation"] = df_hourly_variation["max"] - df_hourly_variation["min"]

    df_hourly_variation["percentage_variation"] = df_hourly_variation["variation"] / df_hourly_variation["mean"].abs() * 100

    return df_hourly_variation["percentage_variation"]


def plot_hourly_price_variation_between_batteries(df_prices_variation, price_type):
    fig, ax = plt.subplots(figsize=FIG_SIZE)
    df_prices_variation.plot(kind="box", ax=ax, showfliers=False, color= "black", medianprops={"color":"orange"})
    ax.set_title(f"Median variation of {price_type} prices between the different batteries")
    ax.set_ylabel("Percentage variation (%)")
    return fig


def get_df_as_revenues(dfs):
    df_revenue_as = pd.DataFrame()

    # To make sure that we multiply the right values together (at the same hours), we merge the dataframes
    # It's inner joins, which means that we only keep the hours that are in both dataframes
    df_temp = dfs["dam_gen"][["nonspin_awarded"]].merge(dfs["gen_price_as"][["nonspin"]], left_index=True, right_index=True,)
    df_revenue_as["Non-spinning Reserve Service"] = df_temp.iloc[:, 0] * df_temp.iloc[:, 1]

    df_temp = dfs["dam_gen"][["rrs_awarded"]].merge(dfs["gen_price_as"][["rrs"]], left_index=True, right_index=True)
    df_revenue_as["Responsive Reserve Service"] = df_temp.iloc[:, 0] * df_temp.iloc[:, 1]

    df_temp = dfs["dam_gen"][["regup_awarded"]].merge(dfs["gen_price_as"][["reg_up"]], left_index=True, right_index=True)
    df_revenue_as["Regulation Service - Up"] = df_temp.iloc[:, 0] * df_temp.iloc[:, 1]

    df_temp = dfs["dam_load"][["regdown_awarded"]].merge(dfs["load_price_as"][["reg_down"]], left_index=True, right_index=True)
    df_revenue_as["Regulation Service - Down"] = df_temp.iloc[:, 0] * df_temp.iloc[:, 1]

    df_revenue_as_total = df_revenue_as.groupby(level=1).sum()

    return df_revenue_as_total


def get_df_energy_revenues(dfs):
    df_energy_quantity = dfs["rtm_pwr"]["MW"].unstack()
    df_energy_quantity.index = pd.to_datetime(df_energy_quantity.index, utc=True)
    df_energy_quantity = pd.DataFrame(df_energy_quantity.resample("H").sum().unstack(), columns=["MWh"])
    # once converted to datetime, timezone is lost and the start hour is 06:00 instead of 00:00.
    # But this is okay for now, because it will be the same for the prices, and because we still have 8760 hours (365 days * 24 hours)
    
    df_energy_price = dfs["bess_lmps"]["rtm_lmps"].unstack()
    df_energy_price.index = pd.to_datetime(df_energy_price.index, utc=True)
    df_energy_price = pd.DataFrame(df_energy_price.resample("H").sum().unstack(), columns=["Price"])
    
    df_revenue_energy = pd.DataFrame()

    # To make sure that we multiply the right values together (at the same hours), we merge the dataframes
    # It's a left join, which means that we keep all the hours that are in the energy quantity dataframe
    df_temp = df_energy_quantity.merge(df_energy_price, left_index=True, right_index=True)
    df_revenue_energy["Energy revenue"] = df_temp.iloc[:, 0] * df_temp.iloc[:, 1]

    df_revenue_energy_total = df_revenue_energy.groupby(level=0).sum()

    return df_revenue_energy_total


def plot_data_against_battery(df_as, column_name, unit):
    # plot the awarded capacity for each battery (with space between the plots)
    fig, ax = plt.subplots(figsize=FIG_SIZE)

    plot_number = df_as.columns.get_loc(column_name)
    # sort the batteries and plot bar charts
    df_as[column_name].sort_values(ascending=False).plot(kind="bar", ax=ax, color="tab:blue")
    ax.set_title(column_name)
    ax.set_ylabel(unit)
    ax.set_xlabel("")
    # rotate the x axis labels
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=75)
    return fig

@st.cache
def df_all_revenues(dfs):
    df_revenue_as_total = get_df_as_revenues(dfs)
    df_revenue_energy_total = get_df_energy_revenues(dfs)
    df_all_revenues = df_revenue_energy_total.merge(df_revenue_as_total, left_index=True, right_index=True)

    df_all_revenues["Total revenue ($)"] = df_all_revenues.sum(axis=1)

    df_battery_power = dfs["dam_load"]["max_power_consumption_for_load_resource"].groupby(level=1).max()
    # Add battery power to the revenue dataframe
    df_all_revenues = df_all_revenues.merge(df_battery_power, left_index=True, right_index=True)
    # compute the total revenue per MW
    df_all_revenues["Total revenue ($/MW)"] = df_all_revenues["Total revenue ($)"] / df_all_revenues["max_power_consumption_for_load_resource"]

    return df_all_revenues




