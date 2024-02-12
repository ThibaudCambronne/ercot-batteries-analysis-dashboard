import streamlit as st
import pandas as pd
import analysis_functions as af
import waterfall_chart

# Load data
dfs = af.get_data()
list_of_batteries = af.get_batteries(dfs)

tab_single_battery_analysis, tab_all_batteries = st.tabs(["Single Battery", "Compare all batteries"])

## 1. Battery analysis
with tab_single_battery_analysis:
    # Select battery 
    battery = st.selectbox(
        f"🔋 Select one of the {len(list_of_batteries)} batteries to analyze : ",
        list_of_batteries,
        index=len(list_of_batteries)-1
        )

    # Display note on how many batteries are new
    st.write(f"*Note: All the batteries come online before the dataset starts, except for {', '.join(af.get_list_new_batteries(dfs))}*")

    st.subheader("Battery Status")
    # Display history of battery status
    st.pyplot(af.plot_battery_status(dfs, battery))

    # DIsplay the revenue of each battery
    st.subheader("Battery Revenue")

    # get the revenue data

    df_all_revenues = af.df_all_revenues(dfs)
    # convert to millions
    
    df_revenue_energy_one_battery = df_all_revenues.loc[battery, :].drop(["Total revenue ($/MW)", "Total revenue ($)"])
    df_revenue_energy_one_battery = df_revenue_energy_one_battery / 1e6

    st.pyplot(waterfall_chart.plot(
        df_revenue_energy_one_battery.index,
        df_revenue_energy_one_battery.values,
        net_label='Total',
        rotation_value=70,
        Title=f"Yearly Revenue of the battery {battery} in 2021",
        y_lab="Revenue (M$)"
        )
    )


with tab_all_batteries:
    st.subheader("Analysis of the hourly price variation")
    tab_energy_price, tab_as_price = st.tabs(["Energy Price", "Ancillary Services Price"])

    with tab_energy_price:
        st.write("Here we analyze the variation of the energy price between the batteries.  \n\
                The first graph shows that the yearly median price is not the same for all the batteries.  \n \
                The second graph shows that the median hourly varation between the batteries is 8%. \
                **Indeed, the energy price varies accross the different nodes of the grid.**")
        df_energy_price = dfs["bess_lmps"]["rtm_lmps"].unstack()
        st.pyplot(af.plot_energy_price_per_battery(df_energy_price))

        st.pyplot(af.plot_hourly_price_variation_between_batteries(
                af.get_hourly_percentage_variation(df_energy_price),
                "energy"
            )
        )

    with tab_as_price:
        st.write("Here we analyze the variation of the ancillary services price between the batteries.  \n\
                The graph shows that **there is no hourly varation between the batteries!**  \n\
                Therefore all the batteries have the same price for the ancillary services. \
                This is because the ancillary services are computed at the ISO level.")
        df_as_prices_variation = pd.DataFrame()

        for column in dfs["gen_price_as"].columns:
            df_as_price_column = dfs["gen_price_as"][column].combine_first(dfs["load_price_as"][column])
            df_as_prices_variation[f"{column}"] = af.get_hourly_percentage_variation(df_as_price_column.unstack())

        st.pyplot(af.plot_hourly_price_variation_between_batteries(df_as_prices_variation, "ancillary services"))


    st.divider()
    st.subheader("Analysis of the yearly revenue")
    col1, col2 = st.columns([5, 1])
    
    with col2:
        mode = st.selectbox(
            f"Mode :",
            ["$", "$/MW"],
            index=0
            )

    if mode == "$":
        st.pyplot(af.plot_data_against_battery(df_all_revenues, "Total revenue ($)", "Yearly revenue ($)"))
    else:
        # plot the total revenue per MW
        st.pyplot(af.plot_data_against_battery(df_all_revenues, "Total revenue ($/MW)", "Yearly revenue per MW ($/MW)"))
