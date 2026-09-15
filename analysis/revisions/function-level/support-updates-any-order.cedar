// Declared revision: the one change iteration 5 makes to an earlier
// decision. Added to iteration 4's policy set, the result must decide
// every iteration 4 action exactly as iteration 5 does; without it,
// the two differ on UpdateOrder, and the runner shows that too. The
// text is P10 of function-level/policies.cedar.
@id("support-updates-any-order")
permit(
  principal in Role::"support",
  action == Action::"UpdateOrder",
  resource
);
