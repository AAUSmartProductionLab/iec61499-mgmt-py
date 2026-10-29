"""The new slides: which page's layers, which beats, which captions and notes."""

P03 = "03-the-filling-module-physical-and-digital"
P05 = "05-the-filling-module-in-motion-an-orchestrator"
P06 = "06-the-filling-module-in-motion-agents-bid-planned"
P07 = "07-product-process-and-resource-aas"
P08 = "08-equipment-and-skill-hierarchies-in-the-aas"
P09 = "09-primitive-and-composite-skills-in-the-aas"
P10 = "10-from-the-aas-to-function-blocks-modsync"
P11 = "11-the-mapping-rules"
MOD = "1 · MODELLING"
AGENTS = "3 · NEXT: AGENT-BASED ORCHESTRATION"

MOTION = ["module", "shuttle-and-vial", "carriage", "home-switch-pressed", "step-pulses", "travel-40-mm",
          "pump-running", "liquid", "weight-2-0-g", "state-machines", "packml-stopped", "packml-resetting",
          "packml-idle", "packml-starting", "packml-execute", "occupied", "skill-idle", "skill-running",
          "skill-succeeded", "step-needledown", "step-dispense", "step-home", "step-weigh"]


def build(m):
    Slide, after, write = m.Slide, m.add_slide_after, m.write_slide

    # ---- after slide 3: one module pulled out of the line -------------------------------------------------
    s = Slide("Inside one module: its parts, their AASs, its program", None,
              ["Its AAS", "Its program", "Three views"],
              "The filling module, physically: a station, a linear axis, a pump, a scale and a Pi",
              [("Its AAS.", "A shell per asset: the module's says what it offers and how it is called; each part's holds its skills"),
               ("Its program.", "The boot file builds the module's application on FORTE; each part brings its equipment block and primitives"),
               ("One part, three views.", "The linear axis is a physical part, an AAS and function blocks, joined by name and asset id")])
    L = s.figure(P03, ["physical", "aas", "iec-61499-program", "same-part-links"])
    s.click(1, [("wipe", L["aas"], {"dir": "left"})])
    s.click(2, [("wipe", L["iec-61499-program"], {"dir": "left"})])
    s.click(3, [("in", L["same-part-links"])])
    write(after("slide6.xml", "slide3.xml"), s, """About 1 min, three clicks. One module pulled out of the line: the filling module.

At the start, what it is physically: a station of the line with a linear axis (a stepper motor, a ball screw stage and a home switch), a pump (not wired yet: dispensing is a time), a scale (simulated) and the Raspberry Pi 5 that is its controller.

1. Its AAS: a shell for the module, with Nameplate, Hierarchical Structures (its parts), Capability Description, Skills, the interface description and its mapping, and Variables; and a shell for each part, holding that part's skills.
2. Its program: the boot file builds the application on FORTE: occupation, the PackML state machine, the Dispensing skill, the procedures, the OPC UA server; each part brings its equipment block and its primitive types, compiled into FORTE.
3. The dashed lines: one part, three views. The linear axis is a physical part, an AAS and function blocks; names and asset ids join them. This is what a vendor ships: the module, its AAS and its program.""")

    # ---- after slide 7: the filling module at work ----------------------------------------------------------
    def motion_slide(title, label, agents):
        labels = (["Call", "Bid", "Accept", "Move", "Arrived", "Occupy", "Reset", "Start", "Start skill", "Fill",
                   "Done", "Release"] if agents else
                  ["Arrive", "Refused", "Occupy", "Reset", "Start", "Start skill", "NeedleDown", "Dispense", "Home",
                   "Weigh", "Succeeded", "Release"])
        if agents:
            caps = [("Call.", "The product agent calls for proposals: Filling, 2.0 mL"),
                    ("Bid.", "The filling module's resource agent can do it with Dispensing, now"),
                    ("Accept.", "The product agent accepts the bid"),
                    ("Move.", "It asks the transport agent to bring the vial to Filling; the shuttle moves"),
                    ("Arrived.", "The vial is under the needle"),
                    ("Occupy.", "The resource agent occupies the module over OPC UA: Occupy(s1) → True, 0"),
                    ("Reset.", "Resetting homes the axis to its switch; then Idle"),
                    ("Start.", "The module goes to Execute"),
                    ("Start skill.", "Dispensing starts with 2.0 mL"),
                    ("Fill.", "Needle down 40 mm, the pump runs, the needle home, the scale weighs"),
                    ("Done.", "Succeeded: the resource agent tells the product agent, 2.0 mL, 2.0 g"),
                    ("Release.", "The module is released and the vial moves on")]
        else:
            caps = [("Arrive.", "A shuttle brings the vial under the needle"),
                    ("Refused.", "Start before occupying: False, 5, not permitted"),
                    ("Occupy.", "The orchestrator occupies the module: session s1"),
                    ("Reset.", "Resetting homes the axis to its limit switch; then Idle"),
                    ("Start.", "Starting, then Execute: the module may run skills"),
                    ("Start skill.", "Dispensing starts with Volume 2.0 mL: True, 0 at once"),
                    ("NeedleDown.", "MoveAxis drives the needle 40 mm down, into the vial"),
                    ("Dispense.", "The pump runs: 2.0 mL into the vial"),
                    ("Home.", "The needle goes back up until the switch closes"),
                    ("Weigh.", "The scale reads the weight, the skill's result"),
                    ("Succeeded.", "Dispensing has succeeded and goes back to Idle by itself"),
                    ("Release.", "The orchestrator releases the module; the vial moves on")]
        s = Slide(title, label, labels, "Click through one skill call: the commands, the states and the module moving", caps)
        pre = (["agents"] + [f"message-0{i}" for i in range(1, 8)] + [f"command-0{i}" for i in range(1, 6)]) if agents \
            else [f"command-0{i}" for i in range(1, 7)]
        L = s.figure(P06 if agents else P05, MOTION + pre)
        down = 260 * s.emu_per_page_px / m.SH
        sh, car, liq = L["shuttle-and-vial"], L["carriage"], L["liquid"]
        on = lambda k, **a: ("in", L[k], a)
        off = lambda k, **a: ("out", L[k], a)
        reset = [[on("packml-resetting"), off("packml-stopped"), on("step-pulses")],
                 [on("home-switch-pressed"), off("step-pulses")],
                 [off("packml-resetting"), on("packml-idle")]]
        start = [[off("packml-idle"), on("packml-starting")], [off("packml-starting"), on("packml-execute")]]
        needle = [on("step-needledown"), off("home-switch-pressed"), on("step-pulses"), on("travel-40-mm"),
                  ("path", car, {"y1": down, "dur": 1500})]
        dispense = [off("step-needledown"), off("step-pulses"), on("step-dispense"), on("pump-running"),
                    ("wipe", liq, {"dir": "bottom", "dur": 1500})]
        home = [off("step-dispense"), off("pump-running"), on("step-home"), off("travel-40-mm"), on("step-pulses"),
                ("path", car, {"y0": down, "y1": 0, "dur": 1500})]
        weigh = [off("step-home"), on("home-switch-pressed"), off("step-pulses"), on("step-weigh"), on("weight-2-0-g")]
        leave = [("path", sh, {"x1": 0.75, "dur": 1200}), ("path", liq, {"x1": 0.75, "dur": 1200})]
        gone = [("out", sh, {"dur": 1}), ("out", liq, {"dur": 1}), off("weight-2-0-g")]
        if not agents:
            c = lambda i: L[f"command-0{i}"]
            s.click(1, [("flyin", sh, {})])
            s.click(2, [("in", c(1))])
            s.click(3, [("out", c(1)), ("in", c(2)), on("occupied")])
            s.click(4, [("out", c(2)), ("in", c(3))] + reset[0], *reset[1:])
            s.click(5, [("out", c(3)), ("in", c(4))] + start[0], *start[1:])
            s.click(6, [("out", c(4)), ("in", c(5)), off("skill-idle"), on("skill-running")])
            s.click(7, [("out", c(5))] + needle, [off("step-pulses")])
            s.click(8, dispense, [off("pump-running")])
            s.click(9, [x for x in home if x[1] != L["pump-running"]], [on("home-switch-pressed"), off("step-pulses")])
            s.click(10, [off("step-home"), on("step-weigh"), on("weight-2-0-g")])
            s.click(11, [off("step-weigh"), off("skill-running"), on("skill-succeeded")],
                    [off("skill-succeeded"), on("skill-idle")])
            s.click(12, [("in", c(6)), off("occupied")] + leave, gone + [("out", c(6))])
        else:
            g = lambda i: L[f"message-0{i}"]
            c = lambda i: L[f"command-0{i}"]
            s.click(1, [("in", g(1))])
            s.click(2, [("out", g(1)), ("in", g(2))])
            s.click(3, [("out", g(2)), ("in", g(3))])
            s.click(4, [("out", g(3)), ("in", g(4)), ("flyin", sh, {})])
            s.click(5, [("out", g(4)), ("in", g(5))])
            s.click(6, [("out", g(5)), ("in", c(1)), on("occupied")])
            s.click(7, [("out", c(1)), ("in", c(2))] + reset[0], *reset[1:])
            s.click(8, [("out", c(2)), ("in", c(3))] + start[0], *start[1:])
            s.click(9, [("out", c(3)), ("in", c(4)), off("skill-idle"), on("skill-running")])
            s.click(10, [("out", c(4))] + needle, dispense, [off("pump-running")] + home[:1] + home[2:], weigh)
            s.click(11, [off("step-weigh"), off("skill-running"), on("skill-succeeded"), ("in", g(6))],
                    [off("skill-succeeded"), on("skill-idle")])
            s.click(12, [("out", g(6)), ("in", c(5)), off("occupied"), ("in", g(7))] + leave,
                    gone + [("out", c(5)), ("out", g(7))])
        return s

    s = motion_slide("The filling module at work: commands, states, motion", MOD, False)
    write(after("slide6.xml", "slide7.xml"), s, """About 1.5 min, twelve clicks. The same skill call as the slide before, now with the module itself: the needle carriage on its linear axis, the vial on its shuttle, the pump and the scale, beside the module's PackML state machine and the Dispensing skill.

1. A shuttle brings the vial under the needle.
2. The orchestrator (the HMI, modlink, later an agent) starts Dispensing without occupying the module: refused, False, 5.
3. Occupy with session s1.
4. Reset: Resetting homes the axis to its limit switch (the step pulses, then AtHome), then Idle.
5. Start: Starting, then Execute.
6. Dispensing's Start with 2.0 mL: accepted at once, the skill runs.
7. NeedleDown: MoveAxis drives the needle 40 mm down into the vial.
8. Dispense: the pump runs and the vial fills.
9. Home: the needle goes up until the switch closes.
10. Weigh: the scale reads the weight, the skill's result.
11. Succeeded, and back to Idle by itself.
12. Release; the vial moves on.

An illustration of the order of things, not a recording: the pump is not wired yet (dispensing is a time) and the scale is simulated.""")

    # ---- slide 8: three kinds of AAS, now as shells --------------------------------------------------------
    s = Slide("Three kinds of AAS: product, process, resource", MOD,
              ["Recipe", "Bindings", "Matching", "Realized by"],
              "Each AAS is a shell; its submodels are below it",
              [("Recipe.", "The product's Production Sequence gives the steps that the process AAS binds"),
               ("Bindings.", "Each step is bound to a module's skill, in the process AAS"),
               ("Matching.", "A required capability matches an offered one: the same meaning, the value in range"),
               ("Realized by.", "A module offers a capability because one of its skills realizes it")])
    L = s.figure(P07, ["product-aas", "process-aas", "resource-aas", "link-recipe", "link-each-step",
                       "link-required", "link-offered"])
    s.click(1, [("wipe", L["link-recipe"], {"dir": "left"})])
    s.click(2, [("wipe", L["link-each-step"], {"dir": "left"})])
    s.click(3, [("wipe", L["link-required"], {"dir": "left"})])
    s.click(4, [("wipe", L["link-offered"], {"dir": "bottom"})])
    write("slide8.xml", s, """About 1 min, four clicks. Three kinds of AAS, as in ISA-88: the product AAS is the general recipe (what the product needs), the process AAS the master recipe (the recipe bound to one line), the resource AAS the equipment (what a line, a module or a component offers and how it is called).

1. The product's Production Sequence gives the steps.
2. The process AAS binds each step to a module's skill.
3. Matching: a required capability (Filling 2.0 mL) matches an offered one by meaning, with the value in its range.
4. A module offers a capability because one of its skills realizes it: the capabilities are derived from the skills.""")

    # ---- after slide 9: the hierarchies, primitive and composite, the mapping ------------------------------
    s = Slide("The AASs nest: line, module, component", MOD)
    s.figure(P08, ["aas-trees"])
    s20 = after("slide6.xml", "slide9.xml")
    write(s20, s, """About 45 s. The AASs as trees, as the AAS server shows them. The line's Hierarchical Structures name its modules by asset id; the filling module's name its components: the linear axis, the pump, the scale. Each component's AAS holds its skills: Home and MoveAxis, Dispense, Tare and Weigh, all primitives.

The module's own skill, Dispensing, is a composite: its Steps run the components' skills (the green lines). And its Capability Description says which skill realizes the capability it offers.""")

    s = Slide("Primitive and composite skills", MOD,
              ["Primitives", "NeedleDown", "Dispense", "Home", "Weigh"],
              "A composite skill of the module: Dispensing, its Start, its result, its steps",
              [("Primitives.", "Each part's AAS describes its own skills: one command on one component, a block type in FORTE"),
               ("NeedleDown.", "The first step runs the linear axis's MoveAxis, with Position = 40.0"),
               ("Dispense.", "The pump's Dispense, with the Volume handed down from Dispensing's Start"),
               ("Home.", "The linear axis's Home: back up to the switch"),
               ("Weigh.", "The scale's Weigh; its Weight becomes Dispensing's result")])
    L = s.figure(P09, ["module-aas", "component-aass", "runs-1", "runs-2", "runs-3", "runs-4"])
    s.click(1, [("in", L["component-aass"])])
    for k in range(2, 6):
        s.click(k, [("wipe", L[f"runs-{k - 1}"], {"dir": "left"})])
    s21 = after("slide6.xml", s20)
    write(s21, s, """About 1 min, five clicks. Two kinds of skill.

A composite skill, here the module's Dispensing, is a sequence of steps over the components' skills, with its Start variable (Volume, 0.5 to 10 mL) and its result (Weight). It has no type of its own: FORTE creates it online from instances.

1. Primitives: each component's AAS describes its own skills, one command on one component until a sensor, a timer or a timeout. Each is a block type compiled into FORTE.
2 to 5. Each step runs one primitive, with its bindings: NeedleDown runs MoveAxis with Position 40.0; Dispense runs the pump's Dispense with the Volume from the Start; Home runs Home; Weigh runs Weigh, and its Weight is the result.""")

    s = Slide("From the AAS to function blocks, while the module runs", MOD,
              ["The skill", "Start", "NeedleDown", "Dispense", "Home", "Weigh", "The rules", "The result"],
              "modsync reads the skill in the AAS and creates its function blocks on FORTE",
              [("The skill.", "Dispensing becomes a subapplication: its Control block and the frame of Execute"),
               ("Start.", "The Start Operation becomes UaStart, the OPC UA method, and the latch for Volume with its limits"),
               ("NeedleDown.", "Step 1 becomes an instance of SK_MoveAxis, with 40.0 at Position"),
               ("Dispense.", "Step 2 becomes SK_Dispense; its Volume is connected from the latch"),
               ("Home.", "Step 3 becomes SK_Home, started by the step before"),
               ("Weigh.", "Step 4 becomes SK_Weigh: the order of the steps is the chain SUCCESS → START"),
               ("The rules.", "Everything faint is drawn by the module rules: INIT, stop and abort, failures merged"),
               ("The result.", "Weigh's Weight is published: the skill's result on OPC UA")])
    pre = ["aas-fillingmoduleaas", "legend", "forte-the-subapplication", "created-1", "created-2", "created-3-1",
           "created-3-2", "created-3-3", "created-3-4", "created-4", "created-5"] + [f"arrow-{i}" for i in range(1, 7)] \
        + ["modsync"]
    L = s.figure(P10, pre)
    targets = ["created-1", "created-2", "created-3-1", "created-3-2", "created-3-3", "created-3-4"]
    for k in range(1, 7):
        first = [("wipe", L[f"arrow-{k}"], {"dir": "left", "dur": 500})]
        if k > 1:
            first.insert(0, ("out", L[f"arrow-{k - 1}"]))
        s.click(k, first, [("in", L[targets[k - 1]])])
    s.click(7, [("out", L["arrow-6"]), ("in", L["created-4"])])
    s.click(8, [("in", L["created-5"])])
    s22 = after("slide6.xml", s21)
    write(s22, s, """About 1.5 min, eight clicks. How a skill described in the AAS becomes function blocks on the running module. Left the filling module's AAS; in the middle modsync, which reads it, compares it with the running program, compiles the skill by the module rules, creates it online with the management protocol (CREATE, CONNECT, WRITE), reads it back and records it as Built; right, the subapplication as FORTE has it.

1. The skill Dispensing becomes a subapplication: its Control block and the Execute subapplication.
2. Its Start Operation becomes UaStart, the OPC UA method, and a latch for Volume with the limits 0.5 and 10.0 as values.
3 to 6. Each step becomes an instance of its primitive's type: SK_MoveAxis with 40.0, SK_Dispense with the Volume from the latch, SK_Home, SK_Weigh. The thick green chain, SUCCESS to START, is the order of the steps.
7. Everything faint is drawn by the rules, not described in the AAS: the INIT chain, HALT, ABORT and RESET to every step, the failures and error codes merged pairwise.
8. Weigh's Weight is published as the skill's result.

The point: the AAS gives the steps, their order and their bindings; the rules give the rest. The same generator builds a vendor's module, so what is created online equals what would have been generated.""")

    s = Slide("The mapping rules: from the AAS to the program, and back", MOD)
    s.figure(P11, ["rules", "rule-1", "rule-2", "rule-3", "rule-4", "rule-5", "rule-6", "rule-7", "rule-8",
                   "keys-and-limits"])
    s23 = after("slide6.xml", s22)
    write(s23, s, """About 1 min. The rules in one table: each element of a skill in the AAS has one fixed form in the IEC 61499 program.

A composite skill is a subapplication of instances, no new type, so it is created online; a primitive is a block type compiled into FORTE. A Start variable with limits is a parameter latch. A step is an instance named by its NodeId; a binding to a value is that input's value, a binding to a source a data connection. The order is the event chain SUCCESS to START. Parallel and decision steps use three library blocks: Join, Condition, Merge.

Names are the keys: the program can be read back into the AAS's terms. What can change online: a value, a new composite skill. What needs a restart: a new primitive or new IO (a FORTE build), removing or reordering what runs.""")

    # ---- after slide 15: agents at the filling module ------------------------------------------------------
    s = motion_slide("At the module: agents bid, then the skill runs", AGENTS, True)
    write(after("slide6.xml", "slide15.xml"), s, """About 1.5 min, twelve clicks. The same filling module, with agents instead of an orchestrator. Planned: the paper's future work, so everything agent-related is dashed.

1 to 3. The product agent of the vial calls for proposals for Filling 2.0 mL; the filling module's resource agent bids with Dispensing, now; the product agent accepts.
4 and 5. The product agent asks the transport agent of a shuttle to bring the vial to Filling.
6 to 9. The resource agent does what the orchestrator did: Occupy, Reset (the axis homes), Start, and Dispensing's Start with 2.0 mL.
10. The skill runs: needle down, the pump fills, needle home, weigh.
11. Succeeded: the resource agent reports to the product agent.
12. The module is released and the vial moves on to the next step.""")
