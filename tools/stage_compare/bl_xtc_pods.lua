-- Black Label Stage 1 XTC fixture, MAME 0.276, using ibarablk (U4 CRC ee1f1f77).
-- OUT=xtc-pods.txt mame ibarablk -rompath /path/to/roms -nodrc -video none -sound none
--     -nothrottle -skip_gameinfo -autoboot_delay 0 -autoboot_script tools/stage_compare/bl_xtc_pods.lua
-- Move an existing bullet next to the player with shot held. Repeat at pod counts zero, three, zero.
assert(emu.romname() == "ibarablk", "use the Black Label arcade set")
local machine = manager.machine
local space = machine.devices[":maincpu"].spaces.program
local ports = machine.ioport.ports
local player = 0x0c29d1d8
local rank = 0x0c297a3c
local bullet_pool = 0x0c297b40
local frame = 0
local index = 1
local previous
local phases = {{pods=0},{pods=3},{pods=0}}
local out = assert(io.open(os.getenv("OUT"), "w"))
local function set(port, button, down)
    local input = ports[port].fields[button]
    if down then input:set_value(1) else input:clear_value() end
end
local function aligned_bullet()
    for slot = 0, 255 do
        local a = bullet_pool + 0x54 * slot
        if space:read_u32(a) & 0x10004000 == 0x10000000 then return a end
    end
end
emu.register_frame_done(function()
    frame = frame + 1
    if frame == 2400 or frame == 2408 then set(":PORT_C","Coin 1",frame==2400) end
    if frame == 2460 or frame == 2468 then set(":PORT_C","1 Player Start",frame==2460) end
    if frame >= 2700 and frame <= 3020 and frame % 40 == 0 then
        set(":PORT_D","P1 Button 1",true)
    elseif frame >= 2700 and frame <= 3020 and frame % 40 == 6 then
        set(":PORT_D","P1 Button 1",false)
    end
    if frame == 3220 then set(":PORT_D","P1 Button 1",true) end
    if frame > 3120 then space:write_u8(player+0x288,240) end
    if frame < 3300 then return end
    local phase = phases[index]
    local quarters = space:read_u32(player+0x280)
    if previous then
        if quarters > previous then phase.gains = (phase.gains or 0) + quarters - previous end
        phase.samples = (phase.samples or 0) + 1
        if phase.samples >= 80 then
            out:write(string.format("pods=%d samples=%d quarters_gained=%d\n",
                phase.pods, phase.samples, phase.gains or 0))
            index = index + 1
            if index > #phases then out:close(); machine:exit(); return end
            phase = phases[index]
        end
    end
    previous = nil
    space:write_u32(rank,0x00800000)
    space:write_u8(player+0x289,phase.pods)
    local bullet = aligned_bullet()
    if frame % 120 == 0 then
        out:write(string.format("diagnostic %d pods=%d held=%d flags=%08x bullet=%s count=%d\n",
            frame, phase.pods, space:read_u8(player+0x270), space:read_u32(player), tostring(bullet), phase.samples or 0))
    end
    if bullet and space:read_u8(player+0x270)>=5 and space:read_u32(player)&0x04000000~=0 then
        space:write_i32(bullet+0x28,space:read_i32(player+0x10)+(9<<16))
        space:write_i32(bullet+0x2c,space:read_i32(player+0x14))
        previous = quarters
    end
    if frame >= 5000 then out:write("incomplete\n"); out:close(); machine:exit() end
end)
