"""The AAS type of a product with its plan, written with the lab's shared AAS model (``aas_model``,
pydantic) like the module type (``model``). It holds what the process planner reads and writes:

- **Nameplate** (IDTA 02006): what the product is.
- **Hierarchical Structures** (IDTA 02011): its bill of material; a part states its quantity.
- **Process Parameters** (IDTA 02031-1 with the lab's extension): the processes the product needs,
  each with the product's values, the materials it uses and the capability it requires.
- **Capability Description** (IDTA 02020, role Required): those capabilities with their values.
- **Production Sequence** (the planner's, 2.0): the plan, each step assigned to a skill of a
  resource, with what is bound to the skill's parameters.

The classes of the last two templates are generated (``modreg.generated``, see ``templates``); the
others are aas-model's. Declared here is only what a product adds to them.
"""
from __future__ import annotations

import base64
from typing import ClassVar, Dict, Optional

from aas_model.constants import BASE_URL
from aas_model.resource_template import nameplate
from aas_pydantic import AAS, Property
from aas_pydantic.submodel_templates import capability_description as cd
from aas_pydantic.submodel_templates.hierarchical_structures import ArcheType, EntryNode, HierarchicalStructures, Node
from aas_pydantic.submodel_templates.nameplate import Nameplate
from pydantic import model_validator

from .generated.process_parameters import Processes, ProcessParameters
from .generated.production_sequence import ProductionSequence

PLANS = f"{BASE_URL}/sm/process-plan"


def plan_id(aas_id: str) -> str:
    """The identifier of a product's own Production Sequence: the planner finds the plan by it."""
    return f"{PLANS}/{base64.urlsafe_b64encode(aas_id.encode()).decode().rstrip('=')}"


class Part(Node):
    """A part of the product. IDTA 02011 counts parts (BulkCount); a product also holds amounts
    (2 mL of liquid), so a part states its quantity and the unit of it, as the planner writes them.
    A part that is made by a plan of its own is a self-managed entity naming its asset."""
    description: str = ""
    entity_type: str = "CoManagedEntity"
    global_asset_id: str = ""
    Quantity: Optional[Property] = None
    QuantityUnit: Optional[Property] = None
    Node: Dict[str, Part] = {}


class Product(EntryNode):
    description: str = ""
    Node: Dict[str, Part] = {}


class BillOfMaterial(HierarchicalStructures):
    EntryNode: Product


def bill_of_material() -> BillOfMaterial:
    return BillOfMaterial(id_short="HierarchicalStructures", EntryNode=Product(), ArcheType=ArcheType(value="OneDown"))


class ProductTypeAAS(AAS):
    """AAS of a product: what it is, what it consists of, the processes it needs and the plan that
    makes it."""
    model_config = {"extra": "forbid"}
    # A product AAS describes a kind of product, not one item of it.
    ASSET_KIND: ClassVar[str] = "Type"

    asset_type: str = "Product"
    nameplate: Nameplate = nameplate()
    hierarchical_structures: BillOfMaterial = bill_of_material()
    process_parameters: ProcessParameters = ProcessParameters(id_short="ProcessParameters", Processes=Processes())
    capability_description: Optional[cd.CapabilityDescription] = None
    production_sequence: Optional[ProductionSequence] = None

    @model_validator(mode="after")
    def the_plan_has_the_planners_identifier(self):
        plan = self.production_sequence
        if plan is not None and plan.id == plan.id_short:           # no identifier given
            plan.id = plan_id(self.id)
        return self


Part.model_rebuild()
Product.model_rebuild()
BillOfMaterial.model_rebuild()
ProductTypeAAS.model_rebuild()
