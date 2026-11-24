-- Optional read-only samples for the original Ibara U4 cadence fixtures.
local deadline = {}
local LIST_PUBLISHED = 0x19671010
local timing_fields = {
    {"profile_tmu", 0x0c21ca18},
    {"draw_parts", 0x0c286064}, {"draw_setup", 0x0c220c48},
    {"draw_overlays", 0x0c21f7f4}, {"publish", 0x0c21ca04},
    {"sim_a", 0x0c2175e0}, {"sim_b", 0x0c286060}, {"sim_c", 0x0c392e04},
}

function deadline.open(machine, path)
    if not path then return end

    local cpu = machine.devices[":maincpu"]
    local space = cpu.spaces.program
    local pc = cpu.state.PC
    local screen = machine.screens[":screen"]
    local existing = io.open(path, "r")
    if existing then
        existing:close()
        error("CSV already exists: " .. path)
    end
    local output = assert(io.open(path, "w"))
    local workload
    if os.getenv("IBARA_DRAW_LIST") == "1" then
        workload = dofile("research/phase22/cv1000_workload.lua")
    end
    output:write("window,frame,tick,time_us,irq_outer,screen_frame,pending,ready,irq_tmu,tmu,pc")
    if workload then
        output:write(",", table.concat(workload.list_fields, ","))
        for _, field in ipairs(timing_fields) do output:write(",", field[1]) end
    end
    output:write("\n")

    return {
        sample = function(window, frame, tick)
            local pending = space:read_u32(0x0c283c94)
            output:write(string.format("%s,%d,%d,%.6f,%d,%d,%08x,%d,%u,%u,%08x",
                window, frame, tick, machine.time:as_double() * 1e6,
                space:read_u32(0x0c392964), screen:frame_number(), pending,
                (space:read_u32(0x18000010) >> 4) & 1,
                space:read_u32(0x0c3929c0), space:read_u32(0x0c04a16c), pc.value))
            if workload then
                local list
                if pending == LIST_PUBLISHED then list = assert(workload.read_list(space)) end
                for _, key in ipairs(workload.list_fields) do
                    output:write(",", list and list[key] or "")
                end
                for _, field in ipairs(timing_fields) do output:write(",", space:read_u32(field[2])) end
            end
            output:write("\n")
        end,
        close = function() output:close() end,
    }
end

return deadline
