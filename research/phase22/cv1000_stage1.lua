-- Base Ibara, MAME set ibara (U4 d5fb6657). Capture 300 Stage 1 refresh intervals
-- from the first live hostile shot, with scripted inputs and no game-state writes.
assert(emu.romname() == "ibara", "use the base Ibara parent set with U4 CRC d5fb6657")
local machine = manager.machine
local ram = machine.devices[":maincpu"].spaces.program
local ports = machine.ioport.ports
local deadline = dofile("research/phase22/cv1000_deadline.lua").open(machine, os.getenv("IBARA_DEADLINE"))
local player, bullets = 0x0C283794, 0x0C27E0FC
local scene, tick, rank = 0x0C392B08, 0x0C21F880, 0x0C27DFF8
local demo = 0x0C21CA15
local output = assert(io.open(assert(os.getenv("IBARA_TRACE"), "set IBARA_TRACE"), "w"))
output:write("window,frame,tick,input,player_x,player_y,score,rank,bombs,hostile_bullets\n")

local refresh, first_refresh, first_tick = 0, nil, nil
local controls = {left = false, right = false, shot = false}

local function set(port, name, pressed)
    local field = assert(ports[port].fields[name], name)
    if pressed then field:set_value(1) else field:clear_value() end
end

local function drive(frame)
    local left = frame >= 45 and frame < 85
    local right = frame >= 130 and frame < 170
    local shot = frame >= 20 and frame < 260
    if left ~= controls.left then set(":PORT_D", "P1 Left", left) end
    if right ~= controls.right then set(":PORT_D", "P1 Right", right) end
    if shot ~= controls.shot then set(":PORT_D", "P1 Button 1", shot) end
    controls.left, controls.right, controls.shot = left, right, shot
end

local function count_bullets()
    local count = 0
    for index = 0, 255 do
        if (ram:read_u32(bullets + index * 0x54) & 0x10004000) == 0x10000000 then count = count + 1 end
    end
    return count
end

emu.register_frame_done(function()
    refresh = refresh + 1
    if refresh == 2400 or refresh == 2408 then set(":PORT_C", "Coin 1", refresh == 2400) end
    if refresh == 2460 or refresh == 2468 then set(":PORT_C", "1 Player Start", refresh == 2460) end
    if not first_refresh then
        if refresh > 2468 and ram:read_u8(scene) == 2 and ram:read_u8(demo) ~= 1 and
            (ram:read_u32(player) & 0x04000000) ~= 0 and count_bullets() > 0 then
            first_refresh, first_tick = refresh, ram:read_u32(tick)
        elseif refresh >= 4200 then
            output:close()
            if deadline then deadline.close() end
            print("Stage 1 did not reach the first live hostile shot")
            machine:exit()
        end
    end
    if not first_refresh then return end

    local frame = refresh - first_refresh
    local input = (controls.left and 1 or 0) | (controls.right and 2 or 0) | (controls.shot and 4 or 0)
    output:write(string.format("stage1,%d,%d,%d,%d,%d,%d,%d,%d,%d\n", frame, ram:read_u32(tick) - first_tick,
        input, ram:read_i32(player + 0x10), ram:read_i32(player + 0x14), ram:read_u32(player + 0x270),
        ram:read_u32(rank), ram:read_u8(player + 0x256), count_bullets()))
    if deadline then deadline.sample("stage1", frame, ram:read_u32(tick) - first_tick) end
    if frame == 300 then
        output:close()
        if deadline then deadline.close() end
        print(string.format("Stage 1 captured at refresh %d: 300 intervals", first_refresh))
        machine:exit()
    else
        drive(frame + 1)
    end
end)
