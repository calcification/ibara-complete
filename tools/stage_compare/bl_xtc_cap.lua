-- MAME 0.276, ibarablk (U4 CRC ee1f1f77). Use -nodrc and -autoboot_delay 0.
-- Run with OUT=/path/to/results.txt and -autoboot_script tools/stage_compare/bl_xtc_cap.lua.
assert(emu.romname() == "ibarablk", "use the Black Label arcade set")
local machine = manager.machine
local space = machine.devices[":maincpu"].spaces.program
local ports = machine.ioport.ports
local player, rank, bullet_pool = 0x0c29d1d8, 0x0c297a3c, 0x0c297b40
local game_frame = 0x0c2b039c
local cap = 4 * 9999
local frame = 0
local score_before, refresh_frame, refresh_left
local out = assert(io.open(os.getenv("OUT"), "w"))

local function set(port, button, down)
    local input = ports[port].fields[button]
    if down then input:set_value(1) else input:clear_value() end
end

local function position_bullet()
    for slot = 0, 255 do
        local bullet = bullet_pool + slot * 0x54
        if space:read_u32(bullet) & 0x10004000 == 0x10000000 then
            space:write_i32(bullet + 0x28, space:read_i32(player + 0x10) + (9 << 16))
            space:write_i32(bullet + 0x2c, space:read_i32(player + 0x14))
            return true
        end
    end
    return false
end

emu.register_frame_done(function()
    frame = frame + 1
    if frame == 2400 or frame == 2408 then set(":PORT_C", "Coin 1", frame == 2400) end
    if frame == 2460 or frame == 2468 then set(":PORT_C", "1 Player Start", frame == 2460) end
    if frame >= 2700 and frame <= 3026 then
        if frame % 40 == 0 then set(":PORT_D", "P1 Button 1", true) end
        if frame % 40 == 6 then set(":PORT_D", "P1 Button 1", false) end
    end
    if frame == 3220 then set(":PORT_D", "P1 Button 1", true) end
    if frame > 3120 then space:write_u8(player + 0x288, 240) end
    if frame < 3300 then return end

    local quarters = space:read_u32(player + 0x280)
    local left = space:read_u16(player + 0x284)
    if refresh_frame then
        if quarters ~= cap then
            local elapsed = space:read_u32(game_frame) - refresh_frame
            out:write(string.format("expiry quarters=%d timer=%d elapsed=%d expected=%d\n",
                quarters, left, elapsed, refresh_left))
            out:close()
            machine:exit()
        end
    else
        space:write_u32(rank, 0)
        space:write_u8(player + 0x289, 3)
        if left > 24 and score_before then
            local score_delta = space:read_u32(player + 0x290) - score_before
            refresh_left = left
            refresh_frame = space:read_u32(game_frame)
            out:write(string.format("refresh quarters=%d timer=%d rank0_score_delta=%d\n", quarters, left, score_delta))
            space:write_u8(player + 0x289, 0)
            set(":PORT_D", "P1 Button 1", false)
        elseif position_bullet() and space:read_u8(player + 0x270) >= 5 then
            score_before = space:read_u32(player + 0x290)
            space:write_u32(player + 0x280, cap)
            space:write_u16(player + 0x284, 24)
        end
    end

    if frame == 4500 then
        out:write("incomplete\n")
        out:close()
        machine:exit()
    end
end)
