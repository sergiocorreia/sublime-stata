* Config
	clear all
	cls

* Get list of ADO files
	insheet using "ados.txt", noname
	drop if mi(v1)
	tempfile ados
	save "`ados'"

* Iterate over MAINT files
loc chars `c(alpha)'
loc base "`c(sysdir_base)'"
foreach c of local chars {
		loc fn "`base'/`c'/`c'help_alias.maint"
		di as text "[`fn']"
		conf file "`fn'"
		insheet using "`fn'", clear
		keep v1
		tempfile c`c'
		save "`c`c''"
		loc files `"`files' "`c`c''""'
}
	
	
* Import candidates
	clear
	import delimited using builtin_candidates.txt, case(preserve) varnames(nonames) delimit("\tasd\tasd\tasd\t", asstring)
	format v1 %200s

* Filter candidates
	replace v1 = trim(v1)
	keep v1
	keep if lower(v1) == v1
	drop if mi(v1)

	gen byte drop = regexm(v1, "[^a-zA-Z0-9_]")
	drop if drop
	drop drop

	gen byte drop = regexm(v1, "^[0-9]")
	drop if drop
	drop drop

	drop if strpos(v1, "ffff")
	drop if strpos(v1, "vvvvvvv")
	drop if strpos(v1, "xxxxxxx")
	drop if strpos(v1, "zzzzzzz")

	contract v1
	drop _freq

	format v1 %20s

* Add files from MAINT
	append using `files'
	
* Test with -which-
	gen byte ok = 0
	loc N = c(N)
	forv i = 1 / `N' {
		cap which `=v1[`i']'
		if (!c(rc)) {
			qui replace ok = 1 in `i'
		}
	}
	keep if ok
	drop ok
	sort v1

* Append ADOs
	append using "`ados'"
	contract v1
	drop _freq
	
* Save
	compress
	outsheet using "stata_commands.txt", nolabel noquote noname replace

exit
