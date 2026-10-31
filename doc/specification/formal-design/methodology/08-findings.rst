8. Findings
===========

- **Finding**: a divergence between the code and a requirement, between two requirements, or
  between the code and a design rule that the code states for itself (for example
  ``RunRuleHolds``). A robustness defect without a requirement is also a finding (for example O1,
  O2 of the scheduler app). All findings are in one **register** (workspace notes). A divergence
  between a test and the code is not a finding. It has its own records (section 10).

- **Candidate finding**: a counterexample of a property or of a refinement. **Triage** examines
  it. The result is one of two:

  - an error of the specification: a wrong reading, a behavior part that does not follow the
    code, or a missing assumption or assumption of use. The specification is corrected.
  - a finding: it goes into the register.

- **Class** of a finding: the result of triage. One of:

  - **defect**: the code is wrong.
  - **intended but undocumented**: the code does what its authors want, but no requirement says
    so.
  - **accepted deviation**: the code is wrong, and the project accepts it.
  - **unspecified**: no property can be written, because the documents are silent.

  A finding without a class is **open**. "Class" has no other meaning in the method.

- **Triage** procedure (D6): for each open finding, the coordinator prepares a proposal (class,
  evidence, reason). The user decides in short triage sessions. The register entry records the
  decision, the date and the reason. Until then, this document calls a counterexample a candidate
  finding and states no verdict on a requirement.

- **Fields of the register** (D7): found by (model, unit test, CBMC, board app, code reading),
  owner and date, upstream status (none, issue, pull request, requirement change), and source
  kind (requirement, design rule, traceability claim, or robustness defect without a
  requirement).

- **Design observation**: a remark on the design that is not a divergence yet (for example O1 and
  O2 of the scheduler app). It becomes a finding when a property or a requirement shows it.
