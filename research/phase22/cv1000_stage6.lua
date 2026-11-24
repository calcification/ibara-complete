-- Original Ibara U4 d5fb6657. Run from the repository root.
-- This fixture selects Garden in the native stage script and shortens two boss
-- timers. The original game loads the stage and spawns Teresa and the Hadou.

assert(emu.romname() == "ibara", "use the original MAME ibara set")
local machine = manager.machine
local space = machine.devices[":maincpu"].spaces["program"]
local ports = machine.ioport.ports
local workload = dofile("research/phase22/cv1000_workload.lua")
-- Some MAME builds reject 64-bit MMIO callback arguments before Lua sees them.
local capture
if os.getenv("IBARA_CPU_ONLY") ~= "1" then capture = workload.attach(machine) end
local side = tonumber(os.getenv("IBARA_SIDE") or "1")
local seeded_rank = tonumber(os.getenv("IBARA_RANK") or "600000", 16)
local ticks_after_release = math.tointeger(tonumber(os.getenv("IBARA_POST_RELEASE") or "640"))
assert(side == 1 or side == 2, "IBARA_SIDE must be 1 or 2")
assert(seeded_rank and seeded_rank >= 0 and seeded_rank <= 0xffffff, "IBARA_RANK must be 24-bit hexadecimal")
assert(ticks_after_release and ticks_after_release > 0, "IBARA_POST_RELEASE must be a positive integer")
local function new_csv(path)
    local existing = io.open(path, "r")
    if existing then
        existing:close()
        error("CSV already exists: " .. path)
    end
    return assert(io.open(path, "w"))
end
local csv = new_csv(assert(os.getenv("IBARA_TRACE"), "set IBARA_TRACE to an unused CSV path"))
local cadence_path = os.getenv("IBARA_CADENCE")
local cadence = cadence_path and new_csv(cadence_path)
local deadline = dofile("research/phase22/cv1000_deadline.lua").open(machine, os.getenv("IBARA_DEADLINE"))
local cadence_start
local window = side == 1 and "stage6-bond" or "stage6-dyne"
if cadence then cadence:write("window,frame,tick\n") end
local objects_path = os.getenv("IBARA_OBJECTS")
local objects = objects_path and new_csv(objects_path)
local last_object_tick
if objects then
    objects:write("tick,player_x,player_y,hostile_bullets,active_enemies,rose_pods\n")
end

-- The retail SH-3 program maintains these TMU1 measurements itself. Read them
-- at refresh boundaries so capture works even when DRC bypasses RAM taps.
local cpu_fields = {
    {"tmu", 0x0c04a16c}, {"irq_tmu", 0x0c3929c0}, {"profile_tmu", 0x0c21ca18},
    {"irq_period", 0x0c286510}, {"pre", 0x0c27dc4c},
    {"draw_parts", 0x0c286064}, {"draw_setup", 0x0c220c48},
    {"draw_overlays", 0x0c21f7f4}, {"publish", 0x0c21ca04},
    {"sim_a", 0x0c2175e0}, {"sim_b", 0x0c286060}, {"sim_c", 0x0c392e04},
}
local columns = {"frame", "outer", "logic", "relative", "rank", "bombs", "boss_age", "kicks", "modeled_ns"}
for _, key in ipairs(workload.list_fields) do columns[#columns + 1] = key end
for _, field in ipairs(cpu_fields) do columns[#columns + 1] = field[1] end
csv:write(table.concat(columns, ",") .. "\n")

local SCENE, SCRIPT, LOOP = 0x0c392b08, 0x0c2859a0, 0x0c28599c
local LOGIC, OUTER, RANK = 0x0c21f880, 0x0c392964, 0x0c27dff8
local INTRO, GARDEN = 0x0c1eeec6, 0x0c1eeeea
local ENEMIES, BULLETS = 0x0c26cd40, 0x0c27e0fc
local player = 0x0c283794 + (side - 1) * 0x280
local start = side == 1 and "1 Player Start" or "2 Players Start"
local port = side == 1 and ":PORT_D" or ":PORT_L"
local shot, bomb = "P" .. side .. " Button 1", "P" .. side .. " Button 2"
local frame, release_tick = 0, nil
local warped, charged, released, shot_stopped = false, false, false, false
local shortened = {}

local event_csv, event_taps
local event_path = os.getenv("IBARA_EVENTS")
if event_path then
    assert(capture, "IBARA_EVENTS requires a MAME build with 64-bit taps, such as 0.276 with -nodrc")
    event_csv, event_taps = new_csv(event_path), {}
    event_csv:write("frame,outer,relative,event,time_us\n")
    local pc = machine.devices[":maincpu"].state.PC
    local function watch(address, source_pc, event)
        event_taps[#event_taps + 1] = space:install_write_tap(address & ~7, address | 7, event,
            function()
                -- On this interpreter PC has advanced past the store.
                if not release_tick or pc.value ~= source_pc then return end
                local outer, logic = space:read_u32(OUTER), space:read_u32(LOGIC)
                -- The outer-counter write marks the new IRQ before RAM is updated.
                if address == OUTER then outer = (outer + 1) & 0xffffffff end
                event_csv:write(string.format("%d,%u,%d,%s,%.4f\n",
                    frame, outer, logic - release_tick, event, machine.time:as_double() * 1e6))
            end)
    end
    watch(OUTER, 0x0c05045e, "irq")
    watch(0x0c27dc4c, 0x0c05a790, "setup_done")
    watch(0x0c392e04, 0x0c05ad9c, "update_done")
    watch(0x0c283c94, 0x0c0508a6, "list_ready")
    watch(0x18000004, 0x0c050280, "submit")
end

local function finish(message)
    csv:close()
    if cadence then cadence:close() end
    if deadline then deadline.close() end
    if objects then objects:close() end
    if event_csv then
        for _, tap in ipairs(event_taps) do tap:remove() end
        event_csv:close()
    end
    print(message)
    machine:exit()
end

local function set(port_name, name, pressed)
    local input = assert(ports[port_name].fields[name], name)
    if pressed then input:set_value(1) else input:clear_value() end
end

local function flying_form()
    for slot = 0, 191 do
        local enemy = ENEMIES + slot * 0xb4
        if (space:read_u32(enemy) & 0x80000000) ~= 0 then
            local kind, part = space:read_u32(enemy + 4), space:read_u32(enemy + 8)
            local age = space:read_u32(enemy + 0x50)
            if kind == 0x4a and part == 2 and space:read_u32(enemy + 0x40) == 300000 then
                return enemy
            end
            if part == 0 and not shortened[kind] then
                if kind == 0x45 and age > 200 then
                    space:write_u32(enemy + 0x50, 2101)
                    shortened[kind] = true
                elseif kind == 0x4a and age > 300 and space:read_u8(enemy + 0x9f) == 1 then
                    space:write_u32(enemy + 0x50, 12601)
                    shortened[kind] = true
                end
            end
        end
    end
end

local function capture_frame(logic, boss)
    local jobs = capture and capture:take_frame() or {}
    local submissions = capture and #jobs or -1
    if #jobs == 0 then jobs = {{}} end
    local outer, rank = space:read_u32(OUTER), space:read_u32(RANK)
    local bombs = space:read_u8(player + 0x256)
    local age = boss and space:read_u32(boss + 0x50) or -1
    for _, job in ipairs(jobs) do
        local values = {frame, outer, logic, logic - release_tick, rank, bombs, age,
                        submissions, job.modeled_ns or -1}
        for _, key in ipairs(workload.list_fields) do
            values[#values + 1] = job.list and job.list[key] or -1
        end
        for _, field in ipairs(cpu_fields) do
            values[#values + 1] = space:read_u32(field[2])
        end
        csv:write(table.concat(values, ",") .. "\n")
        if job.error then error(job.error) end
    end
end

local function capture_objects(logic)
    if logic == last_object_tick then return end
    last_object_tick = logic
    local hostile, enemies, pods = 0, 0, 0
    for slot = 0, 255 do
        local flags = space:read_u32(BULLETS + slot * 0x54)
        if flags & 0x10004000 == 0x10000000 then hostile = hostile + 1 end
    end
    for slot = 0, 191 do
        local enemy = ENEMIES + slot * 0xb4
        if space:read_u32(enemy) & 0x80000000 ~= 0 then
            enemies = enemies + 1
            if space:read_u32(enemy + 4) == 0x4f and space:read_u32(enemy + 8) == 0 then
                pods = pods + 1
            end
        end
    end
    objects:write(string.format("%d,%d,%d,%d,%d,%d\n", logic - release_tick,
        space:read_i32(player + 0x10), space:read_i32(player + 0x14), hostile, enemies, pods))
end

emu.register_frame_done(function()
    frame = frame + 1
    if frame == 2400 or frame == 2408 then set(":PORT_C", "Coin 1", frame == 2400) end
    if frame == 2460 or frame == 2468 then set(":PORT_C", start, frame == 2460) end

    if frame == 3300 and not warped or frame == 30000 then
        finish("Stage 6 capture did not complete")
        return
    end

    local logic = space:read_u32(LOGIC)
    if frame >= 2460 and not warped and space:read_u8(LOOP) ~= 0 and
        logic == 0 and space:read_u32(SCRIPT) == INTRO then
        assert(space:read_u16(GARDEN + 2) == 0xff02 and space:read_u16(GARDEN + 4) == 6,
               "expected Garden's native stage command")
        space:write_u32(SCRIPT, GARDEN)
        space:write_u8(SCENE, 6)
        warped = true
        print("Redirected the native Normal stage script to Garden")
    end
    if not warped or space:read_u8(SCENE) ~= 7 then return end

    space:write_u8(player + 0x269, 240)
    local boss = flying_form()
    if boss and not release_tick then
        release_tick = logic + 152
        space:write_u32(RANK, seeded_rank)
        space:write_u8(player + 0x256, 3)
        space:write_u8(player + 0x254, 4)
        space:write_u8(player + 7, side == 1 and 2 or 5)
        space:write_u32(player + 0x10, 48 << 16)
        space:write_u32(player + 0x14, (side == 1 and 435 or 555) << 16)
        if capture then capture.enabled = true end
        print(string.format("Teresa's flying form at refresh %d, gameplay tick %d", frame, logic))
    end
    if not release_tick then return end
    capture_frame(logic, boss)
    if objects then capture_objects(logic) end

    if (cadence or deadline) and logic >= release_tick then
        cadence_start = cadence_start or frame
        local relative_frame, relative_tick = frame - cadence_start, logic - release_tick
        if cadence then cadence:write(string.format("%s,%d,%d\n", window, relative_frame, relative_tick)) end
        if deadline then deadline.sample(window, relative_frame, relative_tick) end
    end

    if not charged and logic >= release_tick - 138 then
        set(port, bomb, true)
        set(port, shot, true)
        charged = true
    end
    if not released and logic >= release_tick then
        set(port, bomb, false)
        released = true
        print(string.format("Hadou release input at refresh %d, gameplay tick %d", frame, logic))
    end
    if not shot_stopped and logic >= release_tick + 360 then
        set(port, shot, false)
        shot_stopped = true
    end
    if logic >= release_tick + ticks_after_release then
        finish("Stage 6 capture complete")
    end
end)
