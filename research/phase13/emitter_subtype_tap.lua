local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]; local cpu = m.devices[":maincpu"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1 = 0x0C29D1D8; local EN = 0x0C286578; local frame = 0
local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
seen = {}
tap = sp:install_write_tap(EN, EN + 192 * 0xB4 - 1, "st", function(off, data, mask)
  local rel = (off - EN) % 0xB4
  local v = nil
  if rel == 0x08 then v = data & 0xFFFFFFFF; if mask == 0xFFFFFFFF00000000 then v = data >> 32 end end
  if rel == 0x08 - 4 + 4 and false then end
  if rel == 0x04 and mask == 0x00000000FFFFFFFF then v = data & 0xFFFFFFFF end
  if v and v >= 0x50 and v <= 0x55 and frame > t0 + 6000 and sp:read_u32(off - rel + 4) == 5 then
    local k = string.format("frame %d sub %02X PC %08X PR %08X", frame - t0 - 700, data, cpu.state["PC"].value, cpu.state["PR"].value)
    print(k)
  end
end)
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame > t0 + 700 then sp:write_u8(P1 + 0x288, 240); sp:write_u32(0x0C297A3C, 0x800000) end
  if frame == t0 + 9800 then m:exit() end
end)
