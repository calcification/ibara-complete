-- Optional read-only samples for the original Ibara U4 cadence fixtures.
local deadline = {}

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
    output:write("window,frame,tick,time_us,irq_outer,screen_frame,pending,ready,irq_tmu,tmu,pc\n")

    return {
        sample = function(window, frame, tick)
            output:write(string.format("%s,%d,%d,%.6f,%d,%d,%08x,%d,%u,%u,%08x\n",
                window, frame, tick, machine.time:as_double() * 1e6,
                space:read_u32(0x0c392964), screen:frame_number(), space:read_u32(0x0c283c94),
                (space:read_u32(0x18000010) >> 4) & 1,
                space:read_u32(0x0c3929c0), space:read_u32(0x0c04a16c), pc.value))
        end,
        close = function() output:close() end,
    }
end

return deadline
