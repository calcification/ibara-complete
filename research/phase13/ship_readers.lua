-- usage: SHIPVARIANT=A|B ; logs PCs reading P1's ship byte 0C29D1DF
local variant = os.getenv("SHIPVARIANT") or "A"
local m = manager.machine
local cpu = m.devices[":maincpu"]
local space = cpu.spaces["program"]
local ports = m.ioport.ports
local function field(p, n) return ports[p].fields[n] end
local pcs, frame = {}, 0
SHIP_TAP = space:install_read_tap(0x0C29D1D8, 0x0C29D1DF, "ship", function(offset, data, mask)
  if (mask & 0xFF) == 0 then return end
  local pc = cpu.state["PC"].value
  local key = string.format("%08X", pc)
  pcs[key] = (pcs[key] or 0) + 1
end)
local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() field(p, n):set_value(1) end); at(f + (len or 6), function() field(p, n):clear_value() end) end
-- boot ~ 30 s; coin, start, ship select presses, then hold shot
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8)
press(t0 + 60, ":PORT_C", "1 Player Start", 8)
if variant == "B" then press(t0 + 240, ":PORT_D", "P1 Right", 8) end
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
at(t0 + 700, function() field(":PORT_D", "P1 Button 1"):set_value(1) end)
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame % 600 == 0 then
    print(string.format("FRAME %d ship=%02X shipP2=%02X score=%08X", frame, space:read_u8(0x0C29D1DF), space:read_u8(0x0C29D47F), space:read_u32(0x0C29D468)))
  end
  if frame == t0 + 2400 then
    local list = {}
    for k, v in pairs(pcs) do table.insert(list, {k, v}) end
    table.sort(list, function(a, b) return a[1] < b[1] end)
    for _, e in ipairs(list) do print("PC", e[1], e[2]) end
    m:exit()
  end
end)
