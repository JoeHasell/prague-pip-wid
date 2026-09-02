*******************************************************
* fetch_ppp.do — PPP conversion factors from WID (xlcusp)
*
* Run by 00_fetch_wid.py with Stata's working directory
* set to data/raw/wid/, so the output path is relative.
* Fast: one API call, all countries.
*
* xlcusp = local currency units per international (PPP)
* dollar, used in 02_process_wid.py to convert WID's
* local-currency incomes to international dollars.
*******************************************************

clear all
set more off

* Both the data year (2023) and WID's PRICE-BASE year (2025) are fetched;
* 02_process_wid.py selects the price-base year (config.PPP_YEAR).
local target_year = "2023 2025"

wid, indicators(xlcusp) ///
    areas(_all)          ///
    years(`target_year') ///
    clear

rename value ppp
keep country year ppp

* Legacy column kept for compatibility with earlier versions
gen percentile = "p0p100"

export delimited using "WID_ppp.csv", replace delim(",")

*******************************************************
* End of do-file
*******************************************************
