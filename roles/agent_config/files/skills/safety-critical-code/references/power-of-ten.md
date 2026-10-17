# Power of Ten, expanded guidance

These are JPL's 2006 rules for safety-critical C, with practical interpretation. Apply a project's stricter requirements when they differ.

## 1. Keep control flow simple

Avoid `goto`, `setjmp`, `longjmp`, direct recursion, and indirect recursion. Prefer structured branches, loops, and an acyclic call graph.

Why: reviewers and analyzers can follow every path, calculate stack depth, and reason about termination. In other languages, scrutinize exceptions, callbacks, async chains, dynamic dispatch, and generated control flow for the same reason.

## 2. Give loops a fixed, provable upper bound

Every terminating loop needs an upper bound that static analysis can establish. When traversing external or linked data, impose an explicit maximum and handle overflow as an error.

An intentionally nonterminating scheduler or event loop is a documented exception. Its individual work cycles still need bounds, deadlines, or watchdog supervision.

Why: bounded loops prevent hangs and support worst-case execution-time analysis.

## 3. Do not allocate dynamic memory after initialization

Allocate required memory before normal operation, then use fixed-capacity storage, pools, arenas, or statically sized collections. Account for libraries and runtime features that allocate invisibly.

Why: this avoids allocation failure, fragmentation, unpredictable latency, leaks, and difficult resource accounting. If the platform requires runtime allocation, document maximum counts, ownership, failure behavior, and measured timing. Treat that as an adaptation, not strict compliance.

## 4. Keep functions small

The original rule uses roughly 60 lines, about one printed page, as a reviewability limit. Count logical statements and declarations rather than allowing formatting to game the number.

Why: a function should be understandable as one unit. Splitting it only helps when the resulting functions have clear contracts and do not scatter one state transition across many files.

## 5. Use assertions throughout the code

The original guidance calls for at least two assertions per function on average, with typical guidance of two for functions longer than 20 lines. Assertions should be side-effect-free and check invariants, impossible states, bounds, and assumptions.

Why: assertions turn design assumptions into executable checks and help analyzers. Specify what happens when an assertion fails in deployed software. Do not use assertions as the only validation for untrusted input, and do not compile away checks required for safe operation.

## 6. Minimize scope

Declare data at the narrowest possible scope. Keep file-private objects private and avoid mutable global state. Minimize the lifetime and authority of each value.

Why: fewer paths can alter state, which reduces unintended coupling and makes data flow easier to inspect.

## 7. Check parameters and return values

Validate function inputs against their contract. Check every non-void return value. If an API return value is intentionally irrelevant, make that decision explicit in the form accepted by the project's standard and explain it when the reason is not obvious.

Why: ignored errors and invalid inputs otherwise travel until they cause a failure far from their source. Define propagation, retry, fallback, fail-safe, and shutdown behavior rather than merely logging the error.

## 8. Restrict the preprocessor

For C and C++, restrict preprocessing to header inclusion and simple object-like or function-like macros. Avoid conditional compilation that produces many program variants, token pasting, recursive macros, and macros that hide control flow or evaluation.

Why: preprocessors evade normal type and scope rules and make the analyzed code differ from the source a reviewer sees. Prefer typed constants, inline functions, generated artifacts with verification, and explicit build configurations.

## 9. Restrict pointer use

The original rule permits no more than one level of pointer dereferencing and forbids function pointers. Some later summaries describe the expression limit as two levels, so use the exact governing JPL standard when formal compliance matters. Avoid casts that bypass the type system.

Why: aliasing and indirect calls weaken static analysis and obscure ownership. In modern languages, apply the intent by limiting unsafe code, raw pointers, shared mutable references, reflection, and unconstrained dynamic dispatch. Use types and ownership rules that make lifetimes and targets explicit.

## 10. Compile and analyze under strict settings

Enable the compiler's strongest relevant warnings and treat agreed warnings as errors. Run one or more static analyzers appropriate to the language and target. Record tool versions, configurations, suppressions, and results so the analysis is reproducible.

Why: the rules are designed for mechanical checking. A warning suppression is an engineering decision and needs a narrow scope and written reason.

## Compliance record

For each rule, record one of:

- compliant, with supporting evidence;
- adapted, with the mechanism that preserves the safety intent;
- exception, with rationale, risk, mitigation, and approver;
- not assessed, with the information or analysis still needed.

Also record applicable hazards, critical requirements, tests, analysis reports, and traceability. Rule compliance without this system context is only a coding-quality result, not a safety case.
