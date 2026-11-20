-- BL stage-1 enemy spawn log: frame (since first spawn of the stage), slot, type(+04), subtype(+08), hp(+3C), score(+40), x, y
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1 = 0x0C29D1D8; local EN = 0x0C286578
local frame, alive, typ, first = 0, {}, {}, nil
local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
at(t0 + 700, function() fld(":PORT_D", "P1 Button 1"):set_value(1) end)
local out = io.open(os.getenv("SPOUT"), "w")
local LIMIT = tonumber(os.getenv("SPFRAMES") or "16000")
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame > t0 + 700 then
    sp:write_u8(P1 + 0x288, 240)                    -- keep P1 invincible
    local stage = sp:read_u8(0x0C3C4170)
    for i = 0, 191 do
      local a = EN + i * 0xB4
      local fl = sp:read_u32(a); local on = (fl & 0x80000000) ~= 0
      local t = sp:read_u32(a + 4)
      if on and (not alive[i] or typ[i] ~= t) then
        first = first or frame
        out:write(string.format("%d %d %d %d %08X %d %d %d %d %d\n", frame - first, stage, i, t, sp:read_u32(a + 8),
          sp:read_u16(a + 0x3C), sp:read_u32(a + 0x40), sp:read_u32(a + 0x24) >> 16, sp:read_u32(a + 0x28) >> 16, (fl >> 14) & 1))
      end
      alive[i] = on; typ[i] = t
    end
  end
  if frame == t0 + LIMIT then out:close(); m:exit() end
end)
