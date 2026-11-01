# Serialized component-template field differences

**Research-only.** This runbook describes *saved source declarations*, not effective
UE4.24 Blueprint CDO inheritance, runtime actors, selected ammunition or damage.

`scripts/audit_scs_template_field_deltas.py` uses the exact, hash-pinned
component export identities validated by the preceding SCS graph research.
For every parent/child template pair, it rechecks the exported component
`Name` and `Type`, generated class identity and `Outer` ownership.
A changed source SHA or mismatched source owner aborts the audit.

It compares the two saved `Properties` JSON maps using deterministic
canonical values, without exporting field values to summary logs. The four
source categories are:

- `explicit_child_only`: this child template serialized a field absent
  from the parent template export
- `explicit_parent_only`: parent serialized a field absent from child
- `explicit_shared_changed`: both serialized a field but values differ
- `explicit_shared_equal`: both serialized exactly the same JSON value

The tool separately records changed component types instead of attempting a
cross-type comparison. Field-name and occurrence counts aid prioritization;
source hashes and build IDs permit future review.

**Important:** Parent-only does not mean inherited, removed, deleted, or
effective on the child; a child-only field does not prove the runtime component
uses that value. The original UE tagged types and construction semantics may
require independent CUE4Parse inspection and UE4.24 runtime fixture proof.
A binary blob or editor compile could also affect effective defaults without
altering an individual saved JSON field.

Run the private `automation/scs-key-inspection` workflow on the pinned PAK.
Only aggregate counts and the top field names are reported. Full source
exports and complete delta records stay inside restricted runner scratch.
Keep PRs in draft; no Steam update, automatic merge, production bot changes,
or gameplay damage publication.
