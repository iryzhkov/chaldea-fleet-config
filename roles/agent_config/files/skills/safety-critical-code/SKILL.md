---
name: safety-critical-code
description: Apply JPL's Power of Ten principles when designing, implementing, or reviewing software whose failure could threaten people, a mission, equipment, or an unrecoverable operation. Use when the user identifies code as safety-critical, mission-critical, flight software, high-integrity, or asks for NASA/JPL coding practices. Do not silently impose it on ordinary application code.
---

# Safety-critical code

Treat JPL's Power of Ten as a compact engineering baseline, not as proof of safety or a substitute for the project's governing standards, hazard analysis, verification plan, or certification process. The original rules primarily target C. Adapt their intent explicitly when the implementation language provides different safety mechanisms.

Before changing code, identify from the repository and request:

- the code and failure modes that are actually critical;
- the governing language, platform, coding standard, and resource limits;
- whether the user wants strict Power of Ten compliance or its principles adapted to the project.

Do not infer permission to redesign unrelated code. If a rule conflicts with an authoritative project requirement, report the conflict and follow the authoritative requirement.

Read [references/power-of-ten.md](references/power-of-ten.md) before applying or auditing these rules.

## Working method

For design and implementation:

1. Make time, memory, stack use, and control flow bounded where the system requires bounded behavior.
2. Prefer mechanisms that static analysis, tests, and reviewers can verify mechanically.
3. Encode assumptions as checked preconditions, invariants, types, or assertions. Define safe behavior for violations.
4. Keep critical state and authority narrow. Avoid hidden allocation, implicit blocking, uncontrolled concurrency, and ambiguous ownership.
5. Add tests for bounds, invalid inputs, error paths, timeouts, and resource exhaustion. Use the project's required analyzers and compiler settings.

For a review, report findings by severity and include the location, violated rule or safety intent, plausible failure, and concrete remediation. Separate confirmed violations, adaptations that preserve the rule's intent, exceptions that need written justification, and unknowns that require system or hazard information.

Finish with a concise compliance table for rules 1 through 10. Never claim that compliance alone makes software safe, flight-ready, or certified.

## Sources

- Gerard J. Holzmann, *The Power of Ten: Rules for Developing Safety-Critical Code*: https://spinroot.com/gerard/pdf/Power_of_Ten.pdf
- NASA Software Engineering Requirements, NPR 7150.2D: https://nodis3.gsfc.nasa.gov/displayDir.cfm?Internal_ID=N_PR_7150_002D_&page_name=Preface
- NASA Software Assurance and Software Safety Standard, NASA-STD-8739.8B: https://standards.nasa.gov/standard/nasa/nasa-std-87398
