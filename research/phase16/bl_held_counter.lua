local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1 = 0x0C29D1D8; local frame = 0; local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
local out = io.open(os.getenv("OUT"), "w")
local salive = {}
-- phases of 400 frames: hold, release, tap every 2, tap every 4, tap every 8, hold again
local modes = {"none", "hold", "none", "tap2", "tap4", "tap8", "hold", "none"}
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame <= t0 + 700 then return end
  sp:write_u8(P1 + 0x288, 240); sp:write_u32(0x0C297A3C, 0x800000); sp:write_u8(P1 + 0x25B, 2)
  local f = frame - t0 - 700
  local mi = (f // 400) + 1
  if mi > #modes then out:close(); m:exit(); return end
  local mode = modes[mi]; local d = false
  if mode == "hold" then d = true elseif mode == "tap2" then d = (f % 2 == 0) elseif mode == "tap4" then d = (f % 4 < 2) elseif mode == "tap8" then d = (f % 8 < 4) end
  if d then fld(":PORT_D", "P1 Button 1"):set_value(1) else fld(":PORT_D", "P1 Button 1"):clear_value() end
  if f % 20 == 0 then out:write(string.format("S %d %s %d %d\n", f, mode, sp:read_u8(P1 + 0x270), sp:read_u8(P1 + 0x271))) end
  for k = 0, 159 do
    local a = 0x0C2380D0 + 0x34 * k
    local on = (sp:read_u32(a) >> 30) == 3
    if on and not salive[k] then out:write(string.format("%d %s %d %d\n", f, mode, sp:read_u32(a + 4) & 0xFF, sp:read_u32(a + 8) & 0xFF)) end
    salive[k] = on
  end
end)
