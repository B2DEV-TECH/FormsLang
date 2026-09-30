"""Review actions that resolve a modernization finding.

The resolved-review set shared by the generation policy, the projection, the
visualization and the journey status. Other copies of the same two-action set
remain elsewhere in the codebase; this module is not the one definition for
every consumer.
"""

RESOLVED_REVIEWS = frozenset({"APPROVE", "MODIFY"})
