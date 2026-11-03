"""modpy: a module of the line run in Python instead of IEC 61499, for modules whose skills are a
device's own programs (a KUKA robot's jobs): from its module spec, with the module rules' occupation,
PackML module state and skill state machines, served over OPC UA node for node as a generated
module on FORTE serves them. So the agents, the DMP, modlink and the HMI drive it as they drive any
module, and modreg describes it from the same spec.

    python -m modpy serve cell/modules/python/loading.yaml [more specs] [--port 4840]
"""
