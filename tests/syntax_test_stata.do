// SYNTAX TEST "Packages/Stata/Stata.sublime-syntax"

// Modern and user-written commands
// ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ entity.name.section
// --------------------------------
// ^ - entity.name.section

collect create research
// <- support.function.command.stata
future_estimator outcome treatment
// <- support.function.command.stata

quietly future_estimator outcome treatment
// <- keyword.control.prefix.stata
//      ^ support.function.command.stata

by group: hdidregress outcome treatment
// <- keyword.control.prefix.stata
//        ^ support.function.command.stata
by id: quietly capture regress outcome treatment
//     ^^^^^^^ keyword.control.prefix.stata
//                     ^^^^^^^ support.function.command.stata

prog def research_command
// <- support.function.command.stata
//       ^ entity.name.function.stata

local outcome wage
// <- support.function.command.stata
local fields : list uniq fields
//             ^ support.function.command.extended-macro.stata
global PROJECT_ROOT data/derived
display `outcome' $PROJECT_ROOT ${PROJECT_ROOT}
//      ^^^^^^^^^ meta.local.stata
//                 ^^^^^^^^^^^^ variable.other.global.stata
display `"compound text"'
//        ^^^^^^^^ string.quoted.double.compound.stata

frame create analysis id outcome treatment
// <- support.function.command.stata
frlink m:1 id, frame(covariates) generate(_covariates)
// <- support.function.command.stata

regress outcome i.region##c.age
//              ^ storage.modifier.factor-variable.stata
//                      ^^ keyword.operator.interaction.stata
//                        ^ storage.modifier.factor-variable.stata
regress outcome ib3.region bn.industry
//              ^^^ storage.modifier.factor-variable.stata
//                         ^^ storage.modifier.factor-variable.stata
regress outcome ib(first).region
//              ^^^^^^^^^ storage.modifier.factor-variable.stata
regress outcome ib(last).industry
//              ^^^^^^^^ storage.modifier.factor-variable.stata
regress outcome ib(freq).sector
//              ^^^^^^^^ storage.modifier.factor-variable.stata
regress outcome L.outcome L(1/3).income F.lead D.change S.season
//              ^ storage.modifier.time-series.stata
//                        ^^^^^^ storage.modifier.time-series.stata
//                                      ^ storage.modifier.time-series.stata
regress outcome i.`factor_macro'
//              ^ storage.modifier.factor-variable.stata
//                ^^^^^^^^^^^^^^ meta.local.stata

dtable income age ///
    i.region, by(treatment) ///
    continuous(income, statistics(mean sd))
//  ^^^^^^^^^^ meta.command.stata
//  ^ - support.function.command.stata

order price weight ///
    length // an ordinary comment ends this continued command
//  ^^^^^^ meta.command.stata
//  ^ - support.function.command.stata
gear
// <- support.function.command.stata

order price weight ////
    length gear
//  ^^^^^^ meta.command.stata
//  ^ - support.function.command.stata

display r(mean) if (wage > 0)
//      ^ support.function.result.stata
//              ^^ keyword.control.stata

#delimit ;
// <- keyword.control.directive.stata
dtable income age
    i.region,
//  ^ - support.function.command.stata
    by(treatment)
//  ^ - support.function.command.stata
    continuous(income, statistics(mean sd));
//  ^ - support.function.command.stata
collect create report; futuristic outcome ;
// <- support.function.command.stata
//                     ^ support.function.command.stata
mata: sqrt(4); collect clear;
//    ^^^^ support.function.mata
//           ^ punctuation.terminator.statement.stata
//             ^^^^^^^ support.function.command.stata
python: print("semicolon Python"); collect clear;
//      ^^^^^ support.function.builtin.python
//                                 ^^^^^^^ support.function.command.stata

mata;
// <- support.function.command.stata
real scalar function semicolon_square(real scalar x) {
// <- storage.type.mata
//                   ^^^^^^^^^^^^^^^^ entity.name.function.mata
    return(x^2)
//  ^^^^^^ keyword.control.mata
}
end;
// <- support.function.command.stata

python;
# <- support.function.command.stata
semicolon_result = sum([1, 2, 3])
# <- source.python
end;
// <- support.function.command.stata
#delimit cr
// <- keyword.control.directive.stata
summarize outcome
// <- support.function.command.stata
regress outcome treatment
// <- support.function.command.stata

mata:
// <- support.function.command.stata
real scalar function square(real scalar x) {
// <- storage.type.mata
//                   ^^^^^^ entity.name.function.mata
    return(x^2)
//  ^^^^^^ keyword.control.mata
}
end
// <- support.function.command.stata

mata: sqrt(4)
//    ^^^^ support.function.mata
python: print("inline Python")
//      ^^^^^ support.function.builtin.python

python:
# <- support.function.command.stata
result = sum([1, 2, 3])
# <- source.python
end
// <- support.function.command.stata

/***
\section{Methods}
% <- text.tex.latex
***/
