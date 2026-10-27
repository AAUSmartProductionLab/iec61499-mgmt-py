"""Planning new module level skills from a module's Capability Description (docs/skill-planning.md).

- ``expression``: the language of a constraint (an IDTA 02020 BasicConstraint, ARSO 0.11);
- ``domain``: a module's planning domain: its state variables, its capabilities with what they
  need, do and keep, its rest state;
- ``vocabulary``: what holds of each kind of capability wherever it is used (the lab's vocabulary);
- ``check``: runs a skill's flow through the states and reports what does not hold;
- ``plan``: composes the steps of a new skill, a hybrid of HTN and goal regression on GTPyhop;
- ``lift``: a plan as a flow, with parallel blocks where nothing orders two steps.
"""
