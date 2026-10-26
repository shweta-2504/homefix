"""
HomeFix - database layer (SQLite).
Tables
  appliances      -> Module 1 (Appliance Selection)
  problems        -> Module 2 (Problem / Symptom Detection)
  rules           -> Module 3 + 4 (Troubleshooting Engine, Solution & Safety Guide)
  repair_history  -> Module 5 (Repair History & Technician Suggestion)
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("homefix.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS appliances (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE,
    icon  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS problems (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    appliance_id  INTEGER NOT NULL REFERENCES appliances(id),
    symptom       TEXT NOT NULL,
    keywords      TEXT NOT NULL DEFAULT '',
    risky         INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id  INTEGER NOT NULL REFERENCES problems(id),
    cause       TEXT NOT NULL,
    steps       TEXT NOT NULL,          -- one step per line
    safety      TEXT NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 1   -- 1 = most likely cause
);
CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    email          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash  TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS repair_history (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER REFERENCES users(id) ON DELETE CASCADE,
    appliance_id          INTEGER NOT NULL REFERENCES appliances(id),
    problem_id            INTEGER NOT NULL REFERENCES problems(id),
    cause_tried           TEXT,
    resolved              INTEGER NOT NULL,
    technician_suggested  INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

# ---------------------------------------------------------------------------
# Knowledge base: appliance -> icon, list of problems
# problem = (symptom, keywords, risky, [ (cause, [steps], safety), ... ])
# Causes are listed from most to least likely.
# ---------------------------------------------------------------------------
KB = {
    "Air Conditioner": ("❄️", [
        ("AC is not cooling", "not cooling warm air no cold hot room", 0, [
            ("Dirty air filter blocking airflow",
             ["Switch off the AC and unplug it or turn off its MCB.",
              "Open the front panel and slide out the filters.",
              "Wash the filters with lukewarm water and mild soap, then dry completely in shade.",
              "Refit the filters and run the AC for 15 minutes to check cooling."],
             "Always switch off the power before opening the panel. Never refit a wet filter."),
            ("Incorrect settings (mode, temperature, fan)",
             ["Set the mode to 'Cool' (not Fan, Dry or Auto).",
              "Set temperature at least 3-4°C below room temperature (e.g. 24°C).",
              "Close doors and windows of the room.",
              "Check that the remote batteries are working."],
             "No special risk, but do not set below the minimum temperature for long periods."),
            ("Dirty outdoor unit / blocked condenser",
             ["Switch off the AC from the MCB.",
              "Check that nothing blocks the outdoor unit (boxes, leaves, wall).",
              "Gently clear dust with a soft brush from a safe position on the ground.",
              "Do not spray water while the unit is powered."],
             "Do not climb to reach the outdoor unit. Use a licensed technician for high-rise locations."),
            ("Low refrigerant gas (leak)",
             ["Look for ice on the pipes or an oily residue at the pipe joints.",
              "Do NOT try to refill gas yourself.",
              "Book a technician for leak check and gas refill."],
             "Refrigerant handling requires a trained technician. Do not attempt any repair."),
        ]),
        ("AC is leaking water", "water leak dripping drip indoor unit", 0, [
            ("Clogged drain pipe",
             ["Switch off the AC.",
              "Check the drain pipe for kinks or bends and straighten it.",
              "Gently blow or flush the drain pipe to clear dust or algae.",
              "Restart and check if dripping has stopped."],
             "Keep the electrical parts dry. Switch off the AC before touching the drain tray."),
            ("Dirty filter causing ice and melting",
             ["Switch off the AC and wait 30 minutes for the ice to melt.",
              "Clean the filters.",
              "Restart the AC in Fan mode for 10 minutes, then switch to Cool."],
             "Place a tray under the unit to avoid slipping on a wet floor."),
            ("Indoor unit not levelled properly",
             ["Check whether the indoor unit tilts away from the drain side.",
              "Do not adjust the wall mounting yourself.",
              "Ask a technician to re-level the unit."],
             "Do not stand on unstable furniture to inspect the unit."),
        ]),
        ("AC makes strange noise", "noise sound loud rattling vibration buzzing", 0, [
            ("Loose panel or dirty fan blades",
             ["Switch off the AC.",
              "Check that the front panel and screws are tight.",
              "Remove visible dust from the grille with a soft cloth.",
              "Restart and listen again."],
             "Never put your hand inside while the fan can start. Switch off the MCB first."),
            ("Outdoor unit vibration or loose mounting",
             ["Look for loose bolts or objects touching the outdoor unit.",
              "Remove any loose items nearby.",
              "If vibration continues, call a technician to check the stand and compressor mount."],
             "Do not stand on the outdoor unit stand. A grinding or metal noise means stop using the AC."),
        ]),
        ("AC is not turning on", "not starting not turning on dead no power remote display", 1, [
            ("No power supply or tripped MCB",
             ["Check if other appliances in the room work.",
              "Check the MCB/fuse of the AC and switch it on again once.",
              "Ensure the plug is firmly seated in the socket."],
             "If the MCB trips again immediately, do not keep switching it on. Call an electrician."),
            ("Remote or settings problem",
             ["Replace the remote batteries.",
              "Try the manual ON button on the indoor unit.",
              "Check that a 'Timer' or 'Sleep' mode is not blocking start."],
             "No special risk."),
            ("Faulty PCB / capacitor",
             ["Note any error code or blinking light pattern on the display.",
              "Do not open the unit.",
              "Call a technician and share the error code."],
             "Electronic boards hold electric charge. Only a technician should open the unit."),
        ]),
    ]),
    "Refrigerator": ("🧊", [
        ("Refrigerator is not cooling", "not cooling warm not cold food spoiling", 0, [
            ("Temperature dial set too low",
             ["Set the thermostat to a medium setting (3-4 on most models).",
              "Wait 4-6 hours and check the temperature again.",
              "Do not keep the door open for long."],
             "No special risk. Move perishable food to a cooler if it is warm."),
            ("Door seal (gasket) not closing properly",
             ["Close the door on a piece of paper; if it slides out easily, the seal is weak.",
              "Clean the rubber gasket with warm soapy water.",
              "Replace the gasket if it is cracked or torn."],
             "Unplug before cleaning inside. Do not use sharp tools on the gasket."),
            ("Dusty condenser coils or blocked ventilation",
             ["Unplug the refrigerator.",
              "Locate the condenser coils (back or bottom) and vacuum or brush off dust.",
              "Keep at least 5-8 cm gap from the wall.",
              "Plug in again and wait a few hours."],
             "Always unplug before cleaning coils. Wear a mask because of dust."),
            ("Compressor or gas problem",
             ["Listen for the compressor starting; if it never runs or clicks repeatedly, there is a fault.",
              "Do not try to repair it yourself.",
              "Call a technician."],
             "The compressor and relay have high voltage. Do not open the back cover."),
        ]),
        ("Refrigerator is making noise", "noise sound loud humming buzzing clicking", 0, [
            ("Refrigerator not levelled or touching the wall",
             ["Check that the refrigerator stands level on all four feet.",
              "Adjust the front leg screws until it is stable.",
              "Move it a little away from the wall."],
             "Ask someone to help when moving a heavy appliance. Unplug it before moving."),
            ("Dirty or obstructed fan",
             ["Unplug the refrigerator.",
              "Check the freezer fan area for ice or objects.",
              "Defrost the freezer if there is heavy ice buildup."],
             "Never use a knife or sharp object to remove ice."),
            ("Faulty compressor or fan motor",
             ["If the noise is loud and continuous, switch off and unplug.",
              "Do not use the appliance for long.",
              "Call a technician."],
             "Do not open the rear panel."),
        ]),
        ("Water leaking from refrigerator", "water leak leaking puddle wet floor", 0, [
            ("Blocked defrost drain",
             ["Unplug the refrigerator.",
              "Find the drain hole at the back wall of the fridge compartment.",
              "Clear it with warm water and a soft pipe cleaner or cotton swab.",
              "Wipe the water tray at the bottom."],
             "Wipe the floor immediately to avoid slipping. Keep the plug dry."),
            ("Door not closing, causing heavy frost",
             ["Make sure food packets do not block the door.",
              "Clean and check the gasket.",
              "Defrost the freezer if frost is thick."],
             "No special risk."),
        ]),
        ("Refrigerator is not starting", "not starting dead no light no power off", 1, [
            ("No power at the socket",
             ["Test the socket with another appliance.",
              "Check the MCB/fuse.",
              "Check the plug and cable for visible damage."],
             "Do not use the appliance if the cable is damaged or burnt."),
            ("Faulty relay or thermostat",
             ["If the light works but the compressor does not run, note this for the technician.",
              "Do not open the back or the control panel.",
              "Book a technician."],
             "The relay carries mains voltage. Only a technician should touch it."),
        ]),
    ]),
    "Washing Machine": ("🧺", [
        ("Washing machine is not starting", "not starting dead no power not turning on door", 0, [
            ("Door or lid not closed properly",
             ["Close the door or lid firmly until it clicks.",
              "Check that clothes are not trapped in the door.",
              "Press Start again."],
             "Never bypass the door lock."),
            ("No power supply or tripped MCB",
             ["Check the socket with another appliance.",
              "Check the MCB/fuse and plug.",
              "Make sure the water tap is on and the child lock is off."],
             "Keep hands dry when touching the plug."),
            ("Faulty door lock or control board",
             ["Note any error code shown on the display.",
              "Switch off and unplug the machine.",
              "Call a technician with the error code."],
             "Do not open the control panel."),
        ]),
        ("Washing machine is not draining water", "not draining drain water stuck full drum", 0, [
            ("Drain hose kinked or clogged",
             ["Switch off and unplug the machine.",
              "Check that the drain hose is not bent and is placed at the correct height.",
              "Disconnect and rinse the hose to remove lint or debris."],
             "Keep a bucket and towels ready; hot water may spill. Do not touch if water is hot."),
            ("Clogged drain pump filter",
             ["Unplug the machine.",
              "Open the small filter cover at the bottom front.",
              "Place a tray, slowly unscrew the filter and remove coins, lint or socks.",
              "Refit the filter tightly."],
             "Water may come out suddenly. Never do this while the machine is plugged in."),
            ("Faulty drain pump",
             ["If water remains and you hear no pump sound, the pump may be faulty.",
              "Do not force the drum.",
              "Call a technician."],
             "Do not put hands inside the machine."),
        ]),
        ("Washing machine shakes or makes loud noise", "noise shaking vibration loud jumping spinning", 0, [
            ("Unbalanced or overloaded drum",
             ["Pause the cycle and rearrange clothes evenly.",
              "Do not wash a single heavy item alone.",
              "Reduce the load to the recommended capacity."],
             "Wait for the drum to stop completely before opening the door."),
            ("Machine not levelled",
             ["Place a spirit level on top of the machine.",
              "Adjust the feet until it is stable.",
              "Remove transit bolts at the back if it is a new machine."],
             "Unplug the machine before adjusting or moving it."),
            ("Worn bearings or suspension",
             ["If the noise is a loud grinding sound even with a small load, stop using the machine.",
              "Call a technician."],
             "Continued use can damage the drum and cause leaks."),
        ]),
        ("Washing machine is leaking water", "leak leaking water floor wet puddle", 1, [
            ("Loose inlet or drain hose connection",
             ["Switch off the machine and close the water tap.",
              "Check the inlet hose and drain hose connections.",
              "Tighten the clamps by hand and check for cracks in the hose."],
             "Unplug the machine and wipe the floor to avoid slipping and electric shock."),
            ("Too much detergent or wrong detergent",
             ["Use only the recommended amount of detergent.",
              "Use front-load or top-load specific detergent as required."],
             "No special risk."),
            ("Damaged door seal or internal tub",
             ["If the leak occurs inside the door ring, inspect the rubber seal for cuts.",
              "Do not use the machine until it is repaired.",
              "Call a technician."],
             "Water near electrical parts is dangerous. Keep the machine unplugged."),
        ]),
    ]),
    "Fan": ("🌀", [
        ("Fan is not running", "not running not working dead not starting stopped", 1, [
            ("No power or regulator problem",
             ["Check whether the switch and other lights/appliances are working.",
              "Check the MCB/fuse.",
              "Set the regulator to full speed and test again."],
             "Switch off the power before touching any wiring. Do not stand on a chair that is unstable."),
            ("Faulty capacitor",
             ["If the fan hums but does not rotate, give it a gentle push with a stick after switching off.",
              "Do not open the fan body yourself.",
              "Replace the capacitor through a technician."],
             "Capacitors store charge even after power-off. Leave it to a technician."),
            ("Burnt motor winding",
             ["If you smell burning, switch off the fan immediately.",
              "Do not use the fan again.",
              "Call a technician for motor rewinding or replacement."],
             "Burning smell means fire risk. Turn off the MCB."),
        ]),
        ("Fan is running slowly", "slow speed low speed less air weak", 0, [
            ("Dust on blades and motor",
             ["Switch off the fan and wait until it stops.",
              "Wipe the blades with a damp cloth using a stable stool or ladder.",
              "Check that the blades are not bent."],
             "Make sure the fan has completely stopped and the switch is off before cleaning."),
            ("Weak capacitor",
             ["If the fan speed has gradually reduced over time, the capacitor is probably weak.",
              "Call a technician to replace it."],
             "Do not open the motor housing."),
            ("Regulator fault",
             ["Check whether the fan runs normally when connected directly (technician), or try another regulator position.",
              "Replace the regulator if the speed does not change."],
             "Turn off the main switch before replacing the regulator."),
        ]),
        ("Fan is making noise or wobbling", "noise wobble wobbling shaking rattle sound", 0, [
            ("Loose blade screws or canopy",
             ["Switch off the fan.",
              "Check blade screws and tighten them.",
              "Check the canopy and down-rod screws."],
             "Use a stable ladder and make sure the power is off."),
            ("Dirty or unbalanced blades",
             ["Clean all blades and compare their angles.",
              "Use a fan balancing kit if available."],
             "Do not bend the blades by hand."),
            ("Worn bearings",
             ["If you hear a grinding or squeaking sound from the motor, bearings may be worn.",
              "Call a technician to replace the bearings."],
             "Stop using the fan if it wobbles heavily; it may fall."),
        ]),
    ]),
    "Microwave Oven": ("♨️", [
        ("Microwave is not heating food", "not heating cold food not hot no heat", 1, [
            ("Door not closing properly or wrong settings",
             ["Make sure the door closes completely and the latch clicks.",
              "Check the power level (not set on defrost or low).",
              "Use a microwave-safe container and cover the food."],
             "Never operate the microwave with a damaged door. Never use metal containers."),
            ("Faulty door switch or fuse",
             ["If the light and turntable work but food stays cold, a door switch or fuse may be faulty.",
              "Stop using the microwave.",
              "Call a technician."],
             "Do not open the outer casing. The internal capacitor can keep a lethal charge even when unplugged."),
            ("Faulty magnetron or high-voltage diode",
             ["If you hear a loud hum with no heating, switch off.",
              "Do not attempt repair.",
              "Call an authorised service centre."],
             "High voltage parts are extremely dangerous. Technician repair only."),
        ]),
        ("Microwave is not starting", "not starting dead no display no power not turning on", 0, [
            ("No power or tripped MCB",
             ["Check the socket with another appliance.",
              "Check the plug and MCB/fuse.",
              "Reset the microwave by unplugging it for one minute."],
             "Do not use an extension cord with a damaged plug."),
            ("Child lock enabled",
             ["Press and hold the Stop/Cancel button for 3 seconds to disable the child lock (check your model).",
              "Try starting again."],
             "No special risk."),
            ("Faulty control board",
             ["If the display is blank even with power, a control board fault is likely.",
              "Call a technician."],
             "Do not open the control panel."),
        ]),
        ("Microwave is sparking", "spark sparking sparks fire burning smell arcing", 1, [
            ("Metal object or foil inside",
             ["Stop the microwave immediately and open the door when it is safe.",
              "Remove any metal containers, foil or utensils.",
              "Check for gold or silver rim on dishes."],
             "Keep the door closed if there is a fire inside and unplug the oven. Do not open the door."),
            ("Food residue or damaged cavity coating",
             ["Unplug the microwave and let it cool.",
              "Clean the inside walls, ceiling and waveguide cover.",
              "If paint is peeling or burnt, stop using it and call a technician."],
             "A damaged cavity can cause arcing and fire. Do not use it until repaired."),
        ]),
        ("Microwave turntable is not rotating", "turntable plate not rotating not spinning stuck", 0, [
            ("Roller ring or glass tray misplaced",
             ["Remove the glass tray and the roller ring.",
              "Clean them and the floor of the oven.",
              "Place them back correctly on the coupler."],
             "Let the oven cool before cleaning."),
            ("Faulty turntable motor",
             ["If the tray still does not rotate, the motor may be faulty.",
              "Call a technician to replace the motor."],
             "Do not open the bottom plate yourself."),
        ]),
    ]),
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables and load the troubleshooting knowledge base once."""
    conn = get_db()
    conn.executescript(SCHEMA)
    # Migrate databases created by earlier HomeFix versions.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(repair_history)")}
    if "user_id" not in columns:
        conn.execute("ALTER TABLE repair_history ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
    if conn.execute("SELECT COUNT(*) FROM appliances").fetchone()[0] == 0:
        for app_name, (icon, problems) in KB.items():
            cur = conn.execute("INSERT INTO appliances(name, icon) VALUES (?, ?)", (app_name, icon))
            app_id = cur.lastrowid
            for symptom, keywords, risky, causes in problems:
                cur = conn.execute(
                    "INSERT INTO problems(appliance_id, symptom, keywords, risky) VALUES (?,?,?,?)",
                    (app_id, symptom, keywords, risky))
                pid = cur.lastrowid
                for prio, (cause, steps, safety) in enumerate(causes, start=1):
                    conn.execute(
                        "INSERT INTO rules(problem_id, cause, steps, safety, priority) VALUES (?,?,?,?,?)",
                        (pid, cause, "\n".join(steps), safety, prio))
        conn.commit()
    conn.close()
