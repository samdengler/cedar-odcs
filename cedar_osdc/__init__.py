"""The mechanism, with no use case named in it.

A use case is a directory holding policies, facts, a contract, corpora,
fixtures, and a descriptor (usecase.py) that tells the engine the
entity type, the verbs, which payload fields become entity attributes,
and the tool table. The engine supplies everything else: the corpus
runner, the claims projection, the two legs of enforcement, and the
contract build; the command line and the Gateway handlers are its two
interfaces. The test of the split is that cedar_osdc runs every use
case and names none.
"""
