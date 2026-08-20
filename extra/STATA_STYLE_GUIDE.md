# Stata Style Guide for BankRuns Do-Files

This guide is the shared reference for editing BankRuns Stata do-files. It is meant to preserve the existing project style, especially when adding or revising numbered scripts written around `common.do`.

## File Skeleton

Every normal do-file should start with the project header, then `include common.do`, then section headers. Use a literal tab for indented commands.

```stata
* ===========================================================================
* Title of the do-file
* ===========================================================================
	include common.do


// --------------------------------------------------------------------------
// Section header
// --------------------------------------------------------------------------

	use "$data/input-file.dta", clear
```

Use the top `* ===` header only for the file title. Use `// ---` headers for major sections. Keep section names short and descriptive.

For numbered scripts, preserve the surrounding naming and numbering convention. If a script is part of a series, match the structure of nearby scripts before introducing a new pattern.

## Formatting and Naming

- Indent executable code one literal tab inside each section, loop, `preserve` block, or program block.
- Use lowercase variable names with underscores: `bank_id`, `state_abbrev`, `run_no_fail`.
- Avoid spaces in filenames.
- Prefer concise code over defensive boilerplate for stable, hand-maintained inputs.
- Keep readable Stata commands on one line when they are roughly 100 characters or shorter. Do not introduce multiline continuations only to fit an 80-character or 70-character line limit.
- Use comments to explain decisions, data quirks, and non-obvious assumptions; do not narrate ordinary Stata syntax.
- Use `loc` / `local` for temporary script settings and lists. Use project globals only when they come from `common.do` or are intentionally shared.
- Spell out `rename`; do not use `ren` or other abbreviations for it.
- Use `su` for summarize commands in new code. If existing code already says `summarize`, leave it as-is rather than shortening it during unrelated edits.
- End batch-style do-files with `exit` when that is the local convention.

For predictable numeric loops, prefer `forvalues` over `foreach ... of numlist`. Use `foreach ... of numlist` only when the sequence is irregular enough that `forvalues` is impractical.

Prefer:

```stata
	forvalues num = 1/10 {
		...
	}
```

Instead of:

```stata
	foreach num of numlist 1/10 {
		...
	}
```

## Project Setup and Paths

Always rely on `common.do` for project setup. It handles standard settings, dependency loading, `setroot`, graph defaults, and shared paths.

Use the globals created by `common.do` rather than hard-coded project paths:

- `$root` for the project root
- `$code` for Stata code
- `$data` for generated or canonical data
- `$sources` for source inputs
- `$temp` for temporary project artifacts
- `$output` for paper/output files
- `$figures` for figures
- `$tables` for table includes

Hard-coded external paths are acceptable only when they represent a user-specific external dependency already centralized in `common.do`, such as the Overleaf output root.

## Preferred Commands and Packages

Prefer the fast project-standard tools when they fit the job:

- Use `gisid` rather than `isid` unless a built-in-only check is needed.
- Use `gegen`, `gcollapse`, `gcontract`, and `gdistinct` for grouped operations and counts.
- Use `join` from `ftools` when it is clearer than `merge` and the join contract can be stated directly.
- Use `reghdfe` and `ppmlhdfe` for high-dimensional fixed-effect regressions.
- Use `rangestat` for rolling or windowed event calculations when that is already the local pattern.

Built-in Stata commands are fine when they are clearer, required by syntax, or not performance-sensitive. Do not replace a readable built-in command with a package command just for ornament.

For quantile bins, prefer `gegen ... = xtile(...)` from `gtools` over Stata's built-in `egen ... = xtile(...)`. It is much faster, supports `by(...)`, and chooses the appropriate storage type by default, so do not predeclare `int`, `long`, or another type just for the generated category.

Prefer:

```stata
	gegen fund_cat = xtile(fundamentals), n(10)
	gegen fund_cat = xtile(fundamentals), n(10) by(year)
```

Instead of:

```stata
	egen fund_cat = xtile(fundamentals), n(10)
```

Use `gquantiles` directly when its quantile-specific syntax is clearer or when using features beyond `xtile()` categories.

## Types and Missing Values

Declare variable types when the type is known ahead of time:

```stata
	gen byte run = !mi(next_bank_run)
	gen int year = year(date)
	gen long gt_id = _n
	gen double assets_ratio = assets / total_assets
```

Use `byte` for dummies and small categorical flags, `int` for years/months/small counts, `long` for row IDs and Stata daily dates when appropriate, and `double` for large identifiers or calculations where precision matters. `common.do` sets the default numeric type to double, but explicit types still make intent clearer.

Use compact missing-value checks:

```stata
	drop if mi(bank_id, date, event_type)
```

Prefer this over:

```stata
	drop if mi(bank_id) | mi(date) | mi(event_type)
```

For row totals, be precise. Stata's `egen rowtotal()` treats missing inputs as zero by default. With the `missing` option, it returns missing only when all inputs are missing. Therefore:

```stata
	egen y = rowtotal(x1 x2), missing
```

is a replacement for a manual all-missing correction, not for a rule that requires `y` to be missing when any input is missing. If the intended rule is "missing if any component is missing," write that rule explicitly or use a row-missing check.

## Data Workflow

Keep data transformations direct and auditable:

- Load one clear input at the start of each section.
- Assert key invariants near the point where they become true: nonmissing IDs, uniqueness, valid date ranges, expected merge coverage.
- Use `tempfile` for intermediate datasets that do not need to survive the run.
- Use `$temp` only for debug artifacts or temporary files useful outside the
  current Stata session. Earlier versions of this project saved many datasets
  under `$temp` that were never used afterward; when a saved file is only passed
  between steps inside the same do-file, prefer a `tempfile`.
- When accumulating small result datasets from loops, especially regression
  coefficients, table rows, or metrics, prefer Stata frames with `frame post`
  over repeatedly saving one tempfile per loop iteration and later stitching
  them together with `use` / `append`. Create one results frame, post rows into
  it as estimates are produced, then `frame change` or `frame copy` for figure
  and table construction.
- Use `preserve` / `restore` for short side exports or checks that should not disrupt the main dataset.
- Use `compress` before saving durable datasets.
- Use `format` for IDs/dates before export when Stata's display format would otherwise create hard-to-read output.

Prefer:

```stata
	frame create results str32(Y Z era) int(h) double(b se b_u b_l)

	foreach Y of local lhs_list {
		foreach Z of local rhs_list {
			forvalues h = 0/5 {
				qui reghdfe F`h'`Y' `Z', absorb(bank_id year) vce(dkraay 3)
				local b = _b[`Z']
				local se = _se[`Z']
				frame post results ///
					("`Y'") ("`Z'") ("all") (`h') ///
					(`b') (`se') (`b' + 1.96 * `se') (`b' - 1.96 * `se')
			}
		}
	}

	frame change results
```

Instead of creating `coefs_*.dta` files inside the loop, opening each one,
adding one observation with `set obs`, saving it again, and appending all of
those files later.

Prefer early filtering when the input has an authoritative validity flag:

```stata
	use "$sources/benchmark-mit-ras.dta", clear
	keep if is_valid == 1
```

## Merges, Joins, and IDs

### BankRuns Bank Identifiers

Prefer `bank_id` as the bank identifier throughout this project. Use `charter`
only when importing raw OCC or charter-number source data, building a narrow
crosswalk, or displaying the original source identifier. Do not use `charter`
as a durable merge key when `bank_id` is available.

Earlier versions of the pipeline sometimes constructed `bank_id` as
`charter * 10`. This conversion is already done in the current input files. If
you see `gen bank_id = charter * 10` or an equivalent generated rescaling in a
do-file, treat it as likely stale code or an error unless the surrounding code
is explicitly rebuilding a raw charter crosswalk.

Make merge contracts explicit. In `merge` commands, use `keepusing(...)` whenever only specific variables are needed from the using dataset, so it is clear which fields each merge loaded. After merges, inspect or assert `_merge` before dropping it unless `nogen` is used intentionally.

```stata
	merge m:1 bank_id date using "`events'", keep(master match) keepusing(event_type)
	tab _merge
	assert _merge != 2
	drop _merge
```

Use `gisid` after deduplication or construction of a key:

```stata
	bys bank_id date event_type (episode_uid): keep if _n==1
	gisid bank_id date event_type
```

When using `join`, state the fields being joined and the key in a compact form:

```stata
	join runs_within_*, from("$temp/city_runs_by_distance") by(city_id date) keep(master match using)
```

## Refactoring Existing Do-Files

Keep refactors narrow. Preserve the workflow shape, output paths, and public-facing artifacts unless the requested change requires otherwise.

Some variable names and file names may have changed over the life of the
project. When cleaning old code, verify names against current inputs and nearby
scripts rather than preserving stale names just because they appear in the old
do-file.

For repetitive renames, prefer grouped renames or `ds ... , not` loops over long generated-looking blocks:

```stata
	rename (city state event_type) (city_name state_abbrev event_type_raw)
	ds bank_id, not
	foreach var of varlist `r(varlist)' {
		rename `var' gt_`var'
	}
```

Before mass-prefixing, `keep` only the variables needed downstream. Stata variable names are limited to 32 characters, and prefixing every column can silently turn a clean idea into a brittle one.

Avoid speculative fallback branches for stable, hand-maintained inputs. If the Excel schema is fixed, code to the actual schema and let Stata fail clearly if the input changes.

## Output Conventions

When a do-file creates a paper or review artifact, it should usually do two things:

- Print key counts and tabulations to Stata Results so the result is visible immediately.
- Write the durable artifact to `$tables`, `$figures`, `$output`, or `$temp` as appropriate.

For paper tables, prefer one compact primary include file that can be used inside a surrounding LaTeX table environment. If a detailed full-list table is useful, write it as a secondary artifact rather than making it the primary output.

For individual scalar values that LaTeX will consume later, use `post_scalar.ado` instead of open-coding `file open` / `file write` / `file close`. It writes to the project's `$tables` output path, replaces existing files, and expects the filename extension to be provided:

```stata
	count if run == 1
	local N_run = r(N)
	post_scalar, scalar(`N_run') file("N_run.tex")
```

Use the optional `format()` argument when the default `%9.0fc` is not appropriate.

For validation and review workflows, include row-level debug exports when aggregate counts are not enough. A good pattern is one compact summary plus one or more TSVs listing the exact rows to inspect.

## Verification

For code changes, verify with the real Stata executable when possible:

```powershell
& "C:\Program Files\Stata18\StataMP-64.exe" /e do "C:\Dropbox\Projects\bank-runs\code\SCRIPT.do"
```

Then inspect the `.log`, the Stata Results summaries, and any generated artifacts. If a refactor is supposed to preserve behavior, compare key row counts and output files before and after.

For documentation-only changes, verify that examples match `stata.cursorrules`, the Sublime snippets, and current do-file conventions. Do not run formatters or touch unrelated files.

## Graph and Chart Style

The active project setup uses graph defaults from `common.do`, including the project graph scheme. Let `common.do` set the default scheme; specify a scheme inside graph commands only when there is a concrete reason.

Common graph patterns:

- Use `twoway bar` for layered bars, usually with `barwidth(1)` or `barwidth(1.05)`, `base(0)`, and no visible outlines.
- Use `graph bar, stack asyvars` for stacked category bars with explicit `bar(N, color(...))` choices.
- Use `twoway connected` for time-series lines with markers.
- Use `twoway scatter` and `spmap` for map-style visualizations, with transparency and jitter when needed.

Legend conventions:

```stata
	legend(pos(6) rows(1) span order(1 "Runs" 2 "Suspensions"))
```

Use `legend(off)` for simple single-series or self-evident two-series charts. Keep legends below the chart when present.

Axis and label conventions:

- Use explicit `ytitle()` and `xtitle()` unless the surrounding context makes an axis truly obvious.
- Use short `title()` text and sparse `note()` text for caveats.
- Avoid `subtitle()` and `caption()` unless matching an existing nearby figure.
- Use round year intervals in `xlabel()`, such as `1840(20)1950`.
- Use formatted y-axis labels for counts or currency, such as `ylabel(, format("%8.0fc"))`.

Color conventions:

- Prefer Stata named colors already used in the project: `red`, `blue`, `orange`, `green`, `gs10`, `cranberry`, `forest_green`, `lavender`, `dknavy`, `black`.
- Use transparency with `%NN`, such as `orange%25` or `blue%50`.
- Avoid hex colors unless a specific external style requires them.

Export figures as PNG unless a surrounding workflow clearly uses another format:

```stata
	graph export "$figures/my-figure.png", replace
```

When exporting a PDF, rely on the `.pdf` extension; do not add the redundant `as(pdf)` option:

```stata
	graph export "$figures/my-figure.pdf", replace
```

Use `$figures` or another path derived from `common.do`; avoid ad hoc relative export paths in new code.


