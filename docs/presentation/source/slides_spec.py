"""The new slides: which page's layers, which beats, which captions and notes; and what changes on the user's
own slides (pictures, no timelines, slides merged)."""

P03 = "03-the-filling-module-physical-and-digital"
P03C = "03c-the-production-system-in-layers"
P05 = "05-the-filling-module-in-motion-an-orchestrator"
P06 = "06-the-filling-module-in-motion-agents-bid-planned"
P07 = "07-product-process-and-resource-aas"
P08 = "08-equipment-and-skill-hierarchies-in-the-aas"
P09 = "09-primitive-and-composite-skills-in-the-aas"
P10 = "10-from-the-aas-to-function-blocks-modsync"
P11 = "11-the-mapping-rules"
P12 = "12-matching-a-missing-effect-replanning"
P12B = "12b-inside-the-agent-of-a-module"
P12C = "12c-inside-the-agent-of-a-product"
P13 = "13b-agents-on-the-line-every-agent-is-asked"
MOD = "1 · MODELLING"
RECONF = "2 · RECONFIGURATION"
AGENTS = "3 · NEXT: AGENT-BASED ORCHESTRATION"

MOTION = ["module", "shuttle-and-vial", "carriage", "home-switch-pressed", "step-pulses", "travel-40-mm",
          "pump-running", "liquid", "weight-2-0-g", "state-machines", "packml-stopped", "packml-resetting",
          "packml-idle", "packml-starting", "packml-execute", "occupied", "skill-idle", "skill-running",
          "skill-succeeded", "step-needledown", "step-dispense", "step-home", "step-weigh"]


def build(m):
    Slide, after, write = m.Slide, m.add_slide_after, m.write_slide
    run, para = m.run, m.para

    # ---- the user's slides: new pictures, no timelines (only the filling module walks keep one) ------------
    m.replace_picture("image1.png", m.REPO / "docs/presentation/figures/pictures/line.png")
    m.replace_picture("image7.png", m.REPO / "docs/presentation/figures/pictures/tools.png")
    for sf in ["slide3.xml", "slide5.xml", "slide7.xml", "slide10.xml", "slide11.xml", "slide12.xml"]:
        m.strip_timeline(sf)

    # ---- after slide 3: one module pulled out of the line -------------------------------------------------
    s = Slide("Inside one module: its parts, their AASs, its program")
    L = s.figure(P03, ["physical", "aas", "iec-61499-program", "same-part-links"])
    s.plain_click([("wipe", L["aas"], {"dir": "left"})])
    s.plain_click([("wipe", L["iec-61499-program"], {"dir": "left"})])
    s.plain_click([("in", L["same-part-links"])])
    write(after("slide6.xml", "slide3.xml"), s, """About 1 min, three clicks. One module pulled out of the line: the filling module.

At the start, what it is physically: a station of the line with a linear axis (a stepper motor, a ball screw stage and a home switch), a pump (not wired yet: dispensing is a time), a scale (simulated) and the Raspberry Pi 5 that is its controller.

1. Its AAS: a shell for the module, with Nameplate, Hierarchical Structures (its parts), Capability Description, Skills, the interface description and its mapping, and Variables; and a shell for each part, holding that part's skills.
2. Its program: the boot file builds the application on FORTE: occupation, the PackML state machine, the Dispensing skill, the procedures, the OPC UA server; each part brings its equipment block and its primitive types, compiled into FORTE.
3. The dashed lines: one part, three views. The linear axis is a physical part, an AAS and function blocks; names and asset ids join them. This is what a vendor ships: the module, its AAS and its program.""")

    # ---- after slide 5: the layers, illustrated, one plane at a time ----------------------------------------
    s = Slide("The production system, layer by layer", MOD)
    planes = ["the-line", "digital-assets", "behaviour-iec-61499", "aas-models-and-orchestration",
              "hmi-mes-planning-and-scheduling"]
    L = s.figure(P03C, planes, area=(647700, 1206500, 5000000, 5393500))
    TEXT = [(2790, "The line", "The maglev table and its shuttles, four stations, two robots"),
            (2283, "Digital assets", "Each module's parts with their kind and asset id, wired to its Pi"),
            (1771, "Behaviour · IEC 61499", "FORTE on each Pi runs the module's program"),
            (1259, "AAS models and orchestration", "The AASs on the AAS server; modreg, modsync and modlink work on them"),
            (747, "HMI, planning, MES", "The planner, the skill editor and the HMI work from the AASs; MES and ERP later")]
    tx = []
    for py, name, sub in TEXT:
        y = s.at(0, py)[1]
        tx.append(s.textbox(6000000, y - 380000, 5540000, 760000,
                            [para([run(name, 18, True, m.TEAL_D)]), para([run(sub, 13, False, m.INK_T)])]))
    for k in range(1, 5):         # each plane with the lines that reach up to it
        s.plain_click([("wipe", L[planes[k]], {"dir": "bottom", "dur": 700}), ("in", tx[k])])
    write(after("slide6.xml", "slide5.xml"), s, """About 1 min, four clicks. The same five layers as the slide before, drawn as the lab is built, from the line up; each line appears with the layer it reaches up to.

At the start the line: the maglev table with its shuttles, the four stations, the two robots.
1. Digital assets: each module's parts, the linear axis, the process component and the Raspberry Pi 5, with kind and asset id; the robots and the transport with their own controllers.
2. Behaviour: FORTE on each Pi runs the module's IEC 61499 program: the skills as function block networks, the PackML state machine of the module.
3. AAS models and orchestration: product, process and resource AASs on the AAS server; modreg and modsync work on them, agents later.
4. On top the applications: the planner, the skill editor and the HMI, all reading and writing the AASs; MES and ERP later.""")

    # ---- after slide 7: the filling module at work ----------------------------------------------------------
    def motion_slide(title, label, agents):
        if agents:
            labels = ["Arrive", "Occupy", "Reset", "Start", "Start skill", "Fill", "Done", "Release"]
            caps = [("Arrive.", "Its shuttle brings the vial under the needle, as the agents agreed"),
                    ("Occupy.", "The module's agent occupies it over OPC UA: Occupy(s1) → True, 0"),
                    ("Reset.", "Resetting homes the axis to its switch; then Idle"),
                    ("Start.", "The module goes to Execute"),
                    ("Start skill.", "Dispensing starts with 2.0 mL"),
                    ("Fill.", "Needle down 40 mm, the pump runs, the needle home, the scale weighs"),
                    ("Done.", "Succeeded: the module's agent tells the product agent, 2.0 mL, 2.0 g"),
                    ("Release.", "The module is released and the vial moves on to Stoppering")]
        else:
            labels = ["Arrive", "Refused", "Occupy", "Reset", "Start", "Start skill", "NeedleDown", "Dispense", "Home",
                      "Weigh", "Succeeded", "Release"]
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
        pre = (["agents", "message-06", "message-07"] + [f"command-0{i}" for i in range(1, 6)]) if agents \
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
        c = lambda i: L[f"command-0{i}"]
        if not agents:
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
            s.click(1, [("flyin", sh, {})])
            s.click(2, [("in", c(1)), on("occupied")])
            s.click(3, [("out", c(1)), ("in", c(2))] + reset[0], *reset[1:])
            s.click(4, [("out", c(2)), ("in", c(3))] + start[0], *start[1:])
            s.click(5, [("out", c(3)), ("in", c(4)), off("skill-idle"), on("skill-running")])
            s.click(6, [("out", c(4))] + needle, dispense, [off("pump-running")] + home[:1] + home[2:], weigh)
            s.click(7, [off("step-weigh"), off("skill-running"), on("skill-succeeded"), ("in", g(6))],
                    [off("skill-succeeded"), on("skill-idle")])
            s.click(8, [("out", g(6)), ("in", c(5)), off("occupied"), ("in", g(7))] + leave,
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
    s = Slide("Three kinds of AAS: product, process, resource", MOD)
    L = s.figure(P07, ["product-aas", "process-aas", "resource-aas", "link-recipe", "link-each-step",
                       "link-required", "link-offered"])
    s.plain_click([("wipe", L["link-recipe"], {"dir": "left"})])
    s.plain_click([("wipe", L["link-each-step"], {"dir": "left"})])
    s.plain_click([("wipe", L["link-required"], {"dir": "left"})])
    s.plain_click([("wipe", L["link-offered"], {"dir": "bottom"})])
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

    s = Slide("Primitive and composite skills", MOD)
    L = s.figure(P09, ["module-aas", "component-aass", "runs-1", "runs-2", "runs-3", "runs-4"])
    s.plain_click([("in", L["component-aass"])])
    for k in range(2, 6):
        s.plain_click([("wipe", L[f"runs-{k - 1}"], {"dir": "left"})])
    s21 = after("slide6.xml", s20)
    write(s21, s, """About 1 min, five clicks. Two kinds of skill.

A composite skill, here the module's Dispensing, is a sequence of steps over the components' skills, with its Start variable (Volume, 0.5 to 10 mL) and its result (Weight). It has no type of its own: FORTE creates it online from instances.

1. Primitives: each component's AAS describes its own skills, one command on one component until a sensor, a timer or a timeout. Each is a block type compiled into FORTE.
2 to 5. Each step runs one primitive, with its bindings: NeedleDown runs MoveAxis with Position 40.0; Dispense runs the pump's Dispense with the Volume from the Start; Home runs Home; Weigh runs Weigh, and its Weight is the result.""")

    s = Slide("From the AAS to function blocks, while the module runs", MOD,
              ["The skill", "Start", "NeedleDown", "Dispense", "Home", "Weigh", "The rules", "The result", "Verify"],
              "modsync reads the skill in the AAS and sends FORTE the commands that build it",
              [("The skill.", "modsync reads Skills from the AAS; Dispensing gets its Control block"),
               ("Start.", "The Start Operation: UaStart, the OPC UA method, and the latch for Volume, its limits written"),
               ("NeedleDown.", "Step 1: an instance of SK_MoveAxis, 40.0 written to Position, its START connected"),
               ("Dispense.", "Step 2: SK_Dispense; its Volume connected from the latch"),
               ("Home.", "Step 3: SK_Home, started by Dispense's SUCCESS"),
               ("Weigh.", "Step 4: SK_Weigh: the chain SUCCESS → START is the order of the steps"),
               ("The rules.", "Everything faint comes from the module rules: INIT, stop and abort, failures merged"),
               ("The result.", "Weigh's Weight is published as the skill's result; the skill is started"),
               ("Verify.", "Read back: blocks, connections, type hashes and values match the AAS; recorded as Built")])
    cmd = [f"commands-{k}-" for k in range(1, 10)]
    pre = ["aas-fillingmoduleaas", "legend", "forte-the-subapplication", "created-1", "created-2", "created-3-1",
           "created-3-2", "created-3-3", "created-3-4", "created-4", "created-5"] + [f"arrow-{i}" for i in range(1, 7)] \
        + ["modsync", "console"] + cmd
    L = s.figure(P10, pre)
    targets = ["created-1", "created-2", "created-3-1", "created-3-2", "created-3-3", "created-3-4"]
    for k in range(1, 7):
        first = [("wipe", L[f"arrow-{k}"], {"dir": "left", "dur": 500}), ("in", L[cmd[k - 1]])]
        if k > 1:
            first[:0] = [("out", L[f"arrow-{k - 1}"]), ("out", L[cmd[k - 2]])]
        s.click(k, first, [("in", L[targets[k - 1]])])
    s.click(7, [("out", L["arrow-6"]), ("out", L[cmd[5]]), ("in", L[cmd[6]]), ("in", L["created-4"])])
    s.click(8, [("out", L[cmd[6]]), ("in", L[cmd[7]]), ("in", L["created-5"])])
    s.click(9, [("out", L[cmd[7]]), ("in", L[cmd[8]])])
    s22 = after("slide6.xml", s21)
    write(s22, s, """About 2 min, nine clicks. How a skill described in the AAS becomes function blocks on the running module. Left the filling module's AAS; in the middle modsync; right of it the subapplication as FORTE has it; far right what modsync sends: the operations of its management API, create_fb, connect, write, and to check, query and read.

1. modsync reads the Skills submodel. The skill Dispensing becomes a subapplication: its Control block and the Execute subapplication.
2. Its Start Operation becomes UaStart, the OPC UA method, and a latch for Volume; the limits 0.5 and 10.0 are written as values.
3 to 6. Each step becomes an instance of its primitive's type: SK_MoveAxis with 40.0 written, SK_Dispense with the Volume connected from the latch, SK_Home, SK_Weigh. The thick green chain, SUCCESS to START, is the order of the steps.
7. Everything faint is drawn by the rules, not described in the AAS: the INIT chain, HALT, ABORT and RESET to every step, the failures and error codes merged pairwise.
8. Weigh's Weight is published as the skill's result, and the skill is started.
9. Verify: modsync reads the program back (the blocks, the connections, the type hashes, the values) and compares it with the AAS. All match: the skill is recorded as Built.

The point: the AAS gives the steps, their order and their bindings; the rules give the rest. The same generator builds a vendor's module, so what is created online equals what would have been generated.""")

    s = Slide("The mapping rules: from the AAS to the program, and back", MOD)
    s.figure(P11, ["rules", "rule-1", "rule-2", "rule-3", "rule-4", "rule-5", "rule-6", "rule-7", "rule-8",
                   "keys-and-limits"])
    s23 = after("slide6.xml", s22)
    write(s23, s, """About 1 min. The rules in one table: each element of a skill in the AAS has one fixed form in the IEC 61499 program.

A composite skill is a subapplication of instances, no new type, so it is created online; a primitive is a block type compiled into FORTE. A Start variable with limits is a parameter latch. A step is an instance named by its NodeId; a binding to a value is that input's value, a binding to a source a data connection. The order is the event chain SUCCESS to START. Parallel and decision steps use three library blocks: Join, Condition, Merge.

Names are the keys: the program can be read back into the AAS's terms. What can change online: a value, a new composite skill. What needs a restart: a new primitive or new IO (a FORTE build), removing or reordering what runs.""")

    # ---- slides 13 and 14 become one: matching, a missing effect, replanning, checking ----------------------
    s = Slide("Capability matching and replanning", RECONF)
    L = s.figure(P12, ["recipe-and-capabilities", "match", "missing", "replan", "check"])
    s.plain_click([("wipe", L["match"], {"dir": "left"})])
    s.plain_click([("in", L["missing"])])
    s.plain_click([("wipe", L["replan"], {"dir": "bottom", "dur": 700})])
    s.plain_click([("wipe", L["check"], {"dir": "left"})])
    s_match = after("slide6.xml", "slide12.xml")
    write(s_match, s, """About 1 min, four clicks. The line changes over to a new product, a prefilled syringe of 1 mL: three steps, matched against what the modules offer.

1. Match: each required capability against the offered ones, by meaning and range. Stopper and Inspect are offered as they are.
2. Fill 1.0 mL from the bottom is not: Filling is offered, but Dispensing doses with the needle standing still at the fill position. A syringe barrel is tall and narrow, so the needle has to start deep and rise as the liquid rises, or the liquid splashes and foams. No parameter of Dispensing gives that.
3. Replan: a new composite skill from the filling module's own primitives, BottomUpFilling: NeedleDeep, then Dispense and NeedleRise at the same time, then Home and Weigh. The pump and the axis run in parallel: one parallel block, one join block in the program, no new block type. Its capability is derived like any other, offered after a reconfiguration.
4. Check against the recipe again: the module's constraint is that the needle stays in the container while dosing, at the fill position or deeper; it rises from 58 to 40 mm, so that holds, and every step is offered. Once modsync has built BottomUpFilling online, the order can run.

Today the planner does this with the skill editor; later the module's agent (part 3).""")

    # ---- inside the agents: the active part, the AAS as the passive part, what each talks to ----------------
    s = Slide("Inside the agent of a module", AGENTS)
    L = s.figure(P12B, ["the-passive-part-and-the-module", "the-agent", "bidding", "reconfiguration", "execution"])
    s.plain_click([("in", L["the-agent"])])
    for k in ("bidding", "reconfiguration", "execution"):
        s.plain_click([("wipe", L[k], {"dir": "left", "dur": 600})])
    s_inside = after("slide6.xml", s_match)
    write(s_inside, s, """About 1.5 min, four clicks. Planned. After the I4.0 language demonstrator: an agent is the active part of an AAS, the AAS on the server its passive part.

At the start what exists: the filling module's AAS on the AAS server (Capability Description, Skills, the interface description and its mapping, Variables), the module itself (FORTE on its Pi: the IEC 61499 program, the OPC UA server, the management interface) and the DMP, which turns an Operation of the AAS into an OPC UA call.
1. The agent: a SPADE agent. Its messenger is XMPP, speaking the I4.0 language (VDI/VDE 2193), and an interaction manager whose state machine plays the service provider's role: call for proposals in, proposal out, accept in, inform out.
2. Bidding: it checks the required capability against what its AAS offers (meaning and range), its availability (occupation, bookings) and the time, and proposes: now, after a reconfiguration, or refuse.
3. Reconfiguration, on accept and only if needed: the planner composes a skill from the primitives and writes it into the AAS; modsync creates it online over the management protocol, verifies and records it.
4. Execution: modlink occupies the module and starts the skill over OPC UA, directly; or over HTTP, as an Operation of the AAS that the DMP turns into the OPC UA call.""")

    s = Slide("Inside the agent of a product", AGENTS)
    L = s.figure(P12C, ["the-passive-part-and-the-vial", "the-agent", "requesting", "recording"])
    s.plain_click([("in", L["the-agent"])])
    for k in ("requesting", "recording"):
        s.plain_click([("wipe", L[k], {"dir": "left", "dur": 600})])
    s_inside2 = after("slide6.xml", s_inside)
    write(s_inside2, s, """About 1 min, three clicks. Planned. One product agent per order, the same build as a module's agent with the other role.

At the start its passive part: the product AAS (Production Sequence, Required Capabilities, Process Parameters) and the process AAS it fills in (Step Bindings, Process Information); and the vial, which has no interface of its own.
1. The agent: messenger and interaction manager, here as the service requester.
2. Requesting: the next step from the Production Sequence, a call for proposals with the required capability and its values, the best proposal chosen (the earliest), the others rejected.
3. Recording and moving: the step bound to the module's skill in the process AAS, what was done to the vial recorded, and the agent of the shuttle that carries the vial asked to take it to the next module's station.""")

    # ---- slides 15 and 16 become one: agents on the line ------------------------------------------------------
    s = Slide("Agents on the line: every agent is asked", AGENTS)
    steps = [(1, "call-for-proposals-filling"), (2, "proposal-filling"), (3, "call-for-proposals-receiving"),
             (4, "proposal-receiving"), (5, "accept-receiving"), (6, "call-for-proposals-transport"),
             (7, "proposal-transport"), (8, "accept-transport")]
    msgs = [f"{k}-{n}-{w}" for k, n in steps for w in ("card", "arrows")] + ["9-arrived-card", "10-accept-filling-card",
                                                                               "10-accept-filling-arrows"]
    L = s.figure(P13, ["the-line", "product-the-vial", "messages-header", "agents", "product-agent-on-the-vial"] + msgs)
    dx = 77.2 * s.emu_per_page_px / m.SW         # loading to the filling station, on the page
    dy = 44.6 * s.emu_per_page_px / m.SH
    for k, n in steps:
        first = [("in", L[f"{k}-{n}-card"]), ("wipe", L[f"{k}-{n}-arrows"], {"dir": "left", "dur": 500})]
        if k > 1:
            first.insert(0, ("out", L[f"{k - 1}-{steps[k - 2][1]}-arrows"]))
        s.plain_click(first)
    s.plain_click([("out", L["8-accept-transport-arrows"]), ("in", L["9-arrived-card"]),
                   ("path", L["product-the-vial"], {"x1": dx, "y1": dy, "dur": 1500}),
                   ("path", L["product-agent-on-the-vial"], {"x1": dx, "y1": dy, "dur": 1500})])
    s.plain_click([("in", L["10-accept-filling-card"]), ("wipe", L["10-accept-filling-arrows"], {"dir": "left", "dur": 500})])
    s_agents = after("slide6.xml", s_inside2)
    write(s_agents, s, """About 2 min, ten clicks. Built (30 Oct), tested with the modules and the shuttles simulated; on the line for the demo in January. Every vial ordered gets a product agent (P) that travels with it; every resource has a resource agent (R): each module, and each shuttle of the table. They talk in the I4.0 language (VDI/VDE 2193): call for proposals, proposal or refuse, accept or reject. The product agent does not know who can do what: every call goes to every resource agent with the vial's state, and the constraints of the capabilities in each resource's AAS decide who proposes. Who carries the vial is one of those states: custody.

1. The vial's product agent calls for proposals for Fill 2.0 mL, to every resource agent: the four modules and the five shuttles.
2. Only Filling can: it proposes Dispensing, now, and where a shuttle hands it the vial (its station, from the AASs). The proposal is binding: Filling holds itself for this vial. The others refuse.
3. To be carried, the vial needs a resource that has it in its custody, and nobody has it yet: a call for Receiving, again to everyone.
4. Receiving needs room: Occupancy less than Capacity, one vial for a shuttle. The five empty shuttles propose; the modules offer no Receiving and refuse.
5. Shuttle 3, with the vial on it, is accepted, the others rejected. Shuttle 3 holds the vial from now on, and has no room for another.
6. Now the transport: a call for Transporting to Filling's station, to everyone.
7. Transporting needs Holding: only shuttle 3 holds the vial, so only it proposes. The other shuttles refuse, and so do the modules. Nothing in the agents is about shuttles: the same rule binds a vial to a gripper or a tray.
8. Shuttle 3 is accepted and goes.
9. It reports the vial at Filling's station.
10. Only now the product agent accepts Filling's proposal: the vial is there, and the module's agent runs Dispensing: the next slide. At the end of the order the vial asks for Releasing, and shuttle 3 is free again.""")



    # ---- after it: at the filling module -------------------------------------------------------------------
    s = motion_slide("At the filling module: its agent runs the skill", AGENTS, True)
    write(after("slide6.xml", s_agents), s, """About 1.5 min, eight clicks. The same filling module as before, now run by its agent, not by an orchestrator. Planned: everything agent-related is dashed.

1. Its shuttle brings the vial, as agreed on the slide before.
2 to 5. The module's agent does what the orchestrator did: Occupy, Reset (the axis homes), Start, and Dispensing's Start with 2.0 mL.
6. The skill runs: needle down, the pump fills, needle home, weigh.
7. Succeeded: the module's agent reports to the product agent.
8. The module is released and the vial moves on to Stoppering, the next booked step.""")

    m.remove_slides("slide13.xml", "slide14.xml", "slide15.xml", "slide16.xml")
