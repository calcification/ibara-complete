local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1 = 0x0C29D1D8; local frame = 0; local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
at(t0 + 700, function() fld(":PORT_D", "P1 Button 1"):set_value(1) end)
local out = io.open(os.getenv("OUT"), "w")
local born, sub = {}, {}
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame <= t0 + 700 then return end
  sp:write_u8(P1 + 0x288, 240); sp:write_u32(0x0C297A3C, 0x800000); sp:write_u8(P1 + 0x25B, 2)
  local f = frame - t0 - 700
  local px, py = sp:read_i32(P1 + 0x10) >> 16, sp:read_i32(P1 + 0x14) >> 16
  for _, pool in ipairs({{0x0C2380D0, 160, 1}, {0x0C2A6D9C, 64, 2}}) do
  for k = 0, pool[2] - 1 do
    local a = pool[1] + 0x34 * k
    local key = pool[3] * 1000 + k
    local on = (sp:read_u32(a) >> 30) == 3
    local s8 = sp:read_u32(a + 8)
    if on and not born[key] then born[key] = f; out:write(string.format("S %d %d %d %d %d %d %d\n", f, pool[3], sp:read_u32(a + 4), s8, (sp:read_i32(a + 0x10) >> 16) - px, (sp:read_i32(a + 0x14) >> 16) - py, sp:read_u8(P1 + 0x270))) end
    if not on then born[key] = nil end
  end
  end
  if f == 4500 then out:close(); m:exit() end
end)
