cap pr asd
end

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
