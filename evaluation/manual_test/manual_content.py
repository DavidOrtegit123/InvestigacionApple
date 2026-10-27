"""Text of the invented "Verdane GH-4 Greenhouse Controller" operator manual.

The manual exists only to test retrieval on a many-page PDF: every fact in it
is invented, so a correct answer has to come from the document. Chapters 4-8
describe five modules with the same six sections and different values, which
is the hard case for search (right topic, wrong module).

A chapter is {"number", "title", "module", "sections"}; a section is
{"number", "title", "blocks"}; a block is ("p", text), ("bullets", [text]),
("code", text) or ("table", [[cell, ...], ...]) with the first row as header.
"""

BODY_FONT_SIZE = 11
TITLE = "Verdane GH-4 Greenhouse Controller"
SUBTITLE = "Operator Manual - Firmware 3.2"

# --- The seven test questions --------------------------------------------------
# "fact" is text that must appear on exactly one page; "answer_tokens" must
# appear in the whole document only inside that fact. Q7 is not answered by
# the manual on purpose.

QUESTIONS = [
    {
        "id": "Q1",
        "question": "What is the timeout for the ventilation module's vent actuator?",
        "expected_answer": "312 seconds",
        "section": "5.3 Timeout settings",
        "fact": "If a vent actuator does not report its end position within 312 seconds, "
                "the controller stops the motor and raises the travel alarm.",
        "answer_tokens": ["312"],
        "tests": "picking the right one of five look-alike sections",
    },
    {
        "id": "Q2",
        "question": "Which error code means the CO2 valve is stuck open?",
        "expected_answer": "E-C17",
        "section": "8.6 Error codes",
        "fact": "E-C17 Dosing valve stuck open",
        "answer_tokens": ["E-C17"],
        "tests": "look-alike sections and look-alike codes (E-I17, E-H17 mean other things); table",
    },
    {
        "id": "Q3",
        "question": "How often should the irrigation flow sensor be calibrated?",
        "expected_answer": "Every 23 days",
        "section": "4.5 Calibration",
        "fact": "Calibrate each flow sensor every 23 days, and again after any pipe work "
                "upstream of the sensor.",
        "answer_tokens": ["23 days"],
        "tests": "look-alike sections (the heating probe interval is 45 days)",
    },
    {
        "id": "Q4",
        "question": "What does a blinking amber LED on the control panel mean?",
        "expected_answer": "A firmware update has been downloaded and is waiting for confirmation",
        "section": "3.3 Status LEDs",
        "fact": "A blinking amber STATUS LED means that a firmware update has been downloaded "
                "and is waiting for confirmation on the panel.",
        "answer_tokens": ["waiting for confirmation"],
        "tests": "a unique section (easy control question)",
    },
    {
        "id": "Q5",
        "question": "My plants get too much light late in the evening - which setting decides "
                    "when the lamps turn off?",
        "expected_answer": "The dusk cutoff setting (default 21:40)",
        "section": "6.2 Schedules",
        "fact": "The dusk cutoff is the latest time of day at which supplementary lamps may "
                "run; its default value is 21:40.",
        "answer_tokens": ["21:40"],
        "tests": "different wording from the manual",
    },
    {
        "id": "Q6",
        "question": "How many sensors can one controller support?",
        "expected_answer": "64",
        "section": "12.1 Technical specifications",
        "fact": "Maximum sensors per controller 64",
        "answer_tokens": ["64"],
        "tests": "reading a table",
    },
    {
        "id": "Q7",
        "question": "What is the warranty period?",
        "expected_answer": "Not stated in the manual",
        "section": None,
        "fact": None,
        "answer_tokens": [],
        "tests": "the model should say the manual does not cover it",
    },
]

# --- The five look-alike modules ------------------------------------------------

MODULES = [
    {
        "number": 4,
        "name": "irrigation",
        "title": "Irrigation module",
        "code_prefix": "I",
        "timeout_seconds": 240,
        "calibration_days": 23,
        "purpose": "delivers water and dissolved nutrients to up to sixteen growing zones "
                   "through solenoid zone valves fed by a single main pump",
        "actuator": "zone valve",
        "actuators": "zone valves",
        "sensor": "flow sensor",
        "sensors": "flow sensors",
        "menu": "Menu > Irrigation",
        "overview_extra": [
            "Each zone has its own valve, an optional soil moisture probe and a flow sensor "
            "mounted on the zone's supply line. The main pump only runs while at least one "
            "zone valve is open, so a closed system never builds up pressure against the pump.",
            "Fertigation is handled by the same module. When a nutrient recipe is assigned to "
            "a zone, the injector doses the stock solution into the supply line while the zone "
            "valve is open, and the conductivity reading of the drain water is logged after "
            "each cycle.",
        ],
        "schedule_extra": [
            "Irrigation cycles are defined per zone as a start time, a run length in minutes "
            "and the number of repeats per day. The controller staggers zones that would "
            "otherwise start at the same moment, so that the main pump never feeds more than "
            "three zones at once.",
            "A cycle can also be started by soil moisture instead of the clock. In that mode "
            "the zone waters whenever its probe reads below the trigger level, but never more "
            "often than the minimum rest time set for the zone, which defaults to 50 minutes.",
            "Night watering is blocked by default between sunset and sunrise as calculated from "
            "the site coordinates. Growers who irrigate before dawn can lift the block for "
            "individual zones in the zone's schedule page.",
        ],
        "schedule_snippet": "[irrigation.zone.3]\nstart      = 06:30\nrun_min    = 12\nrepeats    = 4\nrecipe     = \"leafy-a\"",
        "timeout_fact": "Each zone valve must confirm that water is flowing within 240 seconds "
                        "of being opened; otherwise the zone is closed and marked as dry-run.",
        "timeout_extra": [
            "The flow confirmation comes from the zone's flow sensor. A short delay is normal "
            "on long supply lines, because the line has to fill before the sensor registers "
            "a steady flow. Lines longer than 60 metres may need a booster pump rather than a "
            "longer timeout.",
            "The pump also has a dry-running guard. If the main pump draws less than a quarter "
            "of its rated current for 20 seconds, it is switched off to protect the seals, "
            "whatever the zone timeouts are set to.",
        ],
        "thresholds": [
            ["Supply pressure", "1.2 bar", "4.5 bar", "Measured after the main pump"],
            ["Drain conductivity", "0.8 mS/cm", "3.6 mS/cm", "Logged after every cycle"],
            ["Zone flow", "35 % of nominal", "140 % of nominal", "Nominal flow is learned in the first week"],
            ["Water tank level", "15 %", "-", "Low level blocks all zones"],
        ],
        "calibration_fact": "Calibrate each flow sensor every 23 days, and again after any pipe "
                            "work upstream of the sensor.",
        "calibration_steps": [
            "Open the zone valve manually from Menu > Irrigation > Service.",
            "Collect the outflow of one dripper line in a measuring container for exactly one minute.",
            "Enter the measured volume; the controller computes the new sensor factor.",
            "Repeat for each zone and close the service page to resume the schedule.",
        ],
        "codes": [
            ["E-I03", "Main pump did not start", "Check the pump fuse and contactor."],
            ["E-I08", "Zone dry-run", "Check the zone valve and the supply line for blockages."],
            ["E-I11", "Supply pressure too high", "Check for closed hand valves after the pump."],
            ["E-I17", "Zone valve stuck closed", "Clean or replace the valve solenoid."],
            ["E-I21", "Flow without open valve", "A valve is leaking; inspect all zone valves."],
            ["E-I26", "Nutrient injector fault", "Check the injector tubing and stock tank."],
            ["E-I30", "Drain conductivity too high", "Flush the substrate with clean water."],
            ["E-I33", "Soil moisture probe lost", "Check the probe cable and bus address."],
            ["E-I38", "Water tank level low", "Check the tank inlet and float valve."],
            ["E-I41", "Recipe not found", "Load the nutrient recipe again from USB."],
        ],
    },
    {
        "number": 5,
        "name": "ventilation",
        "title": "Ventilation module",
        "code_prefix": "V",
        "timeout_seconds": 312,
        "calibration_days": 30,
        "purpose": "opens and closes the ridge and side vents with motorised vent actuators to "
                   "control air temperature and humidity",
        "actuator": "vent actuator",
        "actuators": "vent actuators",
        "sensor": "wind sensor",
        "sensors": "wind sensors",
        "menu": "Menu > Ventilation",
        "overview_extra": [
            "Up to eight vent groups can be configured. Each group is driven by one or more "
            "vent actuators that move together and report their position as a percentage, "
            "from 0 % (closed) to 100 % (fully open).",
            "The module reads the inside air temperature and humidity, the outside temperature, "
            "and the wind speed and direction from the weather mast. Wind and rain always take "
            "priority over temperature: a vent that faces into a strong wind is closed even if "
            "the greenhouse is too warm.",
        ],
        "schedule_extra": [
            "Ventilation does not run on fixed times. Instead, the schedule defines day and "
            "night temperature targets and the times at which the targets change. The vents "
            "open in proportion to how far the air temperature is above the active target.",
            "A morning purge can be scheduled to open all vents to 20 % for a few minutes after "
            "sunrise, which removes the humid night air before the crop starts transpiring.",
            "During the change from the night target to the day target the controller ramps the "
            "target over 45 minutes instead of jumping, so the vents do not open suddenly.",
        ],
        "schedule_snippet": "[ventilation.group.ridge]\nday_target   = 24.0\nnight_target = 17.5\nday_start    = 07:15\nnight_start  = 19:30",
        "timeout_fact": "If a vent actuator does not report its end position within 312 seconds, "
                        "the controller stops the motor and raises the travel alarm.",
        "timeout_extra": [
            "Long ridge vents on older houses can be slow, especially in cold weather when the "
            "gear grease is stiff. If the travel alarm appears regularly on a healthy vent, "
            "check the actuator's end switches before changing anything in the settings.",
            "A separate storm timeout applies when the wind sensor triggers a forced close. In "
            "that case the controller keeps driving the actuator toward closed for as long as "
            "the storm condition lasts and repeats the command every two minutes.",
        ],
        "thresholds": [
            ["Inside humidity", "55 %", "88 %", "Above the high limit the vents open 5 %"],
            ["Wind speed (storm close)", "-", "11 m/s", "Measured on the weather mast"],
            ["Inside temperature", "12 C", "34 C", "Alarm only; does not change targets"],
            ["Rain detection", "-", "on", "Closes windward vents to 10 %"],
        ],
        "calibration_fact": "Calibrate the wind sensor every 30 days by comparing it with a "
                            "handheld anemometer at the mast.",
        "calibration_steps": [
            "Choose a calm moment with a steady light breeze.",
            "Hold the handheld anemometer at the same height as the mast sensor for two minutes.",
            "Enter the average reading in Menu > Ventilation > Service > Wind offset.",
            "Run a full open-close cycle of each vent group to re-learn the travel limits.",
        ],
        "codes": [
            ["E-V02", "Vent position unknown", "Run a travel re-learn from the service page."],
            ["E-V04", "Vent travel too slow", "Check end switches and gear grease."],
            ["E-V09", "Wind sensor not responding", "Check the mast cable and connector."],
            ["E-V17", "Actuator overcurrent", "Remove obstructions from the vent rack."],
            ["E-V22", "Rain sensor fault", "Clean the rain sensor plate."],
            ["E-V30", "Group position mismatch", "Actuators in one group disagree; re-learn."],
            ["E-V34", "Humidity sensor fault", "Check the sensor and its radiation shield."],
            ["E-V37", "Storm close incomplete", "Inspect the vents after the storm has passed."],
            ["E-V40", "End switch stuck", "Free or replace the end switch."],
            ["E-V45", "Weather data missing", "Check the weather master controller."],
        ],
    },
    {
        "number": 6,
        "name": "lighting",
        "title": "Lighting module",
        "code_prefix": "L",
        "timeout_seconds": 95,
        "calibration_days": 60,
        "purpose": "switches and dims the supplementary lamps to reach a daily light target "
                   "measured by PAR sensors",
        "actuator": "lamp driver",
        "actuators": "lamp drivers",
        "sensor": "PAR sensor",
        "sensors": "PAR sensors",
        "menu": "Menu > Lighting",
        "overview_extra": [
            "Lamps are grouped into lighting circuits. Each circuit is switched by a contactor "
            "and, for dimmable fixtures, controlled by lamp drivers on a 0-10 V signal. The "
            "module supports up to twelve circuits.",
            "Instead of switching lamps on at fixed hours, the module adds artificial light "
            "only when the natural light measured by the PAR sensors is not enough to reach the "
            "crop's daily light integral, the total amount of light the crop should receive in "
            "a day.",
        ],
        "schedule_extra": [
            "The lighting schedule sets the photoperiod window, the daily light integral "
            "target and the dimming limits. Inside the window, lamps are switched on whenever "
            "the controller predicts that the target will not be reached by natural light "
            "alone.",
            "The dusk cutoff is the latest time of day at which supplementary lamps may run; "
            "its default value is 21:40. After that time all circuits are switched off, even if "
            "the daily light integral has not been reached, so that the crop gets an "
            "uninterrupted dark period.",
            "A dawn start time works the same way at the beginning of the day. Short-day crops "
            "usually need both limits set carefully, because a single hour of extra lamp light "
            "in the evening can delay flowering.",
        ],
        "schedule_snippet": "[lighting.circuit.2]\ndli_target  = 14.0\nmax_dim     = 85\ncontactor   = \"K2\"",
        "timeout_fact": "Each lamp driver must report a stable output within 95 seconds of being "
                        "switched on; otherwise the circuit is switched off and locked.",
        "timeout_extra": [
            "High-pressure sodium fixtures need several minutes to reach full output, but their "
            "drivers report stable operation much earlier, as soon as the arc has struck. LED "
            "drivers usually report within a few seconds.",
            "A locked circuit stays off until it is released from the lighting service page. "
            "This prevents a faulty fixture from being switched on and off repeatedly through "
            "the night.",
        ],
        "thresholds": [
            ["PAR at canopy", "-", "1,100 umol/m2/s", "Lamps dim when natural light is high"],
            ["Driver temperature", "-", "75 C", "Circuit dims to 50 % above the limit"],
            ["Circuit current", "70 % of rated", "115 % of rated", "Checked every minute"],
            ["Lamp hours", "-", "18,000 h", "Reminder to replace lamps"],
        ],
        "calibration_fact": "Calibrate the PAR sensors every 60 days against the reference "
                            "sensor supplied with the controller.",
        "calibration_steps": [
            "Switch all lighting circuits off and wait for a cloudless, steady light period.",
            "Place the reference sensor next to the PAR sensor, at the same angle.",
            "Read both values from Menu > Lighting > Service > Sensor check.",
            "Accept the proposed correction factor if it lies between 0.85 and 1.15.",
        ],
        "codes": [
            ["E-L01", "Contactor did not close", "Check the contactor coil and fuse."],
            ["E-L06", "Driver not stable in time", "Replace the lamp driver."],
            ["E-L12", "PAR sensor out of range", "Clean the sensor dome."],
            ["E-L17", "Circuit current too low", "One or more lamps have failed."],
            ["E-L19", "Driver overheating", "Check fixture ventilation and ambient temperature."],
            ["E-L25", "Dimming signal lost", "Check the 0-10 V wiring of the circuit."],
            ["E-L29", "Circuit locked", "Release the circuit from the lighting service page."],
            ["E-L32", "Light target not reached", "Check for failed lamps or a too early cutoff."],
            ["E-L36", "Lamp hours exceeded", "Replace the lamps and reset the counter."],
            ["E-L39", "Contactor stuck closed", "Switch off the circuit breaker and replace the contactor."],
        ],
    },
    {
        "number": 7,
        "name": "heating",
        "title": "Heating module",
        "code_prefix": "H",
        "timeout_seconds": 410,
        "calibration_days": 45,
        "purpose": "controls the boiler and the mixing valves of the heating pipe loops to keep "
                   "the greenhouse at its temperature target",
        "actuator": "mixing valve",
        "actuators": "mixing valves",
        "sensor": "pipe probe",
        "sensors": "pipe probes",
        "menu": "Menu > Heating",
        "overview_extra": [
            "The module drives up to four pipe loops, each with its own mixing valve, loop pump "
            "and pipe probe on the supply side. The boiler is requested whenever any loop needs "
            "more heat than the buffer tank can deliver.",
            "Heating and ventilation share the same temperature targets. To avoid wasting energy, "
            "the heating module lowers its target by the dead band whenever the vents are more "
            "than 10 % open.",
        ],
        "schedule_extra": [
            "Heating follows the same day and night targets as the ventilation module, plus a "
            "pre-dawn boost that raises the pipe temperature for a set time before sunrise. The "
            "boost helps dry the crop before the vents open.",
            "A minimum pipe temperature can be set per loop. It keeps a little heat in the "
            "pipes even when the air is warm enough, which reduces condensation on the crop "
            "during humid nights.",
            "The schedule can also lock the boiler during expensive energy periods. During a "
            "lock the module only uses the heat stored in the buffer tank.",
        ],
        "schedule_snippet": "[heating.loop.1]\nmin_pipe     = 35\nboost_before = 01:30\nboost_rise   = 8",
        "timeout_fact": "After the boiler is requested, it must report a supply temperature "
                        "increase within 410 seconds; otherwise the request is cancelled and "
                        "the burner alarm is raised.",
        "timeout_extra": [
            "The time a boiler needs depends on its type and size. Condensing boilers usually "
            "react within two or three minutes; large biomass boilers can be much slower, and "
            "the timeout should then be raised by the installer.",
            "Mixing valves have no separate timeout. A valve that does not move is detected by "
            "comparing the pipe probe reading with the expected temperature after each change.",
        ],
        "thresholds": [
            ["Supply temperature", "20 C", "90 C", "Boiler side, before the mixing valves"],
            ["Pipe temperature", "min_pipe", "75 C", "Per loop"],
            ["Buffer tank", "30 C", "95 C", "Top sensor"],
            ["Flue gas temperature", "-", "240 C", "Burner stops above the limit"],
        ],
        "calibration_fact": "Calibrate each pipe probe every 45 days with the contact "
                            "thermometer from the service kit.",
        "calibration_steps": [
            "Let the loop run at a steady temperature for at least 15 minutes.",
            "Hold the contact thermometer on the bare pipe next to the probe.",
            "Enter the reading in Menu > Heating > Service > Probe offset.",
            "Repeat for each loop; offsets above 3 C indicate a faulty probe.",
        ],
        "codes": [
            ["E-H02", "Boiler did not respond", "Check the boiler enable signal."],
            ["E-H05", "Burner alarm", "Reset the burner and check the fuel supply."],
            ["E-H10", "Pipe probe open circuit", "Check the probe cable."],
            ["E-H17", "Mixing valve not moving", "Check the valve motor and its fuse."],
            ["E-H23", "Buffer tank overheating", "Check the tank's top sensor and pump."],
            ["E-H28", "Loop pump fault", "Check the pump and its circuit breaker."],
            ["E-H31", "Flue gas too hot", "Have the boiler serviced."],
            ["E-H35", "Boiler locked by schedule", "Information only; heat comes from the buffer tank."],
            ["E-H38", "Probe offset too large", "Replace the pipe probe."],
            ["E-H42", "Loop temperature too low", "Check the mixing valve and loop pump."],
        ],
    },
    {
        "number": 8,
        "name": "CO2 dosing",
        "title": "CO2 dosing module",
        "code_prefix": "C",
        "timeout_seconds": 180,
        "calibration_days": 14,
        "purpose": "enriches the greenhouse air with carbon dioxide through a dosing valve, "
                   "using either a gas tank or the boiler's cleaned flue gas",
        "actuator": "dosing valve",
        "actuators": "dosing valves",
        "sensor": "CO2 sensor",
        "sensors": "CO2 sensors",
        "menu": "Menu > CO2 dosing",
        "overview_extra": [
            "The module has one main dosing valve and up to four distribution branches. CO2 is "
            "measured in parts per million (ppm) by infrared CO2 sensors hung at crop height.",
            "Dosing only makes sense while the crop is photosynthesising and the vents are "
            "mostly closed. The module therefore reduces its target as the vents open and stops "
            "dosing completely at night.",
        ],
        "schedule_extra": [
            "The schedule defines a dosing window, a CO2 target for closed vents and a lower "
            "target for open vents. Between the two vent positions the target is interpolated "
            "linearly.",
            "When flue gas is used as the CO2 source, dosing can only happen while the boiler is "
            "running. Surplus heat is then stored in the buffer tank, so the heating schedule "
            "and the dosing schedule should be planned together.",
            "Dosing is always stopped while people are registered as working inside the "
            "compartment, if the optional entry badge reader is installed.",
        ],
        "schedule_snippet": "[co2.dosing]\nwindow_start = 08:00\nwindow_end   = 17:00\ntarget_ppm   = 800\nopen_ppm     = 450",
        "timeout_fact": "After the dosing valve is opened, the CO2 reading must rise within "
                        "180 seconds; otherwise the valve is closed and dosing is suspended "
                        "for the day.",
        "timeout_extra": [
            "Sensors hung far from the distribution tubes react more slowly. If the dosing alarm "
            "appears in large compartments, move one CO2 sensor closer to a distribution branch "
            "before considering any change to the settings.",
            "Suspended dosing restarts automatically on the next day. It can also be restarted "
            "manually from the service page after the cause has been fixed.",
        ],
        "thresholds": [
            ["CO2 concentration", "-", "1,500 ppm", "Dosing stops above the limit"],
            ["Safety limit (people present)", "-", "5,000 ppm", "Sounds the room alarm"],
            ["Gas tank pressure", "6 bar", "-", "Low pressure warning"],
            ["Flue gas CO level", "-", "15 ppm", "Flue dosing stops above the limit"],
        ],
        "calibration_fact": "Calibrate each CO2 sensor every 14 days with outside air, which "
                            "the controller assumes to contain 420 ppm.",
        "calibration_steps": [
            "Stop dosing and open all vents fully for 20 minutes.",
            "Carry the CO2 sensor outside or wait until the inside reading is steady.",
            "Start the fresh-air calibration from Menu > CO2 dosing > Service.",
            "The sensor is ready again after a two-minute warm-up.",
        ],
        "codes": [
            ["E-C04", "CO2 reading did not rise", "Check the gas supply and dosing valve."],
            ["E-C09", "CO2 sensor warm-up failed", "Replace the sensor lamp."],
            ["E-C13", "Flue gas too dirty", "Check the boiler's flue gas cleaner."],
            ["E-C17", "Dosing valve stuck open", "Close the manual gas valve immediately and ventilate."],
            ["E-C20", "Safety limit exceeded", "Leave the compartment and ventilate."],
            ["E-C24", "Gas tank pressure low", "Replace or refill the gas tank."],
            ["E-C28", "Badge reader not responding", "Check the badge reader cable."],
            ["E-C31", "Branch valve fault", "Check the distribution branch valve."],
            ["E-C35", "Sensor calibration overdue", "Run the fresh-air calibration."],
            ["E-C39", "Flue gas source unavailable", "Dosing waits until the boiler runs."],
        ],
    },
]

# --- Appendix table (Q6) ----------------------------------------------------------

SPEC_TABLE = [
    ["Property", "Value"],
    ["Supply voltage", "100-240 V AC, 50/60 Hz"],
    ["Power consumption", "18 W typical, 35 W maximum"],
    ["Operating temperature", "-10 C to 50 C"],
    ["Enclosure rating", "IP65"],
    ["Display", "7-inch colour touch screen"],
    ["Maximum sensors per controller", "64"],
    ["Maximum modules per controller", "5"],
    ["Relay outputs", "24, each 5 A at 230 V"],
    ["Analogue outputs", "12 x 0-10 V"],
    ["Sensor bus", "RS-485, up to 1,000 m"],
    ["Network", "Ethernet 100 Mbit/s"],
    ["Data logging", "Two years at one-minute intervals"],
    ["Weight", "4.2 kg"],
    ["Dimensions", "380 x 300 x 140 mm"],
]


# --- Module chapters (same six sections for every module) ------------------------

def _module_chapter(m):
    n = m["number"]
    name = m["name"]
    return {
        "number": n,
        "title": m["title"],
        "module": True,
        "sections": [
            {"number": f"{n}.1", "title": "Overview", "blocks": [
                ("p", f"The {name} module {m['purpose']}. It is one of the five control "
                      f"modules of the GH-4 and can be enabled or disabled in "
                      f"{m['menu']} > Settings without affecting the other modules."),
                *[("p", text) for text in m["overview_extra"]],
                ("p", f"All {name} settings are found under {m['menu']}. Settings that "
                      f"could damage equipment are only visible after the installer code has "
                      f"been entered, and every change is written to the event log together "
                      f"with the user who made it."),
                ("bullets", [
                    f"{m['menu']} > Status shows the live state of all {m['actuators']} and "
                    f"{m['sensors']}.",
                    f"{m['menu']} > Settings holds the targets, limits and timing values "
                    f"described in this chapter.",
                    f"{m['menu']} > Service is used for manual operation and calibration.",
                ]),
                ("p", f"The status page shows one line per device. For each "
                      f"{m['actuator']} it lists the commanded state, the reported state and "
                      f"the time of the last change; for each {m['sensor']} it lists the "
                      f"current reading, the reading one hour ago and the date of the last "
                      f"calibration. A device that has not reported for more than a minute "
                      f"is shown in grey."),
                ("p", f"When the {name} module is disabled, all its outputs are switched to "
                      f"their safe state and its alarms are suppressed. The module's "
                      f"settings and schedules are kept, so it can be enabled again later "
                      f"without being set up from scratch."),
            ]},
            {"number": f"{n}.2", "title": "Schedules", "blocks": [
                ("p", f"The {name} schedule tells the module what to aim for at each time "
                      f"of day. Schedules are edited on the controller or loaded from a "
                      f"configuration file on a USB stick, using the format shown below."),
                *[("p", text) for text in m["schedule_extra"]],
                ("p", "Example configuration entry:"),
                ("code", m["schedule_snippet"]),
                ("p", f"Schedule changes take effect at the start of the next control "
                      f"cycle, which runs every 30 seconds. Changes made through a USB file "
                      f"are shown on the screen for confirmation before they replace the "
                      f"active {name} schedule."),
                ("p", f"Up to four alternative {name} schedules can be stored, for example "
                      f"one for summer, one for winter and two for special crops. Only one "
                      f"schedule is active at a time; switching between them is done in "
                      f"{m['menu']} > Settings > Schedule set and is recorded in the event "
                      f"log."),
                ("p", "Times in schedules are local times. The controller follows the "
                      "summer time change automatically if the time zone has been set in "
                      "Menu > System > Date and time; otherwise all schedules shift by one "
                      "hour twice a year."),
            ]},
            {"number": f"{n}.3", "title": "Timeout settings", "blocks": [
                ("p", f"Timeouts protect the {name} equipment when a command is sent but "
                      f"the expected reaction does not follow. The controller starts a timer "
                      f"each time it sends a command to a {m['actuator']} and checks the "
                      f"result when the timer runs out."),
                ("p", m["timeout_fact"]),
                *[("p", text) for text in m["timeout_extra"]],
                ("p", f"The timeout value can be changed by the installer in "
                      f"{m['menu']} > Settings > Timing. Raising it hides real faults for "
                      f"longer, so it should only be changed after the cause of repeated "
                      f"alarms has been understood. The value in use is printed on the "
                      f"module's settings report."),
                ("p", f"Every timeout event is counted. The counters for each "
                      f"{m['actuator']} are shown in {m['menu']} > Service > Statistics and "
                      f"can help to find a device that is slowly wearing out: a device whose "
                      f"counter rises week after week usually needs attention before it "
                      f"fails completely."),
            ]},
            {"number": f"{n}.4", "title": "Alarm thresholds", "blocks": [
                ("p", f"Alarm thresholds define the range in which each {name} "
                      f"measurement is considered normal. When a reading leaves its range "
                      f"for longer than the alarm delay of two minutes, the module raises "
                      f"an alarm on the screen, closes the relevant output if required, and "
                      f"sends a notification to the alarm contacts."),
                ("table", [["Measurement", "Low limit", "High limit", "Notes"]]
                          + m["thresholds"]),
                ("p", "A dash means that no limit applies on that side. The limits shown "
                      "are the factory values; they can be adjusted in the settings, within "
                      "the safe range allowed by the firmware."),
                ("p", "Alarms are acknowledged with the ALARM button on the front panel. An "
                      "acknowledged alarm stays in the alarm list until the reading is back "
                      "inside its range, and is then moved to the event log."),
                ("p", f"Each {name} alarm can be given a priority. High-priority alarms are "
                      f"sent to the alarm contacts immediately, day and night; low-priority "
                      f"alarms are collected and sent as one summary message at the start of "
                      f"the working day. By default, alarms that stop equipment are high "
                      f"priority and all others are low priority."),
            ]},
            {"number": f"{n}.5", "title": "Calibration", "blocks": [
                ("p", f"Sensor readings drift slowly over time, and a drifting "
                      f"{m['sensor']} makes the {name} module react to values that are not "
                      f"real. Regular calibration keeps the readings trustworthy."),
                ("p", m["calibration_fact"]),
                ("p", "Calibration procedure:"),
                ("bullets", m["calibration_steps"]),
                ("p", f"The date of the last calibration is stored for every {m['sensor']}. "
                      f"When a calibration is due, a reminder appears in the maintenance list "
                      f"on the home screen; the module keeps working normally until the "
                      f"calibration is done."),
                ("p", f"If a calibration gives a correction that is much larger than the "
                      f"previous one, clean the {m['sensor']} and repeat the procedure "
                      f"before accepting it. A large jump is more often caused by dirt or a "
                      f"mistake during the procedure than by the sensor itself."),
            ]},
            {"number": f"{n}.6", "title": "Error codes", "blocks": [
                ("p", f"Errors of the {name} module start with E-{m['code_prefix']}. The "
                      f"code is shown in the alarm list together with the time at which the "
                      f"error first appeared and the device it belongs to."),
                ("table", [["Code", "Meaning", "What to do"]] + m["codes"]),
                ("p", "If an error comes back after the suggested action, note the code and "
                      "the device, and contact your installer. Codes that are not listed here "
                      "belong to another module; check the first letter after E-."),
                ("p", f"Errors that stop a {m['actuator']} must be acknowledged before the "
                      f"device is used again. Errors that only report a condition clear "
                      f"themselves as soon as the condition has gone, but they stay visible "
                      f"in the event log with their start and end time."),
            ]},
        ],
    }


# --- Other chapters ---------------------------------------------------------------

def _other_chapters():
    return [
        {"number": 1, "title": "Introduction and safety", "module": False, "sections": [
            {"number": "1.1", "title": "About this manual", "blocks": [
                ("p", "This manual describes the installation, operation and maintenance of "
                      "the Verdane GH-4 greenhouse controller with firmware version 3.2. It is "
                      "written for growers who operate the controller every day and for "
                      "installers who set it up."),
                ("p", "Chapters 1 to 3 cover safety, installation and the control panel. "
                      "Chapters 4 to 8 each describe one control module. They follow the same "
                      "structure, so that once you know one module you can find your way in "
                      "the others. Chapters 9 to 11 cover sensors, maintenance and "
                      "troubleshooting, and chapter 12 contains the technical data."),
                ("p", "Keep this manual near the controller. Menu paths are written as "
                      "Menu > Lighting > Settings, and buttons on the front panel are written "
                      "in capital letters, for example the ALARM button."),
            ]},
            {"number": "1.2", "title": "Intended use", "blocks": [
                ("p", "The GH-4 is intended for the climate and irrigation control of "
                      "commercial greenhouses and plant nurseries with a floor area of up to "
                      "two hectares per controller. Larger sites use several controllers "
                      "connected to the same network."),
                ("p", "The controller must not be used as a safety device for people. In "
                      "particular, the CO2 safety limit described in chapter 8 does not "
                      "replace an independent gas detector where local rules require one."),
                ("p", "Any use outside the conditions described in this manual, including "
                      "operation outside the temperature range given in the technical "
                      "specifications, is not intended use."),
            ]},
            {"number": "1.3", "title": "Safety instructions", "blocks": [
                ("p", "Read these instructions before working on the controller or on any "
                      "device connected to it."),
                ("bullets", [
                    "Only qualified electricians may open the controller housing or work on "
                    "its mains wiring.",
                    "Switch off the mains supply and the separate supply of the relay outputs "
                    "before working on any connected device.",
                    "Manual operation from a service page overrides automatic protection. Stay "
                    "near the equipment while using it.",
                    "Never disable the storm protection of the ventilation module while the "
                    "vents are open and nobody is present.",
                    "Keep the controller door closed during operation to keep out water and "
                    "dust.",
                ]),
                ("p", "Ignoring these instructions can cause injury, crop loss or damage to "
                      "the greenhouse equipment."),
            ]},
            {"number": "1.4", "title": "Symbols and conventions", "blocks": [
                ("p", "Notes marked IMPORTANT describe a situation that can damage equipment "
                      "or crops. Notes marked TIP give advice that makes daily use easier but "
                      "is not required."),
                ("p", "Values given in this manual are factory settings unless stated "
                      "otherwise. Temperatures are given in degrees Celsius (C), pressures in "
                      "bar and light in micromoles per square metre per second (umol/m2/s)."),
                ("p", "Configuration examples are printed in a fixed-width font. They show the "
                      "format of the configuration file and are not recommended values for "
                      "every greenhouse."),
            ]},
        ]},
        {"number": 2, "title": "Installation", "module": False, "sections": [
            {"number": "2.1", "title": "Package contents", "blocks": [
                ("p", "Check that the package contains the following parts before starting "
                      "the installation:"),
                ("bullets", [
                    "GH-4 controller with mounting bracket",
                    "Reference PAR sensor in a protective case",
                    "Service kit with contact thermometer, terminal screwdriver and spare fuses",
                    "Two cable glands of each size (M16, M20, M25)",
                    "USB stick with the configuration templates",
                    "This operator manual",
                ]),
                ("p", "Report missing or damaged parts to your supplier before installing the "
                      "controller. Keep the packaging until the controller has been "
                      "commissioned."),
            ]},
            {"number": "2.2", "title": "Mounting the controller", "blocks": [
                ("p", "Mount the controller on a solid wall in the technical room or in a "
                      "sheltered place inside the greenhouse, at eye level, so that the screen "
                      "can be read comfortably. Avoid places with direct sunlight on the "
                      "screen, dripping water or strong vibration."),
                ("p", "Leave at least 20 cm of free space below the controller for the cable "
                      "glands, and at least 10 cm on both sides for cooling. The housing must "
                      "not be covered."),
                ("p", "Fix the bracket with four screws suitable for the wall material, hang "
                      "the controller on the bracket and secure it with the locking screw at "
                      "the bottom."),
            ]},
            {"number": "2.3", "title": "Electrical connections", "blocks": [
                ("p", "All connections are made on the terminal strips inside the housing. The "
                      "mains supply, the relay outputs, the analogue outputs and the sensor bus "
                      "each have their own strip, labelled on the inside of the door."),
                ("p", "Use shielded twisted-pair cable for the sensor bus and connect the "
                      "shield at the controller end only. Route sensor cables away from mains "
                      "and motor cables, or cross them at a right angle."),
                ("p", "The relay outputs are potential-free contacts. Motors, pumps and lamp "
                      "contactors must be switched through external contactors sized for "
                      "their load; the controller relays are not designed to switch motors "
                      "directly."),
                ("p", "IMPORTANT: connect the protective earth before switching on the mains "
                      "supply for the first time."),
            ]},
            {"number": "2.4", "title": "First start-up", "blocks": [
                ("p", "After switching on, the controller runs a self-test that takes about one "
                      "minute. The start-up assistant then asks for the language, the date "
                      "and time, the site coordinates and the installer code."),
                ("p", "The site coordinates are used to calculate sunrise and sunset, which "
                      "several modules use in their schedules. Enter them as decimal degrees, "
                      "for example 52.01 and 4.36."),
                ("p", "Finally, the assistant searches the sensor bus and lists all sensors it "
                      "has found. Assign each sensor to a module and a location before "
                      "leaving the assistant. Sensors can also be added later, as described "
                      "in chapter 9."),
            ]},
        ]},
        {"number": 3, "title": "Control panel overview", "module": False, "sections": [
            {"number": "3.1", "title": "Front panel layout", "blocks": [
                ("p", "The front panel has a 7-inch touch screen in the centre, a jog wheel and "
                      "four buttons on the right, and three status LEDs above the screen. The "
                      "USB port for configuration files is behind a small cover at the bottom "
                      "of the panel."),
                ("p", "The home screen shows the current state of every enabled module as a "
                      "tile. Tapping a tile opens the status page of that module. The top bar "
                      "shows the time, the active alarms and the maintenance reminders."),
                ("p", "The screen switches off after ten minutes without use and comes back "
                      "on as soon as it is touched or a button is pressed."),
            ]},
            {"number": "3.2", "title": "Buttons and the jog wheel", "blocks": [
                ("p", "The four buttons next to the jog wheel are labelled HOME, BACK, ALARM "
                      "and LOCK."),
                ("bullets", [
                    "HOME returns to the home screen from any page.",
                    "BACK goes up one level in the menu.",
                    "ALARM opens the alarm list; pressing it again acknowledges the selected "
                    "alarm.",
                    "LOCK locks the screen; it is unlocked with the user code.",
                ]),
                ("p", "The jog wheel is used to change values precisely. Turn it to change the "
                      "selected value step by step and press it to confirm. Values changed "
                      "with the jog wheel are not saved until they are confirmed."),
            ]},
            {"number": "3.3", "title": "Status LEDs", "blocks": [
                ("p", "The three LEDs above the screen are labelled POWER, STATUS and BUS. "
                      "They show the state of the controller even when the screen is off."),
                ("bullets", [
                    "POWER steady green: the controller is supplied and running.",
                    "STATUS steady green: all modules are working without alarms.",
                    "STATUS steady red: at least one alarm has not been acknowledged.",
                    "STATUS blinking red: a module has stopped because of an error.",
                    "BUS blinking green: data is being exchanged with the sensors.",
                    "BUS off: no sensor has answered for more than one minute.",
                ]),
                ("p", "A blinking amber STATUS LED means that a firmware update has been "
                      "downloaded and is waiting for confirmation on the panel. Control "
                      "continues normally until the update is confirmed, as described in "
                      "chapter 10."),
            ]},
            {"number": "3.4", "title": "Menu structure", "blocks": [
                ("p", "The main menu lists the enabled modules first, followed by Sensors, "
                      "Network, Maintenance and System. Each module has the same three "
                      "sub-menus: Status, Settings and Service."),
                ("p", "System holds the date and time, the site coordinates, the user and "
                      "installer codes, the screen settings and the factory reset. Changes "
                      "under System require the installer code."),
                ("p", "TIP: hold the HOME button for three seconds to open a list of the menu "
                      "pages you have used most recently."),
            ]},
        ]},
        {"number": 9, "title": "Sensors and networking", "module": False, "sections": [
            {"number": "9.1", "title": "Sensor bus", "blocks": [
                ("p", "All sensors are connected to the controller through a single RS-485 "
                      "sensor bus. Sensors are wired one after the other in a line; star "
                      "wiring is not supported. The last sensor on the line must have its "
                      "termination switch set to ON."),
                ("p", "Each sensor has a unique bus address printed on its label. The "
                      "controller polls every sensor in turn, and the BUS LED blinks while "
                      "this happens. See the technical specifications in chapter 12 for the "
                      "limits of the bus."),
                ("p", "Long bus lines may need a repeater. Signs of a weak bus are sensors "
                      "that drop out briefly in the alarm list or readings that freeze for a "
                      "few minutes."),
            ]},
            {"number": "9.2", "title": "Adding a sensor", "blocks": [
                ("p", "To add a sensor after the first start-up, connect it to the bus and "
                      "open Menu > Sensors > Search. The controller lists all sensors that "
                      "answer and are not yet assigned."),
                ("p", "Select the new sensor, assign it to a module and give it a location "
                      "name, for example Bay 3 North. The location name appears in alarms, "
                      "so choose names that the whole team understands."),
                ("p", "A replaced sensor keeps the assignment and calibration history of the "
                      "old one if you select Replace instead of Add. Calibrate the new sensor "
                      "before relying on its readings."),
            ]},
            {"number": "9.3", "title": "Network settings", "blocks": [
                ("p", "The controller has one Ethernet port. By default it gets its network "
                      "address automatically. A fixed address can be set in Menu > Network > "
                      "Address, which is recommended for sites with several controllers."),
                ("p", "Several controllers on the same network share weather data from a "
                      "single weather mast. Set one controller as the weather master in "
                      "Menu > Network > Weather; the others receive its readings every ten "
                      "seconds."),
                ("p", "The network connection is not needed for control. If the network fails, "
                      "every controller continues to work with its own sensors and its last "
                      "known weather data."),
            ]},
            {"number": "9.4", "title": "Remote monitoring", "blocks": [
                ("p", "The GH-4 offers a read-only web page that shows the home screen tiles "
                      "and the alarm list. It is enabled in Menu > Network > Web page and is "
                      "protected by its own password."),
                ("p", "Settings cannot be changed through the web page. This is a deliberate "
                      "design choice: changes to the climate are always made at the "
                      "controller, by someone who can see the greenhouse."),
                ("p", "Alarm notifications can be sent by e-mail to up to five alarm "
                      "contacts. Each contact can choose which modules it receives alarms "
                      "for."),
            ]},
        ]},
        {"number": 10, "title": "Maintenance", "module": False, "sections": [
            {"number": "10.1", "title": "Daily checks", "blocks": [
                ("p", "A short daily check catches most problems before they affect the crop:"),
                ("bullets", [
                    "Look at the alarm list and the maintenance reminders on the home screen.",
                    "Compare the inside temperature shown on the screen with a thermometer in "
                    "the crop.",
                    "Check that the water tank level and the gas tank pressure are sufficient "
                    "for the day.",
                    "Listen for unusual noises from pumps and vent actuators.",
                ]),
                ("p", "Record anything unusual in the event log with Menu > Maintenance > "
                      "Note, so that the next person on duty knows about it."),
            ]},
            {"number": "10.2", "title": "Monthly maintenance", "blocks": [
                ("p", "Once a month, export the event log to a USB stick and keep it for your "
                      "records. Check the tightness of the terminal screws inside the housing "
                      "and look for signs of moisture."),
                ("p", "Test the storm protection by simulating a high wind in Menu > "
                      "Ventilation > Service > Storm test. All vents must close fully within "
                      "the normal travel time."),
                ("p", "The sensor calibration intervals are given in the calibration section "
                      "of each module chapter. The maintenance list on the home screen shows "
                      "which calibrations are due."),
            ]},
            {"number": "10.3", "title": "Firmware updates", "blocks": [
                ("p", "Firmware updates are published by Verdane and can be installed from a "
                      "USB stick or, if the controller is connected to the internet, "
                      "downloaded automatically in the background."),
                ("p", "A downloaded update is never installed on its own. Open Menu > System > "
                      "Update, read the release notes and confirm the installation. The "
                      "controller restarts once; during the restart, which takes about two "
                      "minutes, all outputs keep their last state."),
                ("p", "IMPORTANT: do not switch off the controller during an update. Choose a "
                      "calm moment of the day, when no irrigation cycle is planned and the "
                      "weather is stable."),
            ]},
            {"number": "10.4", "title": "Cleaning", "blocks": [
                ("p", "Clean the screen with a soft, damp cloth. Do not use solvents or "
                      "abrasive cleaners, and never spray water directly onto the controller."),
                ("p", "Sensors in the greenhouse collect dust and spray residue. Clean "
                      "radiation shields, sensor domes and the rain sensor plate as part of "
                      "the monthly maintenance, or more often during spraying periods."),
                ("p", "Keep the area below the controller free, so that the cable glands stay "
                      "dry and accessible."),
            ]},
        ]},
        {"number": 11, "title": "Troubleshooting", "module": False, "sections": [
            {"number": "11.1", "title": "General approach", "blocks": [
                ("p", "Most problems show up as an error code in the alarm list. Start with "
                      "the code: the first letter after E- tells you the module, and the "
                      "error code table in that module's chapter lists the meaning and the "
                      "first action to take."),
                ("p", "If there is no error code, check the status page of the module that "
                      "behaves unexpectedly. It shows the live readings, the active targets "
                      "and the state of every output, which usually explains why the module "
                      "does what it does."),
                ("p", "Before calling for help, note the controller's serial number, the "
                      "firmware version from Menu > System > About, and the exact error code."),
            ]},
            {"number": "11.2", "title": "Controller does not start", "blocks": [
                ("p", "If the screen and the POWER LED stay dark, check the mains fuse inside "
                      "the housing and the circuit breaker that supplies the controller."),
                ("p", "If the POWER LED is on but the screen stays dark, the self-test may "
                      "have found a fault. Wait two minutes; if the screen does not come on, "
                      "switch the controller off for ten seconds and on again."),
                ("p", "While the controller is off, all relay outputs are open. Pumps, lamps "
                      "and vents therefore stop in their current position, except for devices "
                      "that have their own safety logic."),
            ]},
            {"number": "11.3", "title": "Sensor readings drift", "blocks": [
                ("p", "A reading that slowly moves away from reality usually means a dirty "
                      "sensor or a calibration that is overdue. Clean the sensor first and "
                      "then calibrate it as described in the module's chapter."),
                ("p", "If two sensors in the same compartment disagree by more than the normal "
                      "variation, swap their positions for a day. If the difference moves "
                      "with the sensor, the sensor is faulty; if it stays at the location, "
                      "the location itself is different."),
                ("p", "Readings that jump between two values are often caused by a loose "
                      "connector or a weak sensor bus rather than by the sensor itself."),
            ]},
            {"number": "11.4", "title": "Resetting to factory settings", "blocks": [
                ("p", "A factory reset removes all settings, schedules and sensor assignments, "
                      "but keeps the event log and the calibration history. It is started "
                      "from Menu > System > Factory reset and requires the installer code."),
                ("p", "Before resetting, export the current configuration to a USB stick with "
                      "Menu > System > Export. The exported file can be loaded again after "
                      "the reset, which is useful if the reset was only needed to clear a "
                      "faulty setting."),
                ("p", "After the reset, the start-up assistant runs again, as on the first "
                      "start-up."),
            ]},
        ]},
        {"number": 12, "title": "Appendix", "module": False, "sections": [
            {"number": "12.1", "title": "Technical specifications", "blocks": [
                ("p", "The table below lists the technical data of the GH-4 controller."),
                ("table", SPEC_TABLE),
                ("p", "Specifications may change with new hardware revisions. The revision "
                      "of your controller is printed on the label inside the door."),
            ]},
            {"number": "12.2", "title": "Glossary", "blocks": [
                ("bullets", [
                    "Daily light integral (DLI): the total amount of light a crop receives in "
                    "one day, in moles per square metre.",
                    "Dead band: a small range around a target in which no action is taken, "
                    "to avoid constant switching.",
                    "Fertigation: adding dissolved nutrients to irrigation water.",
                    "Installer code: the code that unlocks settings which can damage "
                    "equipment.",
                    "PAR: photosynthetically active radiation, the part of light that plants "
                    "use.",
                    "Photoperiod: the part of the day during which the crop receives light.",
                    "Termination switch: a switch on the last sensor of the bus that prevents "
                    "signal reflections.",
                ]),
            ]},
        ]},
    ]


def _more_sections():
    """Extra sections appended to the non-module chapters, by chapter number."""
    return {
        2: [
            {"number": "2.5", "title": "Connecting the weather mast", "blocks": [
                ("p", "The weather mast carries the outside temperature and humidity sensor, "
                      "the wind sensor, the wind direction vane, the rain sensor and an outside "
                      "light sensor. It is connected to the sensor bus like any other sensor, "
                      "through its own junction box at the foot of the mast."),
                ("p", "Mount the mast at least two metres above the highest ridge of the "
                      "greenhouse and away from chimneys, trees and other buildings, which "
                      "disturb the wind readings. The wind direction vane must be aligned to "
                      "north during installation; the alignment mark is on the vane's base."),
                ("p", "Use the lightning protection module supplied with the mast. Without it, "
                      "a nearby lightning strike can damage every device on the sensor bus, "
                      "not only the mast sensors."),
                ("p", "Only one weather mast is needed per site. Sites with several controllers "
                      "share the mast's readings over the network, as described in chapter 9."),
            ]},
            {"number": "2.6", "title": "Commissioning checklist", "blocks": [
                ("p", "Before handing the controller over to the grower, the installer works "
                      "through the following checklist and signs the commissioning report "
                      "printed from Menu > System > Report."),
                ("bullets", [
                    "All sensors found on the bus and assigned to a module and location.",
                    "Every output tested once from its service page.",
                    "Storm test of the ventilation module carried out successfully.",
                    "Alarm contacts entered and a test notification received.",
                    "Site coordinates, time zone and installer code set.",
                    "Configuration exported to the USB stick and the stick stored with this "
                    "manual.",
                ]),
                ("p", "The commissioning report lists the installed modules, all devices with "
                      "their bus addresses and the most important settings. Keep a printed "
                      "copy in the technical room."),
            ]},
        ],
        3: [
            {"number": "3.5", "title": "Users and codes", "blocks": [
                ("p", "The controller knows two levels of access. The user code unlocks the "
                      "screen and allows growers to change targets and schedules. The "
                      "installer code additionally unlocks timing values, limits, service "
                      "pages and the system settings."),
                ("p", "Up to ten users can be created, each with a name and a personal code. "
                      "Every change on the controller is recorded in the event log together "
                      "with the name of the user who made it, so sharing one code between "
                      "several people is not recommended."),
                ("p", "A forgotten installer code cannot be recovered from the controller. "
                      "Contact your installer, who can reset it with the service key."),
            ]},
            {"number": "3.6", "title": "The event log", "blocks": [
                ("p", "The event log records alarms, setting changes, schedule switches, "
                      "calibrations, restarts and notes entered by users. It is opened from "
                      "Menu > Maintenance > Event log and can be filtered by module, by type "
                      "and by date."),
                ("p", "The log holds two years of events. Older entries are removed "
                      "automatically, oldest first. Export the log regularly if you need to "
                      "keep a longer history, for example for certification of the crop."),
                ("p", "TIP: tap an entry to see the values before and after a setting change. "
                      "This is the quickest way to find out why the climate changed overnight."),
            ]},
        ],
        9: [
            {"number": "9.5", "title": "Sensor types", "blocks": [
                ("p", "The GH-4 works with the Verdane sensor family, which all use the same "
                      "bus connector. The most common types are listed below."),
                ("bullets", [
                    "Climate box: air temperature and humidity in a ventilated radiation "
                    "shield, hung at crop height.",
                    "PAR sensor: light at the canopy, used by the lighting module.",
                    "CO2 sensor: infrared measurement of carbon dioxide in ppm.",
                    "Flow sensor: water flow in a zone supply line.",
                    "Pipe probe: contact temperature sensor for heating pipes.",
                    "Soil moisture probe: water content of the substrate.",
                ]),
                ("p", "Sensors from other manufacturers can be connected through the analogue "
                      "input box, which converts a 4-20 mA or 0-10 V signal into a bus reading. "
                      "Their calibration has to be entered by hand."),
            ]},
            {"number": "9.6", "title": "Weather data", "blocks": [
                ("p", "The weather data from the mast is shown on the home screen and used by "
                      "the ventilation, heating and lighting modules. Each reading is averaged "
                      "over one minute, except the wind speed, which also keeps the highest "
                      "gust of the last ten minutes."),
                ("p", "If the mast stops reporting, the modules fall back to safe behaviour: "
                      "the vents are limited to 30 % open, and lighting uses the inside PAR "
                      "sensors only. An alarm is raised after five minutes without weather "
                      "data."),
                ("p", "Weather readings are stored in the data log together with the inside "
                      "readings, so that the greenhouse climate can later be compared with the "
                      "outside conditions."),
            ]},
        ],
        10: [
            {"number": "10.5", "title": "Spare parts", "blocks": [
                ("p", "Keep a small stock of spare parts on site, so that a failed part does not "
                      "stop the greenhouse for days. The following parts fail most often:"),
                ("bullets", [
                    "Fuses for the controller and the relay outputs (in the service kit).",
                    "One climate box and one CO2 sensor lamp.",
                    "Solenoid coils for the zone valves.",
                    "End switches for the vent actuators.",
                    "A replacement radiation shield for the climate boxes.",
                ]),
                ("p", "Order spare parts through your installer and quote the part name and "
                      "the hardware revision printed on the label inside the controller door."),
            ]},
            {"number": "10.6", "title": "Taking the greenhouse out of use", "blocks": [
                ("p", "When a compartment is empty for a longer time, disable the modules that "
                      "are not needed instead of switching off the controller. The heating "
                      "module can be left on with a low frost-protection target to protect the "
                      "pipes and the irrigation lines."),
                ("p", "Before the new crop is planted, enable the modules again, check all "
                      "calibration reminders, and run a test cycle of every output from its "
                      "service page."),
                ("p", "If the controller itself must be switched off for more than a month, "
                      "export the configuration first. The internal clock keeps running for "
                      "about six months without power."),
            ]},
        ],
        11: [
            {"number": "11.5", "title": "Alarm messages do not arrive", "blocks": [
                ("p", "Send a test message from Menu > Network > Alarm contacts > Test. If it "
                      "does not arrive, check that the controller has a working network "
                      "connection and that the e-mail server settings are correct."),
                ("p", "Check the contact's module selection: a contact only receives alarms "
                      "from the modules ticked for that contact. Low-priority alarms are sent "
                      "as a morning summary and therefore never arrive at night."),
                ("p", "Messages that arrive late are usually delayed by the e-mail server, not "
                      "by the controller. The time at which an alarm was raised is always "
                      "written in the message itself."),
            ]},
            {"number": "11.6", "title": "A device does not do what is expected", "blocks": [
                ("p", "Open the module's status page and compare the commanded state with the "
                      "reported state. If they agree, the controller is doing what its "
                      "settings ask for: check the targets, the active schedule set and any "
                      "overrides such as storm protection or a boiler lock."),
                ("p", "If the commanded and reported states disagree, the problem is between "
                      "the controller and the device. Check the output from the service page, "
                      "then the wiring, the external contactor and finally the device itself."),
                ("p", "Remember that several modules interact. Vents opening during heating, "
                      "for example, reduce the heating target, and open vents reduce the CO2 "
                      "target. The status page shows which rule is currently limiting each "
                      "output."),
            ]},
        ],
        12: [
            {"number": "12.3", "title": "Configuration file format", "blocks": [
                ("p", "Configuration files are plain text files with sections in square "
                      "brackets and one setting per line. They can be edited on a computer and "
                      "loaded from a USB stick. Lines starting with # are comments."),
                ("code", "# GH-4 configuration export\n[system]\nsite_lat   = 52.01\nsite_lon   = 4.36\ntime_zone  = \"Europe/Amsterdam\"\n\n[network]\naddress    = \"dhcp\"\nweather    = \"master\""),
                ("p", "A file only needs to contain the settings that should change; all other "
                      "settings keep their current values. Unknown settings are listed on the "
                      "screen and ignored."),
            ]},
            {"number": "12.4", "title": "Error code prefixes", "blocks": [
                ("p", "Every error code starts with E- followed by a letter that identifies the "
                      "module, and a number. The table below lists the letters."),
                ("table", [
                    ["Prefix", "Module", "Chapter"],
                    ["E-I", "Irrigation", "4"],
                    ["E-V", "Ventilation", "5"],
                    ["E-L", "Lighting", "6"],
                    ["E-H", "Heating", "7"],
                    ["E-C", "CO2 dosing", "8"],
                    ["E-S", "System and sensor bus", "11"],
                ]),
                ("p", "System errors (E-S) concern the controller itself or the sensor bus. "
                      "They are explained on the screen when the alarm is opened."),
            ]},
        ],
    }


def chapters():
    """All twelve chapters in reading order."""
    others = {c["number"]: c for c in _other_chapters()}
    for number, sections in _more_sections().items():
        others[number]["sections"].extend(sections)
    modules = {m["number"]: _module_chapter(m) for m in MODULES}
    combined = {**others, **modules}
    return [combined[n] for n in sorted(combined)]


def find_section(label):
    """The section whose "<number> <title>" equals label, or None."""
    for chapter in chapters():
        for section in chapter["sections"]:
            if f'{section["number"]} {section["title"]}' == label:
                return section
    return None


def section_text(section):
    """All text of a section, with table rows joined by spaces."""
    parts = []
    for kind, value in section["blocks"]:
        if kind in ("p", "code"):
            parts.append(value)
        elif kind == "bullets":
            parts.extend(value)
        elif kind == "table":
            parts.extend(" ".join(row) for row in value)
    return " ".join(parts)
