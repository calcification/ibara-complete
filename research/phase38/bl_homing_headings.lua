-- research/phase38: BL homing pods with no target. mame ibarablk -autoboot_script bl_homing_headings.lua (env ST = a stage savestate, OUT, PODBASE=0x0C2974C8): switches to homing (weapon 3), clears the enemy pool, holds each stick state 60 frames, logs the three pods' heading words (+38).
local machine = manager.machine
local space = machine.devices[":maincpu"].spaces.program
local ports = machine.ioport.ports
local function f(n) return ports[":PORT_D"].fields[n] end
local p1 = 0x0C29D1D8
local POD = tonumber(os.getenv("PODBASE") or "0x0C29D718")
local frame, tick = 0, 0
local dirs = {{}, {"P1 Up"}, {"P1 Down"}, {"P1 Left"}, {"P1 Right"}, {"P1 Up","P1 Left"}, {"P1 Up","P1 Right"}, {"P1 Down","P1 Left"}, {"P1 Down","P1 Right"}}
local names = {"none","up","down","left","right","up-left","up-right","down-left","down-right"}
local out = io.open(os.getenv("OUT"), "w")
emu.register_frame_done(function()
  frame = frame + 1
  if frame == 1 then f("P1 Button 1"):set_value(1); machine:load(os.getenv("ST")); return end
  tick = tick + 1
  space:write_u8(p1 + 0x288, 240)
  if tick < 400 then
    if tick % 20 == 0 and space:read_u8(p1 + 0x26F) ~= 3 then f("P1 Button 4"):set_value(1) end
    if tick % 20 == 6 then f("P1 Button 4"):clear_value() end
    return
  end
  for slot = 0, 191 do space:write_u32(0x0C286578 + 0xB4 * slot, 0) end
  local k = (tick - 400) // 60 + 1
  if k > #dirs then out:close(); machine:exit(); return end
  local ph = (tick - 400) % 60
  if ph == 0 then
    for _, n in ipairs({"P1 Up","P1 Down","P1 Left","P1 Right"}) do f(n):clear_value() end
    for _, n in ipairs(dirs[k]) do f(n):set_value(1) end
  end
  if ph == 10 or ph == 40 then
    local h = {}
    for i = 0, 2 do h[#h + 1] = string.format("kind%d h%d", space:read_u32(POD + 48 * i + 4), space:read_u16(POD + 48 * i + 38)) end
    out:write(string.format("%s ph%d weapon %d %s\n", names[k], ph, space:read_u8(p1 + 0x26F), table.concat(h, " | ")))
  end
end)
