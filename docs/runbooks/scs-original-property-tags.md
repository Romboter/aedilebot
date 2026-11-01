# Original serialized Unreal SCS key PropertyTags

This is the narrow read-only extension to the existing CUE4Parse
`inspect-types` research, not a game-data generator.

Use `inspect-scs-tags` with the same validated, bounded manifest of
`War/Content/Blueprints/... ` paths used by `dump-list`. It prints tagged
field *types*, not values or reconstructed CDO defaults.

Expected record types:
- `SCSKEYTYPE`: original nested `InheritableComponentHandler.Records[i].ComponentKey` tags for `OwnerClass`, `SCSVariableName`, and `AssociatedGuid`.
- `SCSNODETYPE`: original `SCS_Node` tags for `InternalVariableName` and `VariableGuid`.
- `UNRESOLVED`: nested struct is unavailable/malformed; never treat this as an inferred type.

The pinned Foxhole 26058282 scout-tank sample showed child
`SCSVariableName=NameProperty`, `AssociatedGuid=StructProperty`,
`OwnerClass=ObjectProperty`; its owner's `InternalVariableName=NameProperty`
and `VariableGuid=StructProperty`. Thus the two source-only `exhaustR`
/`ExhaustR` and `exhaustL`/`ExhaustL` differences occur in original
`NameProperty` fields, not merely strings flattened from JSON.

Do not treat an equivalent `FName` identifier as proof that the child's
effective component defaults at runtime match its parent. Keep the
full PAK and manifests private, pin the exporter and source build, and
keep bot data writes, scheduled updates and production activation disabled.

Follow-up: use a source-hash- and build-bound typed-evidence manifest to
permit *source identity* case-folding only with unique GUID and NameProperty
proof, without introducing global fuzzy matching.
