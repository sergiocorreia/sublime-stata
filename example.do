gen x = asd("a")

summarize 0 "A" 2 "C" /// 
	1 "B"


replace event = 9 if missing(ent_short_name) & missing(ent_long_name) & missing(ent_type) & ///
					 missing(ent_status) & missing(ent_bad) & missing(ent_public) & ///
					 missing(ent_spinout_from) & missing(ent_absorbed_by) & missing(ent_acquired_by)

****************************************************************
la def event 0 "Error" 1 "Initial definitions (Jan2001)" 2 "New FI" 3 "Acquisition with merger" /// 
				  4 "Acquisition w/out merger" 5 "Change of name" 6 "Change in FI type" 7 "Change of status" ///
				  8 "Spinoff" 9 "Misc. news" 


la def event 0 "Error" 1 "Initial definitions (Jan2001)" 2 "New FI" 3 "Acquisition with merger" /// 
				  4 "Acquisition w/out merger" 5 "Change of name" 6 "Change in FI type" 7 "Change of status" ///
				  8 "Spinoff" 9 "Misc. news" 


cap pr asd
	asd
end


if (tm(2)==8 & 2>1 & 2) {
	asd
}


if ("$foo" == "") {
	asd
}

prog foobar
	asd
	describe
	append
the end
asd
end

di "asd"
di `"asd"'
`i'
foreach i of local ies {
	su `i'
}

foreach var of varlist asd {
	asd
}



/*---------------------------------------------------------------------------
	Sanity check: create total credit, to validate data
---------------------------------------------------------------------------*/
cap asd asd
`as`foo'd'
	cap ado uninstall derc
`asd'
{asd}
${asd}

	net install derc, from("C:\Git\peru-sbs-rcd\stata")
	pr drop _all	


* comment
asd * asdasdasd
di 4 * 9
     * comment

`cap'

foo // bar
foo /// bar
 spam "asd"


di "`asd'"
di "${asd}"
di "asd"

 // --------------------------------------------------------------------------
// Setup
// --------------------------------------------------------------------------
	include common.doh
	log using "$log/aggregates", smcl replace

	* Months of analysis
	loc t0 = tm(2001m01)
	loc tn = tm(2016m12) // 2012m08
	loc replace 0
	ivreghdfe a b c
	loc foo : bar spam
	loc a = 123
	loc b "asd"
	loc c asdasd
	replace 2 = 3
	use, clear

	foo loc asd 

program asd
	describe ending
	su
end

forvalu i = 1(2)10 {
	asd
}



loc a = 2
cap pr drop process_all
pr define process_all
syntax, T0(integer) TN(integer) [TIMEIT] [REPLace(integer 1)]
	noi di as text  " {break}{title: Procesando datos}"
	if ("`timeit'"!="") {
		qui timer clear 10
		qui timer on 10
	}
end

gen double x = 123

loc asd : list 213
loc asd fasd asdasd : 2

local asd



mata:
	J(1,1,1)
end
