/**
 * The skill editor and the skill planner of the web UI (basyx-aas-web-ui), driven in a browser for one
 * reconfiguration task, counting every input a person makes on the way (E1, cell/eval/effort.py).
 *
 *   node cell/eval/ui/effort-ui.cjs <task> <route> <out.json> [shots folder]
 *
 * with NODE_PATH set to the web UI's node_modules (for @playwright/test), the module's AAS on the AAS
 * server EFFORT_REPO, the skill service (modreg serve) at EFFORT_SERVICE, the web UI's dev server at
 * EFFORT_UI. effort.py starts it once per task and route on a freshly posted module.
 *
 * Counted, from the module's Skills submodel shown in the viewer (Visualization) to the skill saved:
 * - pointer: a click on a button, link, card, menu item or option (a list's option is a second click
 *   after the one that opens the list);
 * - typed: a value or name typed into a field (the click into it belongs to it), and its characters
 *   and the key that ends it (Tab, or Enter in a list that takes typed entries) as keystrokes;
 * - keys: a key pressed by itself (Escape to close a list).
 * The path is the shortest the UI offers, as a person who knows it would take; waits are not inputs.
 */
const { chromium } = require('@playwright/test')

const [task, route, out, shots] = process.argv.slice(2)
const repo = process.env.EFFORT_REPO ?? 'http://localhost:18081'
const service = process.env.EFFORT_SERVICE ?? 'http://127.0.0.1:18090'
const ui = process.env.EFFORT_UI ?? 'http://127.0.0.1:4173'
const moduleId = process.env.EFFORT_MODULE ?? 'https://smartproductionlab.aau.dk/aas/FillingModuleAAS'
const b64 = text => Buffer.from(text).toString('base64url')

const tally = { pointer: 0, typed: 0, keys: 0, keystrokes: 0, log: [] }
let page

async function click (locator, what) {
  await locator.click()
  tally.pointer += 1
  tally.log.push(`click ${what}`)
}

/** A list opened and one of its options chosen: two clicks. */
async function choose (field, option, what) {
  await click(field, what)
  await click(page.getByRole('option', { name: option, exact: true }), option)
}

/** A value typed into a field, replacing what is there, and ended with Tab. */
async function type (field, text, what, end = 'Tab') {
  await field.click()
  await field.fill(text)
  await field.press(end)
  tally.typed += 1
  tally.keystrokes += text.length + 1
  tally.log.push(`type ${what}: ${text}`)
}

async function key (name, what) {
  await page.keyboard.press(name)
  tally.keys += 1
  tally.keystrokes += 1
  tally.log.push(`key ${name} ${what}`)
}

const editor = () => page.locator('.v-card', { has: page.getByText('Module level skill', { exact: true }) }).last()
const card = name => editor().getByRole('button', { name, exact: true })
const inspector = () => editor().locator('.skill-panes__side')
const select = label => inspector().locator('.v-select', { has: page.locator('label', { hasText: new RegExp(`^${label}$`) }) }).first()
const field = label => inspector().locator('.v-text-field:not(.v-select)', { has: page.locator('label', { hasText: new RegExp(`^${label}$`) }) }).locator('input:not([type=hidden])').first()
/** The value field next to the source list of a step's input (labelled with the input's unit). */
const valueOf = input => inspector().locator('div.d-flex.ga-2.mb-2', { has: page.locator('label', { hasText: new RegExp(`^${input}$`) }) })
  .locator('.v-text-field:not(.v-select) input:not([type=hidden])').first()

async function saved () {
  await page.getByText(/The module offers:|Saved, but the capabilities/).first().waitFor({ timeout: 60_000 })
}

async function openSkill (name) {
  await click(page.getByRole('link', { name, exact: true }), `open ${name}`)
  await editor().getByText(name, { exact: true }).first().waitFor({ timeout: 30_000 })
  await card('Home').first().waitFor({ timeout: 30_000 })
}

/** A new skill like the one open, named ``name``; ends on the new skill. */
async function newFrom (name) {
  await click(editor().getByRole('button', { name: 'New skill from this' }), 'New skill from this')
  await type(page.getByRole('dialog').getByLabel('Name', { exact: true }), name, 'its name')
  await click(page.getByRole('dialog').getByRole('button', { name: 'Create' }), 'Create')
  await page.getByText('Described, not built', { exact: true }).first().waitFor({ timeout: 60_000 })
  await editor().locator('.v-card-title', { hasText: name }).first().waitFor({ timeout: 30_000 })
  await card('Home').first().waitFor({ timeout: 30_000 })
}

async function save () {
  await click(editor().getByRole('button', { name: 'Save' }), 'Save')
  await saved()
}

const tasks = {
  // T1: Dispensing's dose at 2.0 mL/s instead of 1.0.
  async 'value/editor' () {
    await openSkill('Dispensing')
    await click(card('Dispense'), 'the Dispense step')
    await type(valueOf('FlowRate'), '2.0', 'FlowRate')
    await save()
  },
  // T2: DoubleDose, Dispensing with a second dose of the same volume, 0.5 mL by default.
  async 'double/editor' () {
    await openSkill('Dispensing')
    await newFrom('DoubleDose')
    await click(card('Dispense'), 'the Dispense step')
    await click(editor().getByRole('button', { name: 'Add step' }), 'Add step')
    await choose(select('Runs the skill'), 'Dispense (FillingPump)', 'Runs the skill')
    await click(card('Dispense_2'), 'the new step again (choosing its skill renamed it)')
    await choose(select('Volume'), "The skill's Volume", 'Volume from')
    await click(card('Start'), 'Start (the skill itself)')
    await type(field('default'), '0.5', 'Volume default')
    await save()
  },
  // T3: BottomUpFilling for the syringe: needle deep, then dosing while the needle rises, home, weigh.
  async 'bottomup/editor' () {
    await openSkill('Dispensing')
    await newFrom('BottomUpFilling')
    await click(card('NeedleDown'), 'the NeedleDown step')
    await type(valueOf('Position'), '58', 'Position')
    await click(editor().getByRole('button', { name: 'Add a block' }), 'Add a block')
    await click(page.locator('.v-overlay .v-list-item').filter({ hasText: 'Parallel block' }), 'Parallel block')
    await click(card('Branch 1'), 'Branch 1')
    await click(editor().getByRole('button', { name: 'Add step' }), 'Add step')
    await choose(select('Runs the skill'), 'Dispense (FillingPump)', 'Runs the skill')
    await click(card('Dispense_2'), 'the new step again (choosing its skill renamed it)')
    await choose(select('Volume'), "The skill's Volume", 'Volume from')
    await type(valueOf('FlowRate'), '0.7', 'FlowRate')
    await click(card('Branch 2'), 'Branch 2')
    await click(editor().getByRole('button', { name: 'Add step' }), 'Add step')
    await choose(select('Runs the skill'), 'MoveAxis (FillingLinearAxis)', 'Runs the skill')
    await click(card('MoveAxis'), 'the new step again (choosing its skill renamed it)')
    await type(valueOf('Position'), '40', 'Position')
    await click(card('Dispense'), 'the old Dispense step')
    await click(editor().getByRole('button', { name: 'Remove selected' }), 'Remove selected')
    await save()
  },
  // T4: a skill that fills 15 mL and weighs, written: the planner's two doses of 7.5 mL.
  async 'fifteen/editor' () {
    await openSkill('Dispensing')
    await newFrom('Filling15')
    await click(card('Dispense'), 'the Dispense step')
    await choose(select('Volume'), 'A constant', 'Volume from')
    await type(valueOf('Volume'), '7.5', 'Volume')
    await click(editor().getByRole('button', { name: 'Add step' }), 'Add step')
    await choose(select('Runs the skill'), 'Dispense (FillingPump)', 'Runs the skill')
    await click(card('Dispense_2'), 'the new step again (choosing its skill renamed it)')
    await type(valueOf('Volume'), '7.5', 'Volume')
    await save()
  },
  // T4, planned: the capability, its value and the result asked for.
  async 'fifteen/planner' () {
    await click(page.getByRole('button', { name: 'Plan a skill' }), 'Plan a skill')
    const dialog = page.getByRole('dialog')
    await choose(dialog.locator('.v-select', { has: page.locator('label', { hasText: /^Capability$/ }) }), 'Filling', 'Capability')
    await type(dialog.getByLabel('FillVolume', { exact: true }), '15', 'FillVolume')
    await type(dialog.locator('.v-combobox input').first(), 'FillWeight', 'Results', 'Enter')
    await click(dialog.getByRole('button', { name: 'Plan and describe' }), 'Plan and describe')
    await page.getByText(/Described|offers/).first().waitFor({ timeout: 60_000 })
  },
}

;(async () => {
  const run = tasks[`${task}/${route}`]
  if (!run) throw new Error(`no task ${task}/${route}`)
  const browser = await chromium.launch({ channel: process.env.EFFORT_BROWSER ?? 'chrome' })
  try {
    page = await browser.newPage({ viewport: { width: 1720, height: 1080 } })
    await page.addInitScript(([repository, skillService]) => {
      localStorage.setItem('theme', 'light')
      localStorage.setItem('process-sequence.skill-editor', 'classic')
      localStorage.setItem('process-sequence.skill-service', skillService)
      localStorage.setItem('basyxInfrastructures', JSON.stringify({
        selectedInfrastructureId: 'effort',
        infrastructures: [{
          id: 'effort', name: 'Effort', template: 'mono-repo', isDefault: true, auth: { securityType: 'No Authentication' },
          components: Object.fromEntries(['AASDiscovery', 'AASRegistry', 'SubmodelRegistry', 'AASRepo', 'SubmodelRepo', 'ConceptDescriptionRepo', 'CompanyLookup']
            .map(name => [name, { url: ['AASRepo', 'SubmodelRepo', 'ConceptDescriptionRepo'].includes(name) ? repository : '' }])),
        }],
      }))
    }, [repo, service])
    const skills = `${moduleId}/submodels/Skills`
    await page.goto(`${ui}/aasviewer?aas=${encodeURIComponent(`${repo}/shells/${b64(moduleId)}`)}&path=${encodeURIComponent(`${repo}/submodels/${b64(skills)}`)}`)
    // The start: the module's Skills submodel shown (not counted).
    await page.getByText('Visualization', { exact: true }).click()
    await page.getByText(/^Skills of /).first().waitFor({ timeout: 60_000 })
    await page.getByRole('link', { name: 'Dispensing', exact: true }).waitFor({ timeout: 60_000 })
    await run()
    if (shots) await page.screenshot({ path: `${shots}/${task}-${route}.png`, fullPage: true })
  } catch (error) {
    if (shots && page) await page.screenshot({ path: `${shots}/${task}-${route}-failed.png`, fullPage: true }).catch(() => {})
    throw error
  } finally {
    await browser.close()
  }
  require('node:fs').writeFileSync(out, JSON.stringify({ task, route, ...tally }, null, 1))
})().catch(error => {
  console.error(error)
  process.exit(1)
})
