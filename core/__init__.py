"""The mechanism, with no use case named in it.

A use case is a directory holding policies, facts, a contract, corpora,
fixtures, and a descriptor (usecase.py) that tells core the entity
type, the verbs, which payload fields become entity attributes, and
the tool table. Core supplies everything else: the corpus runner, the
claims projection, the two legs of enforcement, the Gateway handlers,
and the contract build. The test of the split is that core runs every
use case and names none.
"""
