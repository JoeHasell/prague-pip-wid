*******************************************************
* fetch_population.do — adult & total population from WID
*
* Run by 00_fetch_wid.py with Stata's working directory
* set to data/raw/wid/, so the output path is relative.
* Fast: one API call, all countries.
*
* npopul, ages 992 (adults, 20+) and 999 (all ages),
* population(i) = individuals. Used in 02_process_wid.py
* for the per-adult -> per-capita adjustment and for
* bin population weights.
*******************************************************

clear all
set more off

local target_year = 2023

wid, indicators(npopul) ///
    areas(_all)          ///
    years(`target_year') ///
    ages(992 999)        ///
    population(i)        ///
    clear

keep country year value variable
reshape wide value, i(country year) j(variable) string

rename valuenpopul992i adult_pop
rename valuenpopul999i total_pop

export delimited using "WID_aggregate_population.csv", replace delim(",")

*******************************************************
* End of do-file
*******************************************************
