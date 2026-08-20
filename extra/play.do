include common.do

use "$temp/city_level_deposits_loans.dta", clear
*drop pre_nbanks_trim
keep city_id year run_fund_cat1 run_fund_cat2 run_fund_cat3 deposits pre_nbanks g_deposits
compress
xtset city_id year

local horizon 6
local lags 3
local fe city_id
loc lhs deposits

foreach cap of numlist 1 3 5(5)50 75 100 {
	di as error "CAP=`cap'"
	cap drop x
	gen int x = clip(pre_nbanks, 0, `cap') // clip() automatically preserves missings

	capture frame drop results
	frame create results byte(h) long(nobs) double(b1 se1 b1_u b1_l b2 se2 b2_u b2_l b3 se3 b3_u b3_l)
	local events run_fund_cat1 run_fund_cat2 run_fund_cat3

	frame post results ///
		(-1) (.) ///
		(0) (0) (0) (0) ///
		(0) (0) (0) (0) ///
		(0) (0) (0) (0)

	forvalues h = 0/`horizon' {
		display as text "h=`h' " _c
		cap drop Y
		qui gen double Y = 100 * 2 * (F`h'.`lhs' - L.`lhs') / (F`h'.`lhs' + L.`lhs')
		local bw = max(1, ceil(1.5 * `h'))
		qui reghdfe Y L(1/`lags').g_`lhs' L(0/`lags').(`events') [aw=x], a(`fe') vce(dkraay `bw') // cluster(city_id year)

		forvalues i = 1/3 {
			local b`i' = .
			local se`i' = .
			local b`i'_u = .
			local b`i'_l = .
		}

		local i = 0
		foreach event of local events {
			local ++i
			local b`i' = _b[`event']
			local se`i' = _se[`event']
			local b`i'_u = `b`i'' + 1.96 * `se`i''
			local b`i'_l = `b`i'' - 1.96 * `se`i''
		}

		local nobs = e(N)
		frame post results ///
			(`h') (`nobs') ///
			(`b1') (`se1') (`b1_u') (`b1_l') ///
			(`b2') (`se2') (`b2_u') (`b2_l') ///
			(`b3') (`se3') (`b3_u') (`b3_l')

	}

// --------------------------------------------------------------------------

	frame change results
	compress
	gisid h
	assert inrange(h, -1, `horizon')
	sort h

	loc opt1 lwidth(thin) color(navy) msize(vsmall)
	loc opt2 lwidth(thin) color(navy%10)
	loc opt3 lwidth(thin) color(red*1.2) msize(vsmall)
	loc opt4 lwidth(thin) color(red*1.2%10)

	* Runs on weak and strong banks.
	twoway ///
		(connected b3 h, `opt1') ///
		(rarea b3_u b3_l h, `opt2') ///
		(connected b1 h, `opt3') ///
		(rarea b1_u b1_l h, `opt4') ///
		, ///
		ylabel(-60(20)20) ///
		title("LHS=DEP CAP=`cap'") ///
		legend(on order(3 "Run on weak banks" 1 "Run on strong banks") rows(1) size(medium)) ///
		xlabel(-1(1)6) ytitle("City-Level Deposits (in %)") xtitle("Years after shock") xsize(10) ysize(6)

	graph export "E:/Temp/play/DEP-`cap'.png", replace
	graph export "E:/Temp/play/DEP-`cap'.pdf", replace
	frame change default
}
