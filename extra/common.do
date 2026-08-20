* ===========================================================================
* Set global variables and other settings
* ===========================================================================


// --------------------------------------------------------------------------
// Standard settings
// --------------------------------------------------------------------------
	version 16
	cap version 18
	*cap log close _all
	graph close _all
	clear all
	set type double // -gen xyz- will default to -double- instead of -float-
	set varabbrev off // too many hidden errors otherwise
	set emptycells drop
	set trace off
	cap cls
	set more off // useful in batch mode


// --------------------------------------------------------------------------
// Workaround if working dir is not $code
// --------------------------------------------------------------------------
	cap cd "/Users/Everner/Dropbox (Personal)/Research/bank-runs/code"
	cap cd "/Users/everner-mbp-22/Dropbox (Personal)/Research/bank-runs/code"
	cap cd "C:/Users/steph/Dropbox/Research/bank-runs/code"
	_assert strpos(c(pwd), "code"), msg("Working directory should be $root/code")


// --------------------------------------------------------------------------
// Ensure all dependencies/requirements are met
// --------------------------------------------------------------------------
	cap which require
	if (c(rc)) net install require, from("https://raw.githubusercontent.com/sergiocorreia/stata-require/master/src/")
	require using "requirements.txt", install

	* Can't use -require- for SJ software
	cap which labmask
	if (c(rc)) net install gr0034, from("http://www.stata-journal.com/software/sj8-2")
	
	*ssc install binscatter
	*ssc install distinct
	*ssc install mdesc
	*ssc install cleanplots


// --------------------------------------------------------------------------
// Project Paths
// --------------------------------------------------------------------------
	setroot, more search(README.md) // Adds $root $code $data $output // Explicit search so it doesn't trip with .git that codex adds
	global sources   		"$root/sources"

	* Overleaf path
	glo pathO   "C:\Dropbox\Apps\Overleaf\BankRuns2026" // Sergio
	if ("`c(username)'" =="Everner") glo pathO "$root/Apps/Overleaf/BankRuns2026" // Emil 1
	if ("`c(username)'" =="everner-mbp-22") glo pathO "/Users/everner-mbp-22/Dropbox (Personal)/Apps/Overleaf/BankRuns2026" // "/Users/everner-mbp-22/Desktop/runs_tmp" // Emil 2
	if ("`c(username)'" =="steph") glo pathO "C:/Users/steph/Dropbox/Apps/Overleaf/BankRuns2026" // Stephan

	* python path 
	if ("`c(username)'" =="everner-mbp-22") global python_path "/Users/everner-mbp-22/opt/anaconda3/bin/python3"	
	
	* For backwards consistency
	global pathD "$root"

	global temp		"$root/tempfiles"
	global sources	"$root/sources"
	global data   	"$root/data"

	global output	"$pathO/output"
	global figures 	"$output/figures"
	global tables  	"$output/tables"

	global lolr_path "$root/../Lender_of_last_resort"


// --------------------------------------------------------------------------
// Output settings
// --------------------------------------------------------------------------

	* Graphic scheme
	set scheme cleanplots_ev2, perm

	* Font defaults (don't always work)
	graph set window fontface "Avenir"
	if ("`c(os)'" == "Windows") {
		graph set pdf fontface "AvenirNext LT Pro Regular"
		graph set pdf fontfacesans "AvenirNext LT Pro Regular"
	}
	
	* How to show NO in fixed effect row of regression tables (common alternatives "No", "-", "", etc.)
	*global label_no "-"

	global s1 medlarge
	global s2 medium
	global s3 medsmall


// --------------------------------------------------------------------------
// Common globals
// --------------------------------------------------------------------------

**	*Global for key events  (was being defined in 04.do before)
**	global eventlist run_no_fail suspension_no_fail run_only run_sus_open sus_open ///
**		fail_newspaper suspension_closure ///
**		fail_newspaper_w_run run suspension event
