// SYNTAX TEST "Packages/Stata/Mata.sublime-syntax"

real scalar function logistic(real scalar value)
// <- storage.type.mata
//                   ^^^^^^^^ entity.name.function.mata
{
    if (value > 0) return(1 / (1 + exp(-value)))
//  ^^ keyword.control.mata
//                 ^^^^^^ keyword.control.mata
//                               ^^^ support.function.mata
}

class ResearchResult
// <- storage.type.declaration.mata
//    ^^^^^^^^^^^^^^ entity.name.type.mata

struct rowvector result
// <- storage.type.declaration.mata
//     ^^^^^^^^^ entity.name.type.mata

pointer scalar p
// <- storage.type.mata
p = &logistic()
//   ^^^^^^^^ support.function.mata

// Mata section
// <- comment.line.double-slash.mata
/* nested /* block */ comment */
// <- comment.block.mata
