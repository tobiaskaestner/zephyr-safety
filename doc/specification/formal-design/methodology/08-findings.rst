8. Findings
===========

- **Finding**: a divergence between the code and a requirement, or between two requirements. All
  findings are in one **register** (workspace notes). A divergence between a test and the code is
  not a finding. It has its own records (section 10).

- **Candidate finding**: a counterexample of a property or of a refinement. **Triage** examines
  it. The result is one of two:

  - an error of the specification: a wrong reading, a behavior part that does not follow the
    code, or a missing assumption or condition of use. The specification is corrected.
  - a finding: it goes into the register.

- **Class** of a finding: the result of triage. One of:

  - **defect**: the code is wrong.
  - **intended but undocumented**: the code does what its authors want, but no requirement says
    so.
  - **accepted deviation**: the code is wrong, and the project accepts it.
  - **unspecified**: no property can be written, because the documents are silent.

  A finding without a class is **open**. "Class" has no other meaning in the method.

- **Design observation**: a remark on the design that is not a divergence yet (for example O1 and
  O2 of the scheduler app). It becomes a finding when a property or a requirement shows it.
