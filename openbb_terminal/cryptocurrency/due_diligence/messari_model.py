"""Messari model"""
__docformat__ = "numpy"
# flake8: noqa
# pylint: disable=C0301,C0302

import logging
from typing import Any, Tuple
import re
import pandas as pd
import requests

from openbb_terminal import config_terminal as cfg
from openbb_terminal.cryptocurrency.dataframe_helpers import (
    lambda_replace_underscores_in_column_names,
    prettify_column_names,
)
from openbb_terminal.cryptocurrency.due_diligence.pycoingecko_model import (
    get_coin_tokenomics,
)
from openbb_terminal.decorators import log_start_end
from openbb_terminal.helper_funcs import lambda_long_number_format
from openbb_terminal.rich_config import console

logger = logging.getLogger(__name__)

INTERVALS_TIMESERIES = ["5m", "15m", "30m", "1h", "1d", "1w"]


@log_start_end(log=logger)
def get_available_timeseries() -> pd.DataFrame:
    """Returns available messari timeseries
    [Source: https://messari.io/]

    Returns
    -------
    pd.DataFrame
        available timeseries
    """
    r = requests.get("https://data.messari.io/api/v1/assets/metrics")
    if r.status_code == 200:
        data = r.json()
        metrics = data["data"]["metrics"]
        arr = []
        for metric in metrics:
            sources = ""
            for source in metric["source_attribution"]:
                sources += source["name"]
                sources += ","
            sources = sources.rstrip(",")
            arr.append(
                {
                    "id": metric["metric_id"],
                    "Title": metric["name"],
                    "Description": metric["description"],
                    "Requires Paid Key": "role_restriction" in metric,
                    "Sources": sources,
                }
            )
        df = pd.DataFrame(arr)
        df.set_index("id", inplace=True)
        return df
    return pd.DataFrame()


base_url = "https://data.messari.io/api/v1/"
base_url2 = "https://data.messari.io/api/v2/"


@log_start_end(log=logger)
def get_marketcap_dominance(
    coin: str, interval: str, start: str, end: str
) -> pd.DataFrame:
    """Returns market dominance of a coin over time
    [Source: https://messari.io/]

    Parameters
    ----------
    coin : str
        Crypto symbol to check market cap dominance
    start : int
        Initial date like string (e.g., 2021-10-01)
    end : int
        End date like string (e.g., 2021-10-01)
    interval : str
        Interval frequency (e.g., 1d)

    Returns
    -------
    pd.DataFrame
        market dominance percentage over time
    """

    df, _ = get_messari_timeseries(
        coin=coin, end=end, start=start, interval=interval, timeseries_id="mcap.dom"
    )
    return df


@log_start_end(log=logger)
def get_messari_timeseries(
    coin: str, timeseries_id: str, interval: str, start: str, end: str
) -> Tuple[pd.DataFrame, str]:
    """Returns messari timeseries
    [Source: https://messari.io/]

    Parameters
    ----------
    coin : str
        Crypto symbol to check messari timeseries
    timeseries_id : str
        Messari timeserie id
    start : int
        Initial date like string (e.g., 2021-10-01)
    end : int
        End date like string (e.g., 2021-10-01)
    interval : str
        Interval frequency (e.g., 1d)

    Returns
    -------
    pd.DataFrame
        messari timeserie over time
    str
        timeserie title
    """

    url = base_url + f"assets/{coin}/metrics/{timeseries_id}/time-series"

    headers = {"x-messari-api-key": cfg.API_MESSARI_KEY}

    parameters = {
        "start": start,
        "end": end,
        "interval": interval,
    }

    r = requests.get(url, params=parameters, headers=headers)

    df = pd.DataFrame()
    title = ""

    if r.status_code == 200:
        data = r.json()["data"]
        title = data["schema"]["name"]
        df = pd.DataFrame(data["values"], columns=data["parameters"]["columns"])

        if df.empty:
            console.print(f"No data found for {coin}.\n")
        else:
            df = df.set_index("timestamp")
            df.index = pd.to_datetime(df.index, unit="ms")
    elif r.status_code == 401:
        if "requires a pro or enterprise subscription" in r.text:
            console.print("[red]API Key not authorized for Premium Feature[/red]\n")
        else:
            console.print("[red]Invalid API Key[/red]\n")
    else:
        console.print(r.text)
    return df, title


@log_start_end(log=logger)
def get_links(symbol: str) -> pd.DataFrame:
    """Returns asset's links
    [Source: https://messari.io/]

    Parameters
    ----------
    symbol : str
        Crypto symbol to check links

    Returns
    -------
    pd.DataFrame
        asset links
    """

    url = base_url2 + f"assets/{symbol}/profile"

    headers = {"x-messari-api-key": cfg.API_MESSARI_KEY}

    params = {"fields": "profile/general/overview/official_links"}

    r = requests.get(url, headers=headers, params=params)

    df = pd.DataFrame()

    if r.status_code == 200:
        data = r.json()["data"]
        df = pd.DataFrame(data["profile"]["general"]["overview"]["official_links"])
        df.columns = map(str.capitalize, df.columns)
        return df
    if r.status_code == 401:
        print("[red]Invalid API Key[/red]\n")
    else:
        print(r.text)
    return pd.DataFrame()


@log_start_end(log=logger)
def get_roadmap(symbol: str) -> pd.DataFrame:
    """Returns coin roadmap
    [Source: https://messari.io/]

    Parameters
    ----------
    symbol : str
        Crypto symbol to check roadmap

    Returns
    -------
    pd.DataFrame
        roadmap
    """

    url = base_url2 + f"assets/{symbol}/profile"

    headers = {"x-messari-api-key": cfg.API_MESSARI_KEY}

    params = {"fields": "profile/general/roadmap"}

    r = requests.get(url, headers=headers, params=params)

    df = pd.DataFrame()

    if r.status_code == 200:
        data = r.json()["data"]
        df = pd.DataFrame(data["profile"]["general"]["roadmap"])
        df["date"] = pd.to_datetime(df["date"])
        df.columns = map(str.capitalize, df.columns)
        df = df.dropna(axis=1, how="all")
    elif r.status_code == 401:
        console.print("[red]Invalid API Key[/red]\n")
    else:
        console.print(r.text)

    return df


@log_start_end(log=logger)
def get_tokenomics(
    symbol: str, coingecko_symbol: str
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Returns coin tokenomics
    [Source: https://messari.io/]

    Parameters
    ----------
    symbol : str
        Crypto symbol to check tokenomics
    coingecko_symbol : str
        ID from coingecko
    Returns
    -------
    pd.DataFrame
        Metric Value tokenomics
    pd.DataFrame
        Circulating supply overtime
    """

    url = base_url2 + f"assets/{symbol}/profile"

    headers = {"x-messari-api-key": ""}

    params = {"fields": "profile/economics/consensus_and_emission"}

    r = requests.get(url, headers=headers, params=params)

    df = pd.DataFrame()
    circ_df = pd.DataFrame()
    if r.status_code == 200:
        data = r.json()["data"]
        tokenomics_data = data["profile"]["economics"]["consensus_and_emission"]
        df = pd.DataFrame(
            {
                "Metric": [
                    "Emission Type",
                    "Consensus Mechanism",
                    "Consensus Details",
                    "Mining Algorithm",
                    "Block Reward",
                ],
                "Value": [
                    tokenomics_data["supply"]["general_emission_type"],
                    tokenomics_data["consensus"]["general_consensus_mechanism"],
                    tokenomics_data["consensus"]["consensus_details"],
                    tokenomics_data["consensus"]["mining_algorithm"],
                    tokenomics_data["consensus"]["block_reward"],
                ],
            }
        )
        df["Value"] = df["Value"].str.replace("n/a", "-")
        cg_df = get_coin_tokenomics(coingecko_symbol)
        df = pd.concat([df, cg_df], ignore_index=True, sort=False)
        df.fillna("-", inplace=True)
        circ_df, _ = get_messari_timeseries(
            coin=symbol,
            timeseries_id="sply.circ",
            interval="1d",
            start="",
            end="",
        )
    elif r.status_code == 401:
        console.print("[red]Invalid API Key[/red]\n")
    else:
        console.print(r.text)

    return df, circ_df


@log_start_end(log=logger)
def get_project_product_info(
    symbol: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns coin product info
    [Source: https://messari.io/]

    Parameters
    ----------
    symbol : str
        Crypto symbol to check product info

    Returns
    -------
    pd.DataFrame
        Metric, Value with project and technology details
    pd.DataFrame
        coin public repos
    pd.DataFrame
        coin audits
    pd.DataFrame
        coin known exploits/vulns
    """

    url = base_url2 + f"assets/{symbol}/profile"

    headers = {"x-messari-api-key": ""}

    params = {"fields": "profile/general/overview/project_details,profile/technology"}

    r = requests.get(url, headers=headers, params=params)

    df = pd.DataFrame()
    if r.status_code == 200:
        data = r.json()["data"]
        project_details = data["profile"]["general"]["overview"]["project_details"]
        technology_data = data["profile"]["technology"]
        technology_details = technology_data["overview"]["technology_details"]
        df_info = pd.DataFrame(
            {
                "Metric": ["Project Details", "Technology Details"],
                "Value": [project_details, technology_details],
            }
        )
        df_repos = pd.DataFrame(technology_data["overview"]["client_repositories"])
        df_repos.columns = prettify_column_names(df_repos.columns)
        df_repos.fillna("-", inplace=True)
        df_audits = pd.DataFrame(technology_data["security"]["audits"])
        df_audits.columns = prettify_column_names(df_audits.columns)
        if not df_audits.empty:
            df_audits["Date"] = pd.to_datetime(df_audits["Date"])
            df_audits.fillna("-", inplace=True)
        df_vulns = pd.DataFrame(
            technology_data["security"]["known_exploits_and_vulnerabilities"]
        )
        df_vulns.columns = prettify_column_names(df_vulns.columns)
        if not df_vulns.empty:
            df_vulns["Date"] = pd.to_datetime(df_vulns["Date"])
            df_vulns.fillna("-", inplace=True)
        return df_info, df_repos, df_audits, df_vulns
    if r.status_code == 401:
        console.print("[red]Invalid API Key[/red]\n")
    else:
        console.print(r.text)

    return df, df, df, df


@log_start_end(log=logger)
def get_team(symbol: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Returns coin team
    [Source: https://messari.io/]

    Parameters
    ----------
    symbol : str
        Crypto symbol to check team

    Returns
    -------
    pd.DataFrame
        individuals
    pd.DataFrame
        organizations
    """

    url = base_url2 + f"assets/{symbol}/profile"

    headers = {"x-messari-api-key": cfg.API_MESSARI_KEY}

    params = {"fields": "profile/contributors"}

    r = requests.get(url, headers=headers, params=params)

    df = pd.DataFrame()
    if r.status_code == 200:
        data = r.json()["data"]
        df_individual_contributors = pd.DataFrame(
            data["profile"]["contributors"]["individuals"]
        )
        if not df_individual_contributors.empty:
            df_individual_contributors.fillna("-", inplace=True)
            df_individual_contributors.insert(
                0,
                "Name",
                df_individual_contributors[["first_name", "last_name"]].apply(
                    lambda x: " ".join(x), axis=1
                ),
            )
            df_individual_contributors.drop(
                ["slug", "avatar_url", "first_name", "last_name"],
                axis=1,
                inplace=True,
                errors="ignore",
            )
            df_individual_contributors.columns = map(
                str.capitalize, df_individual_contributors.columns
            )
            df_individual_contributors.replace(
                to_replace=[None], value="-", inplace=True
            )
        df_organizations_contributors = pd.DataFrame(
            data["profile"]["contributors"]["organizations"]
        )
        if not df_organizations_contributors.empty:
            df_organizations_contributors.drop(
                ["slug", "logo"], axis=1, inplace=True, errors="ignore"
            )
            df_organizations_contributors.columns = map(
                str.capitalize, df_organizations_contributors.columns
            )
            df_organizations_contributors.replace(
                to_replace=[None], value="-", inplace=True
            )
        return df_individual_contributors, df_organizations_contributors
    if r.status_code == 401:
        console.print("[red]Invalid API Key[/red]\n")
    else:
        console.print(r.text)

    return df, df


@log_start_end(log=logger)
def get_investors(symbol: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Returns coin investors
    [Source: https://messari.io/]

    Parameters
    ----------
    symbol : str
        Crypto symbol to check investors

    Returns
    -------
    pd.DataFrame
        individuals
    pd.DataFrame
        organizations
    """

    url = base_url2 + f"assets/{symbol}/profile"

    headers = {"x-messari-api-key": cfg.API_MESSARI_KEY}

    params = {"fields": "profile/investors"}

    r = requests.get(url, headers=headers, params=params)

    df = pd.DataFrame()
    if r.status_code == 200:
        data = r.json()["data"]
        df_individual_investors = pd.DataFrame(
            data["profile"]["investors"]["individuals"]
        )
        if not df_individual_investors.empty:
            df_individual_investors.fillna("-", inplace=True)
            df_individual_investors.insert(
                0,
                "Name",
                df_individual_investors[["first_name", "last_name"]].apply(
                    lambda x: " ".join(x), axis=1
                ),
            )
            df_individual_investors.drop(
                ["slug", "avatar_url", "first_name", "last_name"],
                axis=1,
                inplace=True,
                errors="ignore",
            )
            df_individual_investors.columns = map(
                str.capitalize, df_individual_investors.columns
            )
            df_individual_investors.replace(to_replace=[None], value="-", inplace=True)
        df_organizations_investors = pd.DataFrame(
            data["profile"]["investors"]["organizations"]
        )
        if not df_organizations_investors.empty:
            df_organizations_investors.drop(
                ["slug", "logo"], axis=1, inplace=True, errors="ignore"
            )
            df_organizations_investors.columns = map(
                str.capitalize, df_organizations_investors.columns
            )
            df_organizations_investors.replace(
                to_replace=[None], value="-", inplace=True
            )
        return df_individual_investors, df_organizations_investors
    if r.status_code == 401:
        console.print("[red]Invalid API Key[/red]\n")
    else:
        console.print(r.text)

    return df, df


@log_start_end(log=logger)
def get_governance(symbol: str) -> Tuple[str, pd.DataFrame]:
    """Returns coin governance
    [Source: https://messari.io/]

    Parameters
    ----------
    symbol : str
        Crypto symbol to check governance

    Returns
    -------
    str
        governance summary
    pd.DataFrame
        Metric Value with governance details
    """

    url = base_url2 + f"assets/{symbol}/profile"

    headers = {"x-messari-api-key": cfg.API_MESSARI_KEY}

    params = {"fields": "profile/governance"}

    r = requests.get(url, headers=headers, params=params)

    df = pd.DataFrame()
    if r.status_code == 200:
        data = r.json()["data"]
        governance_data = data["profile"]["governance"]
        if (
            governance_data["onchain_governance"]["onchain_governance_type"] is not None
            and governance_data["onchain_governance"]["onchain_governance_details"]
            is not None
        ):
            return (
                re.sub("<[^>]*>", "", governance_data["governance_details"]),
                pd.DataFrame(
                    {
                        "Metric": ["Type", "Details"],
                        "Value": [
                            governance_data["onchain_governance"][
                                "onchain_governance_type"
                            ],
                            governance_data["onchain_governance"][
                                "onchain_governance_details"
                            ],
                        ],
                    }
                ),
            )
        return (
            re.sub("<[^>]*>", "", governance_data["governance_details"]),
            df,
        )
    if r.status_code == 401:
        console.print("[red]Invalid API Key[/red]\n")
    else:
        console.print(r.text)

    return "", df


def format_addresses(x: Any):
    final_str = ""
    for address in x:
        final_str += f"{address['name']}: {address['link']}"
    return final_str


@log_start_end(log=logger)
def get_fundraising(
    symbol: str,
) -> Tuple[str, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns coin fundraising
    [Source: https://messari.io/]

    Parameters
    ----------
    symbol : str
        Crypto symbol to check fundraising

    Returns
    -------
    str
        launch summary
    pd.DataFrame
        Sales rounds
    pd.DataFrame
        Treasury Accounts
    pd.DataFrame
        Metric Value launch details
    """

    url = base_url2 + f"assets/{symbol}/profile"

    headers = {"x-messari-api-key": cfg.API_MESSARI_KEY}

    params = {"fields": "profile/economics/launch"}

    r = requests.get(url, headers=headers, params=params)

    df = pd.DataFrame()
    if r.status_code == 200:
        data = r.json()["data"]
        launch_data = data["profile"]["economics"]["launch"]
        launch_details = launch_data["general"]["launch_details"]
        launch_type = launch_data["general"]["launch_style"]
        launch_fundraising_rounds = pd.DataFrame(
            launch_data["fundraising"]["sales_rounds"]
        )
        if not launch_fundraising_rounds.empty:
            launch_fundraising_rounds.fillna("-", inplace=True)
            launch_fundraising_rounds.drop(
                [
                    "details",
                    "asset_collected",
                    "price_per_token_in_asset",
                    "amount_collected_in_asset",
                    "is_kyc_required",
                    "restricted_jurisdictions",
                ],
                axis=1,
                inplace=True,
                errors="ignore",
            )
            launch_fundraising_rounds.columns = [
                lambda_replace_underscores_in_column_names(val)
                for val in launch_fundraising_rounds.columns
            ]
            launch_fundraising_rounds["Start Date"] = launch_fundraising_rounds.apply(
                lambda x: x["Start Date"].split("T")[0], axis=1
            )
            launch_fundraising_rounds["End Date"] = launch_fundraising_rounds.apply(
                lambda x: x["End Date"].split("T")[0], axis=1
            )
            launch_fundraising_rounds.rename(
                columns={
                    "Native Tokens Allocated": "Tokens Allocated",
                    "Equivalent Price Per Token In Usd": "Price [$]",
                    "Amount Collected In Usd": "Amount Collected [$]",
                },
                inplace=True,
            )
            launch_fundraising_rounds.fillna("-", inplace=True)

        launch_fundraising_accounts = pd.DataFrame(
            launch_data["fundraising"]["sales_treasury_accounts"]
        )
        if not launch_fundraising_accounts.empty:
            launch_fundraising_accounts.columns = [
                lambda_replace_underscores_in_column_names(val)
                for val in launch_fundraising_accounts.columns
            ]
            launch_fundraising_accounts.drop(
                ["Asset Held", "Security"], inplace=True, axis=1
            )
            launch_fundraising_accounts["Addresses"] = launch_fundraising_accounts[
                "Addresses"
            ].map(format_addresses)
        launch_distribution = pd.DataFrame(
            {
                "Metric": [
                    "Genesis Date",
                    "Type",
                    "Total Supply",
                    "Investors [%]",
                    "Organization/Founders [%]",
                    "Rewards/Airdrops [%]",
                ],
                "Value": [
                    launch_data["initial_distribution"]["genesis_block_date"].split(
                        "T"
                    )[0]
                    if launch_data["initial_distribution"]["genesis_block_date"]
                    else "-",
                    launch_type,
                    lambda_long_number_format(
                        launch_data["initial_distribution"]["initial_supply"]
                    ),
                    launch_data["initial_distribution"]["initial_supply_repartition"][
                        "allocated_to_investors_percentage"
                    ],
                    launch_data["initial_distribution"]["initial_supply_repartition"][
                        "allocated_to_organization_or_founders_percentage"
                    ],
                    launch_data["initial_distribution"]["initial_supply_repartition"][
                        "allocated_to_premined_rewards_or_airdrops_percentage"
                    ],
                ],
            }
        )
        return (
            launch_details,
            launch_fundraising_rounds,
            launch_fundraising_accounts,
            launch_distribution,
        )
    if r.status_code == 401:
        console.print("[red]Invalid API Key[/red]\n")
    else:
        console.print(r.text)

    return "", df, df, df
