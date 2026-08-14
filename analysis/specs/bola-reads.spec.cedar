// Behavioral spec for iteration 1, as one policy: a read is allowed
// exactly when the principal owns the order or is support. Proving the
// real policy set equivalent to this spec proves both directions:
// everyone intended gets in, nobody else does.
@id("spec-read-owner-or-support")
permit(
  principal,
  action == Action::"ReadOrder",
  resource
) when {
  (resource has owner && resource.owner == principal) ||
  principal in Role::"support"
};
